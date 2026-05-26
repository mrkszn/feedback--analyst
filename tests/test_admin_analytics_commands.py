"""Tests for bot_admin.handlers.analytics_commands — /insights, /metric, /topics."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot_admin.handlers.analytics_commands import (
    _fmt_sentiment,
    _parse_days,
    cmd_insights,
    cmd_metric,
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


def test_fmt_sentiment_labels() -> None:
    assert "позитив" in _fmt_sentiment(0.8)
    assert "негатив" in _fmt_sentiment(-0.8)
    assert "нейтрально" in _fmt_sentiment(0.0)
    assert _fmt_sentiment(None) == "—"


# --------------------------------------------------------------------------- #
# /insights


async def test_cmd_insights_requires_admin() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=False),
    ):
        await cmd_insights(msg, _cmd(None))
    msg.answer.assert_not_awaited()


async def test_cmd_insights_formats_summary() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.summary_overview",
            new=AsyncMock(
                return_value={
                    "sessions_count": 12,
                    "avg_sentiment": 0.5,
                    "top_positive_topics": [
                        {"topic": "food", "count": 5, "avg_sentiment": 1.0},
                    ],
                    "top_negative_topics": [
                        {"topic": "speed", "count": 2, "avg_sentiment": -1.0},
                    ],
                }
            ),
        ),
    ):
        await cmd_insights(msg, _cmd(None))
    msg.answer.assert_awaited_once()
    text = msg.answer.call_args.args[0]
    assert "Сессий: 12" in text
    assert "food" in text
    assert "speed" in text


async def test_cmd_insights_bad_days_arg() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=True),
    ):
        await cmd_insights(msg, _cmd("abc"))
    text = msg.answer.call_args.args[0]
    assert "не понял" in text.lower() or "число" in text.lower()


# --------------------------------------------------------------------------- #
# /metric


async def test_cmd_metric_missing_arg_shows_usage() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=True),
    ):
        await cmd_metric(msg, _cmd(None))
    text = msg.answer.call_args.args[0]
    assert "/metric" in text


async def test_cmd_metric_unknown_metric_key() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands._question_expected_type",
            new=AsyncMock(return_value=None),
        ),
    ):
        await cmd_metric(msg, _cmd("nonexistent"))
    text = msg.answer.call_args.args[0]
    assert "не найден" in text.lower()


async def test_cmd_metric_number_no_data() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands._question_expected_type",
            new=AsyncMock(return_value="number"),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.aggregate_metric",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await cmd_metric(msg, _cmd("service_speed"))
    text = msg.answer.call_args.args[0]
    assert "данных нет" in text.lower()


async def test_cmd_metric_number_renders_ascii_table() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands._question_expected_type",
            new=AsyncMock(return_value="number"),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.aggregate_metric",
            new=AsyncMock(
                return_value=[
                    {"bucket": "2026-05-20", "count": 2, "avg": 4.0, "min": 3.0, "max": 5.0},
                ]
            ),
        ),
    ):
        await cmd_metric(msg, _cmd("speed 14"))
    text = msg.answer.call_args.args[0]
    assert "2026-05-20" in text
    assert "```" in text
    assert msg.answer.call_args.kwargs.get("parse_mode") == "Markdown"


async def test_cmd_metric_enum_routes_to_categorical() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands._question_expected_type",
            new=AsyncMock(return_value="enum"),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.categorical_distribution",
            new=AsyncMock(
                return_value={
                    "metric_key": "age_group",
                    "expected_type": "enum",
                    "total": 5,
                    "categories": [
                        {"value": "18-24", "count": 3, "pct": 0.6},
                        {"value": "25-34", "count": 2, "pct": 0.4},
                    ],
                    "unknown": 0,
                    "enum_values": ["18-24", "25-34"],
                }
            ),
        ),
    ):
        await cmd_metric(msg, _cmd("age_group"))
    text = msg.answer.call_args.args[0]
    assert "Распределение" in text
    assert "18-24" in text
    assert "25-34" in text
    assert msg.answer.call_args.kwargs.get("parse_mode") == "Markdown"


async def test_cmd_metric_boolean_routes_to_categorical() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands._question_expected_type",
            new=AsyncMock(return_value="boolean"),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.categorical_distribution",
            new=AsyncMock(
                return_value={
                    "metric_key": "would_recommend",
                    "expected_type": "boolean",
                    "total": 7,
                    "categories": [
                        {"value": "true", "count": 5, "pct": 5 / 7},
                        {"value": "false", "count": 2, "pct": 2 / 7},
                    ],
                    "unknown": 0,
                    "enum_values": None,
                }
            ),
        ),
    ):
        await cmd_metric(msg, _cmd("would_recommend"))
    text = msg.answer.call_args.args[0]
    assert "true" in text
    assert "false" in text


async def test_cmd_metric_text_question_suggests_alternatives() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands._question_expected_type",
            new=AsyncMock(return_value="text"),
        ),
    ):
        await cmd_metric(msg, _cmd("open_feedback"))
    text = msg.answer.call_args.args[0]
    assert "/find" in text or "/topics" in text


# --------------------------------------------------------------------------- #
# /topics


async def test_cmd_topics_formats_pos_and_neg() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.topic_histogram",
            new=AsyncMock(
                side_effect=[
                    [{"topic": "food", "count": 5, "avg_sentiment": 1.0}],
                    [{"topic": "speed", "count": 2, "avg_sentiment": -1.0}],
                ]
            ),
        ),
    ):
        await cmd_topics(msg, _cmd(None))
    text = msg.answer.call_args.args[0]
    assert "Положительные" in text
    assert "Отрицательные" in text
    assert "food" in text
    assert "speed" in text


async def test_cmd_topics_handles_empty() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.topic_histogram",
            new=AsyncMock(side_effect=[[], []]),
        ),
    ):
        await cmd_topics(msg, _cmd("3"))
    text = msg.answer.call_args.args[0]
    assert "3 дн" in text


# --------------------------------------------------------------------------- #
# router registration order


def test_analytics_router_registered_before_fallback() -> None:
    """В __main__.py analytics_commands должен быть подключён ДО fallback,
    иначе свободный текст admin_agent перехватит /insights /metric /topics.
    """
    import inspect

    from bot_admin import __main__ as adm

    source = inspect.getsource(adm.main)
    a_pos = source.find("analytics_commands.router")
    f_pos = source.find("fallback.router")
    assert a_pos > 0
    assert f_pos > 0
    assert a_pos < f_pos
