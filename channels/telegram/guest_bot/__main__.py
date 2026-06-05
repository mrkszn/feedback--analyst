import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from channels.telegram.guest_bot.handlers import dialogue, feedback, start, survey_consent
from config import settings

GUEST_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="Начать сбор отзыва"),
    BotCommand(command="cancel", description="Отменить и завершить диалог"),
]

# Shown on the bot's profile page BEFORE the user taps Start — Telegram
# uses set_my_description for that. Visible to the user as soon as the
# chat opens. Kept short and warm.
GUEST_DESCRIPTION = (
    "Привет! 👋 Расскажи в одном сообщении (голосом или текстом), как прошёл "
    "твой заказ и доставка — что понравилось, а что нет. Это правда помогает: "
    "владелец читает каждый отзыв."
)

# Shown in Telegram search results and the «What can this bot do?» card.
# Hard cap 120 chars per Telegram API.
GUEST_SHORT_DESCRIPTION = (
    "Поделись впечатлением от доставки — голосом или текстом. Минута, и владелец прочтёт."
)


async def _publish_profile(bot: Bot) -> None:
    """Push description + short description to Telegram once per startup.

    Telegram silently swallows set_my_description if the value is unchanged
    so it's cheap to call on every boot — keeps the profile in lockstep
    with what's in the repo.
    """
    try:
        await bot.set_my_description(description=GUEST_DESCRIPTION)
        await bot.set_my_short_description(short_description=GUEST_SHORT_DESCRIPTION)
    except Exception:
        # Telegram rejects descriptions only on bad token / rate limit. We
        # don't want a profile-publish hiccup to take the bot down.
        logging.exception("Failed to publish guest-bot profile description")


async def main() -> None:
    logging.basicConfig(level=settings.log_level)
    if not settings.telegram_guest_bot_token:
        raise RuntimeError("TELEGRAM_GUEST_BOT_TOKEN is not set")

    bot = Bot(token=settings.telegram_guest_bot_token)
    await bot.set_my_commands(GUEST_COMMANDS)
    await _publish_profile(bot)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(feedback.router)
    dp.include_router(dialogue.router)
    dp.include_router(survey_consent.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
