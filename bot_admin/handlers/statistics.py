"""/statistics — отчёт по отзывам за выбранный период.

Flow:
1. Админ: /statistics  (или жмёт «📊 Статистика» на reply-keyboard)
2. Бот: inline-кнопки [Сегодня | 7 дней | 30 дней | Всё время]
3. Админ: клик
4. Бот: полный отчёт от `services.statistics.full_report`
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.chat_action import ChatActionSender

from bot_admin.handlers.questions import require_admin
from bot_admin.keyboards import BTN_STATISTICS
from services.statistics import FullReport, MetricSummary, full_report

router = Router(name="admin_statistics")


PERIOD_TODAY = "today"
PERIOD_7D = "7d"
PERIOD_30D = "30d"
PERIOD_ALL = "all"

_PERIOD_LABELS: dict[str, str] = {
    PERIOD_TODAY: "сегодня",
    PERIOD_7D: "7 дней",
    PERIOD_30D: "30 дней",
    PERIOD_ALL: "всё время",
}


def _period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="stats:today"),
                InlineKeyboardButton(text="7 дней", callback_data="stats:7d"),
            ],
            [
                InlineKeyboardButton(text="30 дней", callback_data="stats:30d"),
                InlineKeyboardButton(text="Всё время", callback_data="stats:all"),
            ],
        ]
    )


def _window(period_key: str) -> tuple[datetime | None, datetime]:
    """Возвращает (date_from, date_to). date_from=None для 'all'."""
    now = datetime.now(UTC)
    if period_key == PERIOD_TODAY:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if period_key == PERIOD_7D:
        return now - timedelta(days=7), now
    if period_key == PERIOD_30D:
        return now - timedelta(days=30), now
    return None, now


def _fmt_sentiment_avg(score: float | None) -> str:
    if score is None:
        return "—"
    label = "позитив" if score > 0.33 else ("негатив" if score < -0.33 else "нейтрал")
    return f"{score:+.2f} ({label})"


def _pct(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "—"
    return f"{numerator / denominator * 100:.0f}%"


def _topic_lines(rows: Sequence[Mapping[str, Any]], indent: str = "  ") -> str:
    if not rows:
        return f"{indent}—"
    parts = []
    for t in rows:
        parts.append(f"{indent}• {t['topic']} — n={t['count']}")
    return "\n".join(parts)


def _format_metric(m: MetricSummary) -> str:
    label = f"{m['text']!r} ({m['expected_type']})"
    if m["n"] == 0:
        return f"  • {label}: ответов нет"

    if m["expected_type"] == "number":
        avg = f"{m['avg']:.2f}" if m["avg"] is not None else "—"
        mn = f"{m['min']:.2f}" if m["min"] is not None else "—"
        mx = f"{m['max']:.2f}" if m["max"] is not None else "—"
        return f"  • {label}: avg={avg} (min={mn}, max={mx}, n={m['n']})"

    if m["expected_type"] in ("enum", "boolean"):
        dist = m.get("distribution") or []
        if not dist:
            return f"  • {label}: n={m['n']}"
        top = m.get("top_value") or "—"
        top_pct_val = m.get("top_pct")
        top_pct = f"{top_pct_val * 100:.0f}%" if top_pct_val is not None else "—"
        breakdown = ", ".join(
            f"{d['value']}: {d['count']} ({d['pct'] * 100:.0f}%)" for d in dist[:5]
        )
        return f"  • {label}: топ «{top}» ({top_pct}), n={m['n']}\n       {breakdown}"

    # text
    rr = m.get("response_rate")
    rr_str = f"{rr * 100:.0f}%" if rr is not None else "—"
    return f"  • {label}: ответили {rr_str} (n={m['n']})"


def format_report(report: FullReport) -> str:
    period = _PERIOD_LABELS.get(_period_key_from_label(report["period_label"]), "период")
    date_to = report["date_to"][:10]
    date_from_str = (report["date_from"] or "—")[:10]
    range_str = f"{date_from_str}…{date_to}" if report["date_from"] else f"до {date_to}"

    act = report["activity"]
    sentiments = report["sentiment_counts"]
    total_sent = report["sentiment_total"]

    head = [
        f"📊 Статистика — {period}",
        f"({range_str})",
        "",
        "📈 Активность",
        f"  Сессий начато: {act['sessions_started']}",
        f"  Сессий завершено: {act['sessions_finished']} "
        f"({_pct(act['sessions_finished'], act['sessions_started'])})",
        f"  Уникальных клиентов: {act['unique_clients']}",
        f"  Возвращающихся (≥2 сессии): {act['returning_clients']}",
        "",
        "😊 Тональность завершённых отзывов",
        f"  💚 Позитив: {sentiments['positive']} ({_pct(sentiments['positive'], total_sent)})",
        f"  😐 Нейтрал: {sentiments['neutral']} ({_pct(sentiments['neutral'], total_sent)})",
        f"  ❤️‍🩹 Негатив: {sentiments['negative']} ({_pct(sentiments['negative'], total_sent)})",
        f"  Средняя: {_fmt_sentiment_avg(report['avg_sentiment'])}",
        "",
        "🏷 Топики (все)",
        "  💚 Позитивные:",
        _topic_lines(report["topics_positive"], indent="    "),
        "  😐 Нейтральные:",
        _topic_lines(report["topics_neutral"], indent="    "),
        "  ❤️‍🩹 Негативные:",
        _topic_lines(report["topics_negative"], indent="    "),
        "",
        "📋 Метрики (по вопросам)",
    ]
    metrics_block: list[str] = []
    if not report["metrics"]:
        metrics_block.append("  (нет активных вопросов в пуле)")
    else:
        for m in report["metrics"]:
            metrics_block.append(_format_metric(m))

    recent: list[str] = []
    if report["recent_sessions"]:
        recent.append("")
        recent.append("📝 Последние отзывы")
        for r in report["recent_sessions"]:
            date = (r["started_at"] or "—")[:10]
            sent_emoji = {"positive": "💚", "neutral": "😐", "negative": "❤️‍🩹"}.get(
                r["sentiment"] or "", "·"
            )
            snippet = (r["summary"] or "(нет резюме)").strip().replace("\n", " ")
            if len(snippet) > 140:
                snippet = snippet[:137] + "…"
            recent.append(f"  {date} {sent_emoji} {snippet}")

    return "\n".join(head + metrics_block + recent)


def _period_key_from_label(label: str) -> str:
    """Inverse of _PERIOD_LABELS — helper for format_report."""
    for k, v in _PERIOD_LABELS.items():
        if v == label:
            return k
    return PERIOD_7D


# --------------------------------------------------------------------------- #
# handlers


@router.message(Command("statistics"))
async def cmd_statistics(message: Message) -> None:
    if not await require_admin(message):
        return
    await message.answer("За какой период показать статистику?", reply_markup=_period_keyboard())


@router.message(F.text == BTN_STATISTICS)
async def menu_statistics(message: Message) -> None:
    if not await require_admin(message):
        return
    await message.answer("За какой период показать статистику?", reply_markup=_period_keyboard())


@router.callback_query(F.data.startswith("stats:"))
async def cb_statistics_period(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    if not await require_admin(callback.message):
        await callback.answer("Только для админов.", show_alert=True)
        return

    period_key = callback.data.removeprefix("stats:")
    if period_key not in _PERIOD_LABELS:
        await callback.answer("Неизвестный период.", show_alert=True)
        return

    label = _PERIOD_LABELS[period_key]
    date_from, date_to = _window(period_key)

    # снимаем клавиатуру у запроса периода
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    bot = callback.message.bot
    if bot is not None:
        async with ChatActionSender.typing(chat_id=callback.message.chat.id, bot=bot):
            report = await full_report(date_from, date_to, period_label=label)
    else:
        report = await full_report(date_from, date_to, period_label=label)

    await callback.message.answer(format_report(report))
    await callback.answer()
