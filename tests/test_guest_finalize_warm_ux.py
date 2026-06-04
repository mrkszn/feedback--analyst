"""Tests for the warm finalize UX in bot_guest.handlers.feedback.

Two behaviours we lock in:
1. When the last interview answer comes in (`idx + 1 >= len(qids)`),
   `_ask_next_question` sends the "Минутку, собираю всё вместе… 📝"
   progress ping BEFORE the long build-card / Pinecone block.
2. The final goodbye text in `_finalize_session` is warm (emoji + dialogue
   tone), not the old curt "Спасибо за отзыв! Хорошего дня.".
3. `finalize_message_sent` guard is honoured — empty-pool sessions that
   already sent a goodbye don't double-up.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from channels.telegram.guest_bot.handlers import feedback as fb


@pytest.fixture
def state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    return FSMContext(storage=storage, key=key)


def _make_message_mock() -> MagicMock:
    m = MagicMock()
    m.chat = MagicMock(id=1)
    m.bot = None  # bypass ChatActionSender
    m.answer = AsyncMock()
    return m


async def test_ask_next_sends_progress_ping_before_finalize(state: FSMContext) -> None:
    sid = str(uuid4())
    qids = ["q1"]
    await state.update_data(
        session_id=sid,
        client_id=1,
        question_ids=qids,
        question_index=1,  # already past last question → triggers finalize
        questions_map={},
        summary={
            "summary": "ok",
            "sentiment": "positive",
            "topics": [],
            "emotion": "neutral",
        },
        answers=[],
    )
    msg = _make_message_mock()

    with patch.object(fb, "_finalize_with_state", new=AsyncMock()) as fin:
        await fb._ask_next_question(msg, state)

    msg.answer.assert_awaited_once()
    text = msg.answer.await_args.args[0]
    assert "Минутку" in text
    assert "собираю" in text
    fin.assert_awaited_once()


async def test_ask_next_skips_ping_if_finalize_already_sent(state: FSMContext) -> None:
    """Empty-pool path sets `finalize_message_sent=True` upstream — don't
    duplicate the progress ping."""
    sid = str(uuid4())
    await state.update_data(
        session_id=sid,
        client_id=1,
        question_ids=[],
        question_index=0,
        questions_map={},
        summary={
            "summary": "ok",
            "sentiment": "positive",
            "topics": [],
            "emotion": "neutral",
        },
        answers=[],
        finalize_message_sent=True,
    )
    msg = _make_message_mock()

    with patch.object(fb, "_finalize_with_state", new=AsyncMock()) as fin:
        await fb._ask_next_question(msg, state)

    msg.answer.assert_not_called()
    fin.assert_awaited_once()


async def test_finalize_session_sends_warm_goodbye(state: FSMContext) -> None:
    sid = str(uuid4())
    await state.update_data(
        session_id=sid,
        client_id=1,
        question_ids=[],
        question_index=0,
        questions_map={},
        summary={},
        answers=[],
    )
    msg = _make_message_mock()

    fake_card = MagicMock()
    fake_card.summary_text = "card text"
    fake_card.sentiment = "positive"
    fake_card.topics = []

    with (
        patch.object(fb, "build_client_card", new=AsyncMock(return_value=fake_card)),
        patch.object(fb, "embed_text", new=AsyncMock(return_value=[0.0])),
        patch.object(fb, "upsert_client_card_vector", new=AsyncMock(return_value="vid")),
        patch.object(fb, "save_client_card", new=AsyncMock()),
        patch.object(fb, "end_session", new=AsyncMock()),
    ):
        await fb._finalize_session(msg, state, summary=MagicMock(), answers=[])

    # The old curt goodbye must NOT appear
    sent_texts = [c.args[0] for c in msg.answer.await_args_list]
    assert all(t != "Спасибо за отзыв! Хорошего дня." for t in sent_texts)
    # The warm goodbye includes a thank-you + heart + a sign-off emoji
    assert any("Спасибо большое" in t for t in sent_texts)
    assert any("🙏" in t for t in sent_texts)


async def test_finalize_session_skips_goodbye_if_already_sent(state: FSMContext) -> None:
    sid = str(uuid4())
    await state.update_data(
        session_id=sid,
        client_id=1,
        question_ids=[],
        question_index=0,
        questions_map={},
        summary={},
        answers=[],
        finalize_message_sent=True,
    )
    msg = _make_message_mock()

    fake_card = MagicMock()
    fake_card.summary_text = "card text"
    fake_card.sentiment = "positive"
    fake_card.topics = []

    with (
        patch.object(fb, "build_client_card", new=AsyncMock(return_value=fake_card)),
        patch.object(fb, "embed_text", new=AsyncMock(return_value=[0.0])),
        patch.object(fb, "upsert_client_card_vector", new=AsyncMock(return_value="vid")),
        patch.object(fb, "save_client_card", new=AsyncMock()),
        patch.object(fb, "end_session", new=AsyncMock()),
    ):
        await fb._finalize_session(msg, state, summary=MagicMock(), answers=[])

    msg.answer.assert_not_called()
