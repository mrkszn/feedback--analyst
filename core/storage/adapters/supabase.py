"""SupabaseStorage — the production StorageAdapter.

The ONLY module in the codebase allowed to call `get_supabase()` / `.table()`.
Each method is the Supabase query-builder chain that previously lived inline in
the service/tool, now wrapped behind the Protocol. Aggregation stays in the
callers; this layer only fetches and mutates rows.

`db` (a `supabase.Client`) is injected so tests can pass a MagicMock that mimics
the query-builder; the chains below are kept byte-for-byte compatible with the
shapes the existing `_FakeDB`/MagicMock tests assert on.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast
from uuid import UUID

from supabase import Client

from core.storage.protocol import Role
from core.storage.supabase_client import get_supabase


def _rows(resp: Any) -> list[dict[str, Any]]:
    return list(resp.data or [])


def _first(resp: Any) -> dict[str, Any]:
    return cast(dict[str, Any], resp.data[0])


def _first_or_none(resp: Any) -> dict[str, Any] | None:
    rows = resp.data or []
    return cast(dict[str, Any], rows[0]) if rows else None


class SupabaseStorage:
    def __init__(self, client: Client | None = None) -> None:
        self._db = client or get_supabase()

    @property
    def client(self) -> Client:
        return self._db

    # ───────────────────────────────────────── clients ──
    async def get_client(self, telegram_id: int) -> dict[str, Any] | None:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("clients").select("*").eq("telegram_id", telegram_id).limit(1).execute()
            )
        )
        return _first_or_none(resp)

    async def insert_client(self, *, telegram_id: int, name: str | None) -> dict[str, Any]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: db.table("clients").insert({"telegram_id": telegram_id, "name": name}).execute()
        )
        return _first(resp)

    # ───────────────────────────────────────── admin_users ──
    async def is_admin(self, telegram_id: int) -> bool:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("admin_users")
                .select("telegram_id")
                .eq("telegram_id", telegram_id)
                .limit(1)
                .execute()
            )
        )
        return bool(resp.data)

    async def count_admins(self) -> int:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("admin_users")
                .select("telegram_id", count="exact")  # type: ignore[arg-type]
                .limit(1)
                .execute()
            )
        )
        return resp.count or 0

    async def insert_admin(
        self, *, telegram_id: int, name: str | None = None, invited_by: int | None = None
    ) -> None:
        db = self._db
        payload: dict[str, Any] = {"telegram_id": telegram_id}
        if name is not None:
            payload["name"] = name
        if invited_by is not None:
            payload["invited_by"] = invited_by
        await asyncio.to_thread(lambda: db.table("admin_users").insert(payload).execute())

    # ───────────────────────────────────────── admin_settings ──
    async def get_admin_settings(self, telegram_id: int) -> dict[str, Any] | None:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("admin_settings")
                .select("*")
                .eq("telegram_id", telegram_id)
                .limit(1)
                .execute()
            )
        )
        return _first_or_none(resp)

    async def upsert_admin_settings(
        self, *, telegram_id: int, patch: dict[str, Any]
    ) -> dict[str, Any]:
        db = self._db
        payload = {"telegram_id": telegram_id, **patch}
        resp = await asyncio.to_thread(lambda: db.table("admin_settings").upsert(payload).execute())
        return _first(resp)

    # ───────────────────────────────────────── questions ──
    async def list_questions(self, *, active_only: bool) -> list[dict[str, Any]]:
        db = self._db

        def _q() -> Any:
            q = db.table("questions").select("*")
            if active_only:
                q = q.eq("is_active", True)
            return q.order("created_at", desc=True).execute()

        resp = await asyncio.to_thread(_q)
        return _rows(resp)

    async def find_questions_by_text(
        self, *, pattern: str, active_only: bool
    ) -> list[dict[str, Any]]:
        db = self._db

        def _q() -> Any:
            q = db.table("questions").select("*")
            if active_only:
                q = q.eq("is_active", True)
            return q.or_(f"text.ilike.{pattern},metric_key.ilike.{pattern}").execute()

        resp = await asyncio.to_thread(_q)
        return _rows(resp)

    async def get_question_by_metric_key(self, metric_key: str) -> dict[str, Any] | None:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("questions")
                .select("id, text, metric_key, expected_type, enum_values")
                .eq("metric_key", metric_key)
                .limit(1)
                .execute()
            )
        )
        return _first_or_none(resp)

    async def insert_question(self, payload: dict[str, Any]) -> dict[str, Any]:
        db = self._db
        resp = await asyncio.to_thread(lambda: db.table("questions").insert(payload).execute())
        return _first(resp)

    async def update_question(
        self, question_id: str | UUID, patch: dict[str, Any]
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: db.table("questions").update(patch).eq("id", str(question_id)).execute()
        )
        return _rows(resp)

    async def deactivate_questions(
        self, *, restaurant_id: str | None = None
    ) -> list[dict[str, Any]]:
        db = self._db

        def _q() -> Any:
            q = db.table("questions").update({"is_active": False}).eq("is_active", True)
            if restaurant_id is not None:
                q = q.eq("restaurant_id", str(restaurant_id))
            return q.execute()

        resp = await asyncio.to_thread(_q)
        return _rows(resp)

    # ───────────────────────────────────────── sessions ──
    async def insert_session(self, *, client_id: int) -> dict[str, Any]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: db.table("sessions").insert({"client_id": client_id}).execute()
        )
        return _first(resp)

    async def update_session(
        self, session_id: str | UUID, patch: dict[str, Any]
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: db.table("sessions").update(patch).eq("id", str(session_id)).execute()
        )
        return _rows(resp)

    async def insert_session_message(
        self, *, session_id: str | UUID, role: Role, content: str
    ) -> dict[str, Any]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("session_messages")
                .insert({"session_id": str(session_id), "role": role, "content": content})
                .execute()
            )
        )
        return _first(resp)

    async def fetch_sessions_with_feedback(
        self, *, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("sessions")
                .select(columns)
                .gte("started_at", date_from)
                .lte("started_at", date_to)
                .not_.is_("feedback_summary", "null")
                .execute()
            )
        )
        return _rows(resp)

    async def fetch_sessions_in_window(
        self, *, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("sessions")
                .select(columns)
                .gte("started_at", date_from)
                .lte("started_at", date_to)
                .execute()
            )
        )
        return _rows(resp)

    async def fetch_sessions_in_window_ordered(
        self, *, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("sessions")
                .select(columns)
                .gte("started_at", date_from)
                .lte("started_at", date_to)
                .order("started_at", desc=True)
                .execute()
            )
        )
        return _rows(resp)

    async def fetch_recent_sessions(self, *, columns: str, limit: int) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("sessions")
                .select(columns)
                .order("started_at", desc=True)
                .limit(limit)
                .execute()
            )
        )
        return _rows(resp)

    async def fetch_sessions_by_ids(
        self, *, session_ids: list[str], columns: str
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: db.table("sessions").select(columns).in_("id", session_ids).execute()
        )
        return _rows(resp)

    async def fetch_sessions_for_client(
        self, *, client_id: int, columns: str, order_desc: bool = True
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("sessions")
                .select(columns)
                .eq("client_id", client_id)
                .order("started_at", desc=order_desc)
                .execute()
            )
        )
        return _rows(resp)

    async def earliest_session_started_at(self) -> str | None:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("sessions")
                .select("started_at")
                .order("started_at", desc=False)
                .limit(1)
                .execute()
            )
        )
        row = _first_or_none(resp)
        if row is None:
            return None
        raw = row.get("started_at")
        return str(raw) if raw else None

    # ───────────────────────────────────────── session_answers ──
    async def insert_answer(self, payload: dict[str, Any]) -> dict[str, Any]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: db.table("session_answers").insert(payload).execute()
        )
        return _first(resp)

    async def fetch_answers_for_question(
        self,
        *,
        question_id: str,
        date_from: str,
        date_to: str,
        columns: str,
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("session_answers")
                .select(columns)
                .eq("question_id", question_id)
                .gte("created_at", date_from)
                .lte("created_at", date_to)
                .execute()
            )
        )
        return _rows(resp)

    async def fetch_answers_for_sessions(
        self,
        *,
        session_ids: list[str],
        question_ids: list[str],
        columns: str,
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("session_answers")
                .select(columns)
                .in_("session_id", session_ids)
                .in_("question_id", question_ids)
                .execute()
            )
        )
        return _rows(resp)

    # ───────────────────────────────────────── client_cards ──
    async def insert_client_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        db = self._db
        resp = await asyncio.to_thread(lambda: db.table("client_cards").insert(payload).execute())
        return _first(resp)

    async def fetch_cards_by_sessions(
        self, *, session_ids: list[str], columns: str
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("client_cards").select(columns).in_("session_id", session_ids).execute()
            )
        )
        return _rows(resp)

    async def fetch_recent_cards(self, *, columns: str, limit: int) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("client_cards")
                .select(columns)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
        )
        return _rows(resp)

    async def fetch_cards_for_client(
        self, *, client_id: int, columns: str, limit: int
    ) -> list[dict[str, Any]]:
        db = self._db
        resp = await asyncio.to_thread(
            lambda: (
                db.table("client_cards")
                .select(columns)
                .eq("client_id", client_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
        )
        return _rows(resp)
