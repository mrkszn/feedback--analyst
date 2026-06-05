from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from channels.telegram.common.fsm.states import GuestFlow
from core.services.clients import create_or_get_client

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


# Catch any text/voice message from a user with NO FSM state set —
# they either skipped /start (e.g. opened the chat via a QR-deep-link
# and just started talking) OR they're returning after a /cancel or a
# pod restart wiped the in-memory store. Greet them once, flip the
# state, and forward the message straight into the feedback pipeline so
# they don't have to repeat themselves.
#
# Has to live in the same Router as /start so it's registered BEFORE any
# state-scoped handler, but AFTER /start so the explicit command keeps
# precedence over the generic catch-all.
@router.message(StateFilter(None), F.text | F.voice)
async def guest_auto_greet(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await create_or_get_client(
        telegram_id=message.from_user.id,
        name=message.from_user.full_name,
    )
    await state.set_state(GuestFlow.AWAITING_FEEDBACK)
    await message.answer(WELCOME)

    # Local imports to avoid a top-level circular dep
    # (handlers.feedback already imports from this module's siblings).
    if message.text:
        from channels.telegram.guest_bot.handlers.feedback import _process_feedback

        text = message.text.strip()
        if text:
            await _process_feedback(message, state, raw_text=text, source="text")
        return

    if message.voice:
        from channels.telegram.guest_bot.handlers.feedback import process_voice_message

        await process_voice_message(message, state)
        return
