"""Sessions service — session lifecycle + transcript over sessions/session_messages.

DI: `storage: StorageAdapter | None` (new) + `db: Client | None` (back-compat).
"""

from datetime import UTC, datetime
from typing import Any, Literal, TypedDict, cast
from uuid import UUID

from supabase import Client

from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter


class FeedbackSummary(TypedDict):
    summary: str
    sentiment: str
    topics: list[str]
    emotion: str


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


async def start_session(
    client_id: int,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> UUID:
    store = _storage(storage, db)
    row = await store.insert_session(client_id=client_id)
    return UUID(cast(dict[str, Any], row)["id"])


async def append_session_message(
    session_id: str | UUID,
    role: Literal["user", "bot"],
    content: str,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> int:
    if role not in ("user", "bot"):
        raise ValueError(f"role must be 'user' or 'bot', got {role!r}")
    if not content.strip():
        raise ValueError("content must not be empty")

    store = _storage(storage, db)
    row = await store.insert_session_message(session_id=session_id, role=role, content=content)
    return int(cast(dict[str, Any], row)["id"])


async def save_feedback_summary(
    session_id: str | UUID,
    *,
    raw_text: str,
    source: Literal["text", "voice"],
    summary: FeedbackSummary,
    language: str | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> None:
    if source not in ("text", "voice"):
        raise ValueError(f"source must be 'text' or 'voice', got {source!r}")
    if not raw_text.strip():
        raise ValueError("raw_text must not be empty")

    store = _storage(storage, db)
    patch: dict[str, Any] = {
        "feedback_raw_text": raw_text,
        "feedback_source": source,
        "feedback_summary": summary,
        "language": language,
    }
    rows = await store.update_session(session_id, patch)
    if not rows:
        raise LookupError(f"session {session_id} not found")


async def end_session(
    session_id: str | UUID,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> None:
    store = _storage(storage, db)
    ended_at = datetime.now(UTC).isoformat()
    rows = await store.update_session(session_id, {"ended_at": ended_at})
    if not rows:
        raise LookupError(f"session {session_id} not found")
