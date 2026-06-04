"""Tests for services.statistics.recent_sessions — pure query, no LLM."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from core.services.statistics import recent_sessions

# --------------------------------------------------------------------------- #
# fake supabase client (copied from test_services_statistics.py — keeps tests
# self-contained instead of importing private helpers across test modules)


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


# --------------------------------------------------------------------------- #
# tests


async def test_recent_sessions_happy_limits_and_summary_source() -> None:
    db = _FakeDB(
        {
            "sessions": [
                {
                    "id": "s1",
                    "client_id": 1,
                    "started_at": _ts(2026, 5, 1),
                    "feedback_summary": {"sentiment": "positive", "summary": "fallback-1"},
                },
                {
                    "id": "s2",
                    "client_id": 2,
                    "started_at": _ts(2026, 5, 3),
                    "feedback_summary": {"sentiment": "neutral", "summary": "fallback-2"},
                },
                {
                    "id": "s3",
                    "client_id": 3,
                    "started_at": _ts(2026, 5, 2),
                    "feedback_summary": {"sentiment": "negative", "summary": "fallback-3"},
                },
            ],
            "client_cards": [
                {"session_id": "s2", "summary_text": "card-for-s2"},
            ],
        }
    )

    with patch("core.services.statistics.get_supabase", return_value=db):
        result = await recent_sessions(limit=2, db=None)

    assert len(result) == 2
    # newest first: s2 (05-03), then s3 (05-02)
    assert [r["client_id"] for r in result] == [2, 3]
    # s2 has a client_card → summary from card
    assert result[0]["summary"] == "card-for-s2"
    # s3 has no card → fallback to feedback_summary.summary
    assert result[1]["summary"] == "fallback-3"
    assert result[0]["sentiment"] == "neutral"
    assert result[1]["started_at"] == _ts(2026, 5, 2)


async def test_recent_sessions_sentiment_filter() -> None:
    db = _FakeDB(
        {
            "sessions": [
                {
                    "id": "s1",
                    "client_id": 1,
                    "started_at": _ts(2026, 5, 1),
                    "feedback_summary": {"sentiment": "positive"},
                },
                {
                    "id": "s2",
                    "client_id": 2,
                    "started_at": _ts(2026, 5, 2),
                    "feedback_summary": {"sentiment": "positive"},
                },
                {
                    "id": "s3",
                    "client_id": 3,
                    "started_at": _ts(2026, 5, 3),
                    "feedback_summary": {"sentiment": "negative"},
                },
            ],
            "client_cards": [],
        }
    )

    with patch("core.services.statistics.get_supabase", return_value=db):
        result = await recent_sessions(limit=5, sentiment="negative", db=None)

    assert len(result) == 1
    assert result[0]["client_id"] == 3
    assert result[0]["sentiment"] == "negative"
    assert result[0]["summary"] == ""  # no card, no summary field


async def test_recent_sessions_limit_exceeds_available() -> None:
    db = _FakeDB(
        {
            "sessions": [
                {
                    "id": "s1",
                    "client_id": 1,
                    "started_at": _ts(2026, 5, 1),
                    "feedback_summary": {"sentiment": "positive", "summary": "a"},
                },
                {
                    "id": "s2",
                    "client_id": 2,
                    "started_at": _ts(2026, 5, 2),
                    "feedback_summary": {"sentiment": "neutral", "summary": "b"},
                },
            ],
            "client_cards": [],
        }
    )

    with patch("core.services.statistics.get_supabase", return_value=db):
        result = await recent_sessions(limit=10, db=None)

    assert len(result) == 2


async def test_recent_sessions_invalid_limit_raises() -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        await recent_sessions(limit=0)


async def test_recent_sessions_invalid_sentiment_raises() -> None:
    with pytest.raises(ValueError, match="unknown sentiment"):
        await recent_sessions(sentiment="angry")  # type: ignore[arg-type]


async def test_recent_sessions_empty_db() -> None:
    db = _FakeDB({"sessions": [], "client_cards": []})

    with patch("core.services.statistics.get_supabase", return_value=db):
        result = await recent_sessions(limit=5, db=None)

    assert result == []
