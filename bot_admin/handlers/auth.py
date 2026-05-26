from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from bot_admin.keyboards import BTN_ADMINS, BTN_ASK, main_menu_keyboard
from services.admin_auth import claim_admin, is_admin

router = Router(name="admin_auth")


CLAIM_HINT = (
    "Вы не админ. Если вы владелец и у вас есть bootstrap-токен, отправьте "
    "`/claim <token>` (выполняется один раз)."
)


GREETING = (
    "Здравствуйте! Рад снова видеть. 👋\n\n"
    "Снизу — быстрый доступ к основному:\n"
    "📋 Вопросы — посмотреть пул\n"
    "➕ Добавить — создать новый вопрос\n"
    "💬 Спросить — задать вопрос в свободной форме\n"
    "👥 Админы — посмотреть команду\n\n"
    "Слэш-команды (/questions, /add_question, /invite_admin …) тоже работают — "
    "что удобнее."
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
        await message.answer(
            "Готово, вы добавлены в admin_users.",
            reply_markup=main_menu_keyboard(),
        )
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
    await message.answer(GREETING, reply_markup=main_menu_keyboard())


# `📋 Вопросы` and `➕ Добавить` are wired in `bot_admin/handlers/questions.py`
# next to the slash-command handlers they reuse (FSMContext is needed there).
# Below: the two buttons that don't yet have a real backend.


@router.message(F.text == BTN_ASK)
async def admin_menu_ask(message: Message) -> None:
    # The conversational agent picks up any free-form text via the fallback
    # router, so this button just nudges the admin to type what they need.
    await message.answer(
        "Спросите что угодно — например, «покажи активные вопросы», "
        "«удали вопрос про скорость», «добавь вопрос про парковку»."
    )


@router.message(F.text == BTN_ADMINS)
async def admin_menu_admins(message: Message) -> None:
    await message.answer(
        "Список админов: используйте /invite_admin <telegram_id> чтобы добавить нового."
    )
