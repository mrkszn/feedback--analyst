"""Tests for bot_admin.handlers.statistics.cb_statistics_csv — CSV export button.

The `stats_csv:<period>` callback builds the report, renders it to CSV via
`build_csv_report`, wraps it in a `BufferedInputFile`, and ships it with
`callback.message.answer_document`. Admin + period guards short-circuit
before any report is built.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import BufferedInputFile, Message

from presentations.telegram_admin.handlers.statistics import cb_statistics_csv


def _mk_message() -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.from_user = SimpleNamespace(id=1, full_name="Tester")
    msg.chat = SimpleNamespace(id=42)
    msg.answer_document = AsyncMock()
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


async def test_csv_sends_document_with_csv_filename() -> None:
    cb = _mk_callback("stats_csv:7d")
    with (
        patch(
            "presentations.telegram_admin.handlers.statistics.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.statistics.full_report",
            new=AsyncMock(return_value=_empty_report()),
        ) as full,
        patch(
            "presentations.telegram_admin.handlers.statistics.build_csv_report",
            return_value="# Sessions\n",
        ) as build,
    ):
        await cb_statistics_csv(cb)
    full.assert_awaited_once()
    build.assert_called_once()
    cb.message.answer_document.assert_awaited_once()
    document = cb.message.answer_document.await_args.args[0]
    assert isinstance(document, BufferedInputFile)
    assert document.filename is not None
    assert document.filename.startswith("statistics_7d_")
    assert document.filename.endswith(".csv")
    cb.answer.assert_awaited_once()


async def test_csv_non_admin_sends_nothing() -> None:
    cb = _mk_callback("stats_csv:7d")
    with (
        patch(
            "presentations.telegram_admin.handlers.statistics.is_admin",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "presentations.telegram_admin.handlers.statistics.full_report", new=AsyncMock()
        ) as full,
        patch("presentations.telegram_admin.handlers.statistics.build_csv_report") as build,
    ):
        await cb_statistics_csv(cb)
    full.assert_not_awaited()
    build.assert_not_called()
    cb.message.answer_document.assert_not_awaited()
    cb.answer.assert_awaited_with("Только для админов.", show_alert=True)


async def test_csv_unknown_period_sends_nothing() -> None:
    cb = _mk_callback("stats_csv:weird")
    with (
        patch(
            "presentations.telegram_admin.handlers.statistics.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.statistics.full_report", new=AsyncMock()
        ) as full,
        patch("presentations.telegram_admin.handlers.statistics.build_csv_report") as build,
    ):
        await cb_statistics_csv(cb)
    full.assert_not_awaited()
    build.assert_not_called()
    cb.message.answer_document.assert_not_awaited()
    cb.answer.assert_awaited_with("Неизвестный период.", show_alert=True)
