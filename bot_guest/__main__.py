import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot_guest.handlers import dialogue, feedback, start, survey_consent
from config import settings

GUEST_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="Начать сбор отзыва"),
    BotCommand(command="cancel", description="Отменить и завершить диалог"),
]


async def main() -> None:
    logging.basicConfig(level=settings.log_level)
    if not settings.telegram_guest_bot_token:
        raise RuntimeError("TELEGRAM_GUEST_BOT_TOKEN is not set")

    bot = Bot(token=settings.telegram_guest_bot_token)
    await bot.set_my_commands(GUEST_COMMANDS)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(feedback.router)
    dp.include_router(dialogue.router)
    dp.include_router(survey_consent.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
