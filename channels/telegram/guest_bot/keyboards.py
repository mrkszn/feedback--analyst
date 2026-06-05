"""Inline keyboards для типизированных вопросов клиенту.

Каждый вопрос из пула может иметь ``expected_type`` ∈ {boolean, number, enum, text}.
Для типизированных (boolean/number/enum) рендерим компактную inline-клавиатуру;
для text — возвращаем ``None`` и ждём свободный ответ сообщением.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


_SKIP_BUTTON = InlineKeyboardButton(text="⏭ Пропустить", callback_data="ans:skip")


def build_question_keyboard(question: dict[str, Any]) -> InlineKeyboardMarkup | None:
    """Builds inline keyboard for a typed question, or None for text-questions.

    ``question`` keys: ``text``, ``metric_key``, ``expected_type``
    ∈ {boolean, number, enum, text}, ``enum_values`` (``list[str] | None``).

    Returns ``None`` for ``text`` (caller omits ``reply_markup``).
    Raises ``ValueError`` для неизвестного ``expected_type``.
    """
    expected_type = question.get("expected_type")

    if expected_type == "text":
        return None

    if expected_type == "boolean":
        rows = [
            [
                InlineKeyboardButton(text="✅ Да", callback_data="ans:yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="ans:no"),
                InlineKeyboardButton(text="⏭ Пропустить", callback_data="ans:skip"),
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    if expected_type == "number":
        rows = [
            [
                InlineKeyboardButton(text="1", callback_data="ans:1"),
                InlineKeyboardButton(text="2", callback_data="ans:2"),
                InlineKeyboardButton(text="3", callback_data="ans:3"),
                InlineKeyboardButton(text="4", callback_data="ans:4"),
                InlineKeyboardButton(text="5", callback_data="ans:5"),
                InlineKeyboardButton(text="⏭", callback_data="ans:skip"),
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    if expected_type == "enum":
        enum_values = question.get("enum_values") or []
        if not enum_values:
            logger.warning(
                "enum question has empty enum_values, falling back to text: %s",
                question.get("metric_key"),
            )
            return None
        rows = []
        for i in range(0, len(enum_values), 2):
            chunk = enum_values[i : i + 2]
            rows.append([InlineKeyboardButton(text=v, callback_data=f"ans:{v}") for v in chunk])
        rows.append([_SKIP_BUTTON])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    raise ValueError(f"unknown expected_type: {expected_type!r}")
