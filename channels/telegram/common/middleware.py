"""Переиспользуемые aiogram middleware'ы для guest и admin ботов."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from aiogram.utils.chat_action import ChatActionSender


class TypingMiddleware(BaseMiddleware):
    """Включает «typing…» индикатор на время выполнения handler'а.

    Telegram-индикатор активен ~5 сек и автоматически продлевается
    `ChatActionSender`'ом пока хэндлер выполняется. Юзер видит «бот
    печатает», даже когда мы делаем медленные операции (DB, LLM, STT).

    Применяется к message-хэндлерам. Для не-Message событий пропускает
    без изменений.

    Использование:
        dp.message.middleware(TypingMiddleware())
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.bot is not None:
            async with ChatActionSender.typing(
                chat_id=event.chat.id,
                bot=event.bot,
            ):
                return await handler(event, data)
        return await handler(event, data)
