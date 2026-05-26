"""In-dialog AI-assisted question creation (third mode of /add_question).

Flow:
1. Admin clicks [💬 В диалоге] on the /add_question picker → state set to
   AWAITING_NL_DESCRIPTION.
2. Admin types a natural description ("спрашивай гостей, понравилось ли
   как готовят").
3. `draft_question_from_nl` returns a single QuestionDraft. We show it
   with [✅ Создать] [✏️ Поправить] [✖️ Отмена].
4. "Создать" → create_question + confirmation.
   "Поправить" → re-enter AWAITING_NL_DESCRIPTION (admin retypes).
   "Отмена" → clear state.

Voice input intentionally NOT wired here — admins can still use the
existing "Голосом" path which generates multiple drafts at once.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.chat_action import ChatActionSender

from agent.nodes.admin_assistant import draft_question_from_nl
from bot_common.fsm.states import AdminFlow
from config import settings
from services.admin_auth import is_admin
from services.questions import create_question

router = Router(name="admin_question_dialog")


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data="nldraft:yes"),
                InlineKeyboardButton(text="✏️ Поправить", callback_data="nldraft:edit"),
                InlineKeyboardButton(text="✖️ Отмена", callback_data="nldraft:no"),
            ]
        ]
    )


def _draft_preview(draft: dict) -> str:
    type_info = draft["expected_type"]
    if type_info == "enum" and draft.get("enum_values"):
        type_info = f"enum: {', '.join(draft['enum_values'])}"
    return (
        f"📝 Черновик вопроса:\n\n"
        f"«{draft['text']}»\n\n"
        f"тип: {type_info}\n"
        f"metric_key: {draft['metric_key']}"
    )


@router.callback_query(F.data == "addq:dialog")
async def admin_question_dialog_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not await is_admin(callback.from_user.id):
        await callback.answer("Только для админов", show_alert=True)
        return
    await state.set_state(AdminFlow.AWAITING_NL_DESCRIPTION)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Опишите вопрос своими словами — я подберу формулировку и тип.\n"
            "Например: «спрашивай, понравилось ли как готовят»."
        )
    await callback.answer()


@router.message(AdminFlow.AWAITING_NL_DESCRIPTION, F.text)
async def admin_question_dialog_describe(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    bot = message.bot
    description = message.text.strip()

    async def _do_draft() -> None:
        try:
            draft = await draft_question_from_nl(
                description,
                restaurant_context=settings.restaurant_context,
            )
        except ValueError as exc:
            await message.answer(f"Не получилось распарсить: {exc}. Попробуйте ещё раз.")
            return
        except Exception as exc:
            await message.answer(f"Ошибка при обращении к модели: {exc}")
            return

        d = draft.model_dump()
        await state.set_state(AdminFlow.AWAITING_NL_CONFIRMATION)
        await state.update_data(nl_draft=d)
        await message.answer(_draft_preview(d), reply_markup=_confirm_keyboard())

    if bot is not None:
        async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
            await _do_draft()
    else:
        await _do_draft()


@router.callback_query(F.data == "nldraft:yes")
async def admin_question_dialog_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not await is_admin(callback.from_user.id):
        await callback.answer("Только для админов", show_alert=True)
        return
    data = await state.get_data()
    draft = data.get("nl_draft")
    if not draft:
        await callback.answer("Черновик утерян — начните заново.", show_alert=True)
        await state.clear()
        return
    try:
        row = await create_question(
            text=draft["text"],
            metric_key=draft["metric_key"],
            expected_type=draft["expected_type"],
            enum_values=draft.get("enum_values"),
            created_by=callback.from_user.id,
        )
    except ValueError as exc:
        await callback.answer(f"Ошибка: {exc}", show_alert=True)
        return
    await state.clear()
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(
                f"✅ Создан вопрос:\n«{row.get('text', draft['text'])}»"
            )
        except Exception:
            await callback.message.answer(f"✅ Создан вопрос:\n«{row.get('text', draft['text'])}»")
    await callback.answer()


@router.callback_query(F.data == "nldraft:edit")
async def admin_question_dialog_retry(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not await is_admin(callback.from_user.id):
        await callback.answer("Только для админов", show_alert=True)
        return
    await state.set_state(AdminFlow.AWAITING_NL_DESCRIPTION)
    await state.update_data(nl_draft=None)
    if isinstance(callback.message, Message):
        await callback.message.answer("Окей, опишите ещё раз — попробую переформулировать.")
    await callback.answer()


@router.callback_query(F.data == "nldraft:no")
async def admin_question_dialog_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text("Отменено.")
        except Exception:
            await callback.message.answer("Отменено.")
    await callback.answer()
