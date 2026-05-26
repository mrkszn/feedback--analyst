"""Tests for the admin mode toggle (📊 Аналитика ↔ 🛠 Админ)."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import ReplyKeyboardMarkup

from bot_admin.handlers.mode import switch_to_admin, switch_to_analytics
from bot_admin.keyboards import BTN_MODE_ADMIN, BTN_MODE_ANALYTICS


async def test_switch_to_analytics_updates_state_and_shows_hint() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=42)
    message.text = BTN_MODE_ANALYTICS
    message.answer = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()

    with patch("bot_admin.handlers.mode.require_admin", new=AsyncMock(return_value=True)):
        await switch_to_analytics(message, state)

    state.update_data.assert_awaited_once_with(admin_mode="analytics")
    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert "Режим аналитики" in text
    kb = message.answer.await_args.kwargs["reply_markup"]
    assert isinstance(kb, ReplyKeyboardMarkup)
    # In analytics mode the toggle button should now offer switching back to admin.
    labels = [b.text for row in kb.keyboard for b in row]
    assert BTN_MODE_ADMIN in labels
    assert BTN_MODE_ANALYTICS not in labels


async def test_switch_to_admin_updates_state_and_shows_hint() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=42)
    message.text = BTN_MODE_ADMIN
    message.answer = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()

    with patch("bot_admin.handlers.mode.require_admin", new=AsyncMock(return_value=True)):
        await switch_to_admin(message, state)

    state.update_data.assert_awaited_once_with(admin_mode="admin")
    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert "Админ-режим" in text
    kb = message.answer.await_args.kwargs["reply_markup"]
    labels = [b.text for row in kb.keyboard for b in row]
    assert BTN_MODE_ANALYTICS in labels
    assert BTN_MODE_ADMIN not in labels


async def test_switch_to_analytics_gated_for_non_admin() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=99)
    message.text = BTN_MODE_ANALYTICS
    message.answer = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()

    with patch("bot_admin.handlers.mode.require_admin", new=AsyncMock(return_value=False)):
        await switch_to_analytics(message, state)

    state.update_data.assert_not_awaited()
    message.answer.assert_not_awaited()
