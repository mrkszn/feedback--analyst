from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from tools.answers import save_answer_with_metric
from tools.client_cards import save_client_card
from tools.questions import get_active_questions

# --- get_active_questions ---


async def test_get_active_strips_internal_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_questions(*, active_only: bool, db: object) -> list[dict]:
        assert active_only is True
        return [
            {
                "id": uuid4(),
                "text": "q?",
                "metric_key": "k",
                "expected_type": "text",
                "enum_values": None,
                "created_by": 1,
                "updated_at": "x",
                "is_active": True,
            }
        ]

    monkeypatch.setattr("tools.questions.list_questions", fake_list_questions)
    result = await get_active_questions(db=MagicMock())
    assert set(result[0].keys()) == {"id", "text", "metric_key", "expected_type", "enum_values"}
    assert isinstance(result[0]["id"], str)


async def test_get_active_empty_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tools.questions.list_questions",
        AsyncMock(return_value=[]),
    )
    assert await get_active_questions(db=MagicMock()) == []


# --- save_answer_with_metric ---


async def test_save_answer_returns_id() -> None:
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value.data = [{"id": 99}]
    rid = await save_answer_with_metric(
        session_id=uuid4(),
        question_id=uuid4(),
        answer_text="хорошо",
        marked_value={"value": "good"},
        db=db,
    )
    assert rid == 99


async def test_save_answer_empty_text_raises() -> None:
    with pytest.raises(ValueError):
        await save_answer_with_metric(
            session_id=uuid4(),
            question_id=uuid4(),
            answer_text="  ",
            marked_value=None,
            db=MagicMock(),
        )


# --- save_client_card ---


async def test_save_client_card_returns_id() -> None:
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value.data = [{"id": "card-uuid"}]
    result = await save_client_card(
        client_id=1,
        session_id=uuid4(),
        summary_text="клиент доволен",
        pinecone_vector_id="vec-1",
        db=db,
    )
    assert result == "card-uuid"


async def test_save_client_card_empty_summary_raises() -> None:
    with pytest.raises(ValueError):
        await save_client_card(
            client_id=1,
            session_id=uuid4(),
            summary_text="  ",
            pinecone_vector_id="vec-1",
            db=MagicMock(),
        )


async def test_save_client_card_duplicate_raises() -> None:
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "duplicate (23505)"
    )
    with pytest.raises(ValueError, match="already exists"):
        await save_client_card(
            client_id=1,
            session_id=uuid4(),
            summary_text="x",
            pinecone_vector_id="v",
            db=db,
        )
