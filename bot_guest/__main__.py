import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot_guest.handlers import dialogue, feedback, start, survey_consent
from config import settings


async def main() -> None:
    logging.basicConfig(level=settings.log_level)
    if not settings.telegram_guest_bot_token:
        raise RuntimeError("TELEGRAM_GUEST_BOT_TOKEN is not set")

    bot = Bot(token=settings.telegram_guest_bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(feedback.router)
    dp.include_router(dialogue.router)
    dp.include_router(survey_consent.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
