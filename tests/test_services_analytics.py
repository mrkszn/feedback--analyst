"""Unit tests for services/analytics.py — aggregate_metric, topic_histogram,
summary_overview. Supabase replaced with MagicMock; in-memory aggregation.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.services.analytics import (
    _bucket_for,
    _coerce_categorical,
    _coerce_numeric,
    aggregate_metric,
    categorical_distribution,
    summary_overview,
    topic_histogram,
)

# --------------------------------------------------------------------------- #
# helpers


def test_coerce_numeric_handles_jsonb_shapes() -> None:
    assert _coerce_numeric(5) == 5.0
    assert _coerce_numeric(3.14) == pytest.approx(3.14)
    assert _coerce_numeric(True) == 1.0
    assert _coerce_numeric(False) == 0.0
    assert _coerce_numeric("4.5") == 4.5
    assert _coerce_numeric({"value": 7}) == 7.0
    assert _coerce_numeric("hello") is None
    assert _coerce_numeric(None) is None
    assert _coerce_numeric([1, 2]) is None


def test_bucket_for_day_and_week_and_none() -> None:
    dt = datetime(2026, 5, 20, 15, 30, tzinfo=UTC)
    assert _bucket_for(dt, "day") == "2026-05-20"
    assert _bucket_for(dt, "week").startswith("2026-W")
    assert _bucket_for(dt, "none") == "all"
    assert _bucket_for("2026-05-21T10:00:00+00:00", "day") == "2026-05-21"


# --------------------------------------------------------------------------- #
# aggregate_metric


def _mk_db_for_aggregate(question_row: dict | None, answer_rows: list[dict]) -> MagicMock:
    """Build a MagicMock supabase that returns `question_row` for the questions
    lookup and `answer_rows` for the session_answers query.
    """
    db = MagicMock()

    def table(name: str) -> Any:
        chain = MagicMock()
        if name == "questions":
            chain.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
                [question_row] if question_row else []
            )
        elif name == "session_answers":
            chain.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = answer_rows
        return chain

    db.table.side_effect = table
    return db


async def test_aggregate_metric_unknown_metric_returns_empty() -> None:
    db = _mk_db_for_aggregate(None, [])
    out = await aggregate_metric(
        "missing",
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    assert out == []


async def test_aggregate_metric_groups_by_day() -> None:
    db = _mk_db_for_aggregate(
        {"id": "q-1", "metric_key": "speed"},
        [
            {"created_at": "2026-05-20T10:00:00+00:00", "marked_value": 5},
            {"created_at": "2026-05-20T18:00:00+00:00", "marked_value": 3},
            {"created_at": "2026-05-21T09:00:00+00:00", "marked_value": 4},
        ],
    )
    out = await aggregate_metric(
        "speed",
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        group_by="day",
        db=db,
    )
    assert len(out) == 2
    assert out[0]["bucket"] == "2026-05-20"
    assert out[0]["count"] == 2
    assert out[0]["avg"] == pytest.approx(4.0)
    assert out[0]["min"] == 3.0
    assert out[0]["max"] == 5.0
    assert out[1]["count"] == 1
    assert out[1]["avg"] == pytest.approx(4.0)


async def test_aggregate_metric_text_question_keeps_count_no_avg() -> None:
    db = _mk_db_for_aggregate(
        {"id": "q-2", "metric_key": "open_feedback"},
        [
            {"created_at": "2026-05-20T10:00:00+00:00", "marked_value": "хорошо"},
            {"created_at": "2026-05-20T11:00:00+00:00", "marked_value": "ок"},
        ],
    )
    out = await aggregate_metric(
        "open_feedback",
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        group_by="none",
        db=db,
    )
    assert out == [{"bucket": "all", "count": 2, "avg": None, "min": None, "max": None}]


async def test_aggregate_metric_bad_date_range_raises() -> None:
    with pytest.raises(ValueError):
        await aggregate_metric(
            "x",
            datetime(2026, 5, 31, tzinfo=UTC),
            datetime(2026, 5, 1, tzinfo=UTC),
            db=MagicMock(),
        )


async def test_aggregate_metric_empty_metric_key_raises() -> None:
    with pytest.raises(ValueError):
        await aggregate_metric(
            "   ",
            datetime(2026, 5, 1, tzinfo=UTC),
            datetime(2026, 5, 31, tzinfo=UTC),
            db=MagicMock(),
        )


# --------------------------------------------------------------------------- #
# topic_histogram


def _mk_db_for_sessions(rows: list[dict]) -> MagicMock:
    db = MagicMock()
    # topic_histogram chain: sessions → select → gte → lte → not_.is_ → execute
    chain = db.table.return_value
    chain.select.return_value.gte.return_value.lte.return_value.not_.is_.return_value.execute.return_value.data = rows
    # summary_overview chain: sessions → select → gte → lte → execute
    chain.select.return_value.gte.return_value.lte.return_value.execute.return_value.data = rows
    return db


async def test_topic_histogram_counts_and_sorts() -> None:
    rows = [
        {"feedback_summary": {"topics": ["food", "service"], "sentiment": "positive"}},
        {"feedback_summary": {"topics": ["food"], "sentiment": "positive"}},
        {"feedback_summary": {"topics": ["service", "speed"], "sentiment": "negative"}},
    ]
    db = _mk_db_for_sessions(rows)
    out = await topic_histogram(
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    counts = {t["topic"]: t["count"] for t in out}
    assert counts["food"] == 2
    assert counts["service"] == 2
    assert counts["speed"] == 1
    # sorted desc by count
    assert out[0]["count"] >= out[-1]["count"]


async def test_topic_histogram_sentiment_filter_negative_only() -> None:
    rows = [
        {"feedback_summary": {"topics": ["food"], "sentiment": "positive"}},
        {"feedback_summary": {"topics": ["service"], "sentiment": "negative"}},
        {"feedback_summary": {"topics": ["service", "speed"], "sentiment": "negative"}},
    ]
    db = _mk_db_for_sessions(rows)
    out = await topic_histogram(
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        sentiment_filter="negative",
        db=db,
    )
    topics = {t["topic"] for t in out}
    assert "food" not in topics
    assert "service" in topics
    assert "speed" in topics
    for t in out:
        assert t["avg_sentiment"] == pytest.approx(-1.0)


async def test_topic_histogram_skips_malformed_rows() -> None:
    rows: list[dict] = [
        {"feedback_summary": None},
        {"feedback_summary": "garbage"},
        {"feedback_summary": {"topics": "not-a-list", "sentiment": "positive"}},
        {"feedback_summary": {"topics": ["valid"], "sentiment": "positive"}},
    ]
    db = _mk_db_for_sessions(rows)
    out = await topic_histogram(
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    assert len(out) == 1
    assert out[0]["topic"] == "valid"


# --------------------------------------------------------------------------- #
# summary_overview


async def test_summary_overview_aggregates_sentiment_and_topics() -> None:
    rows = [
        {"feedback_summary": {"topics": ["food"], "sentiment": "positive"}},
        {"feedback_summary": {"topics": ["food"], "sentiment": "positive"}},
        {"feedback_summary": {"topics": ["service"], "sentiment": "negative"}},
        {"feedback_summary": {"topics": ["speed"], "sentiment": "neutral"}},
    ]
    db = _mk_db_for_sessions(rows)
    out = await summary_overview(
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    assert out["sessions_count"] == 4
    assert out["avg_sentiment"] is not None
    # 2 positives (1.0), 1 negative (-1.0), 1 neutral (0.0) → avg 0.25
    assert out["avg_sentiment"] == pytest.approx(0.25)
    pos = {t["topic"] for t in out["top_positive_topics"]}
    assert "food" in pos
    neg = {t["topic"] for t in out["top_negative_topics"]}
    assert "service" in neg


async def test_summary_overview_empty_period_returns_zero() -> None:
    db = _mk_db_for_sessions([])
    out = await summary_overview(
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    assert out["sessions_count"] == 0
    assert out["avg_sentiment"] is None
    assert out["top_positive_topics"] == []
    assert out["top_negative_topics"] == []


# --------------------------------------------------------------------------- #
# categorical_distribution


def test_coerce_categorical_handles_jsonb_shapes() -> None:
    assert _coerce_categorical({"value": "18-24"}) == "18-24"
    assert _coerce_categorical("yes") == "yes"
    assert _coerce_categorical(True) == "true"
    assert _coerce_categorical(False) == "false"
    assert _coerce_categorical(5) == "5"
    assert _coerce_categorical("  spaced  ") == "spaced"
    assert _coerce_categorical("") is None
    assert _coerce_categorical(None) is None
    assert _coerce_categorical([1, 2]) is None


def _mk_db_for_categorical(question_row: dict | None, answer_rows: list[dict]) -> MagicMock:
    db = MagicMock()

    def table(name: str) -> Any:
        chain = MagicMock()
        if name == "questions":
            chain.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
                [question_row] if question_row else []
            )
        elif name == "session_answers":
            chain.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = answer_rows
        return chain

    db.table.side_effect = table
    return db


async def test_categorical_distribution_enum_orders_by_enum_values() -> None:
    db = _mk_db_for_categorical(
        {
            "id": "q-age",
            "metric_key": "age_group",
            "expected_type": "enum",
            "enum_values": ["18-24", "25-34", "35-44", "45+"],
        },
        [
            {"marked_value": {"value": "18-24"}},
            {"marked_value": {"value": "18-24"}},
            {"marked_value": {"value": "25-34"}},
            {"marked_value": {"value": "45+"}},
        ],
    )
    out = await categorical_distribution(
        "age_group",
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    assert out["metric_key"] == "age_group"
    assert out["expected_type"] == "enum"
    assert out["total"] == 4
    assert out["unknown"] == 0
    assert [c["value"] for c in out["categories"]] == ["18-24", "25-34", "35-44", "45+"]
    counts = {c["value"]: c["count"] for c in out["categories"]}
    assert counts == {"18-24": 2, "25-34": 1, "35-44": 0, "45+": 1}
    pcts = {c["value"]: c["pct"] for c in out["categories"]}
    assert pcts["18-24"] == pytest.approx(0.5)
    assert pcts["35-44"] == 0.0


async def test_categorical_distribution_counts_out_of_enum_as_unknown() -> None:
    db = _mk_db_for_categorical(
        {
            "id": "q-freq",
            "metric_key": "visit_frequency",
            "expected_type": "enum",
            "enum_values": ["раз в неделю", "раз в месяц"],
        },
        [
            {"marked_value": {"value": "раз в неделю"}},
            {"marked_value": {"value": "каждый день"}},  # not in enum
            {"marked_value": {"value": "раз в месяц"}},
            {"marked_value": {"value": ""}},  # empty → skipped
        ],
    )
    out = await categorical_distribution(
        "visit_frequency",
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    assert out["total"] == 3
    assert out["unknown"] == 1
    counts = {c["value"]: c["count"] for c in out["categories"]}
    assert counts == {"раз в неделю": 1, "раз в месяц": 1}


async def test_categorical_distribution_boolean_question() -> None:
    db = _mk_db_for_categorical(
        {
            "id": "q-recommend",
            "metric_key": "would_recommend",
            "expected_type": "boolean",
            "enum_values": None,
        },
        [
            {"marked_value": True},
            {"marked_value": True},
            {"marked_value": False},
            {"marked_value": {"value": True}},
        ],
    )
    out = await categorical_distribution(
        "would_recommend",
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    assert out["expected_type"] == "boolean"
    assert out["enum_values"] is None
    counts = {c["value"]: c["count"] for c in out["categories"]}
    assert counts == {"true": 3, "false": 1}
    # sorted desc by count when no enum_values are provided
    assert out["categories"][0]["value"] == "true"


async def test_categorical_distribution_unknown_metric_key() -> None:
    db = _mk_db_for_categorical(None, [])
    out = await categorical_distribution(
        "missing_key",
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    assert out["expected_type"] == "unknown"
    assert out["total"] == 0
    assert out["categories"] == []
    assert out["enum_values"] is None


async def test_categorical_distribution_empty_window() -> None:
    db = _mk_db_for_categorical(
        {
            "id": "q-1",
            "metric_key": "x",
            "expected_type": "enum",
            "enum_values": ["a", "b"],
        },
        [],
    )
    out = await categorical_distribution(
        "x",
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
        db=db,
    )
    assert out["total"] == 0
    # categories still rendered for zero-count enum slots
    assert [c["value"] for c in out["categories"]] == ["a", "b"]
    assert all(c["count"] == 0 for c in out["categories"])


async def test_categorical_distribution_bad_date_range_raises() -> None:
    db = _mk_db_for_categorical(None, [])
    with pytest.raises(ValueError):
        await categorical_distribution(
            "x",
            datetime(2026, 5, 31, tzinfo=UTC),
            datetime(2026, 5, 1, tzinfo=UTC),
            db=db,
        )
