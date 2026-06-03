"""Tests for bot_admin.handlers.analytics_commands — only /topics survived
the Phase-5 cleanup (/insights, /metric, /find, /clients, /ask removed)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot_admin.handlers.analytics_commands import (
    _format_topics_report,
    _parse_days,
    cmd_topics,
)


def _mk_message() -> MagicMock:
    msg = MagicMock()
    msg.from_user = SimpleNamespace(id=1, full_name="Tester")
    msg.answer = AsyncMock()
    return msg


def _cmd(args: str | None) -> MagicMock:
    c = MagicMock()
    c.args = args
    return c


# --------------------------------------------------------------------------- #
# helpers


def test_parse_days_defaults_to_7() -> None:
    assert _parse_days(None) == 7
    assert _parse_days("  ") == 7


def test_parse_days_validates() -> None:
    assert _parse_days("14") == 14
    assert isinstance(_parse_days("abc"), str)
    assert isinstance(_parse_days("0"), str)
    assert isinstance(_parse_days("9999"), str)


def test_format_topics_report_buckets_by_sentiment() -> None:
    rows = [
        {"topic": "еда", "count": 8, "avg_sentiment": 0.9},
        {"topic": "сервис", "count": 5, "avg_sentiment": 0.1},
        {"topic": "ожидание", "count": 3, "avg_sentiment": -0.8},
    ]
    text = _format_topics_report(7, rows)
    assert "💚 Позитивные" in text
    assert "😐 Нейтральные" in text
    assert "❤️‍🩹 Негативные" in text
    assert "еда" in text and "сервис" in text and "ожидание" in text
    # totals в шапке
    assert "Всего упоминаний: 16" in text
    assert "уникальных топиков: 3" in text


def test_format_topics_report_empty() -> None:
    text = _format_topics_report(7, [])
    assert "не было упоминаний" in text.lower() or "—" in text


# --------------------------------------------------------------------------- #
# /topics


async def test_cmd_topics_requires_admin() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=False),
    ):
        await cmd_topics(msg, _cmd(None))
    msg.answer.assert_not_awaited()


async def test_cmd_topics_renders_full_report() -> None:
    msg = _mk_message()
    rows = [
        {"topic": "food", "count": 5, "avg_sentiment": 1.0},
        {"topic": "speed", "count": 2, "avg_sentiment": -1.0},
        {"topic": "ambience", "count": 3, "avg_sentiment": 0.0},
    ]
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.topic_histogram",
            new=AsyncMock(return_value=rows),
        ),
    ):
        await cmd_topics(msg, _cmd(None))
    msg.answer.assert_awaited_once()
    text = msg.answer.call_args.args[0]
    assert "Позитивные" in text
    assert "Негативные" in text
    assert "Нейтральные" in text
    assert "food" in text and "speed" in text and "ambience" in text


async def test_cmd_topics_bad_days_arg() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=True),
    ):
        await cmd_topics(msg, _cmd("abc"))
    text = msg.answer.call_args.args[0]
    assert "не понял" in text.lower() or "число" in text.lower()


# --------------------------------------------------------------------------- #
# router registration order


def test_analytics_router_registered_before_fallback() -> None:
    """В __main__.py analytics_commands должен быть подключён ДО fallback,
    иначе свободный текст admin_agent перехватит /topics.
    """
    import inspect

    from bot_admin import __main__ as adm

    source = inspect.getsource(adm.main)
    a_pos = source.find("analytics_commands.router")
    f_pos = source.find("fallback.router")
    assert a_pos > 0
    assert f_pos > 0
    assert a_pos < f_pos
