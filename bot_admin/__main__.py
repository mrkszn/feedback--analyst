import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot_admin.handlers import (
    admin_question_dialog,
    auth,
    fallback,
    question_voice,
    questions,
)
from bot_common.middleware import TypingMiddleware
from config import settings

ADMIN_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="Начать"),
    BotCommand(command="claim", description="Привязать админа"),
    BotCommand(command="questions", description="Показать вопросы"),
    BotCommand(command="add_question", description="Добавить вопрос"),
    BotCommand(command="edit_question", description="Изменить вопрос"),
    BotCommand(command="delete_question", description="Удалить вопрос"),
    BotCommand(command="invite_admin", description="Пригласить ещё одного админа"),
]


async def main() -> None:
    logging.basicConfig(level=settings.log_level)
    if not settings.telegram_admin_bot_token:
        raise RuntimeError("TELEGRAM_ADMIN_BOT_TOKEN is not set")

    bot = Bot(token=settings.telegram_admin_bot_token)
    await bot.set_my_commands(ADMIN_COMMANDS)
    dp = Dispatcher(storage=MemoryStorage())
    # Все message-хэндлеры получают «бот печатает» автоматически —
    # видно когда идёт DB-call. См. bot_common/middleware.py.
    dp.message.middleware(TypingMiddleware())
    dp.include_router(auth.router)
    dp.include_router(questions.router)
    dp.include_router(question_voice.router)
    dp.include_router(admin_question_dialog.router)
    dp.include_router(fallback.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
