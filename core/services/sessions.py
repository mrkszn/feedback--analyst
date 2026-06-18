"""Sessions service — session lifecycle + transcript over sessions/session_messages.

DI: `storage: StorageAdapter | None` (new) + `db: Client | None` (back-compat).
"""

import json
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict, cast
from uuid import UUID

from supabase import Client

from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter

Sentiment = Literal["positive", "neutral", "negative"]


class FeedbackSummary(TypedDict):
    summary: str
    sentiment: str
    topics: list[str]
    emotion: str


class SessionListItem(TypedDict):
    id: str
    client_id: int | None
    client_name: str | None
    started_at: str | None
    ended_at: str | None
    sentiment: str | None
    topics: list[str]
    source: str | None


class SessionMessage(TypedDict):
    role: str
    content: str
    created_at: str | None


class SessionAnswer(TypedDict):
    question_text: str
    answer_text: str | None
    marked_value: str | None


class SessionDetail(TypedDict):
    id: str
    client_id: int | None
    client_name: str | None
    started_at: str | None
    ended_at: str | None
    sentiment: str | None
    topics: list[str]
    source: str | None
    summary: str | None
    messages: list[SessionMessage]
    answers: list[SessionAnswer]
    card_summary: str | None


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


def _summary_dict(row: dict[str, Any]) -> dict[str, Any]:
    s = row.get("feedback_summary")
    return s if isinstance(s, dict) else {}


def _sentiment_of(row: dict[str, Any]) -> str | None:
    sent = _summary_dict(row).get("sentiment")
    return str(sent) if sent else None


def _topics_of(row: dict[str, Any]) -> list[str]:
    topics = _summary_dict(row).get("topics") or []
    if not isinstance(topics, list):
        return []
    return [t.strip().lower() for t in topics if isinstance(t, str) and t.strip()]


async def _client_names(store: StorageAdapter, client_ids: list[Any]) -> dict[int, str | None]:
    uniq = list({int(cid) for cid in client_ids if cid is not None})
    if not uniq:
        return {}
    rows = await store.fetch_clients_by_ids(telegram_ids=uniq, columns="telegram_id, name")
    return {int(r["telegram_id"]): r.get("name") for r in rows}


def _list_item(row: dict[str, Any], names: dict[int, str | None]) -> SessionListItem:
    cid = row.get("client_id")
    cid_int = int(cid) if cid is not None else None
    return SessionListItem(
        id=str(row["id"]),
        client_id=cid_int,
        client_name=names.get(cid_int) if cid_int is not None else None,
        started_at=str(row["started_at"]) if row.get("started_at") else None,
        ended_at=str(row["ended_at"]) if row.get("ended_at") else None,
        sentiment=_sentiment_of(row),
        topics=_topics_of(row),
        source=row.get("feedback_source"),
    )


_MARKED_VALUE_KEYS = ("value", "label", "text", "name", "title")


def _coerce_marked_value(value: Any) -> str | None:
    """Flatten a JSONB `marked_value` to a scalar string for the API.

    `marked_value` may be None, a scalar, a `{"value": ...}`-style dict, or a
    list. The Mini App renders it as a React child, so it must never be an
    object: None stays None, scalars stringify, a dict yields its first scalar
    among value/label/text/name/title (else a JSON fallback), and a list joins.
    """
    if value is None:
        return None
    if isinstance(value, str | int | float | bool):
        return str(value)
    if isinstance(value, dict):
        for key in _MARKED_VALUE_KEYS:
            inner = value.get(key)
            if isinstance(inner, str | int | float | bool):
                return str(inner)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list):
        parts = [_coerce_marked_value(v) for v in value]
        return ", ".join(p for p in parts if p is not None)
    return str(value)


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


# --------------------------------------------------------------------------- #
# drill-down: list sessions + full session detail


async def list_sessions(
    date_from: datetime,
    date_to: datetime,
    *,
    sentiment: Sentiment | None = None,
    limit: int = 50,
    offset: int = 0,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> list[SessionListItem]:
    """Sessions in [date_from, date_to], newest first, paginated. Optional
    sentiment filter (for the dashboard's positive/negative blocks)."""
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if limit < 0 or offset < 0:
        raise ValueError("limit and offset must be non-negative")

    store = _storage(storage, db)
    rows = await store.fetch_sessions_in_window_ordered(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        columns="id, client_id, started_at, ended_at, feedback_summary, feedback_source",
    )
    if sentiment is not None:
        rows = [r for r in rows if _sentiment_of(r) == sentiment]

    page = rows[offset : offset + limit]
    names = await _client_names(store, [r.get("client_id") for r in page])
    return [_list_item(r, names) for r in page]


async def session_detail(
    session_id: str | UUID,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> SessionDetail:
    """Everything that happened in one session: metadata + message transcript
    + extracted structured answers (with question text) + generated card.
    Raises LookupError if the session does not exist."""
    store = _storage(storage, db)

    found = await store.fetch_sessions_by_ids(
        session_ids=[str(session_id)],
        columns="id, client_id, started_at, ended_at, feedback_summary, feedback_source",
    )
    if not found:
        raise LookupError(f"session {session_id} not found")
    row = found[0]

    raw_messages = await store.fetch_session_messages(
        session_id=session_id,
        columns="role, content, created_at",
    )
    messages = [
        SessionMessage(
            role=str(m.get("role") or ""),
            content=str(m.get("content") or ""),
            created_at=str(m["created_at"]) if m.get("created_at") else None,
        )
        for m in raw_messages
    ]

    questions = await store.list_questions(active_only=False)
    answers: list[SessionAnswer] = []
    if questions:
        q_text_by_id = {str(q["id"]): str(q.get("text") or "") for q in questions}
        raw_answers = await store.fetch_answers_for_sessions(
            session_ids=[str(session_id)],
            question_ids=list(q_text_by_id.keys()),
            columns="question_id, answer_text, marked_value",
        )
        answers = [
            SessionAnswer(
                question_text=q_text_by_id.get(str(a.get("question_id")), ""),
                answer_text=a.get("answer_text"),
                marked_value=_coerce_marked_value(a.get("marked_value")),
            )
            for a in raw_answers
        ]

    cards = await store.fetch_cards_by_sessions(
        session_ids=[str(session_id)],
        columns="session_id, summary_text",
    )
    card_summary = str(cards[0]["summary_text"]) if cards and cards[0].get("summary_text") else None

    cid = row.get("client_id")
    names = await _client_names(store, [cid])
    cid_int = int(cid) if cid is not None else None
    summary_text = _summary_dict(row).get("summary")

    return SessionDetail(
        id=str(row["id"]),
        client_id=cid_int,
        client_name=names.get(cid_int) if cid_int is not None else None,
        started_at=str(row["started_at"]) if row.get("started_at") else None,
        ended_at=str(row["ended_at"]) if row.get("ended_at") else None,
        sentiment=_sentiment_of(row),
        topics=_topics_of(row),
        source=row.get("feedback_source"),
        summary=str(summary_text) if summary_text else None,
        messages=messages,
        answers=answers,
        card_summary=card_summary,
    )
