from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_common.fsm.states import GuestFlow
from services.clients import create_or_get_client

router = Router(name="guest_start")


WELCOME = "Привет! 👋 Расскажи, как тебе у нас сегодня? Можешь голосом или текстом — как удобнее."


@router.message(CommandStart())
async def guest_start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await create_or_get_client(
        telegram_id=message.from_user.id,
        name=message.from_user.full_name,
    )
    await state.set_state(GuestFlow.AWAITING_FEEDBACK)
    await message.answer(WELCOME)
