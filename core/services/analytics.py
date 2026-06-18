"""Phase 3 admin analytics — aggregate Supabase + Pinecone в Python.

Все функции async и принимают `storage: StorageAdapter | None` (новый DI-шов) и
`db: Client | None` (back-compat). Тяжёлой агрегации в SQL не делаем — MVP-объёмы
(<<100к строк) спокойно агрегируются в памяти; storage только отдаёт строки.

`embed_text` / `query_similar_sessions` импортируются на уровне модуля и зовутся
напрямую (см. core/storage/vector/* для Protocol-обёртки, используемой в каналах).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Literal, TypedDict, cast

from supabase import Client

from core.integrations.openai_embed import embed_text
from core.integrations.pinecone import query_similar_sessions
from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter

GroupBy = Literal["day", "week", "none"]
Sentiment = Literal["positive", "neutral", "negative"]

_SENTIMENT_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
}


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


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


class CategoryCount(TypedDict):
    value: str
    count: int
    pct: float


class CategoricalDistribution(TypedDict):
    metric_key: str
    expected_type: str
    total: int
    categories: list[CategoryCount]
    unknown: int  # answers whose marked_value didn't match any enum_value
    enum_values: list[str] | None  # canonical list from questions.enum_values


class ClientListItem(TypedDict):
    telegram_id: int
    name: str | None
    sessions_count: int
    last_session_at: str | None
    avg_sentiment: float | None


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


def _coerce_categorical(value: Any) -> str | None:
    """Extract a categorical label from JSONB marked_value.

    For enum/boolean questions `marked_value` is shaped as `{"value": "..."}`
    or a bare scalar. Returns the string label (booleans become "true"/"false")
    or None if the value is empty.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, dict):
        return _coerce_categorical(value.get("value"))
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return None


# --------------------------------------------------------------------------- #
# aggregate_metric


async def aggregate_metric(
    metric_key: str,
    date_from: datetime,
    date_to: datetime,
    group_by: GroupBy = "day",
    *,
    storage: StorageAdapter | None = None,
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

    store = _storage(storage, db)

    question = await store.get_question_by_metric_key(metric_key)
    if question is None:
        return []
    question_id = question["id"]

    iso_from = date_from.isoformat()
    iso_to = date_to.isoformat()

    rows = await store.fetch_answers_for_question(
        question_id=question_id,
        date_from=iso_from,
        date_to=iso_to,
        columns="created_at, marked_value",
    )

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
# categorical_distribution


async def categorical_distribution(
    metric_key: str,
    date_from: datetime,
    date_to: datetime,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> CategoricalDistribution:
    """Распределение ответов по категориям для одного `metric_key`.

    Работает для enum и boolean вопросов (где marked_value — категориальная
    величина, а не число). Возвращает `categories` с count + pct для каждой
    встретившейся категории. Если у вопроса задан `enum_values`, категории
    выстраиваются в порядке этого списка + категории не из enum попадают в
    `unknown` (rare; means extractor returned a value not in enum_values).
    """
    if not metric_key.strip():
        raise ValueError("metric_key must not be empty")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")

    store = _storage(storage, db)

    question = await store.get_question_by_metric_key(metric_key)
    if question is None:
        return CategoricalDistribution(
            metric_key=metric_key,
            expected_type="unknown",
            total=0,
            categories=[],
            unknown=0,
            enum_values=None,
        )
    question_id = question["id"]
    expected_type = str(question.get("expected_type") or "unknown")
    raw_enum = question.get("enum_values")
    enum_values: list[str] | None
    if isinstance(raw_enum, list) and raw_enum:
        enum_values = [str(v) for v in raw_enum]
    else:
        enum_values = None

    iso_from = date_from.isoformat()
    iso_to = date_to.isoformat()

    rows = await store.fetch_answers_for_question(
        question_id=question_id,
        date_from=iso_from,
        date_to=iso_to,
        columns="marked_value",
    )

    counts: dict[str, int] = defaultdict(int)
    unknown = 0
    total = 0
    for r in rows:
        label = _coerce_categorical(r.get("marked_value"))
        if label is None:
            continue
        total += 1
        if enum_values is not None and label not in enum_values:
            unknown += 1
            continue
        counts[label] += 1

    if enum_values is not None:
        ordered_labels = list(enum_values)
        # Append any non-enum categories last (only if extractor relaxed
        # invariant — defensive; usually empty for the enum branch above
        # because mismatches went to `unknown`).
        for label in counts:
            if label not in ordered_labels:
                ordered_labels.append(label)
    else:
        ordered_labels = sorted(counts.keys(), key=lambda k: (-counts[k], k))

    categories: list[CategoryCount] = []
    matched_total = sum(counts.values()) or 1  # avoid div-by-zero for pct
    for label in ordered_labels:
        c = counts.get(label, 0)
        categories.append(
            CategoryCount(
                value=label,
                count=c,
                pct=(c / matched_total) if c else 0.0,
            )
        )

    return CategoricalDistribution(
        metric_key=metric_key,
        expected_type=expected_type,
        total=total,
        categories=categories,
        unknown=unknown,
        enum_values=enum_values,
    )


# --------------------------------------------------------------------------- #
# topic_histogram


async def topic_histogram(
    date_from: datetime,
    date_to: datetime,
    sentiment_filter: Sentiment | None = None,
    *,
    storage: StorageAdapter | None = None,
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

    store = _storage(storage, db)
    iso_from = date_from.isoformat()
    iso_to = date_to.isoformat()

    rows = await store.fetch_sessions_with_feedback(
        date_from=iso_from,
        date_to=iso_to,
        columns="feedback_summary, started_at",
    )

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
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> SummaryOverview:
    """Одна сводка для /insights — sessions count, avg sentiment, top-3
    положительных/отрицательных топика за период.
    """
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")

    store = _storage(storage, db)
    iso_from = date_from.isoformat()
    iso_to = date_to.isoformat()

    rows = await store.fetch_sessions_in_window(
        date_from=iso_from,
        date_to=iso_to,
        columns="feedback_summary, started_at",
    )
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

    pos_topics = await topic_histogram(
        date_from, date_to, sentiment_filter="positive", storage=store
    )
    neg_topics = await topic_histogram(
        date_from, date_to, sentiment_filter="negative", storage=store
    )

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
    storage: StorageAdapter | None = None,
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

    store = _storage(storage, db)

    sessions_rows = await store.fetch_sessions_by_ids(
        session_ids=session_ids,
        columns="id, client_id, feedback_summary, started_at",
    )
    cards_rows = await store.fetch_cards_by_sessions(
        session_ids=session_ids,
        columns="session_id, summary_text",
    )
    sessions_by_id: dict[str, dict[str, Any]] = {str(r["id"]): r for r in sessions_rows}
    cards_by_session: dict[str, str] = {
        str(r["session_id"]): str(r.get("summary_text") or "") for r in cards_rows
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
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> ClientProfile:
    """Полный профиль клиента: все сессии + последние N карточек + сводка
    (avg sentiment, top topics). LookupError если клиент не найден.
    """
    if recent_cards_limit <= 0:
        raise ValueError("recent_cards_limit must be positive")

    store = _storage(storage, db)

    client_row = await store.get_client(telegram_id)
    if client_row is None:
        raise LookupError(f"client {telegram_id} not found")

    sessions = await store.fetch_sessions_for_client(
        client_id=telegram_id,
        columns="id, started_at, feedback_summary",
    )
    cards = await store.fetch_cards_for_client(
        client_id=telegram_id,
        columns="session_id, summary_text, created_at",
        limit=recent_cards_limit,
    )

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


# --------------------------------------------------------------------------- #
# client drill-down lists (topic / category / filter / search)


def _summary_dict(row: dict[str, Any]) -> dict[str, Any]:
    s = row.get("feedback_summary")
    return s if isinstance(s, dict) else {}


def _topic_set(summary: dict[str, Any]) -> set[str]:
    topics = summary.get("topics") or []
    if not isinstance(topics, list):
        return set()
    return {t.strip().lower() for t in topics if isinstance(t, str) and t.strip()}


def _enrich_client_items(
    sessions_by_client: dict[int, list[dict[str, Any]]],
    names: dict[int, str | None],
) -> list[ClientListItem]:
    """Build compact list rows from each client's (in-scope) session rows."""
    items: list[ClientListItem] = []
    for cid, sess in sessions_by_client.items():
        ordered = sorted(sess, key=lambda s: str(s.get("started_at") or ""), reverse=True)
        scores = [
            _SENTIMENT_SCORE[str(_summary_dict(s).get("sentiment"))]
            for s in sess
            if str(_summary_dict(s).get("sentiment")) in _SENTIMENT_SCORE
        ]
        last_at = (
            str(ordered[0]["started_at"]) if ordered and ordered[0].get("started_at") else None
        )
        items.append(
            ClientListItem(
                telegram_id=cid,
                name=names.get(cid),
                sessions_count=len(sess),
                last_session_at=last_at,
                avg_sentiment=(sum(scores) / len(scores)) if scores else None,
            )
        )
    items.sort(key=lambda x: (x["sessions_count"], x["telegram_id"]), reverse=True)
    return items


async def _paged_client_items(
    store: StorageAdapter,
    sessions_by_client: dict[int, list[dict[str, Any]]],
    limit: int,
    offset: int,
) -> list[ClientListItem]:
    name_rows = await store.fetch_clients_by_ids(
        telegram_ids=list(sessions_by_client.keys()),
        columns="telegram_id, name",
    )
    names = {int(r["telegram_id"]): r.get("name") for r in name_rows}
    items = _enrich_client_items(sessions_by_client, names)
    return items[offset : offset + limit]


async def list_clients_by_topic(
    topic: str,
    date_from: datetime,
    date_to: datetime,
    *,
    sentiment: Sentiment | None = None,
    limit: int = 50,
    offset: int = 0,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> list[ClientListItem]:
    """Clients with at least one in-window session tagged with `topic`."""
    if not topic.strip():
        raise ValueError("topic must not be empty")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if sentiment is not None and sentiment not in _SENTIMENT_SCORE:
        raise ValueError(f"unknown sentiment {sentiment!r}")

    store = _storage(storage, db)
    rows = await store.fetch_sessions_with_feedback(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        columns="id, client_id, started_at, feedback_summary",
    )
    needle = topic.strip().lower()

    by_client: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        cid = r.get("client_id")
        if cid is None:
            continue
        summary = _summary_dict(r)
        if sentiment is not None and summary.get("sentiment") != sentiment:
            continue
        if needle in _topic_set(summary):
            by_client[int(cid)].append(r)

    return await _paged_client_items(store, by_client, limit, offset)


async def list_clients_by_enum_answer(
    metric_key: str,
    value: str,
    date_from: datetime,
    date_to: datetime,
    *,
    limit: int = 50,
    offset: int = 0,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> list[ClientListItem]:
    """Clients who answered the `metric_key` question with `value` in window."""
    if not metric_key.strip():
        raise ValueError("metric_key must not be empty")
    if not value.strip():
        raise ValueError("value must not be empty")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")

    store = _storage(storage, db)
    question = await store.get_question_by_metric_key(metric_key)
    if question is None:
        raise LookupError(f"question with metric_key {metric_key!r} not found")

    answers = await store.fetch_answers_for_question(
        question_id=str(question["id"]),
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        columns="session_id, marked_value",
    )
    target = value.strip().lower()
    session_ids = [
        str(a["session_id"])
        for a in answers
        if a.get("session_id") is not None
        and (_coerce_categorical(a.get("marked_value")) or "").lower() == target
    ]
    if not session_ids:
        return []

    sessions = await store.fetch_sessions_by_ids(
        session_ids=session_ids,
        columns="id, client_id, started_at, feedback_summary",
    )
    by_client: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for s in sessions:
        cid = s.get("client_id")
        if cid is not None:
            by_client[int(cid)].append(s)

    return await _paged_client_items(store, by_client, limit, offset)


async def filter_clients_by_topics(
    topics: list[str],
    *,
    match: Literal["and", "or"] = "and",
    date_from: datetime,
    date_to: datetime,
    sentiment: Sentiment | None = None,
    limit: int = 50,
    offset: int = 0,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> list[ClientListItem]:
    """Clients matching selected topics. `and` = intersection (narrows the
    set), `or` = union. Membership is across the client's in-window sessions."""
    cleaned = [t.strip().lower() for t in topics if t.strip()]
    if not cleaned:
        raise ValueError("topics must not be empty")
    if match not in ("and", "or"):
        raise ValueError(f"unknown match {match!r}")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")

    store = _storage(storage, db)
    rows = await store.fetch_sessions_with_feedback(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        columns="id, client_id, started_at, feedback_summary",
    )

    by_client: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen_topics: dict[int, set[str]] = defaultdict(set)
    for r in rows:
        cid = r.get("client_id")
        if cid is None:
            continue
        summary = _summary_dict(r)
        if sentiment is not None and summary.get("sentiment") != sentiment:
            continue
        cid_i = int(cid)
        by_client[cid_i].append(r)
        seen_topics[cid_i] |= _topic_set(summary)

    want = set(cleaned)
    matched: dict[int, list[dict[str, Any]]] = {}
    for cid_i, sess in by_client.items():
        seen = seen_topics[cid_i]
        ok = (want <= seen) if match == "and" else bool(want & seen)
        if ok:
            matched[cid_i] = sess

    return await _paged_client_items(store, matched, limit, offset)


async def search_clients(
    query: str,
    *,
    limit: int = 50,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> list[ClientListItem]:
    """Look up clients by telegram_id (all-digits) or name substring."""
    q = query.strip()
    if not q:
        raise ValueError("query must not be empty")

    store = _storage(storage, db)
    if q.isdigit():
        row = await store.get_client(int(q))
        client_rows = [row] if row is not None else []
    else:
        client_rows = await store.search_clients_by_name(pattern=f"%{q}%", limit=limit)

    by_client: dict[int, list[dict[str, Any]]] = {}
    names: dict[int, str | None] = {}
    for c in client_rows[:limit]:
        cid = int(c["telegram_id"])
        names[cid] = c.get("name")
        by_client[cid] = await store.fetch_sessions_for_client(
            client_id=cid,
            columns="started_at, feedback_summary",
        )
    return _enrich_client_items(by_client, names)
