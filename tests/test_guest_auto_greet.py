"""Unit-тесты для greeting-разводки в guest-боте.

Покрытие:
- auto-greet (StateFilter(None)):
    * голое приветствие → только WELCOME, _process_feedback НЕ зван,
      state = AWAITING_FEEDBACK;
    * содержательный текст → _process_feedback зван с текстом, WELCOME НЕ зван;
    * голос → process_voice_message зван, WELCOME НЕ зван;
    * from_user is None → ранний выход, ничего не происходит.
- AWAITING_FEEDBACK (guest_feedback_text):
    * приветствие → мягкий re-prompt, _process_feedback НЕ зван;
    * содержательный текст → _process_feedback зван.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from channels.telegram.common.fsm.states import GuestFlow
from channels.telegram.guest_bot.handlers import feedback as fh
from channels.telegram.guest_bot.handlers import start as sh

# First-timer re-entry context — patched in so greeting tests don't hit
# Supabase via load_reentry_context (which guest_start/auto_greet now call).
_FIRST_TIMER = {
    "is_returning": False,
    "sessions_count": 0,
    "last_session_at": None,
    "top_topic": None,
}
_RETURNING = {
    "is_returning": True,
    "sessions_count": 2,
    "last_session_at": "2026-06-01T12:00:00+00:00",
    "top_topic": "курьер",
}


@pytest.fixture
def state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    return FSMContext(storage=storage, key=key)


def _make_message_mock(*, text: str | None = None, voice: Any = None) -> MagicMock:
    m = MagicMock()
    m.chat = MagicMock(id=1)
    m.from_user = MagicMock(id=1, full_name="Иван")
    m.bot = MagicMock()
    m.text = text
    m.voice = voice
    m.answer = AsyncMock()
    return m


# ----------------------------- auto-greet: greeting ------------------------- #


async def test_auto_greet_greeting_only_welcomes(state: FSMContext) -> None:
    msg = _make_message_mock(text="Привет! 👋")

    with (
        patch.object(sh, "create_or_get_client", new=AsyncMock()),
        patch.object(sh, "load_reentry_context", new=AsyncMock(return_value=_FIRST_TIMER)),
        patch.object(fh, "_process_feedback", new=AsyncMock()) as p_proc,
        patch.object(fh, "process_voice_message", new=AsyncMock()) as p_voice,
    ):
        await sh.guest_auto_greet(msg, state)

    # Ровно одно сообщение — WELCOME (first-timer), и пайплайн не запущен.
    msg.answer.assert_awaited_once_with(sh.WELCOME)
    p_proc.assert_not_awaited()
    p_voice.assert_not_awaited()
    assert await state.get_state() == GuestFlow.AWAITING_FEEDBACK.state


async def test_auto_greet_greeting_returning_personalizes(state: FSMContext) -> None:
    msg = _make_message_mock(text="привет")

    with (
        patch.object(sh, "create_or_get_client", new=AsyncMock()),
        patch.object(sh, "load_reentry_context", new=AsyncMock(return_value=_RETURNING)),
        patch.object(fh, "_process_feedback", new=AsyncMock()) as p_proc,
    ):
        await sh.guest_auto_greet(msg, state)

    p_proc.assert_not_awaited()
    msg.answer.assert_awaited_once()
    sent = msg.answer.await_args.args[0]
    assert sent != sh.WELCOME
    assert "С возвращением" in sent
    assert "курьер" in sent  # top_topic surfaced


async def test_auto_greet_blank_text_welcomes(state: FSMContext) -> None:
    msg = _make_message_mock(text="   ")

    with (
        patch.object(sh, "create_or_get_client", new=AsyncMock()),
        patch.object(sh, "load_reentry_context", new=AsyncMock(return_value=_FIRST_TIMER)),
        patch.object(fh, "_process_feedback", new=AsyncMock()) as p_proc,
    ):
        await sh.guest_auto_greet(msg, state)

    msg.answer.assert_awaited_once_with(sh.WELCOME)
    p_proc.assert_not_awaited()


# ----------------------------- auto-greet: substantive text ----------------- #


async def test_auto_greet_substantive_text_processes_without_welcome(state: FSMContext) -> None:
    msg = _make_message_mock(text="Заказывал пиццу, привезли холодной")

    with (
        patch.object(sh, "create_or_get_client", new=AsyncMock()),
        patch.object(fh, "_process_feedback", new=AsyncMock()) as p_proc,
    ):
        await sh.guest_auto_greet(msg, state)

    # WELCOME НЕ отправлен (его роль берёт на себя первый ход диалога).
    msg.answer.assert_not_awaited()
    p_proc.assert_awaited_once()
    # текст и source прокинуты верно
    assert p_proc.await_args is not None
    assert p_proc.await_args.kwargs["raw_text"] == "Заказывал пиццу, привезли холодной"
    assert p_proc.await_args.kwargs["source"] == "text"


# ----------------------------- auto-greet: voice ---------------------------- #


async def test_auto_greet_voice_processes_without_welcome(state: FSMContext) -> None:
    voice = MagicMock(file_id="vfile-1")
    msg = _make_message_mock(voice=voice)

    with (
        patch.object(sh, "create_or_get_client", new=AsyncMock()),
        patch.object(fh, "process_voice_message", new=AsyncMock()) as p_voice,
        patch.object(fh, "_process_feedback", new=AsyncMock()) as p_proc,
    ):
        await sh.guest_auto_greet(msg, state)

    msg.answer.assert_not_awaited()
    p_voice.assert_awaited_once()
    p_proc.assert_not_awaited()


# ----------------------------- auto-greet: no user -------------------------- #


async def test_auto_greet_no_user_is_noop(state: FSMContext) -> None:
    msg = _make_message_mock(text="привет")
    msg.from_user = None

    with (
        patch.object(sh, "create_or_get_client", new=AsyncMock()) as p_client,
        patch.object(fh, "_process_feedback", new=AsyncMock()) as p_proc,
    ):
        await sh.guest_auto_greet(msg, state)

    p_client.assert_not_awaited()
    p_proc.assert_not_awaited()
    msg.answer.assert_not_awaited()
    assert await state.get_state() is None


# ----------------------- AWAITING_FEEDBACK: greeting guard ------------------ #


async def test_awaiting_feedback_greeting_reprompts(state: FSMContext) -> None:
    await state.set_state(GuestFlow.AWAITING_FEEDBACK)
    msg = _make_message_mock(text="привет")

    with patch.object(fh, "_process_feedback", new=AsyncMock()) as p_proc:
        await fh.guest_feedback_text(msg, state)

    p_proc.assert_not_awaited()
    msg.answer.assert_awaited_once()
    reply = msg.answer.await_args.args[0]
    assert "как прошёл заказ" in reply.lower()
    # state не двигается — ждём реальный отзыв здесь же.
    assert await state.get_state() == GuestFlow.AWAITING_FEEDBACK.state


async def test_awaiting_feedback_substantive_processes(state: FSMContext) -> None:
    await state.set_state(GuestFlow.AWAITING_FEEDBACK)
    msg = _make_message_mock(text="всё понравилось, курьер вежливый")

    with patch.object(fh, "_process_feedback", new=AsyncMock()) as p_proc:
        await fh.guest_feedback_text(msg, state)

    p_proc.assert_awaited_once()
    assert p_proc.await_args is not None
    assert p_proc.await_args.kwargs["raw_text"] == "всё понравилось, курьер вежливый"


# ----------------------------- /start: personalization --------------------- #


async def test_guest_start_first_timer_welcomes(state: FSMContext) -> None:
    msg = _make_message_mock(text="/start")

    with (
        patch.object(sh, "create_or_get_client", new=AsyncMock()),
        patch.object(sh, "load_reentry_context", new=AsyncMock(return_value=_FIRST_TIMER)),
    ):
        await sh.guest_start(msg, state)

    msg.answer.assert_awaited_once_with(sh.WELCOME)
    assert await state.get_state() == GuestFlow.AWAITING_FEEDBACK.state


async def test_guest_start_returning_personalizes(state: FSMContext) -> None:
    msg = _make_message_mock(text="/start")

    with (
        patch.object(sh, "create_or_get_client", new=AsyncMock()),
        patch.object(sh, "load_reentry_context", new=AsyncMock(return_value=_RETURNING)),
    ):
        await sh.guest_start(msg, state)

    msg.answer.assert_awaited_once()
    sent = msg.answer.await_args.args[0]
    assert sent != sh.WELCOME
    assert "С возвращением" in sent
    assert await state.get_state() == GuestFlow.AWAITING_FEEDBACK.state
