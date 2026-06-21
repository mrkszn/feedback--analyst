from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from core.services.sessions import (
    append_session_message,
    end_session,
    save_feedback_summary,
    session_detail,
    start_session,
)
from core.storage.adapters.in_memory import InMemoryStorage

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


# --- session_detail: journey ribbon for web sessions ---


async def test_session_detail_includes_journey_for_web_session() -> None:
    mem = InMemoryStorage()
    tpl = str(uuid4())
    food = str(uuid4())
    mem.journey_templates.append(
        {
            "id": tpl,
            "name": "restaurant",
            "label_uk": "Р",
            "label_en": "R",
            "is_default": True,
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    mem.journey_beats.append(
        {
            "id": food,
            "template_id": tpl,
            "position": 1,
            "beat_key": "food",
            "label_uk": "Їжа",
            "label_en": "Food",
            "icon": "🍽️",
            "input_type": "mood_slider",
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    mem.beat_tags.append(
        {
            "id": str(uuid4()),
            "beat_id": food,
            "position": 1,
            "tag_key": "cold",
            "label_uk": "Холодна",
            "label_en": "Cold",
        }
    )
    sid = str(uuid4())
    mem.sessions.append(
        {
            "id": sid,
            "client_id": None,
            "feedback_source": "web_anon",
            "mode": "targeted",
            "meal_occasion": "dinner",
            "journey_template_name": "restaurant",
            "started_at": "2026-06-15T18:00:00+00:00",
            "ended_at": "2026-06-15T18:05:00+00:00",
            "feedback_summary": None,
        }
    )
    mem.session_beats.append(
        {
            "session_id": sid,
            "beat_id": food,
            "score": 2,
            "tags": ["cold"],
            "skipped": False,
            "emoji_transcription_uk": "не сподобалось",
            "updated_at": "2026-06-15T18:01:00+00:00",
        }
    )

    detail = await session_detail(sid, storage=mem)
    j = detail["journey"]
    assert j is not None
    assert j["mode"] == "targeted"
    assert j["meal_occasion"] == "dinner"
    beat = j["beats"][0]
    assert beat["label_uk"] == "Їжа"
    assert beat["score"] == 2
    assert beat["emoji"] == "🙁"  # score 2 face
    assert beat["transcription_uk"] == "не сподобалось"
    assert beat["tags"] == ["Холодна"]


async def test_session_detail_journey_none_for_bot_session() -> None:
    mem = InMemoryStorage()
    sid = str(uuid4())
    mem.sessions.append(
        {
            "id": sid,
            "client_id": 1,
            "feedback_source": "text",
            "started_at": None,
            "ended_at": None,
            "feedback_summary": None,
        }
    )
    detail = await session_detail(sid, storage=mem)
    assert detail["journey"] is None
