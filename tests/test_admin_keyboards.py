"""Tests for bot_admin.keyboards.main_menu_keyboard + greeting wiring."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import ReplyKeyboardMarkup

from bot_admin.handlers.auth import admin_menu_admins, admin_start
from bot_admin.keyboards import (
    BTN_ADD_QUESTION,
    BTN_ADMINS,
    BTN_MODE_ADMIN,
    BTN_MODE_ANALYTICS,
    BTN_QUESTIONS,
    main_menu_keyboard,
    mode_toggle_label,
)


def test_main_menu_keyboard_default_admin_mode() -> None:
    kb = main_menu_keyboard()
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert kb.resize_keyboard is True
    assert kb.is_persistent is True
    rows = kb.keyboard
    assert len(rows) == 2
    assert [b.text for b in rows[0]] == [BTN_QUESTIONS, BTN_ADD_QUESTION]
    # In admin mode the toggle button offers to SWITCH to analytics.
    assert [b.text for b in rows[1]] == [BTN_MODE_ANALYTICS, BTN_ADMINS]


def test_main_menu_keyboard_analytics_mode() -> None:
    kb = main_menu_keyboard(current_mode="analytics")
    rows = kb.keyboard
    # In analytics mode the toggle button offers to SWITCH back to admin.
    assert [b.text for b in rows[1]] == [BTN_MODE_ADMIN, BTN_ADMINS]


def test_mode_toggle_label_inverts() -> None:
    assert mode_toggle_label("admin") == BTN_MODE_ANALYTICS
    assert mode_toggle_label("analytics") == BTN_MODE_ADMIN


async def test_admin_start_attaches_keyboard_for_admin() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=1)
    message.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={})

    with patch("bot_admin.handlers.auth.is_admin", new=AsyncMock(return_value=True)):
        await admin_start(message, state)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert "Здравствуйте" in args[0]
    assert isinstance(kwargs.get("reply_markup"), ReplyKeyboardMarkup)


async def test_admin_start_keyboard_respects_existing_mode() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=1)
    message.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"admin_mode": "analytics"})

    with patch("bot_admin.handlers.auth.is_admin", new=AsyncMock(return_value=True)):
        await admin_start(message, state)

    kb = message.answer.await_args.kwargs["reply_markup"]
    assert [b.text for b in kb.keyboard[1]] == [BTN_MODE_ADMIN, BTN_ADMINS]


async def test_admin_start_no_keyboard_for_non_admin() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=2)
    message.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={})

    with patch("bot_admin.handlers.auth.is_admin", new=AsyncMock(return_value=False)):
        await admin_start(message, state)

    args, kwargs = message.answer.await_args
    assert "не админ" in args[0].lower()
    assert "reply_markup" not in kwargs


async def test_button_admins_returns_invite_hint() -> None:
    message = MagicMock()
    message.answer = AsyncMock()
    await admin_menu_admins(message)
    text = message.answer.await_args.args[0]
    assert "/invite_admin" in text


async def test_button_questions_forwards_to_list() -> None:
    from bot_admin.handlers.questions import admin_questions_list_button

    message = MagicMock()
    message.from_user = MagicMock(id=3)
    message.answer = AsyncMock()

    with (
        patch("bot_admin.handlers.questions.is_admin", new=AsyncMock(return_value=True)),
        patch(
            "bot_admin.handlers.questions.list_questions",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await admin_questions_list_button(message)

    message.answer.assert_awaited()


async def test_button_add_question_forwards_to_picker() -> None:
    from bot_admin.handlers.questions import admin_question_add_button

    message = MagicMock()
    message.from_user = MagicMock(id=4)
    message.answer = AsyncMock()
    state = MagicMock()

    with patch("bot_admin.handlers.questions.is_admin", new=AsyncMock(return_value=True)):
        await admin_question_add_button(message, state)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert "Как добавить" in args[0]
    assert kwargs.get("reply_markup") is not None
