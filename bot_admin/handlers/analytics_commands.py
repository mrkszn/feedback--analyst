"""Admin analytics slash-команды: /insights, /metric, /topics (+/find, /clients, /ask).

Эти handler'ы — тонкая UX-обёртка над `services.analytics` и
`agent.nodes.admin_ask`. Никаких HTTP-вызовов, никакого auth-слоя — bot
зовёт services напрямую (см. архитектурный invariant Phase 3 в плане).

Регистрируются в `bot_admin/__main__.py` ПЕРЕД `fallback` (admin_agent),
чтобы /commands ловились слотом первыми, а свободный текст уходил в
admin_agent или /ask по явной команде.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot_admin.handlers.questions import require_admin
from services.analytics import (
    aggregate_metric,
    client_profile,
    semantic_search,
    summary_overview,
    topic_histogram,
)

router = Router(name="admin_analytics")

DEFAULT_DAYS = 7
MAX_DAYS = 365


def _window(days: int) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return now - timedelta(days=max(days, 1)), now


def _parse_days(arg: str | None, default: int = DEFAULT_DAYS) -> int | str:
    """Returns int days or error message string."""
    if not arg or not arg.strip():
        return default
    try:
        n = int(arg.strip())
    except ValueError:
        return f"Не понял число дней: {arg!r}"
    if n < 1:
        return "Дней должно быть ≥ 1."
    if n > MAX_DAYS:
        return f"Дней должно быть ≤ {MAX_DAYS}."
    return n


def _fmt_sentiment(score: float | None) -> str:
    if score is None:
        return "—"
    label = "позитив" if score > 0.33 else ("негатив" if score < -0.33 else "нейтрально")
    return f"{score:+.2f} ({label})"


# --------------------------------------------------------------------------- #
# /insights


@router.message(Command("insights"))
async def cmd_insights(message: Message, command: CommandObject) -> None:
    if not await require_admin(message):
        return
    days_or_err = _parse_days(command.args)
    if isinstance(days_or_err, str):
        await message.answer(days_or_err)
        return
    days = days_or_err
    date_from, date_to = _window(days)
    o = await summary_overview(date_from, date_to)
    pos = "\n".join(f"  • {t['topic']} (n={t['count']})" for t in o["top_positive_topics"]) or "  —"
    neg = "\n".join(f"  • {t['topic']} (n={t['count']})" for t in o["top_negative_topics"]) or "  —"
    await message.answer(
        f"📊 Сводка за {days} дн.\n\n"
        f"Сессий: {o['sessions_count']}\n"
        f"Avg sentiment: {_fmt_sentiment(o['avg_sentiment'])}\n\n"
        f"Топ позитив:\n{pos}\n\n"
        f"Топ негатив:\n{neg}"
    )


# --------------------------------------------------------------------------- #
# /metric <metric_key> [days]


@router.message(Command("metric"))
async def cmd_metric(message: Message, command: CommandObject) -> None:
    if not await require_admin(message):
        return
    args = (command.args or "").strip().split()
    if not args:
        await message.answer("Использование: /metric <metric_key> [days]")
        return
    metric_key = args[0]
    days_arg = args[1] if len(args) > 1 else None
    days_or_err = _parse_days(days_arg)
    if isinstance(days_or_err, str):
        await message.answer(days_or_err)
        return
    days = days_or_err

    date_from, date_to = _window(days)
    points = await aggregate_metric(metric_key, date_from, date_to, group_by="day")
    if not points:
        await message.answer(f"По «{metric_key}» за {days} дн. данных нет.")
        return

    lines = [f"📈 Метрика «{metric_key}» за {days} дн.\n"]
    lines.append("дата       │ n  │ avg  │ min  │ max")
    lines.append("───────────┼────┼──────┼──────┼──────")
    for p in points:
        avg = f"{p['avg']:.2f}" if p["avg"] is not None else "  — "
        mn = f"{p['min']:.2f}" if p["min"] is not None else "  — "
        mx = f"{p['max']:.2f}" if p["max"] is not None else "  — "
        lines.append(f"{p['bucket']:10s} │ {p['count']:>2} │ {avg:>4} │ {mn:>4} │ {mx:>4}")
    await message.answer("```\n" + "\n".join(lines) + "\n```", parse_mode="Markdown")


# --------------------------------------------------------------------------- #
# /topics [days]


@router.message(Command("topics"))
async def cmd_topics(message: Message, command: CommandObject) -> None:
    if not await require_admin(message):
        return
    days_or_err = _parse_days(command.args)
    if isinstance(days_or_err, str):
        await message.answer(days_or_err)
        return
    days = days_or_err
    date_from, date_to = _window(days)
    pos = await topic_histogram(date_from, date_to, sentiment_filter="positive")
    neg = await topic_histogram(date_from, date_to, sentiment_filter="negative")
    pos_lines = "\n".join(f"  • {t['topic']} (n={t['count']})" for t in pos[:5]) or "  —"
    neg_lines = "\n".join(f"  • {t['topic']} (n={t['count']})" for t in neg[:5]) or "  —"
    await message.answer(
        f"🏷 Топики за {days} дн.\n\nПоложительные:\n{pos_lines}\n\nОтрицательные:\n{neg_lines}"
    )


# --------------------------------------------------------------------------- #
# /find <natural query>


@router.message(Command("find"))
async def cmd_find(message: Message, command: CommandObject) -> None:
    if not await require_admin(message):
        return
    query = (command.args or "").strip()
    if not query:
        await message.answer("Использование: /find <natural query>")
        return
    try:
        hits = await semantic_search(query, top_k=10)
    except ValueError as exc:
        await message.answer(f"Поиск не удался: {exc}")
        return
    if not hits:
        await message.answer(f"По запросу «{query}» похожих сессий не нашёл.")
        return

    lines = [f"🔎 Похожие сессии для «{query}» (top {len(hits)}):\n"]
    for i, h in enumerate(hits, 1):
        snippet = (h["summary_text"] or "").strip().replace("\n", " ")[:160]
        sent = h["sentiment"] or "—"
        date = (h["started_at"] or "")[:10]
        client = h["client_id"] if h["client_id"] is not None else "—"
        lines.append(
            f"{i}. [{date}] sentiment={sent} score={h['score']:.2f} client={client}\n   {snippet}"
        )
    await message.answer("\n".join(lines))


# --------------------------------------------------------------------------- #
# /clients <telegram_id>


@router.message(Command("clients"))
async def cmd_clients(message: Message, command: CommandObject) -> None:
    if not await require_admin(message):
        return
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("Использование: /clients <telegram_id>")
        return
    try:
        telegram_id = int(arg)
    except ValueError:
        await message.answer(f"telegram_id должен быть числом, не {arg!r}.")
        return
    try:
        p = await client_profile(telegram_id)
    except LookupError:
        await message.answer(f"Клиент {telegram_id} не найден.")
        return

    name = p["name"] or "(без имени)"
    topics = "\n".join(f"  • {t['topic']} (n={t['count']})" for t in p["top_topics"][:5]) or "  —"
    cards = (
        "\n".join(f"  • {(c.get('summary_text') or '').strip()[:200]}" for c in p["recent_cards"])
        or "  (карточек ещё нет)"
    )
    await message.answer(
        f"👤 {name} (id={telegram_id})\n\n"
        f"Сессий: {p['sessions_count']}\n"
        f"Последняя: {p['last_session_at'] or '—'}\n"
        f"Avg sentiment: {_fmt_sentiment(p['avg_sentiment'])}\n\n"
        f"Топ-топики:\n{topics}\n\n"
        f"Recent cards:\n{cards}"
    )
