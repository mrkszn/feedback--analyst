"""Mode toggle for admin chat: questions-CRUD ↔ analytics.

The admin can switch the meaning of free-form text in this chat between two
agents:

- `admin` (default) — text goes to the questions-CRUD agent (list / create /
  delete / find from the questions pool). This is the Phase 2A.6 admin agent.
- `analytics` — text goes to the analytics agent (`agent.nodes.admin_ask`),
  which has tool-access to the live feedback data via `services.analytics`.

The current mode is stored as `admin_mode` in FSM data (MemoryStorage,
volatile across bot restarts — acceptable for a UX iteration). Slash
commands like `/insights` and `/ask` keep working regardless of mode.
"""

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_admin.handlers.questions import require_admin
from bot_admin.keyboards import (
    BTN_MODE_ADMIN,
    BTN_MODE_ANALYTICS,
    main_menu_keyboard,
)

router = Router(name="admin_mode")


SWITCH_TO_ANALYTICS_HINT = (
    "📊 Режим аналитики включён.\n\n"
    "Пиши свободным текстом — отвечу по реальным данным из базы. Например:\n"
    "• какие топ-3 жалобы за неделю?\n"
    "• сколько сессий было за последние 14 дней?\n"
    "• что говорят про доставку?\n\n"
    "Прямые команды тоже работают: /insights, /topics, /metric <key>, "
    "/find <текст>, /clients <id>."
)

SWITCH_TO_ADMIN_HINT = (
    "🛠 Админ-режим включён.\n\n"
    "Свободный текст теперь идёт помощнику по пулу вопросов. Например:\n"
    "• покажи активные вопросы\n"
    "• добавь вопрос про парковку\n"
    "• удали вопрос про скорость\n\n"
    "Аналитика всё ещё доступна через /ask, /insights, /topics, /find, /clients."
)


@router.message(StateFilter(None), F.text == BTN_MODE_ANALYTICS)
async def switch_to_analytics(message: Message, state: FSMContext) -> None:
    if not await require_admin(message):
        return
    await state.update_data(admin_mode="analytics")
    await message.answer(
        SWITCH_TO_ANALYTICS_HINT,
        reply_markup=main_menu_keyboard(current_mode="analytics"),
    )


@router.message(StateFilter(None), F.text == BTN_MODE_ADMIN)
async def switch_to_admin(message: Message, state: FSMContext) -> None:
    if not await require_admin(message):
        return
    await state.update_data(admin_mode="admin")
    await message.answer(
        SWITCH_TO_ADMIN_HINT,
        reply_markup=main_menu_keyboard(current_mode="admin"),
    )
