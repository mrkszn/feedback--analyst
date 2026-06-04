"""Unit tests for services.analytics.semantic_search + client_profile.

Pinecone and OpenAI patched at module level; Supabase replaced with MagicMock.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.analytics import client_profile, semantic_search

# --------------------------------------------------------------------------- #
# semantic_search


def _mk_db_for_semantic(session_rows: list[dict], card_rows: list[dict]) -> MagicMock:
    db = MagicMock()

    def table(name: str) -> Any:
        chain = MagicMock()
        if name == "sessions":
            chain.select.return_value.in_.return_value.execute.return_value.data = session_rows
        elif name == "client_cards":
            chain.select.return_value.in_.return_value.execute.return_value.data = card_rows
        return chain

    db.table.side_effect = table
    return db


async def test_semantic_search_joins_sessions_and_cards() -> None:
    matches = [
        {
            "session_id": "sess-1",
            "client_id": 42,
            "score": 0.91,
            "metadata": {"sentiment": "positive"},
        },
        {
            "session_id": "sess-2",
            "client_id": 7,
            "score": 0.80,
            "metadata": {},
        },
    ]
    sessions = [
        {
            "id": "sess-1",
            "client_id": 42,
            "feedback_summary": {"sentiment": "positive", "topics": ["food"]},
            "started_at": "2026-05-20T10:00:00+00:00",
        },
        {
            "id": "sess-2",
            "client_id": 7,
            "feedback_summary": {"sentiment": "negative", "topics": ["service"]},
            "started_at": "2026-05-21T10:00:00+00:00",
        },
    ]
    cards = [
        {"session_id": "sess-1", "summary_text": "Понравилась еда"},
        {"session_id": "sess-2", "summary_text": "Жалоба на сервис"},
    ]
    db = _mk_db_for_semantic(sessions, cards)

    with (
        patch(
            "core.services.analytics.embed_text",
            new=AsyncMock(return_value=[0.1] * 1536),
        ),
        patch(
            "core.services.analytics.query_similar_sessions",
            new=AsyncMock(return_value=matches),
        ),
    ):
        out = await semantic_search("вкусная еда", top_k=5, db=db)

    assert len(out) == 2
    assert out[0]["session_id"] == "sess-1"
    assert out[0]["summary_text"] == "Понравилась еда"
    assert out[0]["sentiment"] == "positive"
    assert out[0]["started_at"] == "2026-05-20T10:00:00+00:00"
    assert out[1]["sentiment"] == "negative"


async def test_semantic_search_empty_query_raises() -> None:
    with pytest.raises(ValueError):
        await semantic_search("   ")


async def test_semantic_search_no_matches_returns_empty() -> None:
    with (
        patch(
            "core.services.analytics.embed_text",
            new=AsyncMock(return_value=[0.0] * 1536),
        ),
        patch(
            "core.services.analytics.query_similar_sessions",
            new=AsyncMock(return_value=[]),
        ),
    ):
        out = await semantic_search("ничего", db=MagicMock())
    assert out == []


# --------------------------------------------------------------------------- #
# client_profile


def _mk_db_for_profile(
    *,
    client_row: dict | None,
    sessions: list[dict],
    cards: list[dict],
) -> MagicMock:
    db = MagicMock()

    def table(name: str) -> Any:
        chain = MagicMock()
        if name == "clients":
            chain.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
                [client_row] if client_row else []
            )
        elif name == "sessions":
            chain.select.return_value.eq.return_value.order.return_value.execute.return_value.data = sessions
        elif name == "client_cards":
            chain.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = cards
        return chain

    db.table.side_effect = table
    return db


async def test_client_profile_unknown_client_raises() -> None:
    db = _mk_db_for_profile(client_row=None, sessions=[], cards=[])
    with pytest.raises(LookupError):
        await client_profile(999, db=db)


async def test_client_profile_aggregates_sentiment_and_topics() -> None:
    db = _mk_db_for_profile(
        client_row={"telegram_id": 42, "name": "Анна"},
        sessions=[
            {
                "id": "s1",
                "started_at": "2026-05-21T10:00:00+00:00",
                "feedback_summary": {"sentiment": "positive", "topics": ["food", "service"]},
            },
            {
                "id": "s2",
                "started_at": "2026-05-20T10:00:00+00:00",
                "feedback_summary": {"sentiment": "negative", "topics": ["service"]},
            },
        ],
        cards=[
            {"session_id": "s1", "summary_text": "Анна. Положительный.", "created_at": "..."},
        ],
    )

    out = await client_profile(42, db=db)
    assert out["telegram_id"] == 42
    assert out["name"] == "Анна"
    assert out["sessions_count"] == 2
    assert out["last_session_at"] == "2026-05-21T10:00:00+00:00"
    assert out["avg_sentiment"] == pytest.approx(0.0)
    topics = {t["topic"]: t["count"] for t in out["top_topics"]}
    assert topics["service"] == 2
    assert topics["food"] == 1
    assert len(out["recent_cards"]) == 1


async def test_client_profile_no_sessions_returns_empty_aggregates() -> None:
    db = _mk_db_for_profile(
        client_row={"telegram_id": 1, "name": None},
        sessions=[],
        cards=[],
    )
    out = await client_profile(1, db=db)
    assert out["sessions_count"] == 0
    assert out["avg_sentiment"] is None
    assert out["recent_cards"] == []
    assert out["top_topics"] == []
    assert out["last_session_at"] is None
