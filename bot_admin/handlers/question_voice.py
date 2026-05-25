"""Voice-driven advisor для генерации черновиков вопросов админом."""

from __future__ import annotations

import uuid
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.chat_action import ChatActionSender

from agent.nodes.synthesize_questions import (
    QuestionDraft,
    regenerate_single_question,
    synthesize_questions,
)
from bot_common.fsm.states import AdminFlow
from config import settings
from integrations.whisper import transcribe_voice
from services.admin_auth import is_admin
from services.questions import create_question
from utils.voice_download import download_voice_to_tmp

router = Router(name="admin_question_voice")


# --------------------------------------------------------------------------- #
# helpers


def _draft_text(d: dict[str, Any]) -> str:
    type_info = d["expected_type"]
    if type_info == "enum" and d.get("enum_values"):
        type_info = f"enum: {', '.join(d['enum_values'])}"
    return f"{d['text']}\n[{type_info}]\nmetric_key: {d['metric_key']}"


def _draft_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить", callback_data=f"draft:confirm:{draft_id}"
                ),
                InlineKeyboardButton(text="✏️ Правка", callback_data=f"draft:edit:{draft_id}"),
            ],
            [
                InlineKeyboardButton(text="🔄 Переген.", callback_data=f"draft:regen:{draft_id}"),
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"draft:cancel:{draft_id}"),
            ],
        ]
    )


def _parse_edit_input(text: str) -> tuple[str, str, list[str] | None]:
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 2:
        raise ValueError("Формат: metric_key|expected_type[|enum1,enum2,...]")
    metric_key, expected_type = parts[0], parts[1]
    if not metric_key:
        raise ValueError("metric_key не может быть пустым")
    if expected_type not in ("text", "number", "enum", "boolean"):
        raise ValueError("expected_type ∈ text|number|enum|boolean")
    enum_values: list[str] | None = None
    if expected_type == "enum":
        if len(parts) < 3:
            raise ValueError("Для enum нужны значения через запятую")
        enum_values = [v.strip() for v in parts[2].split(",") if v.strip()]
        if len(enum_values) < 2:
            raise ValueError("enum требует ≥2 значений")
    return metric_key, expected_type, enum_values


async def _get_draft(
    state: FSMContext, draft_id: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    data = await state.get_data()
    drafts: dict[str, dict[str, Any]] = data.get("drafts", {})
    return drafts, drafts.get(draft_id)


# --------------------------------------------------------------------------- #
# 1) start: callback addq:voice → AWAITING_QUESTION_COUNT


@router.callback_query(F.data == "addq:voice")
async def admin_handle_voice_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer()
        return
    if not await is_admin(callback.from_user.id):
        await callback.answer("Только для админов", show_alert=True)
        return
    await state.set_state(AdminFlow.AWAITING_QUESTION_COUNT)
    if isinstance(callback.message, Message):
        await callback.message.answer("Сколько вопросов сгенерировать? (1–10)")
    await callback.answer()


# --------------------------------------------------------------------------- #
# 2) count → AWAITING_QUESTION_VOICE


@router.message(AdminFlow.AWAITING_QUESTION_COUNT, F.text)
async def admin_handle_voice_count(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    try:
        n = int(text)
    except ValueError:
        await message.answer("Нужно число от 1 до 10.")
        return
    if not (1 <= n <= 10):
        await message.answer("Нужно число от 1 до 10.")
        return
    await state.update_data(voice_count=n)
    await state.set_state(AdminFlow.AWAITING_QUESTION_VOICE)
    await message.answer("Запишите голосовое: о чём хотите спрашивать гостей?")


# --------------------------------------------------------------------------- #
# 3) text in AWAITING_QUESTION_VOICE → reject


@router.message(AdminFlow.AWAITING_QUESTION_VOICE, F.text)
async def admin_handle_voice_text_reject(message: Message) -> None:
    await message.answer("Жду голосовое сообщение. Пришлите voice или /cancel.")


# --------------------------------------------------------------------------- #
# 4) voice intake → transcribe → synthesize → dispatch drafts


@router.message(AdminFlow.AWAITING_QUESTION_VOICE, F.voice)
async def admin_handle_voice_intake(message: Message, state: FSMContext) -> None:
    voice = message.voice
    bot = message.bot
    if voice is None or bot is None:
        return
    data = await state.get_data()
    count = int(data.get("voice_count", 1))

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
            await state.set_state(None)
            await message.answer(
                "Не удалось разобрать голос. Попробуйте ещё раз через /add_question."
            )
            return

        try:
            drafts = await synthesize_questions(transcript, count, settings.restaurant_context)
        except Exception as exc:
            await state.set_state(None)
            await message.answer(f"Ошибка генерации: {exc}")
            return

    if not drafts:
        await state.set_state(None)
        await message.answer("Не удалось сгенерировать ни одного валидного черновика.")
        return

    drafts_state: dict[str, dict[str, Any]] = {}
    for draft in drafts:
        draft_id = uuid.uuid4().hex[:8]
        d = draft.model_dump()
        sent = await message.answer(_draft_text(d), reply_markup=_draft_keyboard(draft_id))
        d["message_id"] = sent.message_id
        drafts_state[draft_id] = d

    await state.update_data(drafts=drafts_state, transcript=transcript, editing_draft_id=None)
    await state.set_state(None)

    if len(drafts) < count:
        await message.answer(f"Получилось {len(drafts)} из {count}.")


# --------------------------------------------------------------------------- #
# 5) callback confirm → create_question


@router.callback_query(F.data.startswith("draft:confirm:"))
async def admin_handle_draft_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.from_user is None or callback.data is None:
        await callback.answer()
        return
    draft_id = callback.data.split(":", 2)[2]
    drafts, draft = await _get_draft(state, draft_id)
    if draft is None:
        await callback.answer("Уже подтверждено или отменено.", show_alert=True)
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
    drafts.pop(draft_id, None)
    await state.update_data(drafts=drafts)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"✅ Создан вопрос {row['id']}\n{draft['text']}")
    await callback.answer()


# --------------------------------------------------------------------------- #
# 6) callback cancel


@router.callback_query(F.data.startswith("draft:cancel:"))
async def admin_handle_draft_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    draft_id = callback.data.split(":", 2)[2]
    drafts, draft = await _get_draft(state, draft_id)
    if draft is None:
        await callback.answer("Уже обработано.", show_alert=True)
        return
    drafts.pop(draft_id, None)
    await state.update_data(drafts=drafts)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"❌ Отменено\n{draft['text']}")
    await callback.answer()


# --------------------------------------------------------------------------- #
# 7) callback regen → new draft same id


@router.callback_query(F.data.startswith("draft:regen:"))
async def admin_handle_draft_regen(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    draft_id = callback.data.split(":", 2)[2]
    drafts, draft = await _get_draft(state, draft_id)
    if draft is None:
        await callback.answer("Уже обработано.", show_alert=True)
        return
    data = await state.get_data()
    transcript = data.get("transcript", "")
    current = QuestionDraft.model_validate({k: v for k, v in draft.items() if k != "message_id"})
    all_drafts = [
        QuestionDraft.model_validate({k: v for k, v in d.items() if k != "message_id"})
        for d in drafts.values()
    ]
    try:
        new_draft = await regenerate_single_question(
            transcript=transcript,
            current_draft=current,
            all_drafts=all_drafts,
            restaurant_context=settings.restaurant_context,
        )
    except Exception as exc:
        await callback.answer(f"Ошибка регенерации: {exc}", show_alert=True)
        return
    new_d = new_draft.model_dump()
    new_d["message_id"] = draft["message_id"]
    drafts[draft_id] = new_d
    await state.update_data(drafts=drafts)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(_draft_text(new_d), reply_markup=_draft_keyboard(draft_id))
    await callback.answer()


# --------------------------------------------------------------------------- #
# 8) callback edit → AWAITING_DRAFT_EDIT


@router.callback_query(F.data.startswith("draft:edit:"))
async def admin_handle_draft_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    draft_id = callback.data.split(":", 2)[2]
    _drafts, draft = await _get_draft(state, draft_id)
    if draft is None:
        await callback.answer("Уже обработано.", show_alert=True)
        return
    await state.update_data(editing_draft_id=draft_id)
    await state.set_state(AdminFlow.AWAITING_DRAFT_EDIT)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Введите новые параметры для:\n«{draft['text']}»\n\n"
            "Формат: metric_key|expected_type[|enum1,enum2,...]"
        )
    await callback.answer()


# --------------------------------------------------------------------------- #
# 9) edit input


@router.message(AdminFlow.AWAITING_DRAFT_EDIT, F.text)
async def admin_handle_draft_edit_input(message: Message, state: FSMContext) -> None:
    if not message.text:
        return
    data = await state.get_data()
    editing_id: str | None = data.get("editing_draft_id")
    drafts: dict[str, dict[str, Any]] = data.get("drafts", {})
    if editing_id is None or editing_id not in drafts:
        await state.set_state(None)
        await message.answer("Сессия редактирования утеряна.")
        return
    try:
        metric_key, expected_type, enum_values = _parse_edit_input(message.text)
    except ValueError as exc:
        await message.answer(f"Ошибка: {exc}")
        return  # остаёмся в AWAITING_DRAFT_EDIT

    draft = drafts[editing_id]
    draft["metric_key"] = metric_key
    draft["expected_type"] = expected_type
    draft["enum_values"] = enum_values
    drafts[editing_id] = draft
    await state.update_data(drafts=drafts, editing_draft_id=None)
    await state.set_state(None)

    bot = message.bot
    if bot is not None and "message_id" in draft:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=draft["message_id"],
                text=_draft_text(draft),
                reply_markup=_draft_keyboard(editing_id),
            )
        except Exception:
            pass
    await message.answer("Обновлено. Подтвердите кнопкой на сообщении выше.")
