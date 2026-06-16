"""Unit-тесты для core.services.re_entry.

Мокаем на уровне service-функции (`client_profile`), не на уровне storage —
по инварианту тестирования. Главные ветки:
- неизвестный клиент (LookupError) → first-timer;
- строка есть, но 0 сессий → first-timer (returning гейтится на sessions_count>=1);
- вернувшийся с темой → персональная строка с темой;
- вернувшийся без тем → персональная строка без темы;
- reentry_greeting(first-timer) → None (caller использует WELCOME).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from channels.telegram.guest_bot.handlers.start import WELCOME
from core.services import re_entry


async def test_unknown_client_is_first_timer() -> None:
    with patch.object(re_entry, "client_profile", new=AsyncMock(side_effect=LookupError)):
        ctx = await re_entry.load_reentry_context(999)
    assert ctx["is_returning"] is False
    assert re_entry.reentry_greeting(ctx) is None


async def test_client_row_but_no_sessions_is_first_timer() -> None:
    profile: dict[str, Any] = {
        "telegram_id": 1,
        "name": "Иван",
        "sessions_count": 0,
        "last_session_at": None,
        "avg_sentiment": None,
        "recent_cards": [],
        "top_topics": [],
    }
    with patch.object(re_entry, "client_profile", new=AsyncMock(return_value=profile)):
        ctx = await re_entry.load_reentry_context(1)
    assert ctx["is_returning"] is False
    assert re_entry.reentry_greeting(ctx) is None


async def test_returning_with_topic_surfaces_it() -> None:
    profile: dict[str, Any] = {
        "telegram_id": 1,
        "name": "Иван",
        "sessions_count": 3,
        "last_session_at": "2026-06-01T12:00:00+00:00",
        "avg_sentiment": -0.3,
        "recent_cards": [{"summary_text": "..."}],
        "top_topics": [
            {"topic": "курьер", "count": 2, "avg_sentiment": -1.0},
            {"topic": "еда", "count": 1, "avg_sentiment": 1.0},
        ],
    }
    with patch.object(re_entry, "client_profile", new=AsyncMock(return_value=profile)):
        ctx = await re_entry.load_reentry_context(1)
    assert ctx["is_returning"] is True
    assert ctx["sessions_count"] == 3
    assert ctx["top_topic"] == "курьер"
    greeting = re_entry.reentry_greeting(ctx)
    assert greeting is not None
    assert "С возвращением" in greeting
    assert "курьер" in greeting


async def test_returning_without_topics_generic_greeting() -> None:
    profile: dict[str, Any] = {
        "telegram_id": 1,
        "name": None,
        "sessions_count": 1,
        "last_session_at": "2026-06-01T12:00:00+00:00",
        "avg_sentiment": None,
        "recent_cards": [],
        "top_topics": [],
    }
    with patch.object(re_entry, "client_profile", new=AsyncMock(return_value=profile)):
        ctx = await re_entry.load_reentry_context(1)
    assert ctx["is_returning"] is True
    assert ctx["top_topic"] is None
    greeting = re_entry.reentry_greeting(ctx)
    assert greeting is not None
    assert "С возвращением" in greeting
    assert greeting != WELCOME


def test_reentry_greeting_first_timer_is_none() -> None:
    ctx: re_entry.ReEntryContext = {
        "is_returning": False,
        "sessions_count": 0,
        "last_session_at": None,
        "top_topic": None,
    }
    assert re_entry.reentry_greeting(ctx) is None
