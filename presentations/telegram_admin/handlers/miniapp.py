"""`/miniapp` — opens the admin Mini App via Telegram WebApp inline button.

The URL is configurable via `ADMIN_MINI_APP_URL` env. For local dev that's a
cloudflared / ngrok tunnel; for prod — a stable HTTPS domain.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from config import settings
from presentations.telegram_admin.handlers.questions import require_admin

router = Router(name="admin_miniapp")


@router.message(Command("miniapp"))
async def admin_miniapp(message: Message) -> None:
    if not await require_admin(message):
        return
    url = settings.admin_mini_app_url
    if not url:
        await message.answer(
            "Mini App ещё не настроен. Задайте `ADMIN_MINI_APP_URL` в .env "
            "(публичный HTTPS-URL) и перезапустите бота."
        )
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть Mini App", web_app=WebAppInfo(url=url))]
        ]
    )
    await message.answer(
        "Нажмите кнопку ниже — Mini App откроется внутри Telegram.",
        reply_markup=keyboard,
    )
