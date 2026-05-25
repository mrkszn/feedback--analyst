import asyncio

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_common.fsm.states import AdminFlow
from db.client import get_supabase
from services.admin_auth import is_admin
from services.questions import (
    create_question,
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


@router.message(Command("questions"))
async def admin_questions_list(message: Message) -> None:
    if not await require_admin(message):
        return
    rows = await list_questions()
    if not rows:
        await message.answer("Пул пуст. /add_question чтобы создать.")
        return
    lines = []
    for r in rows:
        flag = "✓" if r.get("is_active") else "·"
        lines.append(f"{flag} {r['id']} [{r['metric_key']}, {r['expected_type']}] — {r['text']}")
    await message.answer("\n".join(lines))


@router.message(Command("add_question"))
async def admin_question_add(message: Message, state: FSMContext) -> None:
    if not await require_admin(message):
        return
    await state.set_state(AdminFlow.AWAITING_QUESTION_TEXT)
    await message.answer(
        "Отправьте текст вопроса в формате:\n"
        "<metric_key>|<expected_type>|<text>[|enum1,enum2,...]\n"
        "Пример: service_speed|number|Оцените скорость обслуживания от 1 до 5"
    )


@router.message(AdminFlow.AWAITING_QUESTION_TEXT)
async def admin_question_add_save(message: Message, state: FSMContext) -> None:
    user = message.from_user
    if user is None or not message.text:
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
