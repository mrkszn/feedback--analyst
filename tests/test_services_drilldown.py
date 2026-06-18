"""Unit tests for the admin drill-down services (backed by InMemoryStorage).

Covers session list/detail (core/services/sessions.py) and the client-list
builders (core/services/analytics.py): by-topic, by-enum-answer, multi-topic
filter, and name/id search.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.services.analytics import (
    filter_clients_by_topics,
    list_clients_by_enum_answer,
    list_clients_by_topic,
    search_clients,
)
from core.services.sessions import _coerce_marked_value, list_sessions, session_detail
from core.storage.adapters.in_memory import InMemoryStorage

WINDOW_FROM = datetime(2026, 6, 1, tzinfo=UTC)
WINDOW_TO = datetime(2026, 6, 30, tzinfo=UTC)


def _seed() -> InMemoryStorage:
    """Two clients, two sessions: Alice (positive, сервис+еда, 'Больше года')
    and Bob (negative, сервис, 'Первый раз')."""
    mem = InMemoryStorage()
    mem.clients += [
        {"telegram_id": 1, "name": "Alice", "created_at": "2026-05-01T00:00:00+00:00"},
        {"telegram_id": 2, "name": "Bob", "created_at": "2026-05-02T00:00:00+00:00"},
    ]
    mem.questions.append(
        {
            "id": "q1",
            "text": "Как давно были у нас?",
            "metric_key": "visit_recency",
            "expected_type": "enum",
            "enum_values": ["Первый раз", "Больше года"],
            "is_active": True,
            "created_at": "2026-05-01T00:00:00+00:00",
        }
    )
    mem.sessions += [
        {
            "id": "s1",
            "client_id": 1,
            "started_at": "2026-06-10T12:00:00+00:00",
            "ended_at": "2026-06-10T12:05:00+00:00",
            "feedback_summary": {
                "summary": "great",
                "sentiment": "positive",
                "topics": ["Сервис", "Еда"],
                "emotion": "joy",
            },
            "feedback_source": "text",
        },
        {
            "id": "s2",
            "client_id": 2,
            "started_at": "2026-06-12T09:00:00+00:00",
            "ended_at": None,
            "feedback_summary": {
                "summary": "long wait",
                "sentiment": "negative",
                "topics": ["Сервис"],
                "emotion": "anger",
            },
            "feedback_source": "voice",
        },
    ]
    mem.session_messages += [
        {
            "id": 1,
            "session_id": "s1",
            "role": "user",
            "content": "Было супер",
            "created_at": "2026-06-10T12:00:01+00:00",
        },
        {
            "id": 2,
            "session_id": "s1",
            "role": "bot",
            "content": "Спасибо!",
            "created_at": "2026-06-10T12:00:05+00:00",
        },
    ]
    mem.session_answers += [
        {
            "id": 1,
            "session_id": "s1",
            "question_id": "q1",
            "answer_text": "Был год назад",
            "marked_value": "Больше года",
            "created_at": "2026-06-10T12:01:00+00:00",
        },
        {
            "id": 2,
            "session_id": "s2",
            "question_id": "q1",
            "answer_text": "Впервые",
            "marked_value": "Первый раз",
            "created_at": "2026-06-12T09:01:00+00:00",
        },
    ]
    mem.client_cards.append(
        {
            "id": "c1",
            "client_id": 1,
            "session_id": "s1",
            "summary_text": "Alice — постоянный гость, доволен сервисом",
            "pinecone_vector_id": "s1",
            "created_at": "2026-06-10T12:06:00+00:00",
        }
    )
    return mem


# --------------------------------------------------------------------------- #
# list_sessions


async def test_list_sessions_returns_enriched_items() -> None:
    mem = _seed()
    rows = await list_sessions(WINDOW_FROM, WINDOW_TO, storage=mem)
    assert [r["id"] for r in rows] == ["s2", "s1"]  # newest first
    s1 = next(r for r in rows if r["id"] == "s1")
    assert s1["client_name"] == "Alice"
    assert s1["sentiment"] == "positive"
    assert s1["topics"] == ["сервис", "еда"]  # normalized lowercase
    assert s1["source"] == "text"


async def test_list_sessions_sentiment_filter_and_pagination() -> None:
    mem = _seed()
    neg = await list_sessions(WINDOW_FROM, WINDOW_TO, sentiment="negative", storage=mem)
    assert [r["id"] for r in neg] == ["s2"]
    page = await list_sessions(WINDOW_FROM, WINDOW_TO, limit=1, offset=1, storage=mem)
    assert [r["id"] for r in page] == ["s1"]  # second-newest after the offset


async def test_list_sessions_rejects_bad_range() -> None:
    mem = _seed()
    with pytest.raises(ValueError, match="date_from"):
        await list_sessions(WINDOW_TO, WINDOW_FROM, storage=mem)


# --------------------------------------------------------------------------- #
# session_detail


async def test_session_detail_full_content() -> None:
    mem = _seed()
    d = await session_detail("s1", storage=mem)
    assert d["client_name"] == "Alice"
    assert d["sentiment"] == "positive"
    assert d["topics"] == ["сервис", "еда"]
    assert [m["content"] for m in d["messages"]] == ["Было супер", "Спасибо!"]
    assert d["answers"][0]["question_text"] == "Как давно были у нас?"
    assert d["answers"][0]["marked_value"] == "Больше года"
    assert "постоянный гость" in (d["card_summary"] or "")


async def test_session_detail_missing_raises() -> None:
    mem = _seed()
    with pytest.raises(LookupError):
        await session_detail("does-not-exist", storage=mem)


# --------------------------------------------------------------------------- #
# _coerce_marked_value


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, None),
        ("Больше года", "Больше года"),
        (5, "5"),
        (4.5, "4.5"),
        (True, "True"),
        ({"value": "Больше года"}, "Больше года"),
        ({"label": "X"}, "X"),
        ({"value": None, "text": "Y"}, "Y"),  # skip null scalar, fall to next key
        (["a", "b"], "a, b"),
        ([{"value": "a"}, "b"], "a, b"),
    ],
)
def test_coerce_marked_value(raw: object, expected: str | None) -> None:
    assert _coerce_marked_value(raw) == expected


def test_coerce_marked_value_unknown_dict_is_json_string() -> None:
    # No value/label/text/name/title key → JSON fallback, but still a string.
    out = _coerce_marked_value({"foo": {"bar": 1}})
    assert out == '{"foo": {"bar": 1}}'


async def test_session_detail_flattens_dict_marked_value() -> None:
    mem = _seed()
    for a in mem.session_answers:
        if a["session_id"] == "s1":
            a["marked_value"] = {"value": "Больше года"}
    d = await session_detail("s1", storage=mem)
    assert d["answers"][0]["marked_value"] == "Больше года"
    assert isinstance(d["answers"][0]["marked_value"], str)


# --------------------------------------------------------------------------- #
# list_clients_by_topic


async def test_list_clients_by_topic_dedup_and_match() -> None:
    mem = _seed()
    serv = await list_clients_by_topic("сервис", WINDOW_FROM, WINDOW_TO, storage=mem)
    assert {r["telegram_id"] for r in serv} == {1, 2}
    eda = await list_clients_by_topic("еда", WINDOW_FROM, WINDOW_TO, storage=mem)
    assert [r["telegram_id"] for r in eda] == [1]
    assert eda[0]["name"] == "Alice"
    assert eda[0]["sessions_count"] == 1


async def test_list_clients_by_topic_sentiment_filter() -> None:
    mem = _seed()
    rows = await list_clients_by_topic(
        "сервис", WINDOW_FROM, WINDOW_TO, sentiment="negative", storage=mem
    )
    assert [r["telegram_id"] for r in rows] == [2]


# --------------------------------------------------------------------------- #
# list_clients_by_enum_answer


async def test_list_clients_by_enum_answer() -> None:
    mem = _seed()
    rows = await list_clients_by_enum_answer(
        "visit_recency", "Больше года", WINDOW_FROM, WINDOW_TO, storage=mem
    )
    assert [r["telegram_id"] for r in rows] == [1]


async def test_list_clients_by_enum_answer_unknown_metric_raises() -> None:
    mem = _seed()
    with pytest.raises(LookupError):
        await list_clients_by_enum_answer("nope", "x", WINDOW_FROM, WINDOW_TO, storage=mem)


async def test_list_clients_by_enum_answer_no_match_is_empty() -> None:
    mem = _seed()
    rows = await list_clients_by_enum_answer(
        "visit_recency", "Меньше месяца", WINDOW_FROM, WINDOW_TO, storage=mem
    )
    assert rows == []


# --------------------------------------------------------------------------- #
# filter_clients_by_topics


async def test_filter_clients_by_topics_and_vs_or() -> None:
    mem = _seed()
    both = await filter_clients_by_topics(
        ["сервис", "еда"], match="and", date_from=WINDOW_FROM, date_to=WINDOW_TO, storage=mem
    )
    assert [r["telegram_id"] for r in both] == [1]  # only Alice has both
    either = await filter_clients_by_topics(
        ["сервис", "еда"], match="or", date_from=WINDOW_FROM, date_to=WINDOW_TO, storage=mem
    )
    assert {r["telegram_id"] for r in either} == {1, 2}


async def test_filter_clients_by_topics_empty_raises() -> None:
    mem = _seed()
    with pytest.raises(ValueError, match="topics"):
        await filter_clients_by_topics(
            [], match="and", date_from=WINDOW_FROM, date_to=WINDOW_TO, storage=mem
        )


# --------------------------------------------------------------------------- #
# search_clients


async def test_search_clients_by_id_and_name() -> None:
    mem = _seed()
    by_id = await search_clients("1", storage=mem)
    assert [r["telegram_id"] for r in by_id] == [1]
    assert by_id[0]["sessions_count"] == 1
    assert by_id[0]["avg_sentiment"] == 1.0

    by_name = await search_clients("ali", storage=mem)
    assert [r["telegram_id"] for r in by_name] == [1]

    assert await search_clients("zzz", storage=mem) == []


async def test_search_clients_empty_query_raises() -> None:
    mem = _seed()
    with pytest.raises(ValueError, match="query"):
        await search_clients("   ", storage=mem)
