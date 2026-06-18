"""Reply-keyboard helpers for the admin bot.

The keyboard is persistent (not one-time): it sticks at the bottom of the
chat until the admin explicitly removes it, so navigation never relies on
remembering slash-commands. Button labels are matched verbatim by the
handlers in `bot_admin/handlers/` — keep them in sync if you change the
text here.
"""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_QUESTIONS = "📋 Вопросы"
BTN_ADD_QUESTION = "➕ Добавить"
BTN_ADMINS = "👥 Админы"
BTN_STATISTICS = "📊 Статистика"
BTN_SETTINGS = "⚙️ Настройки"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_QUESTIONS), KeyboardButton(text=BTN_ADD_QUESTION)],
            [KeyboardButton(text=BTN_STATISTICS), KeyboardButton(text=BTN_ADMINS)],
            [KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Команда или вопрос…",
    )
