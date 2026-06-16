"""Unit-тесты для bot_guest.handlers.survey_consent (consent_yes / consent_no).

Покрытие:
- survey:yes + непустой pool + selected.question_ids непуст → state → IN_INTERVIEW,
  _ask_next_question вызван, FSM содержит question_ids, question_index=0,
  questions_map, answers=[];
- survey:yes + selected.question_ids пустой → fallback-сообщение,
  _finalize_session(answers=[]);
- survey:no → прощание, finalize_message_sent=True, _finalize_session(answers=[]).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from channels.telegram.common.fsm.states import GuestFlow
from channels.telegram.guest_bot.copy import GUEST_GOODBYE
from channels.telegram.guest_bot.handlers import survey_consent as sc
from core.agent.nodes.select import SelectedQuestions


@pytest.fixture
def state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    return FSMContext(storage=storage, key=key)


async def _seed_consent_state(state: FSMContext) -> str:
    sid = str(uuid4())
    await state.update_data(
        session_id=sid,
        client_id=1,
        feedback_summary={
            "summary": "Хорошо",
            "sentiment": "positive",
            "topics": ["food"],
            "emotion": "joy",
        },
    )
    await state.set_state(GuestFlow.AWAITING_SURVEY_CONSENT)
    return sid


def _make_message_mock() -> MagicMock:
    m = MagicMock()
    m.chat = MagicMock(id=1)
    m.bot = MagicMock()
    m.bot.send_chat_action = AsyncMock()
    m.answer = AsyncMock()
    m.edit_reply_markup = AsyncMock()
    return m


def _make_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user = MagicMock(id=1)
    cb.message = _make_message_mock()
    cb.bot = cb.message.bot
    cb.answer = AsyncMock()
    return cb


# ----------------------------- survey:yes + happy path --------------------- #


async def test_consent_yes_with_questions_starts_interview(state: FSMContext) -> None:
    await _seed_consent_state(state)
    cb = _make_callback("survey:yes")

    pool = [
        {"id": "q1", "metric_key": "k1", "text": "Q1", "expected_type": "boolean"},
        {"id": "q2", "metric_key": "k2", "text": "Q2", "expected_type": "text"},
    ]
    selected = SelectedQuestions(question_ids=["q1", "q2"], reasoning="r")

    with (
        patch.object(sc, "get_active_questions", new=AsyncMock(return_value=pool)),
        patch.object(sc, "select_adaptive_questions", new=AsyncMock(return_value=selected)),
        patch.object(sc, "_ask_next_question", new=AsyncMock()) as p_ask,
        patch.object(sc, "_finalize_session", new=AsyncMock()) as p_finalize,
    ):
        await sc.consent_yes(cb, state)

    # _ask_next_question вызван ровно один раз с (message, state)
    p_ask.assert_awaited_once()
    assert p_ask.await_args is not None
    assert p_ask.await_args.args[0] is cb.message
    assert p_ask.await_args.args[1] is state

    # _finalize_session НЕ вызывается — интервью только начинается.
    p_finalize.assert_not_awaited()

    # FSM-поля проставлены
    data = await state.get_data()
    assert data["question_ids"] == ["q1", "q2"]
    assert data["question_index"] == 0
    assert set(data["questions_map"].keys()) == {"q1", "q2"}
    assert data["answers"] == []

    # state переключился в IN_INTERVIEW
    assert await state.get_state() == GuestFlow.IN_INTERVIEW.state

    # Клавиатура снята + callback подтверждён
    cb.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
    cb.answer.assert_awaited()


# ----------------------------- survey:yes + empty selection ---------------- #


async def test_consent_yes_empty_selection_finalizes(state: FSMContext) -> None:
    await _seed_consent_state(state)
    cb = _make_callback("survey:yes")

    pool = [{"id": "q1", "metric_key": "k1", "text": "Q1", "expected_type": "text"}]
    selected = SelectedQuestions(question_ids=[], reasoning="nothing relevant")

    with (
        patch.object(sc, "get_active_questions", new=AsyncMock(return_value=pool)),
        patch.object(sc, "select_adaptive_questions", new=AsyncMock(return_value=selected)),
        patch.object(sc, "_ask_next_question", new=AsyncMock()) as p_ask,
        patch.object(sc, "_finalize_session", new=AsyncMock()) as p_finalize,
    ):
        await sc.consent_yes(cb, state)

    # Fallback-message отправлен
    cb.message.answer.assert_awaited_once()
    assert cb.message.answer.await_args is not None
    text = cb.message.answer.await_args.args[0]
    assert "Кажется" in text or "Спасибо" in text

    p_ask.assert_not_awaited()
    p_finalize.assert_awaited_once()
    assert p_finalize.await_args is not None
    assert p_finalize.await_args.kwargs["answers"] == []
    # summary — это FeedbackSummary
    assert p_finalize.await_args.kwargs["summary"].sentiment == "positive"

    data = await state.get_data()
    assert data.get("finalize_message_sent") is True


async def test_consent_yes_empty_pool_finalizes(state: FSMContext) -> None:
    """Граничный кейс: админ удалил все вопросы пока шёл диалог."""
    await _seed_consent_state(state)
    cb = _make_callback("survey:yes")

    with (
        patch.object(sc, "get_active_questions", new=AsyncMock(return_value=[])),
        patch.object(sc, "select_adaptive_questions", new=AsyncMock()) as p_select,
        patch.object(sc, "_ask_next_question", new=AsyncMock()) as p_ask,
        patch.object(sc, "_finalize_session", new=AsyncMock()) as p_finalize,
    ):
        await sc.consent_yes(cb, state)

    # select_adaptive_questions даже не вызывался — выйти раньше.
    p_select.assert_not_awaited()
    p_ask.assert_not_awaited()
    p_finalize.assert_awaited_once()
    assert p_finalize.await_args is not None
    assert p_finalize.await_args.kwargs["answers"] == []


# ----------------------------- survey:no ----------------------------------- #


async def test_consent_no_sends_goodbye_and_finalizes(state: FSMContext) -> None:
    await _seed_consent_state(state)
    cb = _make_callback("survey:no")

    with (
        patch.object(sc, "_finalize_session", new=AsyncMock()) as p_finalize,
    ):
        await sc.consent_no(cb, state)

    # Прощание отправлено
    cb.message.answer.assert_awaited_once()
    assert cb.message.answer.await_args is not None
    text = cb.message.answer.await_args.args[0]
    assert text == GUEST_GOODBYE

    # finalize_message_sent выставлен
    data = await state.get_data()
    assert data.get("finalize_message_sent") is True

    # _finalize_session(answers=[]) с FeedbackSummary
    p_finalize.assert_awaited_once()
    assert p_finalize.await_args is not None
    call_kwargs = p_finalize.await_args.kwargs
    assert call_kwargs["answers"] == []
    assert call_kwargs["summary"].sentiment == "positive"

    # Клавиатура снята + callback подтверждён
    cb.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
    cb.answer.assert_awaited()
