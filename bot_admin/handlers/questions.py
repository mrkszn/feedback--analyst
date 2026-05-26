import asyncio

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot_admin.keyboards import BTN_ADD_QUESTION, BTN_QUESTIONS
from bot_common.fsm.states import AdminFlow
from db.client import get_supabase
from services.admin_auth import is_admin
from services.questions import (
    create_question,
    deactivate_all_questions,
    delete_question,
    list_questions,
    update_question,
)

router = Router(name="admin_questions")


async def require_admin(message: Message) -> bool:
    user = message.from_user
    if user is None:
        return False
    if not await is_admin(user.id):
        await message.answer("Доступ только для админов. /claim — для первой регистрации.")
        return False
    return True


async def _require_admin_cb(callback: CallbackQuery) -> bool:
    if callback.from_user is None or not await is_admin(callback.from_user.id):
        await callback.answer("Только для админов", show_alert=True)
        return False
    return True


@router.message(F.text == BTN_QUESTIONS)
async def admin_questions_list_button(message: Message) -> None:
    await admin_questions_list(message)


@router.message(F.text == BTN_ADD_QUESTION)
async def admin_question_add_button(message: Message, state: FSMContext) -> None:
    await admin_question_add(message, state)


@router.message(Command("questions"))
async def admin_questions_list(message: Message) -> None:
    if not await require_admin(message):
        return
    rows = await list_questions(active_only=True)
    if not rows:
        await message.answer("Пул пуст. /add_question чтобы создать.")
        return

    await message.answer(f"📋 Активные вопросы ({len(rows)}):")
    for idx, r in enumerate(rows, 1):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Изменить", callback_data=f"qedit:{r['id']}"),
                    InlineKeyboardButton(text="🗑 Удалить", callback_data=f"qdel:{r['id']}"),
                ]
            ]
        )
        await message.answer(
            f"{idx}. {r['text']} ({r['expected_type']})",
            reply_markup=kb,
        )

    footer_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🗑 Удалить все", callback_data="qdelall")]]
    )
    await message.answer("Действия со всем пулом:", reply_markup=footer_kb)


_ADD_QUESTION_TEXT_PROMPT = (
    "Отправьте текст вопроса в формате:\n"
    "<metric_key>|<expected_type>|<text>[|enum1,enum2,...]\n"
    "Пример: service_speed|number|Оцените скорость обслуживания от 1 до 5"
)


@router.message(Command("add_question"))
async def admin_question_add(message: Message, state: FSMContext) -> None:
    if not await require_admin(message):
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Текстом", callback_data="addq:text"),
                InlineKeyboardButton(text="Голосом", callback_data="addq:voice"),
            ],
            [
                InlineKeyboardButton(text="💬 В диалоге", callback_data="addq:dialog"),
            ],
        ]
    )
    await message.answer("Как добавить?", reply_markup=keyboard)


@router.callback_query(F.data == "addq:text")
async def admin_question_add_text(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _require_admin_cb(callback):
        return
    await state.set_state(AdminFlow.AWAITING_QUESTION_TEXT)
    if isinstance(callback.message, Message):
        await callback.message.answer(_ADD_QUESTION_TEXT_PROMPT)
    await callback.answer()


def _natural_language_exit_check(text: str) -> bool:
    """Heuristic: does this look like a free-form message, not the structured
    metric_key|expected_type|text format?

    Triggered to offer the admin a cancel/continue hatch out of a sticky
    FSM state (live-test 2026-05-25 issue #6 — typing «как у тебя дела?»
    inside AWAITING_QUESTION_TEXT used to dead-end on a format error).
    """
    s = text.strip()
    if not s or "|" in s:
        return False
    # Single token (`food`, `service_speed`) is more likely an aborted
    # attempt at the structured format than NL — let the existing parser
    # report the format error.
    return len(s.split()) >= 2


def _exit_hatch_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✖️ Отмена", callback_data="fsmexit:cancel"),
                InlineKeyboardButton(text="↩️ Продолжить", callback_data="fsmexit:keep"),
            ]
        ]
    )


@router.message(AdminFlow.AWAITING_QUESTION_TEXT)
async def admin_question_add_save(message: Message, state: FSMContext) -> None:
    user = message.from_user
    if user is None or not message.text:
        return

    if _natural_language_exit_check(message.text):
        await state.update_data(_pending_nl=message.text)
        await message.answer(
            "Похоже, это обычное сообщение, а не формат "
            "metric_key|expected_type|text. Выйти из режима «новый вопрос»?",
            reply_markup=_exit_hatch_keyboard(),
        )
        return

    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) < 3:
        await message.answer("Нужно минимум 3 поля: metric_key|expected_type|text")
        return
    metric_key, expected_type, text = parts[0], parts[1], parts[2]
    enum_values = None
    if len(parts) >= 4 and expected_type == "enum":
        enum_values = [v.strip() for v in parts[3].split(",") if v.strip()]
    try:
        row = await create_question(
            text=text,
            metric_key=metric_key,
            expected_type=expected_type,  # type: ignore[arg-type]
            enum_values=enum_values,
            created_by=user.id,
        )
    except ValueError as e:
        await message.answer(f"Ошибка: {e}")
        return
    await state.clear()
    await message.answer(f"Создан вопрос {row['id']}")


@router.callback_query(F.data.startswith("qedit:"))
async def admin_question_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _require_admin_cb(callback):
        return
    qid = (callback.data or "").removeprefix("qedit:")
    await state.set_state(AdminFlow.AWAITING_QUESTION_EDIT)
    await state.update_data(edit_qid=qid)
    if isinstance(callback.message, Message):
        await callback.message.answer("✏️ Введите новый текст вопроса:")
    await callback.answer()


@router.message(AdminFlow.AWAITING_QUESTION_EDIT)
async def admin_question_edit_save(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    data = await state.get_data()
    qid = data.get("edit_qid")
    if not qid:
        await state.clear()
        await message.answer("Сессия редактирования утеряна, начните заново.")
        return
    try:
        row = await update_question(qid, text=message.text.strip())
    except (ValueError, LookupError) as e:
        await message.answer(f"Ошибка: {e}")
        return
    await state.clear()
    await message.answer(f"✏️ Обновлено: {row.get('text', message.text.strip())}")


@router.callback_query(F.data.startswith("qdel:"))
async def admin_question_delete_confirm(callback: CallbackQuery) -> None:
    if not await _require_admin_cb(callback):
        return
    qid = (callback.data or "").removeprefix("qdel:")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"qdelyes:{qid}"),
                InlineKeyboardButton(text="✖️ Отмена", callback_data="qdelno"),
            ]
        ]
    )
    if isinstance(callback.message, Message):
        await callback.message.answer("Удалить этот вопрос?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("qdelyes:"))
async def admin_question_delete_apply(callback: CallbackQuery) -> None:
    if not await _require_admin_cb(callback):
        return
    qid = (callback.data or "").removeprefix("qdelyes:")
    try:
        await delete_question(qid)
    except LookupError:
        if isinstance(callback.message, Message):
            await callback.message.answer("Вопрос уже удалён.")
        await callback.answer()
        return
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text("🗑 Удалено.")
        except Exception:
            await callback.message.answer("🗑 Удалено.")
    await callback.answer()


@router.callback_query(F.data == "qdelno")
async def admin_question_delete_cancel(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text("Отменено.")
        except Exception:
            await callback.message.answer("Отменено.")
    await callback.answer()


# Удаление всего пула — confirmation + service call в commit #3.
# В этом коммите делаем кнопку и confirmation; финальный delete-all — placeholder.
@router.callback_query(F.data == "qdelall")
async def admin_question_delete_all_confirm(callback: CallbackQuery) -> None:
    if not await _require_admin_cb(callback):
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="qdelallyes"),
                InlineKeyboardButton(text="✖️ Отмена", callback_data="qdelno"),
            ]
        ]
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Удалить ВСЕ активные вопросы? Это скроет их у гостей (история сохранится).",
            reply_markup=kb,
        )
    await callback.answer()


@router.callback_query(F.data == "qdelallyes")
async def admin_question_delete_all_apply(callback: CallbackQuery) -> None:
    if not await _require_admin_cb(callback):
        return
    count = await deactivate_all_questions()
    if isinstance(callback.message, Message):
        if count == 0:
            text = "Активных вопросов нет — нечего скрывать."
        else:
            text = f"🗑 Скрыто вопросов: {count}. История сохранена."
        try:
            await callback.message.edit_text(text)
        except Exception:
            await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "fsmexit:cancel")
async def admin_fsm_exit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _require_admin_cb(callback):
        return
    data = await state.get_data()
    pending: str = data.get("_pending_nl") or ""
    await state.clear()
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(
                "Хорошо, вышли из режима. Пересылаю сообщение ассистенту."
            )
        except Exception:
            pass
        if pending:
            # Lazy import to avoid an import cycle (admin_agent → questions
            # would close the loop via require_admin).
            from bot_admin.handlers.admin_agent import run_admin_agent

            reply = await run_admin_agent(pending)
            await callback.message.answer(reply)
    await callback.answer()


@router.callback_query(F.data == "fsmexit:keep")
async def admin_fsm_exit_keep(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _require_admin_cb(callback):
        return
    await state.update_data(_pending_nl=None)
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text("Ок, остаёмся в режиме добавления вопроса.")
        except Exception:
            pass
        await callback.message.answer(_ADD_QUESTION_TEXT_PROMPT)
    await callback.answer()


@router.message(Command("edit_question"))
async def admin_question_edit(message: Message, command: CommandObject) -> None:
    if not await require_admin(message):
        return
    args = (command.args or "").strip()
    if "|" not in args:
        await message.answer("Использование: /edit_question <id>|<new_text>[|on|off]")
        return
    qid, _, rest = args.partition("|")
    parts = [p.strip() for p in rest.split("|")]
    new_text = parts[0] or None
    is_active: bool | None = None
    if len(parts) > 1:
        flag = parts[1].lower()
        if flag == "on":
            is_active = True
        elif flag == "off":
            is_active = False
    try:
        row = await update_question(qid.strip(), text=new_text, is_active=is_active)
    except (ValueError, LookupError) as e:
        await message.answer(f"Ошибка: {e}")
        return
    await message.answer(f"Обновлено: {row['id']}")


@router.message(Command("delete_question"))
async def admin_question_delete(message: Message, command: CommandObject) -> None:
    if not await require_admin(message):
        return
    qid = (command.args or "").strip()
    if not qid:
        await message.answer("Использование: /delete_question <id>")
        return
    try:
        await delete_question(qid)
    except LookupError as e:
        await message.answer(f"Ошибка: {e}")
        return
    await message.answer(f"Деактивирован: {qid}")


@router.message(Command("invite_admin"))
async def admin_invite_admin(message: Message, command: CommandObject) -> None:
    if not await require_admin(message):
        return
    arg = (command.args or "").strip()
    try:
        target_id = int(arg)
    except ValueError:
        await message.answer("Использование: /invite_admin <telegram_id>")
        return
    inviter = message.from_user.id if message.from_user else None
    db = get_supabase()
    try:
        await asyncio.to_thread(
            lambda: (
                db.table("admin_users")
                .insert({"telegram_id": target_id, "invited_by": inviter})
                .execute()
            )
        )
    except Exception as exc:
        if "23505" in str(exc):
            await message.answer("Этот telegram_id уже админ.")
            return
        await message.answer(f"Ошибка БД: {exc}")
        return
    await message.answer(f"Готово: {target_id} добавлен в admin_users.")
