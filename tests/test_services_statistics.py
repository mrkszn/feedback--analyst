"""Tests for services.statistics.full_report — pure aggregation, no LLM."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import patch

import pytest

from services.statistics import (
    FullReport,
    TopicRow,
    _classify_topic,
    _classify_value,
    _summarize_metric,
    _summarize_topics,
    _to_number,
    build_csv_report,
    full_report,
)

# --------------------------------------------------------------------------- #
# unit-level helpers


def test_classify_value_handles_all_shapes() -> None:
    assert _classify_value({"value": "ужин"}) == "ужин"
    assert _classify_value({"value": True}) == "Да"
    assert _classify_value({"value": False}) == "Нет"
    assert _classify_value({"value": 18}) == "18"
    assert _classify_value("  ") is None
    assert _classify_value(None) is None
    assert _classify_value({"value": ""}) is None


def test_to_number_handles_all_shapes() -> None:
    assert _to_number({"value": 4}) == 4.0
    assert _to_number({"value": 3.5}) == 3.5
    assert _to_number({"value": True}) == 1.0
    assert _to_number({"value": False}) == 0.0
    assert _to_number({"value": "4"}) == 4.0
    assert _to_number({"value": "abc"}) is None
    assert _to_number(None) is None


def test_summarize_topics_groups_with_avg_sentiment() -> None:
    rows: list[dict[str, Any]] = [
        {
            "feedback_summary": {
                "topics": ["еда", "сервис"],
                "sentiment": "positive",
            }
        },
        {
            "feedback_summary": {
                "topics": ["сервис", "ожидание"],
                "sentiment": "negative",
            }
        },
        {"feedback_summary": None},
        {"feedback_summary": {"topics": [""], "sentiment": "neutral"}},
    ]
    topics = _summarize_topics(rows)
    by_topic = {t["topic"]: t for t in topics}
    assert by_topic["еда"]["count"] == 1
    assert by_topic["сервис"]["count"] == 2
    # сервис: один positive (+1) + один negative (-1) = 0.0
    assert by_topic["сервис"]["avg_sentiment"] == pytest.approx(0.0)
    assert by_topic["ожидание"]["avg_sentiment"] == pytest.approx(-1.0)


def test_classify_topic_partitions_by_threshold() -> None:
    rows: list[TopicRow] = [
        TopicRow(topic="good", count=3, avg_sentiment=0.9),
        TopicRow(topic="meh", count=2, avg_sentiment=0.2),
        TopicRow(topic="bad", count=5, avg_sentiment=-0.7),
        TopicRow(topic="mid", count=1, avg_sentiment=0.0),
    ]
    pos, neu, neg = _classify_topic(rows)
    assert [t["topic"] for t in pos] == ["good"]
    assert [t["topic"] for t in neu] == ["meh", "mid"]  # sorted by count desc
    assert [t["topic"] for t in neg] == ["bad"]


def test_summarize_metric_number() -> None:
    question = {
        "id": "q1",
        "metric_key": "speed",
        "text": "Скорость?",
        "expected_type": "number",
    }
    answers = [
        {"marked_value": {"value": 5}},
        {"marked_value": {"value": 3}},
        {"marked_value": {"value": 4}},
    ]
    m = _summarize_metric(question, answers)
    assert m["n"] == 3
    assert m["avg"] == pytest.approx(4.0)
    assert m["min"] == 3.0
    assert m["max"] == 5.0


def test_summarize_metric_enum() -> None:
    question = {
        "id": "q2",
        "metric_key": "purpose",
        "text": "Цель визита?",
        "expected_type": "enum",
    }
    answers = [
        {"marked_value": {"value": "ужин"}},
        {"marked_value": {"value": "ужин"}},
        {"marked_value": {"value": "бизнес"}},
    ]
    m = _summarize_metric(question, answers)
    assert m["n"] == 3
    assert m["top_value"] == "ужин"
    assert m["top_pct"] == pytest.approx(2 / 3)
    assert m["distribution"] is not None
    assert m["distribution"][0]["value"] == "ужин"


def test_summarize_metric_boolean() -> None:
    question = {
        "id": "q3",
        "metric_key": "would_return",
        "text": "Вернётесь?",
        "expected_type": "boolean",
    }
    answers = [
        {"marked_value": {"value": True}},
        {"marked_value": {"value": True}},
        {"marked_value": {"value": False}},
    ]
    m = _summarize_metric(question, answers)
    assert m["n"] == 3
    assert m["top_value"] == "Да"
    assert m["distribution"] is not None
    assert {d["value"] for d in m["distribution"]} == {"Да", "Нет"}


def test_summarize_metric_text() -> None:
    question = {
        "id": "q4",
        "metric_key": "favorite_dish",
        "text": "Любимое блюдо?",
        "expected_type": "text",
    }
    answers = [
        {"answer_text": "паста", "marked_value": None},
        {"answer_text": "  ", "marked_value": None},
        {"answer_text": "стейк", "marked_value": None},
    ]
    m = _summarize_metric(question, answers)
    assert m["n"] == 3
    assert m["response_rate"] == pytest.approx(2 / 3)


def test_summarize_metric_empty() -> None:
    question = {
        "id": "q5",
        "metric_key": "x",
        "text": "x",
        "expected_type": "number",
    }
    m = _summarize_metric(question, [])
    assert m["n"] == 0
    assert m["avg"] is None


# --------------------------------------------------------------------------- #
# full_report — integration with a fake supabase client


class _FakeResp:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, owner: _FakeTable) -> None:
        self.owner = owner
        self.filters: list[tuple[str, Any]] = []
        self.order_field: str | None = None
        self.order_desc: bool = False
        self.limit_n: int | None = None

    def select(self, *_cols: str) -> _FakeQuery:
        return self

    def gte(self, field: str, value: Any) -> _FakeQuery:
        self.filters.append(("gte", (field, value)))
        return self

    def lte(self, field: str, value: Any) -> _FakeQuery:
        self.filters.append(("lte", (field, value)))
        return self

    def eq(self, field: str, value: Any) -> _FakeQuery:
        self.filters.append(("eq", (field, value)))
        return self

    def in_(self, field: str, values: list[Any]) -> _FakeQuery:
        self.filters.append(("in", (field, list(values))))
        return self

    def order(self, field: str, *, desc: bool = False) -> _FakeQuery:
        self.order_field = field
        self.order_desc = desc
        return self

    def limit(self, n: int) -> _FakeQuery:
        self.limit_n = n
        return self

    def execute(self) -> _FakeResp:
        rows = list(self.owner.rows)
        for kind, (field, value) in self.filters:
            if kind == "eq":
                rows = [r for r in rows if r.get(field) == value]
            elif kind == "in":
                rows = [r for r in rows if r.get(field) in value]
            elif kind == "gte":
                rows = [r for r in rows if (r.get(field) or "") >= value]
            elif kind == "lte":
                rows = [r for r in rows if (r.get(field) or "") <= value]
        if self.order_field:
            rows.sort(
                key=lambda r: r.get(self.order_field or "") or "",
                reverse=self.order_desc,
            )
        if self.limit_n is not None:
            rows = rows[: self.limit_n]
        return _FakeResp(rows)


class _FakeTable:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows


class _FakeDB:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(_FakeTable(self.tables.get(name, [])))


def _ts(year: int, month: int, day: int) -> str:
    return datetime(year, month, day, 12, 0, tzinfo=UTC).isoformat()


async def test_full_report_aggregates_sessions_and_topics() -> None:
    db = _FakeDB(
        {
            "sessions": [
                {
                    "id": "s1",
                    "client_id": 100,
                    "started_at": _ts(2026, 5, 30),
                    "ended_at": _ts(2026, 5, 30),
                    "feedback_summary": {
                        "summary": "Очень вкусно",
                        "sentiment": "positive",
                        "topics": ["еда"],
                        "emotion": "happy",
                    },
                },
                {
                    "id": "s2",
                    "client_id": 100,  # returning
                    "started_at": _ts(2026, 5, 31),
                    "ended_at": _ts(2026, 5, 31),
                    "feedback_summary": {
                        "summary": "Понравилось обслуживание",
                        "sentiment": "positive",
                        "topics": ["сервис"],
                        "emotion": "happy",
                    },
                },
                {
                    "id": "s3",
                    "client_id": 200,
                    "started_at": _ts(2026, 6, 1),
                    "ended_at": None,  # не финализирована
                    "feedback_summary": {
                        "summary": "Долго ждали",
                        "sentiment": "negative",
                        "topics": ["ожидание"],
                        "emotion": "disappointed",
                    },
                },
            ],
            "client_cards": [
                {
                    "session_id": "s1",
                    "summary_text": "Гость хвалил еду.",
                    "created_at": _ts(2026, 5, 30),
                },
            ],
            "questions": [
                {
                    "id": "q-speed",
                    "text": "Скорость?",
                    "metric_key": "speed",
                    "expected_type": "number",
                    "enum_values": None,
                    "is_active": True,
                },
            ],
            "session_answers": [
                {
                    "question_id": "q-speed",
                    "session_id": "s1",
                    "answer_text": "5",
                    "marked_value": {"value": 5},
                },
                {
                    "question_id": "q-speed",
                    "session_id": "s2",
                    "answer_text": "4",
                    "marked_value": {"value": 4},
                },
            ],
        }
    )

    date_from = datetime(2026, 5, 29, tzinfo=UTC)
    date_to = datetime(2026, 6, 2, tzinfo=UTC)

    with patch("services.statistics.get_supabase", return_value=db):
        report = await full_report(date_from, date_to, period_label="7 дней")

    assert report["activity"]["sessions_started"] == 3
    assert report["activity"]["sessions_finished"] == 2
    assert report["activity"]["unique_clients"] == 2
    assert report["activity"]["returning_clients"] == 1  # client 100 → 2 сессии
    assert report["sentiment_counts"]["positive"] == 2
    assert report["sentiment_counts"]["negative"] == 1
    assert report["sentiment_counts"]["neutral"] == 0
    topics = {t["topic"] for t in report["topics_positive"]}
    assert "еда" in topics
    assert "сервис" in topics
    assert {t["topic"] for t in report["topics_negative"]} == {"ожидание"}
    assert len(report["metrics"]) == 1
    speed = report["metrics"][0]
    assert speed["metric_key"] == "speed"
    assert speed["n"] == 2
    assert speed["avg"] == pytest.approx(4.5)
    # recent: новейшая сессия первой (s3), summary берётся из feedback_summary
    # (карточки нет), но строка не пустая
    assert report["recent_sessions"][0]["client_id"] == 200
    assert report["recent_sessions"][0]["summary"]


async def test_full_report_empty_database() -> None:
    db = _FakeDB({"sessions": [], "client_cards": [], "questions": []})
    date_from = None
    date_to = datetime(2026, 6, 2, tzinfo=UTC)
    with patch("services.statistics.get_supabase", return_value=db):
        report = await full_report(date_from, date_to, period_label="всё время")
    assert report["activity"]["sessions_started"] == 0
    assert report["sentiment_total"] == 0
    assert report["topics_positive"] == []
    assert report["topics_negative"] == []
    assert report["metrics"] == []
    assert report["recent_sessions"] == []


async def test_full_report_validates_dates() -> None:
    with pytest.raises(ValueError):
        await full_report(
            datetime(2026, 6, 2, tzinfo=UTC),
            datetime(2026, 5, 1, tzinfo=UTC),
        )


async def test_full_report_none_date_from_uses_earliest() -> None:
    db = _FakeDB(
        {
            "sessions": [
                {
                    "id": "old",
                    "client_id": 1,
                    "started_at": _ts(2026, 1, 1),
                    "ended_at": _ts(2026, 1, 1),
                    "feedback_summary": {
                        "summary": "x",
                        "sentiment": "positive",
                        "topics": [],
                        "emotion": "",
                    },
                },
            ],
            "client_cards": [],
            "questions": [],
        }
    )
    date_to = datetime(2026, 6, 2, tzinfo=UTC)
    with patch("services.statistics.get_supabase", return_value=db):
        report = await full_report(None, date_to, period_label="всё время")
    assert report["activity"]["sessions_started"] == 1
    assert (report["date_from"] or "").startswith("2026-01-01")


def _unused_timedelta_import_marker() -> None:
    """Keep `timedelta` referenced so the linter doesn't strip the import in a
    future edit. (We may use it for parametric windows soon.)
    """
    _ = timedelta(days=1)


# --------------------------------------------------------------------------- #
# build_csv_report


def _csv_report(
    *,
    recent: list[dict[str, Any]] | None = None,
    metrics: list[dict[str, Any]] | None = None,
    topics_positive: list[dict[str, Any]] | None = None,
) -> FullReport:
    report: dict[str, Any] = {
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
        "topics_positive": topics_positive or [],
        "topics_neutral": [],
        "topics_negative": [],
        "metrics": metrics or [],
        "recent_sessions": recent or [],
    }
    return cast(FullReport, report)


def _full_csv_report() -> FullReport:
    return _csv_report(
        recent=[
            {
                "started_at": "2026-06-05T12:00:00+00:00",
                "sentiment": "positive",
                "summary": "Хвалили подачу",
                "client_id": 100,
            },
        ],
        metrics=[
            {
                "metric_key": "purpose",
                "text": "Цель визита?",
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
            {
                "metric_key": "speed",
                "text": "Скорость?",
                "expected_type": "number",
                "n": 2,
                "avg": 4.5,
                "min": 4.0,
                "max": 5.0,
                "top_value": None,
                "top_pct": None,
                "distribution": None,
                "response_rate": None,
            },
        ],
        topics_positive=[{"topic": "еда", "count": 4, "avg_sentiment": 0.9}],
    )


def test_build_csv_report_has_all_sections() -> None:
    out = build_csv_report(_full_csv_report())
    assert "# Sessions" in out
    assert "# Metrics" in out
    assert "# Topics" in out


def test_build_csv_report_is_valid_csv() -> None:
    out = build_csv_report(_full_csv_report())
    # Секции-разделители (# ...) и пустые строки убираем перед парсингом —
    # остаётся набор header+data строк, которые csv.reader обязан разобрать.
    data_lines = [line for line in out.splitlines() if line.strip() and not line.startswith("#")]
    rows = list(csv.reader(io.StringIO("\n".join(data_lines))))
    # каждая строка распарсилась хотя бы в одну колонку
    assert rows
    assert all(len(r) >= 1 for r in rows)
    # заголовок секции Sessions присутствует среди распарсенных строк
    assert ["date", "client_id", "sentiment", "topics", "summary_text"] in rows


def test_build_csv_report_escapes_commas() -> None:
    report = _csv_report(
        topics_positive=[
            {"topic": "Семья с детьми, малыши", "count": 3, "avg_sentiment": 0.8},
        ],
    )
    out = build_csv_report(report)
    # значение с запятой завёрнуто в кавычки сырым writer'ом
    assert '"Семья с детьми, малыши"' in out
    # и читается обратно как ОДНО поле
    rows = list(csv.reader(io.StringIO(out)))
    topic_rows = [r for r in rows if r and r[0] == "Семья с детьми, малыши"]
    assert len(topic_rows) == 1
    assert topic_rows[0][1] == "positive"


def test_build_csv_report_handles_empty() -> None:
    out = build_csv_report(_csv_report())
    # секции и их headers есть даже при пустом отчёте
    assert "# Sessions" in out
    assert "# Metrics" in out
    assert "# Topics" in out
    rows = list(csv.reader(io.StringIO(out)))
    # три header-строки присутствуют; data-строк нет
    assert ["date", "client_id", "sentiment", "topics", "summary_text"] in rows
    assert ["topic", "sentiment_filter", "count", "avg_sentiment"] in rows
