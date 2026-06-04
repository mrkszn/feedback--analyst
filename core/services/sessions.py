import asyncio
from typing import Any, Literal, TypedDict, cast
from uuid import UUID

from supabase import Client

from core.storage.supabase_client import get_supabase


class FeedbackSummary(TypedDict):
    summary: str
    sentiment: str
    topics: list[str]
    emotion: str


async def start_session(client_id: int, *, db: Client | None = None) -> UUID:
    db = db or get_supabase()
    resp = await asyncio.to_thread(
        lambda: db.table("sessions").insert({"client_id": client_id}).execute()
    )
    row = cast(dict[str, Any], resp.data[0])
    return UUID(row["id"])


async def append_session_message(
    session_id: str | UUID,
    role: Literal["user", "bot"],
    content: str,
    *,
    db: Client | None = None,
) -> int:
    if role not in ("user", "bot"):
        raise ValueError(f"role must be 'user' or 'bot', got {role!r}")
    if not content.strip():
        raise ValueError("content must not be empty")

    db = db or get_supabase()
    resp = await asyncio.to_thread(
        lambda: (
            db.table("session_messages")
            .insert({"session_id": str(session_id), "role": role, "content": content})
            .execute()
        )
    )
    row = cast(dict[str, Any], resp.data[0])
    return int(row["id"])


async def save_feedback_summary(
    session_id: str | UUID,
    *,
    raw_text: str,
    source: Literal["text", "voice"],
    summary: FeedbackSummary,
    language: str | None = None,
    db: Client | None = None,
) -> None:
    if source not in ("text", "voice"):
        raise ValueError(f"source must be 'text' or 'voice', got {source!r}")
    if not raw_text.strip():
        raise ValueError("raw_text must not be empty")

    db = db or get_supabase()
    payload: dict[str, Any] = {
        "feedback_raw_text": raw_text,
        "feedback_source": source,
        "feedback_summary": summary,
        "language": language,
    }
    resp = await asyncio.to_thread(
        lambda: db.table("sessions").update(payload).eq("id", str(session_id)).execute()
    )
    if not resp.data:
        raise LookupError(f"session {session_id} not found")


async def end_session(session_id: str | UUID, *, db: Client | None = None) -> None:
    from datetime import UTC, datetime

    db = db or get_supabase()
    ended_at = datetime.now(UTC).isoformat()
    resp = await asyncio.to_thread(
        lambda: (
            db.table("sessions").update({"ended_at": ended_at}).eq("id", str(session_id)).execute()
        )
    )
    if not resp.data:
        raise LookupError(f"session {session_id} not found")
