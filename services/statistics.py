"""Full report aggregator for /statistics.

Single function `full_report(date_from, date_to)` собирает разом:
- активность (sessions started/finished, уникальных клиентов, возвращающихся)
- распределение sentiment'ов
- разбивку по топикам (positive / neutral / negative)
- сводку по каждому активному вопросу (number → avg/min/max,
  enum/boolean → топ-значение + распределение, text → response rate)
- последние N резюме отзывов

Период `date_from=None` → от самой ранней `sessions.started_at` (= «всё время»).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, Literal, TypedDict, cast

from supabase import Client

from db.client import get_supabase

Sentiment = Literal["positive", "neutral", "negative"]

_SENTIMENT_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
}


class SentimentCounts(TypedDict):
    positive: int
    neutral: int
    negative: int


class ActivityBlock(TypedDict):
    sessions_started: int
    sessions_finished: int
    unique_clients: int
    returning_clients: int  # клиенты с >= 2 сессий в периоде


class TopicRow(TypedDict):
    topic: str
    count: int
    avg_sentiment: float


class MetricSummary(TypedDict):
    metric_key: str
    text: str
    expected_type: str
    n: int
    # number-only
    avg: float | None
    min: float | None
    max: float | None
    # enum/boolean only
    top_value: str | None
    top_pct: float | None
    distribution: list[dict[str, Any]] | None
    # text only
    response_rate: float | None


class RecentSession(TypedDict):
    started_at: str | None
    sentiment: str | None
    summary: str
    client_id: int | None


class FullReport(TypedDict):
    period_label: str
    date_from: str | None  # ISO; None если БД пуста
    date_to: str  # ISO (now или фактический end)
    activity: ActivityBlock
    sentiment_counts: SentimentCounts
    sentiment_total: int
    avg_sentiment: float | None
    topics_positive: list[TopicRow]
    topics_neutral: list[TopicRow]
    topics_negative: list[TopicRow]
    metrics: list[MetricSummary]
    recent_sessions: list[RecentSession]


# --------------------------------------------------------------------------- #
# helpers


async def _earliest_started_at(db: Client) -> datetime | None:
    """Возвращает самую раннюю `sessions.started_at` или None (БД пуста)."""

    def _q() -> Any:
        return (
            db.table("sessions")
            .select("started_at")
            .order("started_at", desc=False)
            .limit(1)
            .execute()
        )

    resp = await asyncio.to_thread(_q)
    rows = resp.data or []
    if not rows:
        return None
    raw = rows[0].get("started_at")
    if not raw:
        return None
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


def _classify_topic(rows: list[TopicRow]) -> tuple[list[TopicRow], list[TopicRow], list[TopicRow]]:
    """Разбивает топики по знаку avg_sentiment (порог ±0.33).

    Возвращает (positive, neutral, negative), каждый отсортирован по count desc.
    """
    pos: list[TopicRow] = []
    neu: list[TopicRow] = []
    neg: list[TopicRow] = []
    for t in rows:
        s = float(t.get("avg_sentiment") or 0.0)
        if s > 0.33:
            pos.append(t)
        elif s < -0.33:
            neg.append(t)
        else:
            neu.append(t)
    for bucket in (pos, neu, neg):
        bucket.sort(key=lambda x: x["count"], reverse=True)
    return pos, neu, neg


def _summarize_topics(sessions_rows: list[dict[str, Any]]) -> list[TopicRow]:
    """Группирует topics из feedback_summary.topics[] с avg sentiment."""
    counts: dict[str, int] = defaultdict(int)
    sentiments: dict[str, list[float]] = defaultdict(list)
    for r in sessions_rows:
        summary = r.get("feedback_summary") or {}
        if not isinstance(summary, dict):
            continue
        sent = summary.get("sentiment")
        score = _SENTIMENT_SCORE.get(str(sent), 0.0)
        topics = summary.get("topics") or []
        if not isinstance(topics, list):
            continue
        for t in topics:
            if not isinstance(t, str) or not t.strip():
                continue
            key = t.strip().lower()
            counts[key] += 1
            sentiments[key].append(score)
    out: list[TopicRow] = []
    for topic, count in counts.items():
        scores = sentiments[topic]
        out.append(
            TopicRow(
                topic=topic,
                count=count,
                avg_sentiment=(sum(scores) / len(scores)) if scores else 0.0,
            )
        )
    out.sort(key=lambda x: x["count"], reverse=True)
    return out


def _classify_value(value: Any) -> str | None:
    """marked_value → categorical label (для enum/boolean)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, dict):
        return _classify_value(value.get("value"))
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return None


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, dict):
        return _to_number(value.get("value"))
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _summarize_metric(question: dict[str, Any], answers: list[dict[str, Any]]) -> MetricSummary:
    metric_key = str(question["metric_key"])
    expected = str(question.get("expected_type") or "unknown")
    text = str(question.get("text") or metric_key)
    n = len(answers)
    base = MetricSummary(
        metric_key=metric_key,
        text=text,
        expected_type=expected,
        n=n,
        avg=None,
        min=None,
        max=None,
        top_value=None,
        top_pct=None,
        distribution=None,
        response_rate=None,
    )
    if n == 0:
        return base

    if expected == "number":
        values = [v for v in (_to_number(a.get("marked_value")) for a in answers) if v is not None]
        if values:
            base["avg"] = sum(values) / len(values)
            base["min"] = min(values)
            base["max"] = max(values)
        return base

    if expected in ("enum", "boolean"):
        counts: dict[str, int] = defaultdict(int)
        for a in answers:
            label = _classify_value(a.get("marked_value"))
            if label is None:
                continue
            counts[label] += 1
        total = sum(counts.values()) or 1
        distribution = sorted(
            ({"value": k, "count": v, "pct": v / total} for k, v in counts.items()),
            key=lambda d: cast(int, d["count"]),
            reverse=True,
        )
        base["distribution"] = list(distribution)
        if distribution:
            top = distribution[0]
            base["top_value"] = str(top["value"])
            base["top_pct"] = float(cast(float, top["pct"]))
        return base

    # text question — only "responded vs skipped" makes sense
    responded = sum(1 for a in answers if (a.get("answer_text") or "").strip())
    base["response_rate"] = responded / n if n else None
    return base


# --------------------------------------------------------------------------- #
# main entry


async def full_report(
    date_from: datetime | None,
    date_to: datetime,
    *,
    period_label: str = "период",
    recent_limit: int = 5,
    db: Client | None = None,
) -> FullReport:
    """Собирает полный отчёт за окно [date_from, date_to].

    `date_from=None` → от MIN(sessions.started_at). Если БД пуста — оба поля
    равны `date_to` (now), все блоки нулевые.
    """
    if date_from is not None and date_from > date_to:
        raise ValueError("date_from must be <= date_to")

    db = db or get_supabase()

    if date_from is None:
        date_from = await _earliest_started_at(db) or date_to

    iso_from = date_from.isoformat()
    iso_to = date_to.isoformat()

    def _q_sessions() -> Any:
        return (
            db.table("sessions")
            .select("id, client_id, started_at, ended_at, feedback_summary")
            .gte("started_at", iso_from)
            .lte("started_at", iso_to)
            .order("started_at", desc=True)
            .execute()
        )

    def _q_cards() -> Any:
        # клиентские карточки финализированных сессий — берём summary_text
        return (
            db.table("client_cards")
            .select("session_id, summary_text, created_at")
            .order("created_at", desc=True)
            .limit(recent_limit * 4)  # подушка на случай если сессия вне периода
            .execute()
        )

    def _q_questions() -> Any:
        return (
            db.table("questions")
            .select("id, text, metric_key, expected_type, enum_values, is_active")
            .eq("is_active", True)
            .execute()
        )

    s_resp, c_resp, q_resp = await asyncio.gather(
        asyncio.to_thread(_q_sessions),
        asyncio.to_thread(_q_cards),
        asyncio.to_thread(_q_questions),
    )

    sessions = list(s_resp.data or [])
    cards = list(c_resp.data or [])
    questions = list(q_resp.data or [])

    # ---------- activity ----------
    sessions_started = len(sessions)
    sessions_finished = sum(1 for s in sessions if s.get("ended_at"))
    client_session_count: dict[int, int] = defaultdict(int)
    for s in sessions:
        cid = s.get("client_id")
        if cid is not None:
            client_session_count[int(cid)] += 1
    unique_clients = len(client_session_count)
    returning_clients = sum(1 for n in client_session_count.values() if n >= 2)

    activity = ActivityBlock(
        sessions_started=sessions_started,
        sessions_finished=sessions_finished,
        unique_clients=unique_clients,
        returning_clients=returning_clients,
    )

    # ---------- sentiment ----------
    sentiment_counts = SentimentCounts(positive=0, neutral=0, negative=0)
    sentiment_scores: list[float] = []
    for s in sessions:
        summary = s.get("feedback_summary") or {}
        if not isinstance(summary, dict):
            continue
        sent = summary.get("sentiment")
        if sent == "positive":
            sentiment_counts["positive"] += 1
        elif sent == "neutral":
            sentiment_counts["neutral"] += 1
        elif sent == "negative":
            sentiment_counts["negative"] += 1
        score = _SENTIMENT_SCORE.get(str(sent))
        if score is not None:
            sentiment_scores.append(score)

    sentiment_total = (
        sentiment_counts["positive"] + sentiment_counts["neutral"] + sentiment_counts["negative"]
    )
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None

    # ---------- topics ----------
    all_topics = _summarize_topics(sessions)
    pos_topics, neu_topics, neg_topics = _classify_topic(all_topics)

    # ---------- metrics ----------
    if questions and sessions:
        session_ids = [str(s["id"]) for s in sessions]
        question_ids = [str(q["id"]) for q in questions]

        def _q_answers() -> Any:
            return (
                db.table("session_answers")
                .select("question_id, answer_text, marked_value")
                .in_("session_id", session_ids)
                .in_("question_id", question_ids)
                .execute()
            )

        a_resp = await asyncio.to_thread(_q_answers)
        answers = list(a_resp.data or [])
        answers_by_qid: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for a in answers:
            qid = str(a.get("question_id") or "")
            if qid:
                answers_by_qid[qid].append(a)
        metrics = [_summarize_metric(q, answers_by_qid.get(str(q["id"]), [])) for q in questions]
    else:
        metrics = [_summarize_metric(q, []) for q in questions]

    # ---------- recent sessions ----------
    cards_by_sid: dict[str, str] = {
        str(c.get("session_id") or ""): str(c.get("summary_text") or "") for c in cards
    }
    recent: list[RecentSession] = []
    for s in sessions[:recent_limit]:
        summary = s.get("feedback_summary") or {}
        sent = summary.get("sentiment") if isinstance(summary, dict) else None
        sid = str(s.get("id") or "")
        card_text = cards_by_sid.get(sid, "")
        if not card_text and isinstance(summary, dict):
            card_text = str(summary.get("summary") or "")
        recent.append(
            RecentSession(
                started_at=str(s.get("started_at")) if s.get("started_at") else None,
                sentiment=str(sent) if sent else None,
                summary=card_text,
                client_id=int(s["client_id"]) if s.get("client_id") is not None else None,
            )
        )

    return FullReport(
        period_label=period_label,
        date_from=iso_from if sessions_started > 0 or date_from != date_to else None,
        date_to=iso_to,
        activity=activity,
        sentiment_counts=sentiment_counts,
        sentiment_total=sentiment_total,
        avg_sentiment=avg_sentiment,
        topics_positive=pos_topics,
        topics_neutral=neu_topics,
        topics_negative=neg_topics,
        metrics=metrics,
        recent_sessions=recent,
    )


# --------------------------------------------------------------------------- #
# recent_sessions


async def recent_sessions(
    limit: int = 5,
    sentiment: Sentiment | None = None,
    *,
    db: Client | None = None,
) -> list[RecentSession]:
    """Последние N сессий (по started_at desc), опц. с фильтром по sentiment.

    Фильтр по `feedback_summary.sentiment` применяется в Python после выборки
    (Supabase REST неудобно фильтрует по вложенному JSONB). summary_text берётся
    из `client_cards` по session_id, fallback — `feedback_summary.summary`.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")
    if sentiment is not None and sentiment not in _SENTIMENT_SCORE:
        raise ValueError(f"unknown sentiment {sentiment!r}")

    db = db or get_supabase()

    def _q_sessions() -> Any:
        return (
            db.table("sessions")
            .select("id, client_id, started_at, feedback_summary")
            .order("started_at", desc=True)
            .limit(limit * 4)
            .execute()
        )

    s_resp = await asyncio.to_thread(_q_sessions)
    sessions = list(s_resp.data or [])

    selected: list[dict[str, Any]] = []
    for s in sessions:
        summary = s.get("feedback_summary") or {}
        sent = summary.get("sentiment") if isinstance(summary, dict) else None
        if sentiment is not None and sent != sentiment:
            continue
        selected.append(s)
        if len(selected) >= limit:
            break

    if not selected:
        return []

    session_ids = [str(s["id"]) for s in selected]

    def _q_cards() -> Any:
        return (
            db.table("client_cards")
            .select("session_id, summary_text")
            .in_("session_id", session_ids)
            .execute()
        )

    c_resp = await asyncio.to_thread(_q_cards)
    cards_by_sid: dict[str, str] = {
        str(c.get("session_id") or ""): str(c.get("summary_text") or "")
        for c in (c_resp.data or [])
    }

    out: list[RecentSession] = []
    for s in selected:
        summary = s.get("feedback_summary") or {}
        sent = summary.get("sentiment") if isinstance(summary, dict) else None
        sid = str(s.get("id") or "")
        card_text = cards_by_sid.get(sid, "")
        if not card_text and isinstance(summary, dict):
            card_text = str(summary.get("summary") or "")
        out.append(
            RecentSession(
                started_at=str(s.get("started_at")) if s.get("started_at") else None,
                sentiment=str(sent) if sent else None,
                summary=card_text,
                client_id=int(s["client_id"]) if s.get("client_id") is not None else None,
            )
        )
    return out
