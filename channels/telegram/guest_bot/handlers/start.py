from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from channels.telegram.common.fsm.states import GuestFlow
from channels.telegram.guest_bot.intent import looks_like_greeting
from core.services.clients import create_or_get_client
from core.services.re_entry import load_reentry_context, reentry_greeting

router = Router(name="guest_start")


WELCOME = "Привет! 👋 Расскажи, как прошёл заказ и доставка — голосом или текстом, как удобнее."


async def _greeting_for(telegram_id: int) -> str:
    """Personalized greeting for a returning client, else the static WELCOME.

    Returning-detection comes from the DB (via load_reentry_context), so it
    survives pod restarts that wipe the in-memory FSM store. Falls back to
    WELCOME for first-timers and on any lookup miss.
    """
    ctx = await load_reentry_context(telegram_id)
    return reentry_greeting(ctx) or WELCOME


@router.message(CommandStart())
async def guest_start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await create_or_get_client(
        telegram_id=message.from_user.id,
        name=message.from_user.full_name,
    )
    await state.set_state(GuestFlow.AWAITING_FEEDBACK)
    await message.answer(await _greeting_for(message.from_user.id))


# Catch any text/voice message from a user with NO FSM state set —
# they either skipped /start (e.g. opened the chat via a QR-deep-link
# and just started talking) OR they're returning after a /cancel or a
# pod restart wiped the in-memory store.
#
# Exactly ONE coherent bot reply per message:
#   - a bare greeting ("привет", "добрый день") → say hello (WELCOME) and
#     wait for the real feedback;
#   - substantive text / any voice → process it as feedback straight away,
#     WITHOUT a separate WELCOME (the dialogue's first turn already greets
#     and reacts, so WELCOME would be a redundant second message).
#
# The old code did both at once — greeted AND ran the message through the
# pipeline — so a plain "привет" got a WELCOME plus an out-of-nowhere
# follow-up question, and opened a nonsense session keyed on the greeting.
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

    # Local imports to avoid a top-level circular dep
    # (handlers.feedback already imports from this module's siblings).
    if message.text is not None:
        text = message.text.strip()
        if not text or looks_like_greeting(text):
            # Greeting branch only — personalize. The substantive-feedback
            # branch below deliberately skips this extra DB read so a real
            # review isn't delayed at intake.
            await message.answer(await _greeting_for(message.from_user.id))
            return
        from channels.telegram.guest_bot.handlers.feedback import _process_feedback

        await _process_feedback(message, state, raw_text=text, source="text")
        return

    if message.voice is not None:
        from channels.telegram.guest_bot.handlers.feedback import process_voice_message

        await process_voice_message(message, state)
        return
