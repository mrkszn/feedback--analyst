"""HTTP tests for /admin/auth, /admin/overview, /admin/metrics, /admin/topics."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Iterator
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from config import settings
from presentations.http_api.auth.jwt import issue_token, verify_token
from presentations.http_api.main import create_app

VALID_BOT_TOKEN = "999:fake-admin-bot-token"
SECRET = "test-jwt-secret-32-bytes-or-more-aaaa"


@pytest.fixture(autouse=True)
def _patched_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "telegram_admin_bot_token", VALID_BOT_TOKEN)
    monkeypatch.setattr(settings, "mini_app_session_secret", SECRET)
    monkeypatch.setattr(settings, "allowed_mini_app_origins", "https://miniapp.test")
    yield


@pytest.fixture
def client() -> TestClient:
    # Build the app AFTER settings have been monkeypatched so CORS middleware
    # picks up the configured origins.
    return TestClient(create_app())


def _sign_initdata(telegram_id: int = 7) -> str:
    payload = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": telegram_id, "first_name": "Bob"}, separators=(",", ":")),
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret = hmac.new(b"WebAppData", VALID_BOT_TOKEN.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**payload, "hash": h})


def _admin_token(telegram_id: int = 7) -> str:
    return issue_token(telegram_id, SECRET)


# --------------------------------------------------------------------------- #
# /admin/auth


def test_auth_succeeds_for_known_admin(client: TestClient) -> None:
    init_data = _sign_initdata(7)
    with patch("presentations.http_api.routes.admin.is_admin", return_value=True):
        resp = client.post("/admin/auth", json={"init_data": init_data})
    assert resp.status_code == 200
    body = resp.json()
    assert body["telegram_id"] == 7
    assert isinstance(body["token"], str) and body["token"].count(".") == 2


def test_auth_rejects_bad_initdata(client: TestClient) -> None:
    resp = client.post("/admin/auth", json={"init_data": "auth_date=1&user=%7B%7D&hash=00"})
    assert resp.status_code == 401
    assert "invalid init_data" in resp.json()["detail"]


def test_auth_rejects_non_admin(client: TestClient) -> None:
    init_data = _sign_initdata(99)
    with patch("presentations.http_api.routes.admin.is_admin", return_value=False):
        resp = client.post("/admin/auth", json={"init_data": init_data})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not an admin"


# --------------------------------------------------------------------------- #
# /admin/auth/web — Telegram Login Widget (web OAuth)


def _sign_widget(data: dict[str, object], bot_token: str = VALID_BOT_TOKEN) -> dict[str, object]:
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(bot_token.encode()).digest()
    h = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {**data, "hash": h}


def test_auth_web_succeeds_for_whitelisted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "admin_telegram_ids", "7,8")
    payload = _sign_widget({"id": 7, "first_name": "Bob", "auth_date": int(time.time())})
    with patch("presentations.http_api.routes.admin.ensure_admin", return_value=None):
        resp = client.post("/admin/auth/web", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["telegram_id"] == 7
    # same JWT shape as /admin/auth → works on every /admin/* route (acceptance #6)
    assert verify_token(body["token"], SECRET)["telegram_id"] == 7


def test_auth_web_rejects_forged_hash(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_telegram_ids", "7")
    payload = _sign_widget({"id": 7, "auth_date": int(time.time())})
    payload["hash"] = "0" * 64
    with patch("presentations.http_api.routes.admin.ensure_admin", return_value=None):
        resp = client.post("/admin/auth/web", json=payload)
    assert resp.status_code == 401


def test_auth_web_rejects_expired(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_telegram_ids", "7")
    payload = _sign_widget({"id": 7, "auth_date": int(time.time()) - 100_000})
    resp = client.post("/admin/auth/web", json=payload)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "auth_data_expired"


def test_auth_web_rejects_not_whitelisted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "admin_telegram_ids", "8,9")
    payload = _sign_widget({"id": 7, "auth_date": int(time.time())})
    resp = client.post("/admin/auth/web", json=payload)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_authorized"


def test_auth_web_empty_whitelist_forbids_everyone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "admin_telegram_ids", "")
    payload = _sign_widget({"id": 7, "auth_date": int(time.time())})
    resp = client.post("/admin/auth/web", json=payload)
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# auth middleware (current_admin dependency)


def test_overview_requires_authorization_header(client: TestClient) -> None:
    resp = client.get(
        "/admin/overview", params={"date_from": "2026-01-01", "date_to": "2026-01-31"}
    )
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_overview_rejects_bad_jwt(client: TestClient) -> None:
    resp = client.get(
        "/admin/overview",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        headers={"Authorization": "Bearer garbage.not.jwt"},
    )
    assert resp.status_code == 401


def test_overview_rejects_revoked_admin(client: TestClient) -> None:
    token = _admin_token(7)
    with patch("presentations.http_api.deps.auth.is_admin", return_value=False):
        resp = client.get(
            "/admin/overview",
            params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "not an admin"


# --------------------------------------------------------------------------- #
# /admin/overview


def test_overview_returns_summary(client: TestClient) -> None:
    token = _admin_token(7)
    fake = {
        "sessions_count": 12,
        "avg_sentiment": 0.42,
        "top_positive_topics": [{"topic": "service", "count": 5, "avg_sentiment": 1.0}],
        "top_negative_topics": [{"topic": "wait", "count": 3, "avg_sentiment": -1.0}],
    }
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin.summary_overview", return_value=fake) as m,
    ):
        resp = client.get(
            "/admin/overview",
            params={"date_from": "2026-01-01T00:00:00", "date_to": "2026-01-31T23:59:59"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sessions_count"] == 12
    assert body["top_positive_topics"][0]["topic"] == "service"
    m.assert_called_once()


def test_overview_rejects_inverted_range(client: TestClient) -> None:
    token = _admin_token(7)
    with patch("presentations.http_api.deps.auth.is_admin", return_value=True):
        resp = client.get(
            "/admin/overview",
            params={"date_from": "2026-02-01", "date_to": "2026-01-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# /admin/metrics


def test_metrics_returns_404_for_unknown_metric_key(client: TestClient) -> None:
    token = _admin_token(7)
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin._question_expected_type", return_value=None),
    ):
        resp = client.get(
            "/admin/metrics",
            params={
                "metric_key": "nope",
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 404


def test_metrics_returns_points_for_number_question(client: TestClient) -> None:
    token = _admin_token(7)
    fake_points = [
        {"bucket": "2026-01-01", "count": 3, "avg": 4.5, "min": 3.0, "max": 5.0},
    ]
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin._question_expected_type", return_value="number"),
        patch("presentations.http_api.routes.admin.aggregate_metric", return_value=fake_points),
    ):
        resp = client.get(
            "/admin/metrics",
            params={
                "metric_key": "service_rating",
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["expected_type"] == "number"
    assert body["points"][0]["avg"] == 4.5
    assert body["distribution"] is None


def test_metrics_returns_distribution_for_enum_question(client: TestClient) -> None:
    token = _admin_token(7)
    fake_dist = {
        "metric_key": "age_group",
        "expected_type": "enum",
        "total": 10,
        "categories": [
            {"value": "18-25", "count": 4, "pct": 0.4},
            {"value": "26-35", "count": 6, "pct": 0.6},
        ],
        "unknown": 0,
        "enum_values": ["18-25", "26-35"],
    }
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin._question_expected_type", return_value="enum"),
        patch(
            "presentations.http_api.routes.admin.categorical_distribution", return_value=fake_dist
        ),
    ):
        resp = client.get(
            "/admin/metrics",
            params={
                "metric_key": "age_group",
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["expected_type"] == "enum"
    assert body["distribution"][0]["value"] == "18-25"
    assert body["points"] is None
    assert body["enum_values"] == ["18-25", "26-35"]


# --------------------------------------------------------------------------- #
# /admin/topics


def test_topics_returns_histogram(client: TestClient) -> None:
    token = _admin_token(7)
    fake = [{"topic": "noise", "count": 2, "avg_sentiment": -1.0}]
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin.topic_histogram", return_value=fake) as m,
    ):
        resp = client.get(
            "/admin/topics",
            params={
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
                "sentiment": "negative",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["topics"][0]["topic"] == "noise"
    # sentiment filter must be forwarded
    _, kwargs = m.call_args
    assert kwargs["sentiment_filter"] == "negative"


# --------------------------------------------------------------------------- #
# CORS


def test_cors_preflight_allows_configured_origin(client: TestClient) -> None:
    resp = client.options(
        "/admin/overview",
        headers={
            "Origin": "https://miniapp.test",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://miniapp.test"


def test_cors_blocks_other_origins(client: TestClient) -> None:
    resp = client.options(
        "/admin/overview",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    # Starlette returns 400 disallowed instead of an ACAO header for unknown origins
    assert resp.headers.get("access-control-allow-origin") in (None, "")
