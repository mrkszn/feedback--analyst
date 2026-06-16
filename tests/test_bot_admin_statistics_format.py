"""Tests for bot_admin.handlers.statistics.format_report — list[str] renderer.

format_report renders a FullReport into 1-3 Telegram messages, each ≤ 4096
chars. Questions get a `▸` header; enum/boolean distributions get a `█`
ascii-bar; number metrics get an `avg=/min=/max=` line.
"""

from __future__ import annotations

from typing import cast

from core.services.statistics import FullReport
from presentations.telegram_admin.handlers.statistics import _TG_LIMIT, format_report


def _report() -> FullReport:
    report: dict = {
        "period_label": "7 дней",
        "date_from": "2026-05-29T00:00:00+00:00",
        "date_to": "2026-06-05T00:00:00+00:00",
        "activity": {
            "sessions_started": 10,
            "sessions_finished": 8,
            "unique_clients": 6,
            "returning_clients": 2,
        },
        "sentiment_counts": {"positive": 5, "neutral": 2, "negative": 1},
        "sentiment_total": 8,
        "avg_sentiment": 0.4,
        "topics_positive": [{"topic": "еда", "count": 4, "avg_sentiment": 0.9}],
        "topics_neutral": [{"topic": "интерьер", "count": 1, "avg_sentiment": 0.0}],
        "topics_negative": [{"topic": "ожидание", "count": 2, "avg_sentiment": -0.8}],
        "metrics": [
            {
                "metric_key": "purpose",
                "text": "Цель визита?",
                "expected_type": "enum",
                "n": 6,
                "avg": None,
                "min": None,
                "max": None,
                "top_value": "ужин",
                "top_pct": 0.5,
                "distribution": [
                    {"value": "ужин", "count": 3, "pct": 0.5},
                    {"value": "бизнес", "count": 2, "pct": 0.33},
                    {"value": "свидание", "count": 1, "pct": 0.17},
                ],
                "response_rate": None,
            },
            {
                "metric_key": "speed",
                "text": "Скорость обслуживания?",
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
        ],
        "recent_sessions": [
            {
                "started_at": "2026-06-05T12:00:00+00:00",
                "sentiment": "positive",
                "summary": "Хвалили подачу",
                "client_id": 100,
            },
            {
                "started_at": "2026-06-04T18:00:00+00:00",
                "sentiment": "negative",
                "summary": "Долго ждали счёт",
                "client_id": 200,
            },
        ],
    }
    return cast(FullReport, report)


def test_format_report_returns_list_of_str() -> None:
    messages = format_report(_report())
    assert isinstance(messages, list)
    assert 1 <= len(messages) <= 3
    assert all(isinstance(m, str) for m in messages)


def test_first_message_has_header_and_period() -> None:
    messages = format_report(_report())
    assert "📊" in messages[0]
    assert "7 дней" in messages[0]


def test_loop_block_rendered_when_present() -> None:
    report = _report()
    cast(dict, report)["loop"] = {
        "repeat_rate": 0.25,
        "sessions_per_client": 1.67,
        "median_days_to_2nd": 3.0,
    }
    text = "\n".join(format_report(report))
    assert "🔁 Повторяемость" in text
    assert "25%" in text  # repeat_rate
    assert "Сессий на клиента: 1.67" in text
    assert "3.0 дн." in text


def test_loop_block_absent_when_missing() -> None:
    # _report() carries no "loop" key → recurrence block silently omitted.
    text = "\n".join(format_report(_report()))
    assert "🔁 Повторяемость" not in text


def test_enum_metric_has_ascii_bar() -> None:
    text = "\n".join(format_report(_report()))
    assert "█" in text
    # enum категории присутствуют
    assert "ужин" in text and "бизнес" in text and "свидание" in text


def test_number_metric_has_avg_min_max() -> None:
    text = "\n".join(format_report(_report()))
    # avg=/min=/max= на одной строке для number-метрики
    line = next(line for line in text.splitlines() if "avg=" in line)
    assert "min=" in line and "max=" in line


def test_each_question_prefixed_with_marker() -> None:
    text = "\n".join(format_report(_report()))
    assert "▸ Цель визита?" in text
    assert "▸ Скорость обслуживания?" in text


def test_every_message_within_telegram_limit() -> None:
    messages = format_report(_report())
    for m in messages:
        assert len(m) <= _TG_LIMIT


def test_many_questions_split_across_messages_all_within_limit() -> None:
    """Lots of long-named questions must split into ≤_TG_LIMIT chunks."""
    report = _report()
    long_metric = {
        "metric_key": "q",
        "text": "Очень длинный вопрос про впечатления гостя " * 4,
        "expected_type": "number",
        "n": 3,
        "avg": 4.0,
        "min": 3.0,
        "max": 5.0,
        "top_value": None,
        "top_pct": None,
        "distribution": None,
        "response_rate": None,
    }
    cast(dict, report)["metrics"] = [dict(long_metric, metric_key=f"q{i}") for i in range(200)]
    messages = format_report(report)
    assert len(messages) >= 2
    for m in messages:
        assert len(m) <= _TG_LIMIT
