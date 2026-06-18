"""Tests for bot_admin.keyboards.main_menu_keyboard + greeting wiring."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from presentations.telegram_admin.handlers.auth import admin_menu_admins, admin_start
from presentations.telegram_admin.handlers.settings_menu import (
    admin_settings_button,
    admin_settings_update,
)
from presentations.telegram_admin.keyboards import (
    BTN_ADD_QUESTION,
    BTN_ADMINS,
    BTN_QUESTIONS,
    BTN_SETTINGS,
    BTN_STATISTICS,
    main_menu_keyboard,
)


def test_main_menu_keyboard_layout() -> None:
    kb = main_menu_keyboard()
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert kb.resize_keyboard is True
    assert kb.is_persistent is True
    rows = kb.keyboard
    assert len(rows) == 3
    assert [b.text for b in rows[0]] == [BTN_QUESTIONS, BTN_ADD_QUESTION]
    assert [b.text for b in rows[1]] == [BTN_STATISTICS, BTN_ADMINS]
    assert [b.text for b in rows[2]] == [BTN_SETTINGS]


async def test_admin_start_attaches_keyboard_for_admin() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=1)
    message.answer = AsyncMock()

    with patch(
        "presentations.telegram_admin.handlers.auth.is_admin", new=AsyncMock(return_value=True)
    ):
        await admin_start(message)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert "Здравствуйте" in args[0]
    assert isinstance(kwargs.get("reply_markup"), ReplyKeyboardMarkup)


async def test_admin_start_no_keyboard_for_non_admin() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=2)
    message.answer = AsyncMock()

    with patch(
        "presentations.telegram_admin.handlers.auth.is_admin", new=AsyncMock(return_value=False)
    ):
        await admin_start(message)

    args, kwargs = message.answer.await_args
    assert "не админ" in args[0].lower()
    assert "reply_markup" not in kwargs


async def test_button_admins_returns_invite_hint() -> None:
    message = MagicMock()
    message.answer = AsyncMock()
    await admin_menu_admins(message)
    text = message.answer.await_args.args[0]
    assert "/invite_admin" in text


async def test_button_settings_shows_theme_and_language() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=5)
    message.answer = AsyncMock()

    fake = {"theme": "dark", "language": "en", "notifications_enabled": True}
    with (
        patch(
            "presentations.telegram_admin.handlers.settings_menu.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.settings_menu.get_admin_settings",
            new=AsyncMock(return_value=fake),
        ),
    ):
        await admin_settings_button(message)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert "Настройки" in args[0]
    assert "Тема приложения: Тёмная" in args[0]
    assert "Язык: English" in args[0]
    assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)


async def test_settings_callback_updates_language() -> None:
    callback = MagicMock()
    callback.from_user = MagicMock(id=5)
    callback.data = "settings:language:ru"
    callback.message = None
    callback.answer = AsyncMock()

    fake = {"theme": "dark", "language": "ru", "notifications_enabled": True}
    with (
        patch(
            "presentations.telegram_admin.handlers.settings_menu.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.settings_menu.update_admin_settings",
            new=AsyncMock(return_value=fake),
        ) as update,
    ):
        await admin_settings_update(callback)

    update.assert_awaited_once_with(5, language="ru")
    callback.answer.assert_awaited_once_with("Сохранено")


async def test_button_questions_forwards_to_list() -> None:
    from presentations.telegram_admin.handlers.questions import admin_questions_list_button

    message = MagicMock()
    message.from_user = MagicMock(id=3)
    message.answer = AsyncMock()

    with (
        patch(
            "presentations.telegram_admin.handlers.questions.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.questions.list_questions",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await admin_questions_list_button(message)

    message.answer.assert_awaited()


async def test_button_add_question_forwards_to_picker() -> None:
    from presentations.telegram_admin.handlers.questions import admin_question_add_button

    message = MagicMock()
    message.from_user = MagicMock(id=4)
    message.answer = AsyncMock()
    state = MagicMock()

    with patch(
        "presentations.telegram_admin.handlers.questions.is_admin", new=AsyncMock(return_value=True)
    ):
        await admin_question_add_button(message, state)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.await_args
    assert "Как добавить" in args[0]
    assert kwargs.get("reply_markup") is not None
