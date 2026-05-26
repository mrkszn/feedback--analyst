"""Phase 3 admin analytics — aggregate Supabase + Pinecone в Python.

Все функции async и принимают опциональный `db: Client` для тестов (паттерн из
`services.questions`). Тяжёлой агрегации в SQL не делаем — MVP-объёмы (<<100к
строк) спокойно агрегируются в памяти, а Supabase REST не даёт удобного
GROUP BY поверх JSONB без RPC. Когда объёмы вырастут — переносим тяжёлые
функции в Postgres views/RPC, сигнатура останется.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, Literal, TypedDict, cast

from supabase import Client

from db.client import get_supabase
from integrations.openai_embed import embed_text
from integrations.pinecone import query_similar_sessions

GroupBy = Literal["day", "week", "none"]
Sentiment = Literal["positive", "neutral", "negative"]

_SENTIMENT_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
}


class MetricPoint(TypedDict):
    bucket: str
    count: int
    avg: float | None
    min: float | None
    max: float | None


class TopicCount(TypedDict):
    topic: str
    count: int
    avg_sentiment: float


class SummaryOverview(TypedDict):
    sessions_count: int
    avg_sentiment: float | None
    top_positive_topics: list[TopicCount]
    top_negative_topics: list[TopicCount]


class SemanticHit(TypedDict):
    session_id: str
    client_id: int | None
    score: float
    summary_text: str
    sentiment: str | None
    started_at: str | None


class ClientProfile(TypedDict):
    telegram_id: int
    name: str | None
    sessions_count: int
    last_session_at: str | None
    avg_sentiment: float | None
    recent_cards: list[dict[str, Any]]
    top_topics: list[TopicCount]


# --------------------------------------------------------------------------- #
# helpers


def _bucket_for(ts: str | datetime, group_by: GroupBy) -> str:
    if group_by == "none":
        return "all"
    if isinstance(ts, str):
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    else:
        dt = ts
    if group_by == "week":
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return dt.date().isoformat()


def _coerce_numeric(value: Any) -> float | None:
    """marked_value is JSONB — может быть int/float/bool/str/dict/None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, dict):
        return _coerce_numeric(value.get("value"))
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------- #
# aggregate_metric


async def aggregate_metric(
    metric_key: str,
    date_from: datetime,
    date_to: datetime,
    group_by: GroupBy = "day",
    *,
    db: Client | None = None,
) -> list[MetricPoint]:
    """Aggregate session_answers.marked_value для вопроса с заданным
    metric_key. Возвращает список бакетов с count/avg/min/max (avg/min/max =
    None если ответы нечисловые, например text вопрос).
    """
    if not metric_key.strip():
        raise ValueError("metric_key must not be empty")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if group_by not in ("day", "week", "none"):
        raise ValueError(f"unknown group_by {group_by!r}")

    db = db or get_supabase()

    def _q_questions() -> Any:
        return (
            db.table("questions")
            .select("id, metric_key")
            .eq("metric_key", metric_key)
            .limit(1)
            .execute()
        )

    q_resp = await asyncio.to_thread(_q_questions)
    if not q_resp.data:
        return []
    question_id = q_resp.data[0]["id"]

    iso_from = date_from.isoformat()
    iso_to = date_to.isoformat()

    def _q_answers() -> Any:
        return (
            db.table("session_answers")
            .select("created_at, marked_value")
            .eq("question_id", question_id)
            .gte("created_at", iso_from)
            .lte("created_at", iso_to)
            .execute()
        )

    a_resp = await asyncio.to_thread(_q_answers)
    rows = list(a_resp.data or [])

    buckets: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        bucket = _bucket_for(r.get("created_at") or iso_from, group_by)
        counts[bucket] += 1
        num = _coerce_numeric(r.get("marked_value"))
        if num is not None:
            buckets[bucket].append(num)

    out: list[MetricPoint] = []
    for bucket in sorted(counts.keys()):
        values = buckets.get(bucket, [])
        out.append(
            MetricPoint(
                bucket=bucket,
                count=counts[bucket],
                avg=(sum(values) / len(values)) if values else None,
                min=min(values) if values else None,
                max=max(values) if values else None,
            )
        )
    return out


# --------------------------------------------------------------------------- #
# topic_histogram


async def topic_histogram(
    date_from: datetime,
    date_to: datetime,
    sentiment_filter: Sentiment | None = None,
    *,
    db: Client | None = None,
) -> list[TopicCount]:
    """Подсчёт упоминаний топиков из `sessions.feedback_summary.topics[]`.
    Опционально фильтрует сессии по sentiment перед агрегацией — удобно для
    `top complaints` (sentiment_filter="negative").
    """
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if sentiment_filter is not None and sentiment_filter not in _SENTIMENT_SCORE:
        raise ValueError(f"unknown sentiment_filter {sentiment_filter!r}")

    db = db or get_supabase()
    iso_from = date_from.isoformat()
    iso_to = date_to.isoformat()

    def _q() -> Any:
        return (
            db.table("sessions")
            .select("feedback_summary, started_at")
            .gte("started_at", iso_from)
            .lte("started_at", iso_to)
            .not_.is_("feedback_summary", "null")
            .execute()
        )

    resp = await asyncio.to_thread(_q)
    rows = list(resp.data or [])

    topic_counts: dict[str, int] = defaultdict(int)
    topic_sentiments: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        summary = r.get("feedback_summary") or {}
        if not isinstance(summary, dict):
            continue
        sentiment = summary.get("sentiment")
        if sentiment_filter is not None and sentiment != sentiment_filter:
            continue
        topics = summary.get("topics") or []
        if not isinstance(topics, list):
            continue
        score = _SENTIMENT_SCORE.get(str(sentiment), 0.0)
        for t in topics:
            if not isinstance(t, str) or not t.strip():
                continue
            key = t.strip().lower()
            topic_counts[key] += 1
            topic_sentiments[key].append(score)

    out: list[TopicCount] = []
    for topic, count in topic_counts.items():
        scores = topic_sentiments[topic]
        out.append(
            TopicCount(
                topic=topic,
                count=count,
                avg_sentiment=(sum(scores) / len(scores)) if scores else 0.0,
            )
        )
    out.sort(key=lambda x: x["count"], reverse=True)
    return out


# --------------------------------------------------------------------------- #
# summary_overview


async def summary_overview(
    date_from: datetime,
    date_to: datetime,
    *,
    db: Client | None = None,
) -> SummaryOverview:
    """Одна сводка для /insights — sessions count, avg sentiment, top-3
    положительных/отрицательных топика за период.
    """
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")

    db = db or get_supabase()
    iso_from = date_from.isoformat()
    iso_to = date_to.isoformat()

    def _q() -> Any:
        return (
            db.table("sessions")
            .select("feedback_summary, started_at")
            .gte("started_at", iso_from)
            .lte("started_at", iso_to)
            .execute()
        )

    resp = await asyncio.to_thread(_q)
    rows = list(resp.data or [])
    sessions_count = len(rows)

    sentiments: list[float] = []
    for r in rows:
        summary = r.get("feedback_summary")
        if isinstance(summary, dict):
            sent = summary.get("sentiment")
            score = _SENTIMENT_SCORE.get(str(sent))
            if score is not None:
                sentiments.append(score)

    avg_sentiment = (sum(sentiments) / len(sentiments)) if sentiments else None

    pos_topics = await topic_histogram(date_from, date_to, sentiment_filter="positive", db=db)
    neg_topics = await topic_histogram(date_from, date_to, sentiment_filter="negative", db=db)

    return cast(
        SummaryOverview,
        {
            "sessions_count": sessions_count,
            "avg_sentiment": avg_sentiment,
            "top_positive_topics": pos_topics[:3],
            "top_negative_topics": neg_topics[:3],
        },
    )


# --------------------------------------------------------------------------- #
# semantic_search


async def semantic_search(
    query_text: str,
    top_k: int = 20,
    *,
    db: Client | None = None,
) -> list[SemanticHit]:
    """Natural-language поиск по client-cards. Embed → Pinecone query →
    JOIN с Supabase sessions + client_cards для контекста (summary_text,
    sentiment, started_at).
    """
    if not query_text.strip():
        raise ValueError("query_text must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    vector = await embed_text(query_text.strip())
    matches = await query_similar_sessions(vector=vector, top_k=top_k)
    if not matches:
        return []

    session_ids = [m["session_id"] for m in matches if m["session_id"]]
    if not session_ids:
        return []

    db = db or get_supabase()

    def _q_sessions() -> Any:
        return (
            db.table("sessions")
            .select("id, client_id, feedback_summary, started_at")
            .in_("id", session_ids)
            .execute()
        )

    def _q_cards() -> Any:
        return (
            db.table("client_cards")
            .select("session_id, summary_text")
            .in_("session_id", session_ids)
            .execute()
        )

    s_resp, c_resp = await asyncio.gather(
        asyncio.to_thread(_q_sessions),
        asyncio.to_thread(_q_cards),
    )
    sessions_by_id: dict[str, dict[str, Any]] = {str(r["id"]): r for r in (s_resp.data or [])}
    cards_by_session: dict[str, str] = {
        str(r["session_id"]): str(r.get("summary_text") or "") for r in (c_resp.data or [])
    }

    out: list[SemanticHit] = []
    for m in matches:
        sid = m["session_id"]
        sess = sessions_by_id.get(sid) or {}
        summary = sess.get("feedback_summary") or {}
        sentiment = summary.get("sentiment") if isinstance(summary, dict) else None
        out.append(
            SemanticHit(
                session_id=sid,
                client_id=m.get("client_id") or sess.get("client_id"),
                score=m["score"],
                summary_text=cards_by_session.get(sid, ""),
                sentiment=str(sentiment) if sentiment else None,
                started_at=str(sess.get("started_at")) if sess.get("started_at") else None,
            )
        )
    return out


# --------------------------------------------------------------------------- #
# client_profile


async def client_profile(
    telegram_id: int,
    *,
    recent_cards_limit: int = 3,
    db: Client | None = None,
) -> ClientProfile:
    """Полный профиль клиента: все сессии + последние N карточек + сводка
    (avg sentiment, top topics). LookupError если клиент не найден.
    """
    if recent_cards_limit <= 0:
        raise ValueError("recent_cards_limit must be positive")

    db = db or get_supabase()

    def _q_client() -> Any:
        return (
            db.table("clients")
            .select("telegram_id, name")
            .eq("telegram_id", telegram_id)
            .limit(1)
            .execute()
        )

    c_resp = await asyncio.to_thread(_q_client)
    if not c_resp.data:
        raise LookupError(f"client {telegram_id} not found")
    client_row = c_resp.data[0]

    def _q_sessions() -> Any:
        return (
            db.table("sessions")
            .select("id, started_at, feedback_summary")
            .eq("client_id", telegram_id)
            .order("started_at", desc=True)
            .execute()
        )

    def _q_cards() -> Any:
        return (
            db.table("client_cards")
            .select("session_id, summary_text, created_at")
            .eq("client_id", telegram_id)
            .order("created_at", desc=True)
            .limit(recent_cards_limit)
            .execute()
        )

    s_resp, c2_resp = await asyncio.gather(
        asyncio.to_thread(_q_sessions),
        asyncio.to_thread(_q_cards),
    )
    sessions = list(s_resp.data or [])
    cards = list(c2_resp.data or [])

    last_session_at = (
        str(sessions[0]["started_at"]) if sessions and sessions[0].get("started_at") else None
    )

    sentiments: list[float] = []
    topic_counts: dict[str, int] = defaultdict(int)
    topic_sentiments: dict[str, list[float]] = defaultdict(list)
    for s in sessions:
        summary = s.get("feedback_summary")
        if not isinstance(summary, dict):
            continue
        sent = summary.get("sentiment")
        score = _SENTIMENT_SCORE.get(str(sent))
        if score is not None:
            sentiments.append(score)
        topics = summary.get("topics") or []
        if not isinstance(topics, list):
            continue
        for t in topics:
            if not isinstance(t, str) or not t.strip():
                continue
            key = t.strip().lower()
            topic_counts[key] += 1
            topic_sentiments[key].append(score if score is not None else 0.0)

    top_topics: list[TopicCount] = []
    for topic, count in topic_counts.items():
        scores = topic_sentiments[topic]
        top_topics.append(
            TopicCount(
                topic=topic,
                count=count,
                avg_sentiment=(sum(scores) / len(scores)) if scores else 0.0,
            )
        )
    top_topics.sort(key=lambda x: x["count"], reverse=True)

    return cast(
        ClientProfile,
        {
            "telegram_id": int(client_row["telegram_id"]),
            "name": client_row.get("name"),
            "sessions_count": len(sessions),
            "last_session_at": last_session_at,
            "avg_sentiment": (sum(sentiments) / len(sentiments)) if sentiments else None,
            "recent_cards": cards,
            "top_topics": top_topics[:5],
        },
    )
