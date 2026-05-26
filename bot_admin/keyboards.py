"""Reply-keyboard helpers for the admin bot.

The keyboard is persistent (not one-time): it sticks at the bottom of the
chat until the admin explicitly removes it, so navigation never relies on
remembering slash-commands. Button labels are matched verbatim by the
handlers in `bot_admin/handlers/` — keep them in sync if you change the
text here.

The second-row button is a **mode toggle**: it shows the OPPOSITE of the
admin's current mode, so clicking it switches modes. Free-text fallback
routes to the questions-CRUD agent (admin mode) or the analytics agent
(analytics mode) based on the stored FSM data.
"""

from typing import Literal

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

AdminMode = Literal["admin", "analytics"]

BTN_QUESTIONS = "📋 Вопросы"
BTN_ADD_QUESTION = "➕ Добавить"
BTN_ADMINS = "👥 Админы"
BTN_MODE_ANALYTICS = "📊 Режим: Аналитика"
BTN_MODE_ADMIN = "🛠 Режим: Админ"


def mode_toggle_label(current_mode: AdminMode) -> str:
    """Returns the label of the button that switches AWAY from current mode."""
    return BTN_MODE_ADMIN if current_mode == "analytics" else BTN_MODE_ANALYTICS


def main_menu_keyboard(*, current_mode: AdminMode = "admin") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_QUESTIONS), KeyboardButton(text=BTN_ADD_QUESTION)],
            [KeyboardButton(text=mode_toggle_label(current_mode)), KeyboardButton(text=BTN_ADMINS)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Команда или вопрос…",
    )
