from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.chat_action import ChatActionSender

from channels.telegram.common.fsm.states import GuestFlow
from channels.telegram.guest_bot.handlers.feedback import _ask_next_question, _finalize_session
from core.agent.nodes.analyze import FeedbackSummary
from core.agent.nodes.select import select_adaptive_questions
from core.tools.questions import get_active_questions

router = Router(name="guest_survey_consent")


@router.callback_query(GuestFlow.AWAITING_SURVEY_CONSENT, F.data == "survey:yes")
async def consent_yes(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.bot is None:
        return

    # Снимаем клавиатуру, чтобы не было повторных кликов.
    try:
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
    except Exception:
        pass

    await callback.answer("Отлично! 💛")

    async with ChatActionSender.typing(chat_id=callback.message.chat.id, bot=callback.bot):
        data = await state.get_data()
        summary_dict = data.get("feedback_summary") or data["summary"]
        summary = FeedbackSummary.model_validate(summary_dict)

        pool = await get_active_questions()

        if not pool:
            # Defensive: dialogue handler should have routed away, но админ мог
            # удалить все вопросы пока шёл диалог.
            await callback.message.answer("Кажется, вопросов больше нет. Спасибо за разговор! 🙏")
            await state.update_data(finalize_message_sent=True)
            await _finalize_session(
                callback.message,  # type: ignore[arg-type]
                state,
                summary=summary,
                answers=[],
            )
            return

        selected = await select_adaptive_questions(summary, pool)

        if not selected.question_ids:
            # Селектор ничего не выбрал — интервью не запускаем.
            await callback.message.answer("Кажется, вопросов больше нет. Спасибо за разговор! 🙏")
            await state.update_data(finalize_message_sent=True)
            await _finalize_session(
                callback.message,  # type: ignore[arg-type]
                state,
                summary=summary,
                answers=[],
            )
            return

        await state.update_data(
            question_ids=selected.question_ids,
            question_index=0,
            questions_map={str(q["id"]): q for q in pool},
            summary=summary.model_dump(),
            feedback_summary=summary.model_dump(),
            answers=[],
        )
        await state.set_state(GuestFlow.IN_INTERVIEW)
        await _ask_next_question(callback.message, state)  # type: ignore[arg-type]


@router.callback_query(GuestFlow.AWAITING_SURVEY_CONSENT, F.data == "survey:no")
async def consent_no(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
    except Exception:
        pass

    await callback.answer("Спасибо!")

    bot = callback.bot
    if bot is None:
        return

    async with ChatActionSender.typing(chat_id=callback.message.chat.id, bot=bot):
        await callback.message.answer(
            "Спасибо большое за рассказ! 🙏 Передам владельцу. Хорошего дня! ☀️"
        )
        data = await state.get_data()
        summary_dict = data.get("feedback_summary") or data["summary"]
        summary = FeedbackSummary.model_validate(summary_dict)

        # Suppress duplicate goodbye в _finalize_session.
        await state.update_data(finalize_message_sent=True)
        await _finalize_session(
            callback.message,  # type: ignore[arg-type]
            state,
            summary=summary,
            answers=[],
        )
