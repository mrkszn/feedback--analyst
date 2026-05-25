from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from services.admin_auth import claim_admin, is_admin

router = Router(name="admin_auth")


CLAIM_HINT = (
    "Вы не админ. Если вы владелец и у вас есть bootstrap-токен, отправьте "
    "`/claim <token>` (выполняется один раз)."
)


@router.message(Command("claim"))
async def admin_claim(message: Message, command: CommandObject) -> None:
    user = message.from_user
    if user is None:
        return
    token = (command.args or "").strip()
    if not token:
        await message.answer("Использование: /claim <bootstrap-token>")
        return
    ok = await claim_admin(telegram_id=user.id, token=token, name=user.full_name)
    if ok:
        await message.answer("Готово, вы добавлены в admin_users.")
    else:
        await message.answer(
            "Не удалось. Возможно, токен неверен или администратор уже зарегистрирован."
        )


@router.message(CommandStart())
async def admin_start(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    if not await is_admin(user.id):
        await message.answer(CLAIM_HINT)
        return
    await message.answer(
        "Привет, админ. Доступные команды:\n"
        "/questions — список вопросов\n"
        "/add_question — создать вопрос\n"
        "/edit_question <id> — изменить вопрос\n"
        "/delete_question <id> — деактивировать вопрос\n"
        "/invite_admin <telegram_id> — добавить нового админа"
    )
