import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot_admin.handlers import auth, questions
from bot_common.middleware import TypingMiddleware
from config import settings


async def main() -> None:
    logging.basicConfig(level=settings.log_level)
    if not settings.telegram_admin_bot_token:
        raise RuntimeError("TELEGRAM_ADMIN_BOT_TOKEN is not set")

    bot = Bot(token=settings.telegram_admin_bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    # Все message-хэндлеры получают «бот печатает» автоматически —
    # видно когда идёт DB-call. См. bot_common/middleware.py.
    dp.message.middleware(TypingMiddleware())
    dp.include_router(auth.router)
    dp.include_router(questions.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
