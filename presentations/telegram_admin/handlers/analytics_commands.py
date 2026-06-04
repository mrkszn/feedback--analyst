"""/topics — полная статистика по топикам за период.

Тонкая обёртка над `services.analytics.topic_histogram`. Старые команды
(/insights, /metric, /find, /clients, /ask) убраны — pending Phase 5
redesign of the analytics agent.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from core.services.analytics import topic_histogram
from presentations.telegram_admin.handlers.questions import require_admin

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


def _format_sentiment(score: float) -> str:
    if score > 0.33:
        return "позитив"
    if score < -0.33:
        return "негатив"
    return "нейтрал"


def _format_topics_report(days: int, all_topics: list[dict]) -> str:
    """Полная разбивка: позитивные / нейтральные / негативные секции +
    общая таблица по убыванию упоминаний.
    """
    if not all_topics:
        return f"🏷 Топики за {days} дн.\n\nЗа этот период не было упоминаний топиков."

    positive: list[dict] = []
    neutral: list[dict] = []
    negative: list[dict] = []
    for t in all_topics:
        s = float(t.get("avg_sentiment") or 0.0)
        if s > 0.33:
            positive.append(t)
        elif s < -0.33:
            negative.append(t)
        else:
            neutral.append(t)

    def _section(title: str, rows: list[dict]) -> str:
        if not rows:
            return f"{title}\n  —"
        lines = [title]
        for t in rows:
            score = float(t.get("avg_sentiment") or 0.0)
            lines.append(f"  • {t['topic']} — n={t['count']}, sentiment={score:+.2f}")
        return "\n".join(lines)

    total_mentions = sum(int(t["count"]) for t in all_topics)
    distinct_topics = len(all_topics)

    parts = [
        f"🏷 Топики за {days} дн.",
        f"Всего упоминаний: {total_mentions} · уникальных топиков: {distinct_topics}",
        "",
        _section("💚 Позитивные:", positive),
        "",
        _section("😐 Нейтральные:", neutral),
        "",
        _section("❤️‍🩹 Негативные:", negative),
    ]
    return "\n".join(parts)


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
    rows = await topic_histogram(date_from, date_to)
    await message.answer(_format_topics_report(days, [dict(r) for r in rows]))
