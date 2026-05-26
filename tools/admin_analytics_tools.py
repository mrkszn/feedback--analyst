"""LangChain tool wrappers around `services.analytics` for admin_ask.

Tools принимают relative-day аргумент (`days`) и сами считают окно — это
удобнее для LLM, который думает «за последнюю неделю», чем требовать у него
ISO timestamps. Каждый tool возвращает короткую LLM-friendly строку, ошибки
не raise'ятся (LLM мягко проговорит проблему пользователю).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from langchain_core.tools import tool

from services.analytics import (
    aggregate_metric,
    client_profile,
    semantic_search,
    summary_overview,
    topic_histogram,
)


def _window(days: int) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return now - timedelta(days=max(days, 1)), now


def _fmt_avg_sentiment(score: float | None) -> str:
    if score is None:
        return "—"
    label = "позитив" if score > 0.33 else ("негатив" if score < -0.33 else "нейтрально")
    return f"{score:+.2f} ({label})"


@tool
async def aggregate_metric_tool(
    metric_key: str,
    days: int = 7,
    group_by: str = "day",
) -> str:
    """Aggregate a numeric question metric over the last N days.

    `metric_key` — stable key from `questions.metric_key` (e.g. `service_speed`).
    `group_by` — one of "day", "week", "none".
    Returns a compact ASCII table.
    """
    if group_by not in ("day", "week", "none"):
        return f"group_by must be day|week|none, got {group_by!r}"
    date_from, date_to = _window(days)
    try:
        points = await aggregate_metric(
            metric_key,
            date_from,
            date_to,
            group_by=group_by,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        return f"Не удалось посчитать метрику: {exc}"
    if not points:
        return f"По метрике «{metric_key}» за {days} дн. данных нет."
    lines = [f"Метрика {metric_key} за {days} дн. (group_by={group_by}):"]
    for p in points:
        avg = f"{p['avg']:.2f}" if p["avg"] is not None else "—"
        lines.append(f"  {p['bucket']}: n={p['count']}, avg={avg}")
    return "\n".join(lines)


@tool
async def topic_histogram_tool(
    days: int = 7,
    sentiment: str | None = None,
    limit: int = 10,
) -> str:
    """Top mentioned topics across recent feedback sessions.

    `sentiment` — optional filter: positive | neutral | negative.
    """
    if sentiment is not None and sentiment not in ("positive", "neutral", "negative"):
        return f"sentiment must be positive|neutral|negative|None, got {sentiment!r}"
    date_from, date_to = _window(days)
    try:
        rows = await topic_histogram(
            date_from,
            date_to,
            sentiment_filter=sentiment,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        return f"Не удалось получить топики: {exc}"
    if not rows:
        return f"Топиков за {days} дн. (sentiment={sentiment}) не найдено."
    lines = [f"Топики за {days} дн. (sentiment={sentiment or 'все'}):"]
    for r in rows[:limit]:
        lines.append(f"  {r['topic']}: n={r['count']}, sentiment={r['avg_sentiment']:+.2f}")
    return "\n".join(lines)


@tool
async def summary_overview_tool(days: int = 7) -> str:
    """One-shot dashboard for the last N days: sessions count, avg
    sentiment, top-3 positive + top-3 negative topics."""
    date_from, date_to = _window(days)
    o = await summary_overview(date_from, date_to)
    pos = ", ".join(t["topic"] for t in o["top_positive_topics"]) or "—"
    neg = ", ".join(t["topic"] for t in o["top_negative_topics"]) or "—"
    return (
        f"Сводка за {days} дн.:\n"
        f"  Сессий: {o['sessions_count']}\n"
        f"  Avg sentiment: {_fmt_avg_sentiment(o['avg_sentiment'])}\n"
        f"  Топ позитив: {pos}\n"
        f"  Топ негатив: {neg}"
    )


@tool
async def semantic_search_tool(query: str, top_k: int = 10) -> str:
    """Semantic search across client-card summaries.

    Use when admin asks "find clients who complained about service",
    "найди гостей с жалобами на скорость" — natural-language phrase.
    """
    if not query.strip():
        return "Пустой запрос — нечего искать."
    try:
        hits = await semantic_search(query, top_k=top_k)
    except ValueError as exc:
        return f"Поиск не удался: {exc}"
    if not hits:
        return f"По запросу «{query}» похожих сессий не найдено."
    lines = [f"Похожие сессии для «{query}»:"]
    for h in hits[:top_k]:
        snippet = (h["summary_text"] or "").strip().replace("\n", " ")[:140]
        sent = h["sentiment"] or "—"
        date = (h["started_at"] or "")[:10]
        lines.append(
            f"  [{date}] sentiment={sent} score={h['score']:.2f} client={h['client_id']}: {snippet}"
        )
    return "\n".join(lines)


@tool
async def client_profile_tool(telegram_id: int) -> str:
    """Full profile of one client by Telegram ID — sessions count, avg
    sentiment, top topics, last 3 card summaries.
    """
    try:
        p = await client_profile(telegram_id)
    except LookupError:
        return f"Клиент с telegram_id={telegram_id} не найден."
    name = p["name"] or "(без имени)"
    topics = ", ".join(t["topic"] for t in p["top_topics"]) or "—"
    cards_lines = []
    for c in p["recent_cards"]:
        txt = (c.get("summary_text") or "").strip().replace("\n", " ")[:200]
        cards_lines.append(f"    • {txt}")
    cards_block = "\n".join(cards_lines) if cards_lines else "    (карточек ещё нет)"
    return (
        f"Клиент {name} (id={telegram_id}):\n"
        f"  Сессий: {p['sessions_count']}\n"
        f"  Последняя: {p['last_session_at'] or '—'}\n"
        f"  Avg sentiment: {_fmt_avg_sentiment(p['avg_sentiment'])}\n"
        f"  Топ-топики: {topics}\n"
        f"  Recent cards:\n{cards_block}"
    )


ADMIN_ANALYTICS_TOOLS = [
    aggregate_metric_tool,
    topic_histogram_tool,
    summary_overview_tool,
    semantic_search_tool,
    client_profile_tool,
]
