"""Tests for bot_admin.handlers.statistics — /statistics + inline period flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message

from presentations.telegram_admin.handlers.statistics import (
    PERIOD_7D,
    PERIOD_ALL,
    PERIOD_TODAY,
    _period_keyboard,
    _window,
    cb_statistics_period,
    cmd_statistics,
    format_report,
)


def _mk_message() -> MagicMock:
    # spec=Message so that `isinstance(msg, Message)` is True (production
    # cb_statistics_period guards against InaccessibleMessage with isinstance).
    msg = MagicMock(spec=Message)
    msg.from_user = SimpleNamespace(id=1, full_name="Tester")
    msg.chat = SimpleNamespace(id=42)
    msg.answer = AsyncMock()
    msg.edit_reply_markup = AsyncMock()
    msg.bot = None
    return msg


def _mk_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.from_user = SimpleNamespace(id=1, full_name="Tester")
    cb.data = data
    cb.message = _mk_message()
    cb.answer = AsyncMock()
    return cb


def _empty_report() -> dict:
    return {
        "period_label": "7 дней",
        "date_from": "2026-05-29T00:00:00+00:00",
        "date_to": "2026-06-05T00:00:00+00:00",
        "activity": {
            "sessions_started": 0,
            "sessions_finished": 0,
            "unique_clients": 0,
            "returning_clients": 0,
        },
        "sentiment_counts": {"positive": 0, "neutral": 0, "negative": 0},
        "sentiment_total": 0,
        "avg_sentiment": None,
        "topics_positive": [],
        "topics_neutral": [],
        "topics_negative": [],
        "metrics": [],
        "recent_sessions": [],
    }


# --------------------------------------------------------------------------- #
# _window


def test_window_today_starts_at_midnight() -> None:
    date_from, _ = _window(PERIOD_TODAY)
    assert date_from is not None
    assert date_from.hour == 0 and date_from.minute == 0


def test_window_7d_spans_7_days() -> None:
    date_from, date_to = _window(PERIOD_7D)
    assert date_from is not None
    assert (date_to - date_from).days == 7


def test_window_all_returns_none_from() -> None:
    date_from, _ = _window(PERIOD_ALL)
    assert date_from is None


def test_period_keyboard_has_4_buttons() -> None:
    kb = _period_keyboard()
    flat = [b for row in kb.inline_keyboard for b in row]
    assert len(flat) == 4
    callbacks = {b.callback_data for b in flat}
    assert callbacks == {"stats:today", "stats:7d", "stats:30d", "stats:all"}


# --------------------------------------------------------------------------- #
# format_report


def test_format_report_renders_all_sections() -> None:
    report = _empty_report()
    report["activity"] = {
        "sessions_started": 10,
        "sessions_finished": 8,
        "unique_clients": 6,
        "returning_clients": 2,
    }
    report["sentiment_counts"] = {"positive": 5, "neutral": 2, "negative": 1}
    report["sentiment_total"] = 8
    report["avg_sentiment"] = 0.4
    report["topics_positive"] = [{"topic": "еда", "count": 4, "avg_sentiment": 0.9}]
    report["topics_negative"] = [{"topic": "ожидание", "count": 2, "avg_sentiment": -0.8}]
    report["metrics"] = [
        {
            "metric_key": "speed",
            "text": "Скорость?",
            "expected_type": "number",
            "n": 5,
            "avg": 4.2,
            "min": 3.0,
            "max": 5.0,
            "top_value": None,
            "top_pct": None,
            "distribution": None,
            "response_rate": None,
        },
        {
            "metric_key": "purpose",
            "text": "Цель?",
            "expected_type": "enum",
            "n": 3,
            "avg": None,
            "min": None,
            "max": None,
            "top_value": "ужин",
            "top_pct": 0.67,
            "distribution": [
                {"value": "ужин", "count": 2, "pct": 0.67},
                {"value": "бизнес", "count": 1, "pct": 0.33},
            ],
            "response_rate": None,
        },
    ]
    report["recent_sessions"] = [
        {
            "started_at": "2026-06-05T12:00:00+00:00",
            "sentiment": "positive",
            "summary": "Хвалили подачу",
            "client_id": 100,
        }
    ]
    from typing import cast

    from core.services.statistics import FullReport

    messages = format_report(cast(FullReport, report))
    # format_report теперь возвращает list[str] (1-3 сообщения); склеиваем для
    # ассертов по содержимому, проверяя что ни одна секция не потерялась.
    assert isinstance(messages, list)
    text = "\n".join(messages)
    # шапка
    assert "Статистика" in text
    # активность
    assert "Сессий начато: 10" in text
    assert "Сессий завершено: 8" in text
    assert "Уникальных клиентов: 6" in text
    assert "Возвращающихся" in text
    # тональность
    assert "Позитив: 5" in text and "Негатив: 1" in text
    # топики
    assert "еда" in text and "ожидание" in text
    # метрики
    assert "Скорость" in text
    assert "avg=4.20" in text or "avg=4.2" in text
    assert "ужин" in text
    # последние
    assert "Хвалили подачу" in text


def test_format_report_handles_empty() -> None:
    from typing import cast

    from core.services.statistics import FullReport

    messages = format_report(cast(FullReport, _empty_report()))
    assert isinstance(messages, list)
    text = "\n".join(messages)
    assert "Статистика" in text
    assert "—" in text  # пустые секции дают тире


# --------------------------------------------------------------------------- #
# /statistics command


async def test_cmd_statistics_requires_admin() -> None:
    msg = _mk_message()
    with patch(
        "presentations.telegram_admin.handlers.statistics.require_admin",
        new=AsyncMock(return_value=False),
    ):
        await cmd_statistics(msg)
    msg.answer.assert_not_awaited()


async def test_cmd_statistics_shows_period_keyboard() -> None:
    msg = _mk_message()
    with patch(
        "presentations.telegram_admin.handlers.statistics.require_admin",
        new=AsyncMock(return_value=True),
    ):
        await cmd_statistics(msg)
    msg.answer.assert_awaited_once()
    kwargs = msg.answer.call_args.kwargs
    kb = kwargs["reply_markup"]
    # 4 кнопки в inline keyboard
    flat = [b for row in kb.inline_keyboard for b in row]
    assert len(flat) == 4


# --------------------------------------------------------------------------- #
# callback flow


async def test_cb_statistics_calls_full_report_and_replies() -> None:
    cb = _mk_callback("stats:7d")
    with (
        patch(
            "presentations.telegram_admin.handlers.statistics.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.statistics.full_report",
            new=AsyncMock(return_value=_empty_report()),
        ) as m,
    ):
        await cb_statistics_period(cb)
    m.assert_awaited_once()
    # format_report → list[str]; handler шлёт по одному .answer на сообщение
    # (для пустого отчёта это >=2: обзор + блок вопросов).
    calls = cb.message.answer.await_args_list
    assert len(calls) >= 2
    # первое сообщение — обзор с заголовком
    assert "Статистика" in calls[0].args[0]
    # CSV-кнопка крепится только к ПОСЛЕДНЕМУ сообщению
    last_markup = calls[-1].kwargs.get("reply_markup")
    assert last_markup is not None
    csv_btn = last_markup.inline_keyboard[0][0]
    assert csv_btn.callback_data == "stats_csv:7d"
    # к остальным сообщениям кнопка не цепляется
    for c in calls[:-1]:
        assert c.kwargs.get("reply_markup") is None


async def test_cb_statistics_rejects_unknown_period() -> None:
    cb = _mk_callback("stats:weird")
    with patch(
        "presentations.telegram_admin.handlers.statistics.is_admin",
        new=AsyncMock(return_value=True),
    ):
        await cb_statistics_period(cb)
    cb.answer.assert_awaited_with("Неизвестный период.", show_alert=True)


async def test_cb_statistics_rejects_non_admin() -> None:
    """Регрессионный тест: callback.from_user != callback.message.from_user.

    Раньше require_admin(callback.message) проверял ID БОТА вместо ID кликающего
    админа, что давало false negative «Только для админов» даже для зарегистр.
    админа. Теперь проверка идёт через callback.from_user.id.
    """
    cb = _mk_callback("stats:7d")
    with patch(
        "presentations.telegram_admin.handlers.statistics.is_admin",
        new=AsyncMock(return_value=False),
    ):
        await cb_statistics_period(cb)
    cb.answer.assert_awaited_with("Только для админов.", show_alert=True)
