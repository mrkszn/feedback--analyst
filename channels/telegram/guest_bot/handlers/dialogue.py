"""Handler for the IN_DIALOGUE FSM phase.

After feedback intake (`AWAITING_FEEDBACK`) the guest enters `IN_DIALOGUE` for
a 3-5 turn empathic conversation driven by `continue_dialogue`. Once the LLM
(or the hard cap) decides it's time, we either offer the structured survey
(transition to `AWAITING_SURVEY_CONSENT` with inline buttons) or — if the
question pool is empty — finalize the session immediately.

Invariant: this handler writes ONLY to `session_messages` (free conversation).
Metric extraction lives in the `IN_INTERVIEW` handlers in `feedback.py`.
"""

from __future__ import annotations

import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.chat_action import ChatActionSender

from channels.telegram.common.fsm.states import GuestFlow
from channels.telegram.guest_bot.handlers.feedback import _finalize_session
from config import settings
from core.agent.nodes.analyze import FeedbackSummary
from core.agent.nodes.dialogue import continue_dialogue
from core.integrations.whisper import transcribe_voice
from core.services.sessions import append_session_message
from core.tools.questions import get_active_questions
from core.utils.voice_download import download_voice_to_tmp

router = Router(name="guest_dialogue")


async def _process_dialogue_turn(
    message: Message,
    state: FSMContext,
    user_text: str,
) -> None:
    """Shared core for text + voice handlers in IN_DIALOGUE."""
    bot = message.bot
    if bot is None or not user_text.strip():
        return

    async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
        data = await state.get_data()
        session_id = data["session_id"]
        history: list[dict[str, str]] = list(data.get("history", []))
        turn_count: int = int(data.get("turn_count", 0))
        feedback_summary_data: dict = data["feedback_summary"]

        # Persist user message to session_messages (vector-invariant: free convo only).
        await append_session_message(session_id, "user", user_text)
        history.append({"role": "user", "content": user_text})

        new_turn_count = turn_count + 1
        feedback_summary_json = json.dumps(feedback_summary_data, ensure_ascii=False)

        turn = await continue_dialogue(
            feedback_summary=feedback_summary_json,
            history=history,
            restaurant_context=settings.restaurant_context,
            turn_count=new_turn_count,
            max_turns=5,
        )

        await append_session_message(session_id, "bot", turn.bot_reply)
        history.append({"role": "bot", "content": turn.bot_reply})

        await state.update_data(history=history, turn_count=new_turn_count)

    if turn.transition == "offer_survey":
        await _emit_survey_offer_or_finalize(
            message,
            state,
            bot_reply=turn.bot_reply,
            feedback_summary_data=feedback_summary_data,
        )
    else:
        await message.answer(turn.bot_reply)


@router.message(GuestFlow.IN_DIALOGUE, F.text)
async def guest_dialogue_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or message.bot is None:
        return
    await _process_dialogue_turn(message, state, text)


@router.message(GuestFlow.IN_DIALOGUE, F.voice)
async def guest_dialogue_voice(message: Message, state: FSMContext) -> None:
    voice = message.voice
    bot = message.bot
    if voice is None or bot is None:
        return

    async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
        path = await download_voice_to_tmp(voice.file_id, bot)
        try:
            transcript = await transcribe_voice(path)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    if not transcript.strip():
        await message.answer("Не разобрал голос. Можешь повторить или написать текстом?")
        return

    await _process_dialogue_turn(message, state, transcript)


async def _emit_survey_offer_or_finalize(
    message: Message,
    state: FSMContext,
    *,
    bot_reply: str,
    feedback_summary_data: dict,
) -> None:
    """End-of-dialogue branch: offer survey if pool non-empty, else finalize silently."""
    # Send the empathic last line first so it isn't swallowed by the offer text.
    await message.answer(bot_reply)

    pool = await get_active_questions()

    if pool:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="💛 Давайте", callback_data="survey:yes"),
                    InlineKeyboardButton(text="Нет, спасибо", callback_data="survey:no"),
                ]
            ]
        )
        await message.answer(
            "Спасибо за разговор! 🙏 У сервиса есть пара коротких вопросов "
            "специально под твой отзыв — займут минутку. За ответы я подарю "
            "скидку 🎁 на следующий заказ. Хочешь попробовать?",
            reply_markup=keyboard,
        )
        await state.set_state(GuestFlow.AWAITING_SURVEY_CONSENT)
        return

    # Pool empty — finalize silently (we send our own goodbye to avoid the
    # default one in _finalize_session).
    await message.answer("Спасибо большое за рассказ! 🙏 Передам владельцу. Хорошего дня! ☀️")
    await state.update_data(finalize_message_sent=True)
    summary = FeedbackSummary.model_validate(feedback_summary_data)
    await _finalize_session(message, state, summary=summary, answers=[])
