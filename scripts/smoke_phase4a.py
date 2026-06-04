"""Phase 4A HTTP API live smoke — runs the FastAPI app in-process via the
async TestClient (httpx + ASGI transport, no socket binding) and exercises:

- POST /admin/auth         (valid initData → JWT)
- POST /admin/auth         (invalid hash → 401)
- POST /admin/auth         (non-admin user → 403)
- GET  /admin/overview     (no JWT → 401)
- GET  /admin/overview     (bad JWT → 401)
- GET  /admin/overview     (valid JWT → 200)
- GET  /admin/metrics      (enum + number routing)
- GET  /admin/topics       (with and without sentiment)
- POST /admin/semantic     (live Pinecone + Supabase JOIN)
- GET  /admin/clients/{id} (live profile)
- GET  /admin/clients/0    (LookupError → 404)
- OPTIONS preflight        (CORS headers)

This **does** call live OpenAI/Pinecone/Supabase — read-only. Skip /admin/ask
unless --include-ask is passed (it's a 5-round LLM loop, slow + costs tokens).

Run:
    uv run python scripts/smoke_phase4a.py
    uv run python scripts/smoke_phase4a.py --include-ask
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set settings via env BEFORE importing api.* (Settings reads env at class load).
os.environ.setdefault("MINI_APP_SESSION_SECRET", "test-secret-for-smoke-32-chars-min!")
os.environ.setdefault(
    "ALLOWED_MINI_APP_ORIGINS",
    "http://localhost:3000,https://miniapp.example.com",
)


from httpx import ASGITransport, AsyncClient

from config import settings
from presentations.http_api.main import app

ADMIN_TELEGRAM_ID = 413722495  # Mark, from admin_users table
NON_ADMIN_TELEGRAM_ID = 999_999_999


def _build_init_data(
    *,
    telegram_id: int,
    bot_token: str,
    auth_date: int | None = None,
    name: str = "Smoke Tester",
    corrupt_hash: bool = False,
) -> str:
    """Build a valid Telegram WebApp initData query string signed with bot_token."""
    if auth_date is None:
        auth_date = int(time.time())
    user_json = json.dumps(
        {"id": telegram_id, "first_name": name, "username": "smoke"},
        separators=(",", ":"),
    )
    pairs = [
        ("auth_date", str(auth_date)),
        ("user", user_json),
        ("query_id", "smoke-query-id"),
    ]
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs, key=lambda p: p[0]))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if corrupt_hash:
        h = "0" * len(h)
    pairs.append(("hash", h))
    return urlencode(pairs)


def _truncate(s: str, n: int = 280) -> str:
    return s if len(s) <= n else s[:n] + "…"


PASS = "✅"
FAIL = "❌"


async def main() -> int:
    include_ask = "--include-ask" in sys.argv
    bot_token = settings.telegram_admin_bot_token
    if not bot_token:
        print("ERROR: TELEGRAM_ADMIN_BOT_TOKEN not set; cannot sign initData.")
        return 1

    failures: list[str] = []

    def check(name: str, ok: bool, info: str = "") -> None:
        mark = PASS if ok else FAIL
        print(f"{mark} {name:48s} {_truncate(info)}")
        if not ok:
            failures.append(name)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ---------------- auth happy path ----------------
        init_ok = _build_init_data(telegram_id=ADMIN_TELEGRAM_ID, bot_token=bot_token)
        r = await client.post("/admin/auth", json={"init_data": init_ok})
        check(
            "POST /admin/auth (admin)",
            r.status_code == 200 and "token" in r.json(),
            f"status={r.status_code} body={r.text[:160]}",
        )
        token = r.json().get("token", "") if r.status_code == 200 else ""

        # ---------------- auth: corrupted hash ----------------
        bad_init = _build_init_data(
            telegram_id=ADMIN_TELEGRAM_ID, bot_token=bot_token, corrupt_hash=True
        )
        r = await client.post("/admin/auth", json={"init_data": bad_init})
        check(
            "POST /admin/auth (bad hash → 401)",
            r.status_code == 401,
            f"status={r.status_code}",
        )

        # ---------------- auth: non-admin ----------------
        non_admin_init = _build_init_data(telegram_id=NON_ADMIN_TELEGRAM_ID, bot_token=bot_token)
        r = await client.post("/admin/auth", json={"init_data": non_admin_init})
        check(
            "POST /admin/auth (non-admin → 403)",
            r.status_code == 403,
            f"status={r.status_code}",
        )

        # ---------------- auth: stale auth_date ----------------
        stale_init = _build_init_data(
            telegram_id=ADMIN_TELEGRAM_ID,
            bot_token=bot_token,
            auth_date=int(time.time()) - 86400 - 60,
        )
        r = await client.post("/admin/auth", json={"init_data": stale_init})
        check(
            "POST /admin/auth (stale auth_date → 401)",
            r.status_code == 401,
            f"status={r.status_code}",
        )

        if not token:
            print("\nCannot continue without valid JWT.")
            return 1

        auth_h = {"Authorization": f"Bearer {token}"}
        now = datetime.now(UTC)
        days30 = (now - timedelta(days=30)).isoformat()
        now_iso = now.isoformat()

        # ---------------- protected: no auth ----------------
        r = await client.get("/admin/overview", params={"date_from": days30, "date_to": now_iso})
        check(
            "GET /admin/overview (no auth → 401)",
            r.status_code == 401,
            f"status={r.status_code}",
        )

        # ---------------- protected: bad JWT ----------------
        r = await client.get(
            "/admin/overview",
            params={"date_from": days30, "date_to": now_iso},
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        check(
            "GET /admin/overview (bad JWT → 401)",
            r.status_code == 401,
            f"status={r.status_code}",
        )

        # ---------------- protected: valid JWT ----------------
        r = await client.get(
            "/admin/overview",
            params={"date_from": days30, "date_to": now_iso},
            headers=auth_h,
        )
        ok = r.status_code == 200 and "sessions_count" in r.json()
        info = (
            f"sessions={r.json().get('sessions_count')} avg_sent={r.json().get('avg_sentiment')}"
            if ok
            else r.text[:160]
        )
        check("GET /admin/overview (auth → 200)", ok, info)

        # ---------------- metrics: enum ----------------
        r = await client.get(
            "/admin/metrics",
            params={
                "metric_key": "age_group",
                "date_from": (now - timedelta(days=60)).isoformat(),
                "date_to": now_iso,
            },
            headers=auth_h,
        )
        ok = r.status_code == 200 and r.json().get("expected_type") == "enum"
        info = (
            f"type={r.json().get('expected_type')} total={r.json().get('total')}"
            if ok
            else r.text[:160]
        )
        check("GET /admin/metrics (enum: age_group)", ok, info)

        # ---------------- metrics: number ----------------
        r = await client.get(
            "/admin/metrics",
            params={
                "metric_key": "age",
                "date_from": (now - timedelta(days=60)).isoformat(),
                "date_to": now_iso,
            },
            headers=auth_h,
        )
        ok = r.status_code == 200 and r.json().get("expected_type") == "number"
        info = (
            f"type={r.json().get('expected_type')} points={len(r.json().get('points') or [])}"
            if ok
            else r.text[:160]
        )
        check("GET /admin/metrics (number: age)", ok, info)

        # ---------------- metrics: unknown key ----------------
        r = await client.get(
            "/admin/metrics",
            params={
                "metric_key": "nonexistent_metric",
                "date_from": days30,
                "date_to": now_iso,
            },
            headers=auth_h,
        )
        check(
            "GET /admin/metrics (unknown key → 404)",
            r.status_code == 404,
            f"status={r.status_code}",
        )

        # ---------------- topics: no filter ----------------
        r = await client.get(
            "/admin/topics",
            params={"date_from": days30, "date_to": now_iso},
            headers=auth_h,
        )
        ok = r.status_code == 200 and isinstance(r.json().get("topics"), list)
        info = f"topics_count={len(r.json().get('topics') or [])}" if ok else r.text[:160]
        check("GET /admin/topics (all)", ok, info)

        # ---------------- topics: negative ----------------
        r = await client.get(
            "/admin/topics",
            params={"date_from": days30, "date_to": now_iso, "sentiment": "negative"},
            headers=auth_h,
        )
        ok = r.status_code == 200 and isinstance(r.json().get("topics"), list)
        info = f"negative={len(r.json().get('topics') or [])}" if ok else r.text[:160]
        check("GET /admin/topics (negative)", ok, info)

        # ---------------- semantic search ----------------
        r = await client.post(
            "/admin/semantic",
            json={"query": "качество еды", "top_k": 3},
            headers=auth_h,
        )
        ok = r.status_code == 200 and isinstance(r.json().get("hits"), list)
        info = f"hits={len(r.json().get('hits') or [])}" if ok else r.text[:160]
        check("POST /admin/semantic", ok, info)

        # ---------------- client profile: existing ----------------
        r = await client.get(f"/admin/clients/{ADMIN_TELEGRAM_ID}", headers=auth_h)
        ok = r.status_code == 200 and r.json().get("telegram_id") == ADMIN_TELEGRAM_ID
        info = (
            f"name={r.json().get('name')!r} sessions={r.json().get('sessions_count')}"
            if ok
            else r.text[:160]
        )
        check("GET /admin/clients/<id> (existing)", ok, info)

        # ---------------- client profile: non-existent ----------------
        r = await client.get("/admin/clients/0", headers=auth_h)
        check(
            "GET /admin/clients/0 (not found → 404)",
            r.status_code == 404,
            f"status={r.status_code}",
        )

        # ---------------- CORS preflight ----------------
        r = await client.options(
            "/admin/overview",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        allowed = r.headers.get("access-control-allow-origin", "")
        ok = r.status_code in (200, 204) and "localhost:3000" in allowed
        info = f"status={r.status_code} allow-origin={allowed!r}"
        check("CORS preflight (allowed origin)", ok, info)

        # ---------------- CORS: disallowed origin ----------------
        r = await client.options(
            "/admin/overview",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI CORS middleware: when origin not allowed, header is absent.
        ok = not r.headers.get("access-control-allow-origin")
        info = (
            f"status={r.status_code} allow-origin={r.headers.get('access-control-allow-origin')!r}"
        )
        check("CORS preflight (disallowed origin)", ok, info)

        # ---------------- /admin/ask (LLM, slow; opt-in) ----------------
        if include_ask:
            r = await client.post(
                "/admin/ask",
                json={
                    "question": "сколько сессий за последние 30 дней?",
                    "history": [],
                },
                headers=auth_h,
                timeout=60.0,
            )
            ok = r.status_code == 200 and "answer_text" in r.json()
            info = f"answer={r.json().get('answer_text', '')[:120]!r}" if ok else r.text[:160]
            check("POST /admin/ask (LLM)", ok, info)
        else:
            print(
                "⏭️  POST /admin/ask                                  skipped (pass --include-ask to run)"
            )

    print()
    if failures:
        print(f"{FAIL} {len(failures)} failed: {', '.join(failures)}")
        return 1
    print(f"{PASS} All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
