"""Unit-тесты для bot_guest.handlers.dialogue (фаза IN_DIALOGUE).

Покрытие:
- t1: текстовое сообщение + continue → append_session_message ×2,
      turn_count ++, history растёт, message.answer вызван, FSM остаётся в IN_DIALOGUE;
- t2: голосовое сообщение → transcribe_voice вызывается и transcript идёт в continue_dialogue;
- t3: offer_survey + непустой pool → bot_reply, затем клавиатура,
      state → AWAITING_SURVEY_CONSENT;
- t4: offer_survey + пустой pool → прощание, _finalize_session(answers=[]);
- t5: turn_count >= max_turns (на ноде) — проверяется в test_agent_dialogue.py.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from agent.nodes.dialogue import DialogueTurn
from bot_common.fsm.states import GuestFlow
from bot_guest.handlers import dialogue as dh


@pytest.fixture
def state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    return FSMContext(storage=storage, key=key)


def _make_message_mock(*, text: str | None = None, voice: Any = None) -> MagicMock:
    m = MagicMock()
    m.chat = MagicMock(id=1)
    m.from_user = MagicMock(id=1)
    m.bot = MagicMock()
    m.bot.send_chat_action = AsyncMock()
    m.text = text
    m.voice = voice
    m.answer = AsyncMock()
    return m


async def _seed_dialogue_state(
    state: FSMContext,
    *,
    turn_count: int = 0,
    history: list[dict[str, str]] | None = None,
) -> str:
    sid = str(uuid4())
    await state.update_data(
        session_id=sid,
        client_id=1,
        history=history or [],
        turn_count=turn_count,
        feedback_summary={
            "summary": "Хорошо",
            "sentiment": "positive",
            "topics": ["food"],
            "emotion": "joy",
        },
    )
    await state.set_state(GuestFlow.IN_DIALOGUE)
    return sid


# ----------------------------- t1: text + continue --------------------------- #


async def test_text_continue_appends_and_keeps_state(state: FSMContext) -> None:
    sid = await _seed_dialogue_state(state)
    msg = _make_message_mock(text="очень понравилось!")

    fake_turn = DialogueTurn(
        bot_reply="Рад слышать! 💛 Что больше всего запомнилось?",
        transition="continue",
        insights={},
    )

    with (
        patch.object(dh, "append_session_message", new=AsyncMock()) as p_append,
        patch.object(dh, "continue_dialogue", new=AsyncMock(return_value=fake_turn)),
        patch.object(dh, "get_active_questions", new=AsyncMock(return_value=[])),
    ):
        await dh.guest_dialogue_text(msg, state)

    # append_session_message: один раз user, один раз bot
    assert p_append.await_count == 2
    roles = [call.args[1] for call in p_append.await_args_list]
    assert roles == ["user", "bot"]
    assert p_append.await_args_list[0].args == (sid, "user", "очень понравилось!")
    assert p_append.await_args_list[1].args == (sid, "bot", fake_turn.bot_reply)

    # FSM data: turn_count++, history выросла на 2 (user + bot)
    data = await state.get_data()
    assert data["turn_count"] == 1
    assert len(data["history"]) == 2
    assert data["history"][0] == {"role": "user", "content": "очень понравилось!"}
    assert data["history"][1] == {"role": "bot", "content": fake_turn.bot_reply}

    # Ответ отправлен пользователю
    msg.answer.assert_awaited_once_with(fake_turn.bot_reply)

    # state остался IN_DIALOGUE
    assert await state.get_state() == GuestFlow.IN_DIALOGUE.state


# ----------------------------- t2: voice path ------------------------------- #


async def test_voice_message_transcribes_then_dialogues(state: FSMContext) -> None:
    await _seed_dialogue_state(state)
    voice = MagicMock(file_id="vfile-1")
    msg = _make_message_mock(voice=voice)

    fake_turn = DialogueTurn(
        bot_reply="Понимаю тебя ✨",
        transition="continue",
        insights={},
    )

    from pathlib import Path

    fake_path_mock = MagicMock(spec=Path)
    fake_path_mock.unlink = MagicMock()

    with (
        patch.object(
            dh, "download_voice_to_tmp", new=AsyncMock(return_value=fake_path_mock)
        ) as p_dl,
        patch.object(
            dh, "transcribe_voice", new=AsyncMock(return_value="это голосовой текст")
        ) as p_tx,
        patch.object(dh, "append_session_message", new=AsyncMock()) as p_append,
        patch.object(dh, "continue_dialogue", new=AsyncMock(return_value=fake_turn)) as p_cd,
        patch.object(dh, "get_active_questions", new=AsyncMock(return_value=[])),
    ):
        await dh.guest_dialogue_voice(msg, state)

    p_dl.assert_awaited_once()
    p_tx.assert_awaited_once_with(fake_path_mock)

    # transcript ушёл в continue_dialogue через _process_dialogue_turn (history),
    # и в append_session_message как user-сообщение.
    user_appends = [c for c in p_append.await_args_list if c.args[1] == "user"]
    assert len(user_appends) == 1
    assert user_appends[0].args[2] == "это голосовой текст"

    # continue_dialogue вызывался с history, содержащей transcript
    p_cd.assert_awaited_once()
    call_kwargs = p_cd.await_args.kwargs
    assert any(h.get("content") == "это голосовой текст" for h in call_kwargs["history"])

    msg.answer.assert_awaited_once_with(fake_turn.bot_reply)


async def test_voice_empty_transcript_prompts_retry(state: FSMContext) -> None:
    await _seed_dialogue_state(state)
    voice = MagicMock(file_id="vfile-empty")
    msg = _make_message_mock(voice=voice)

    from pathlib import Path

    fake_path_mock = MagicMock(spec=Path)
    fake_path_mock.unlink = MagicMock()

    with (
        patch.object(dh, "download_voice_to_tmp", new=AsyncMock(return_value=fake_path_mock)),
        patch.object(dh, "transcribe_voice", new=AsyncMock(return_value="   ")),
        patch.object(dh, "append_session_message", new=AsyncMock()) as p_append,
        patch.object(dh, "continue_dialogue", new=AsyncMock()) as p_cd,
    ):
        await dh.guest_dialogue_voice(msg, state)

    p_cd.assert_not_awaited()
    p_append.assert_not_awaited()
    msg.answer.assert_awaited_once()
    text = msg.answer.await_args.args[0]
    assert "разобрал" in text.lower() or "повторить" in text.lower()


# ----------------------------- t3: offer_survey + pool non-empty ----------- #


async def test_offer_survey_with_pool_transitions_to_consent(state: FSMContext) -> None:
    await _seed_dialogue_state(state, turn_count=4)
    msg = _make_message_mock(text="ну да, ещё хочу сказать")

    fake_turn = DialogueTurn(
        bot_reply="Спасибо за этот тёплый разговор! 🌟",
        transition="offer_survey",
        insights={},
    )

    pool = [
        {"id": "q1", "metric_key": "k1", "text": "Q1", "expected_type": "boolean"},
    ]

    with (
        patch.object(dh, "append_session_message", new=AsyncMock()),
        patch.object(dh, "continue_dialogue", new=AsyncMock(return_value=fake_turn)),
        patch.object(dh, "get_active_questions", new=AsyncMock(return_value=pool)),
        patch.object(dh, "_finalize_session", new=AsyncMock()) as p_finalize,
    ):
        await dh.guest_dialogue_text(msg, state)

    # Два answer'a: сначала bot_reply, потом текст offer'а с клавиатурой.
    assert msg.answer.await_count == 2
    first_call = msg.answer.await_args_list[0]
    assert first_call.args[0] == fake_turn.bot_reply

    second_call = msg.answer.await_args_list[1]
    offer_text = second_call.args[0]
    assert "Спасибо за разговор" in offer_text
    keyboard = second_call.kwargs.get("reply_markup")
    assert keyboard is not None
    # У клавиатуры две кнопки в одном ряду.
    rows = keyboard.inline_keyboard
    assert len(rows) == 1
    assert len(rows[0]) == 2
    callbacks = {btn.callback_data for btn in rows[0]}
    assert callbacks == {"survey:yes", "survey:no"}

    # state переключился в AWAITING_SURVEY_CONSENT
    assert await state.get_state() == GuestFlow.AWAITING_SURVEY_CONSENT.state

    # _finalize_session НЕ должен быть вызван (опрос ещё не запущен).
    p_finalize.assert_not_awaited()


# ----------------------------- t4: offer_survey + empty pool --------------- #


async def test_offer_survey_empty_pool_finalizes(state: FSMContext) -> None:
    await _seed_dialogue_state(state, turn_count=4)
    msg = _make_message_mock(text="всё было супер!")

    fake_turn = DialogueTurn(
        bot_reply="Так приятно слышать! ☀️",
        transition="offer_survey",
        insights={},
    )

    with (
        patch.object(dh, "append_session_message", new=AsyncMock()),
        patch.object(dh, "continue_dialogue", new=AsyncMock(return_value=fake_turn)),
        patch.object(dh, "get_active_questions", new=AsyncMock(return_value=[])),
        patch.object(dh, "_finalize_session", new=AsyncMock()) as p_finalize,
    ):
        await dh.guest_dialogue_text(msg, state)

    # answer: 1) bot_reply, 2) прощание «Спасибо большое за рассказ!...»
    assert msg.answer.await_count == 2
    assert msg.answer.await_args_list[0].args[0] == fake_turn.bot_reply
    goodbye = msg.answer.await_args_list[1].args[0]
    assert "Спасибо большое за рассказ" in goodbye

    # _finalize_session вызван с answers=[]
    p_finalize.assert_awaited_once()
    call_kwargs = p_finalize.await_args.kwargs
    assert call_kwargs["answers"] == []
    # summary прокидывается как FeedbackSummary (model)
    assert call_kwargs["summary"].sentiment == "positive"

    # finalize_message_sent выставлен — чтобы _finalize_session не дублировал goodbye.
    data = await state.get_data()
    assert data.get("finalize_message_sent") is True


# ----------------------------- t5: hard-cap on node ------------------------- #


async def test_handler_propagates_node_hard_cap(state: FSMContext) -> None:
    """Когда нода форсит offer_survey (turn_count >= max_turns),
    handler корректно ветвится в _emit_survey_offer_or_finalize."""
    # turn_count=4 → new_turn_count=5 == max_turns → нода форсирует offer_survey.
    # Здесь имитируем уже-форсированный возврат ноды (она и есть источник правды).
    await _seed_dialogue_state(state, turn_count=4)
    msg = _make_message_mock(text="ещё один ход")

    forced_turn = DialogueTurn(
        bot_reply="Огонь беседа! 🔥",
        transition="offer_survey",  # форсировано хард-капом ноды
        insights={},
    )

    with (
        patch.object(dh, "append_session_message", new=AsyncMock()),
        patch.object(dh, "continue_dialogue", new=AsyncMock(return_value=forced_turn)),
        patch.object(
            dh,
            "get_active_questions",
            new=AsyncMock(
                return_value=[{"id": "q1", "metric_key": "k", "text": "Q", "expected_type": "text"}]
            ),
        ),
        patch.object(dh, "_finalize_session", new=AsyncMock()),
    ):
        await dh.guest_dialogue_text(msg, state)

    # state должен быть AWAITING_SURVEY_CONSENT — handler уважает решение ноды.
    assert await state.get_state() == GuestFlow.AWAITING_SURVEY_CONSENT.state
