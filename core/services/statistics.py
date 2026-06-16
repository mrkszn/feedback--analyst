"""Full report aggregator for /statistics.

Single function `full_report(date_from, date_to)` собирает разом:
- активность (sessions started/finished, уникальных клиентов, возвращающихся)
- распределение sentiment'ов
- разбивку по топикам (positive / neutral / negative)
- сводку по каждому активному вопросу (number → avg/min/max,
  enum/boolean → топ-значение + распределение, text → response rate)
- последние N резюме отзывов

Период `date_from=None` → от самой ранней `sessions.started_at` (= «всё время»).

DI: `storage: StorageAdapter | None` (new) + `db: Client | None` (back-compat).
`get_supabase` остаётся импортированным — это патч-точка существующих тестов.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime
from typing import Any, Literal, TypedDict, cast

from supabase import Client

from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter
from core.storage.supabase_client import get_supabase

Sentiment = Literal["positive", "neutral", "negative"]

_SENTIMENT_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
}


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db or get_supabase())


class SentimentCounts(TypedDict):
    positive: int
    neutral: int
    negative: int


class ActivityBlock(TypedDict):
    sessions_started: int
    sessions_finished: int
    unique_clients: int
    returning_clients: int  # клиенты с >= 2 сессий в периоде


class LoopMetrics(TypedDict):
    """Recurrence metrics — does the feedback loop actually repeat?

    Все три считаются по сессиям ВНУТРИ окна (не глобально по клиенту):
    - repeat_rate — доля клиентов с ≥2 сессиями (returning/unique), 0..1;
    - sessions_per_client — sessions_started / unique_clients;
    - median_days_to_2nd — медиана разрыва (в днях) между 1-й и 2-й сессией
      вернувшихся клиентов; None если вернувшихся нет.
    """

    repeat_rate: float
    sessions_per_client: float
    median_days_to_2nd: float | None


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
    loop: LoopMetrics
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


def _median(values: list[float]) -> float | None:
    """Median of a list of floats, or None when empty."""
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _parse_ts(raw: Any) -> datetime | None:
    """Parse an ISO `started_at` (handles trailing Z); None on bad/empty input."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _loop_metrics(
    sessions: list[dict[str, Any]],
    *,
    sessions_started: int,
    unique_clients: int,
    returning_clients: int,
) -> LoopMetrics:
    """Recurrence metrics from window sessions (see LoopMetrics docstring)."""
    repeat_rate = (returning_clients / unique_clients) if unique_clients else 0.0
    sessions_per_client = (sessions_started / unique_clients) if unique_clients else 0.0

    # First-to-second-session gap (days) per returning client.
    starts_by_client: dict[int, list[datetime]] = defaultdict(list)
    for s in sessions:
        cid = s.get("client_id")
        ts = _parse_ts(s.get("started_at"))
        if cid is not None and ts is not None:
            starts_by_client[int(cid)].append(ts)
    gaps: list[float] = []
    for starts in starts_by_client.values():
        if len(starts) < 2:
            continue
        starts.sort()
        gaps.append((starts[1] - starts[0]).total_seconds() / 86400.0)

    return LoopMetrics(
        repeat_rate=repeat_rate,
        sessions_per_client=sessions_per_client,
        median_days_to_2nd=_median(gaps),
    )


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
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> FullReport:
    """Собирает полный отчёт за окно [date_from, date_to].

    `date_from=None` → от MIN(sessions.started_at). Если БД пуста — оба поля
    равны `date_to` (now), все блоки нулевые.
    """
    if date_from is not None and date_from > date_to:
        raise ValueError("date_from must be <= date_to")

    store = _storage(storage, db)

    if date_from is None:
        raw_earliest = await store.earliest_session_started_at()
        if raw_earliest:
            date_from = datetime.fromisoformat(raw_earliest.replace("Z", "+00:00"))
        else:
            date_from = date_to

    iso_from = date_from.isoformat()
    iso_to = date_to.isoformat()

    sessions = await store.fetch_sessions_in_window_ordered(
        date_from=iso_from,
        date_to=iso_to,
        columns="id, client_id, started_at, ended_at, feedback_summary",
    )
    cards = await store.fetch_recent_cards(
        columns="session_id, summary_text, created_at",
        limit=recent_limit * 4,  # подушка на случай если сессия вне периода
    )
    questions = await store.list_questions(active_only=True)

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

    loop = _loop_metrics(
        sessions,
        sessions_started=sessions_started,
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

        answers = await store.fetch_answers_for_sessions(
            session_ids=session_ids,
            question_ids=question_ids,
            columns="question_id, answer_text, marked_value",
        )
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
        loop=loop,
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
    storage: StorageAdapter | None = None,
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

    store = _storage(storage, db)

    sessions = await store.fetch_recent_sessions(
        columns="id, client_id, started_at, feedback_summary",
        limit=limit * 4,
    )

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

    cards_rows = await store.fetch_cards_by_sessions(
        session_ids=session_ids,
        columns="session_id, summary_text",
    )
    cards_by_sid: dict[str, str] = {
        str(c.get("session_id") or ""): str(c.get("summary_text") or "") for c in cards_rows
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


# --------------------------------------------------------------------------- #
# CSV export


def _fmt_num(value: float | None) -> str:
    return "" if value is None else f"{value:g}"


def build_csv_report(report: FullReport) -> str:
    """Render a `FullReport` as a multi-section CSV string.

    Three `#`-prefixed sections: Sessions (recent only — `FullReport` does not
    carry the full session list), Metrics (one row per category for enum/boolean,
    one row per question for number/text), Topics (positive/neutral/negative
    flattened with their sign as `sentiment_filter`). Encode with `utf-8-sig`
    at the call site so Excel reads Cyrillic correctly.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)

    # ---------- Loop (recurrence) ----------
    loop = report.get("loop")
    if loop is not None:
        writer.writerow(["# Loop"])
        writer.writerow(["metric", "value"])
        writer.writerow(["repeat_rate", _fmt_num(loop["repeat_rate"])])
        writer.writerow(["sessions_per_client", _fmt_num(loop["sessions_per_client"])])
        writer.writerow(["median_days_to_2nd", _fmt_num(loop["median_days_to_2nd"])])
        writer.writerow([])

    # ---------- Sessions ----------
    writer.writerow(["# Sessions"])
    writer.writerow(["date", "client_id", "sentiment", "topics", "summary_text"])
    for s in report["recent_sessions"]:
        date = (s["started_at"] or "")[:10]
        summary_text = (s["summary"] or "").strip().replace("\n", " ")
        writer.writerow(
            [
                date,
                "" if s["client_id"] is None else str(s["client_id"]),
                s["sentiment"] or "",
                "",  # per-session topics are not part of FullReport
                summary_text,
            ]
        )

    # ---------- Metrics ----------
    writer.writerow([])
    writer.writerow(["# Metrics"])
    writer.writerow(
        [
            "question_text",
            "metric_key",
            "expected_type",
            "total",
            "category",
            "count",
            "pct",
            "avg",
            "min",
            "max",
        ]
    )
    for m in report["metrics"]:
        if m["expected_type"] in ("enum", "boolean"):
            distribution = m["distribution"] or []
            if not distribution:
                writer.writerow(
                    [m["text"], m["metric_key"], m["expected_type"], m["n"], "", "", "", "", "", ""]
                )
            for d in distribution:
                writer.writerow(
                    [
                        m["text"],
                        m["metric_key"],
                        m["expected_type"],
                        m["n"],
                        d["value"],
                        d["count"],
                        _fmt_num(d.get("pct")),
                        "",
                        "",
                        "",
                    ]
                )
        elif m["expected_type"] == "number":
            writer.writerow(
                [
                    m["text"],
                    m["metric_key"],
                    m["expected_type"],
                    m["n"],
                    "",
                    "",
                    "",
                    _fmt_num(m["avg"]),
                    _fmt_num(m["min"]),
                    _fmt_num(m["max"]),
                ]
            )
        else:
            writer.writerow(
                [m["text"], m["metric_key"], m["expected_type"], m["n"], "", "", "", "", "", ""]
            )

    # ---------- Topics ----------
    writer.writerow([])
    writer.writerow(["# Topics"])
    writer.writerow(["topic", "sentiment_filter", "count", "avg_sentiment"])
    topic_buckets: list[tuple[str, list[TopicRow]]] = [
        ("positive", report["topics_positive"]),
        ("neutral", report["topics_neutral"]),
        ("negative", report["topics_negative"]),
    ]
    for sentiment_filter, rows in topic_buckets:
        for t in rows:
            writer.writerow(
                [t["topic"], sentiment_filter, t["count"], _fmt_num(t["avg_sentiment"])]
            )

    return buf.getvalue()
