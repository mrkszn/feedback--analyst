from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from core.services.sessions import (
    append_session_message,
    end_session,
    save_feedback_summary,
    start_session,
)

# --- start_session ---


async def test_start_session_returns_uuid() -> None:
    db = MagicMock()
    sid = uuid4()
    db.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": str(sid), "client_id": 1}
    ]
    result = await start_session(1, db=db)
    assert isinstance(result, UUID)
    assert result == sid


# --- append_session_message ---


async def test_append_user_message_returns_id() -> None:
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value.data = [{"id": 7}]
    rid = await append_session_message(uuid4(), "user", "hi", db=db)
    assert rid == 7


async def test_append_empty_content_raises() -> None:
    with pytest.raises(ValueError):
        await append_session_message(uuid4(), "user", "   ", db=MagicMock())


async def test_append_invalid_role_raises() -> None:
    with pytest.raises(ValueError):
        await append_session_message(uuid4(), "system", "hi", db=MagicMock())  # type: ignore[arg-type]


# --- save_feedback_summary ---


async def test_save_feedback_text() -> None:
    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "x"}
    ]
    summary = {"summary": "ok", "sentiment": "positive", "topics": [], "emotion": "happy"}
    await save_feedback_summary(
        uuid4(),
        raw_text="great",
        source="text",
        summary=summary,  # type: ignore[arg-type]
        db=db,
    )


async def test_save_feedback_invalid_source() -> None:
    with pytest.raises(ValueError):
        await save_feedback_summary(
            uuid4(),
            raw_text="x",
            source="audio",  # type: ignore[arg-type]
            summary={"summary": "", "sentiment": "", "topics": [], "emotion": ""},
            db=MagicMock(),
        )


async def test_save_feedback_session_not_found() -> None:
    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    with pytest.raises(LookupError):
        await save_feedback_summary(
            uuid4(),
            raw_text="x",
            source="text",
            summary={"summary": "x", "sentiment": "neutral", "topics": [], "emotion": ""},
            db=db,
        )


# --- end_session ---


async def test_end_session_sets_ended_at() -> None:
    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "x"}
    ]
    await end_session(uuid4(), db=db)
    db.table.return_value.update.assert_called_once()
    args, _ = db.table.return_value.update.call_args
    assert "ended_at" in args[0]


async def test_end_session_not_found_raises() -> None:
    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    with pytest.raises(LookupError):
        await end_session(uuid4(), db=db)
