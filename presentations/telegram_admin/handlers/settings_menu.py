from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.services.admin_auth import is_admin
from core.services.settings import get_admin_settings, update_admin_settings
from presentations.telegram_admin.keyboards import BTN_SETTINGS

router = Router(name="admin_settings")

THEME_LABELS = {
    "system": "Системная",
    "light": "Светлая",
    "dark": "Тёмная",
}

LANGUAGE_LABELS = {
    "ru": "Русский",
    "en": "English",
}


async def _require_admin_message(message: Message) -> bool:
    user = message.from_user
    if user is None:
        return False
    if not await is_admin(user.id):
        await message.answer("Доступ только для админов. /claim — для первой регистрации.")
        return False
    return True


async def _require_admin_callback(callback: CallbackQuery) -> bool:
    user = callback.from_user
    if user is None or not await is_admin(user.id):
        await callback.answer("Только для админов", show_alert=True)
        return False
    return True


def _selected(label: str, selected: bool) -> str:
    return f"✓ {label}" if selected else label


def settings_keyboard(settings: dict[str, Any]) -> InlineKeyboardMarkup:
    theme = settings["theme"]
    language = settings["language"]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_selected(THEME_LABELS["system"], theme == "system"),
                    callback_data="settings:theme:system",
                ),
                InlineKeyboardButton(
                    text=_selected(THEME_LABELS["light"], theme == "light"),
                    callback_data="settings:theme:light",
                ),
                InlineKeyboardButton(
                    text=_selected(THEME_LABELS["dark"], theme == "dark"),
                    callback_data="settings:theme:dark",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=_selected(LANGUAGE_LABELS["ru"], language == "ru"),
                    callback_data="settings:language:ru",
                ),
                InlineKeyboardButton(
                    text=_selected(LANGUAGE_LABELS["en"], language == "en"),
                    callback_data="settings:language:en",
                ),
            ],
        ]
    )


def settings_text(settings: dict[str, Any]) -> str:
    theme = THEME_LABELS.get(settings["theme"], settings["theme"])
    language = LANGUAGE_LABELS.get(settings["language"], settings["language"])
    return (
        f"⚙️ Настройки\n\nТема приложения: {theme}\nЯзык: {language}\n\nВыберите новый вариант ниже."
    )


@router.message(F.text == BTN_SETTINGS)
async def admin_settings_button(message: Message) -> None:
    await admin_settings(message)


@router.message(Command("settings"))
async def admin_settings(message: Message) -> None:
    if not await _require_admin_message(message):
        return
    user = message.from_user
    if user is None:
        return
    settings = await get_admin_settings(user.id)
    await message.answer(settings_text(settings), reply_markup=settings_keyboard(settings))


@router.callback_query(F.data.startswith("settings:"))
async def admin_settings_update(callback: CallbackQuery) -> None:
    if not await _require_admin_callback(callback):
        return
    user = callback.from_user
    if user is None:
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Не понял настройку", show_alert=True)
        return

    _, field, value = parts
    try:
        if field == "theme":
            settings = await update_admin_settings(user.id, theme=value)
        elif field == "language":
            settings = await update_admin_settings(user.id, language=value)
        else:
            await callback.answer("Не понял настройку", show_alert=True)
            return
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            settings_text(settings),
            reply_markup=settings_keyboard(settings),
        )
    await callback.answer("Сохранено")
