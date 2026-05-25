from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from bot_admin.handlers.questions import require_admin

router = Router(name="admin_fallback")

_FALLBACK_TEXT = (
    "Я понимаю только команды. Доступные:\n"
    "/questions — список\n"
    "/add_question — создать (теперь с голосом)\n"
    "/edit_question <id> — изменить\n"
    "/delete_question <id> — деактивировать\n"
    "/invite_admin <telegram_id> — добавить админа"
)


@router.message(StateFilter(None))
async def admin_handle_freetext_fallback(message: Message) -> None:
    if not await require_admin(message):
        return
    await message.answer(_FALLBACK_TEXT)
