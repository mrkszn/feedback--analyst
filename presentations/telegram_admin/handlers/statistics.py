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
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.chat_action import ChatActionSender

from core.services.admin_auth import is_admin
from core.services.statistics import (
    FullReport,
    MetricSummary,
    build_csv_report,
    full_report,
)
from presentations.telegram_admin.handlers.questions import require_admin
from presentations.telegram_admin.keyboards import BTN_STATISTICS

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


def _loop_lines(report: FullReport) -> list[str]:
    """Recurrence block (🔁) — empty list if the report carries no loop data."""
    loop = report.get("loop")
    if loop is None:
        return []
    to_2nd = loop["median_days_to_2nd"]
    to_2nd_str = "—" if to_2nd is None else f"{to_2nd:.1f} дн."
    return [
        "🔁 Повторяемость",
        f"  Повторно оставили отзыв: {loop['repeat_rate'] * 100:.0f}%",
        f"  Сессий на клиента: {loop['sessions_per_client']:.2f}",
        f"  Медиана до 2-го отзыва: {to_2nd_str}",
        "",
    ]


_TG_LIMIT = 4096
_BAR_WIDTH = 10
_LABEL_CAP = 24


def _ascii_bar(pct: float) -> str:
    """Filled-block bar of width _BAR_WIDTH for a 0..1 ratio."""
    filled = round(max(0.0, min(1.0, pct)) * _BAR_WIDTH)
    return "█" * filled


def _format_metric_block(m: MetricSummary) -> list[str]:
    """One question rendered as a multi-line block (▸ header + body lines)."""
    et = m["expected_type"]

    if et in ("enum", "boolean"):
        dist = m.get("distribution") or []
        header = f"▸ {m['text']}  [{et}, n={m['n']}]"
        if not dist:
            return [header, "   (нет ответов)"]
        label_w = min(_LABEL_CAP, max(len(str(d["value"])) for d in dist))
        lines = [header]
        for d in dist:
            value = str(d["value"])
            label = value[:_LABEL_CAP].ljust(label_w)
            pct = float(d.get("pct") or 0.0)
            lines.append(f"   {label}  {_ascii_bar(pct)}  {d['count']} ({pct * 100:.0f}%)")
        return lines

    if et == "number":
        header = f"▸ {m['text']}  [number, n={m['n']}]"
        if m["n"] == 0 or m["avg"] is None:
            return [header, "   (нет ответов)"]
        avg = f"{m['avg']:.2f}"
        mn = f"{m['min']:.2f}" if m["min"] is not None else "—"
        mx = f"{m['max']:.2f}" if m["max"] is not None else "—"
        return [header, f"   avg={avg}   min={mn}   max={mx}"]

    # text
    header = f"▸ {m['text']}  [text]"
    rr = m.get("response_rate")
    if rr is None:
        return [header, "   ответили: 0"]
    answered = round(rr * m["n"])
    return [header, f"   ответили: {answered} из {m['n']} ({rr * 100:.0f}%)"]


def _split_by_limit(blocks: list[list[str]], head: list[str]) -> list[str]:
    """Pack per-question blocks into ≤_TG_LIMIT messages, splitting on block boundaries."""
    messages: list[str] = []
    current: list[str] = list(head)
    for block in blocks:
        candidate = [*current, "", *block] if current else block
        if current and len("\n".join(candidate)) > _TG_LIMIT:
            messages.append("\n".join(current))
            current = list(block)
        else:
            current = candidate
    if current:
        messages.append("\n".join(current))
    return messages


def format_report(report: FullReport) -> list[str]:
    """Render a `FullReport` as 1-3 Telegram messages (each ≤_TG_LIMIT chars)."""
    period = _PERIOD_LABELS.get(_period_key_from_label(report["period_label"]), "период")
    date_to = report["date_to"][:10]
    date_from_str = (report["date_from"] or "—")[:10]
    range_str = f"{date_from_str}…{date_to}" if report["date_from"] else f"до {date_to}"

    act = report["activity"]
    sentiments = report["sentiment_counts"]
    total_sent = report["sentiment_total"]

    messages: list[str] = []

    # ---- message 1: KPI + sentiment + topics ----
    overview = [
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
        *_loop_lines(report),
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
    ]
    messages.append("\n".join(overview))

    # ---- message(s) 2: questions (split if > limit) ----
    q_head = ["📋 Вопросы"]
    if not report["metrics"]:
        messages.append("\n".join([*q_head, "", "   (нет активных вопросов в пуле)"]))
    else:
        blocks = [_format_metric_block(m) for m in report["metrics"]]
        messages.extend(_split_by_limit(blocks, q_head))

    # ---- message 3: recent reviews ----
    if report["recent_sessions"]:
        recent = ["📝 Последние отзывы"]
        for r in report["recent_sessions"]:
            date = (r["started_at"] or "—")[:10]
            sent_emoji = {"positive": "💚", "neutral": "😐", "negative": "❤️‍🩹"}.get(
                r["sentiment"] or "", "·"
            )
            snippet = (r["summary"] or "(нет резюме)").strip().replace("\n", " ")
            if len(snippet) > 140:
                snippet = snippet[:137] + "…"
            recent.append(f"  {date} {sent_emoji} {snippet}")
        messages.append("\n".join(recent))

    return messages


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
    # NB: используем callback.from_user.id напрямую — у callback.message.from_user
    # лежит БОТ (а не кликающий админ), поэтому require_admin(message) даёт
    # false negative для inline-кнопок.
    if not await is_admin(callback.from_user.id):
        await callback.answer("Только для админов.", show_alert=True)
        return
    if not isinstance(callback.message, Message):
        await callback.answer()
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

    messages = format_report(report)
    csv_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Получить CSV", callback_data=f"stats_csv:{period_key}")],
        ]
    )
    for i, text in enumerate(messages):
        markup = csv_markup if i == len(messages) - 1 else None
        await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("stats_csv:"))
async def cb_statistics_csv(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return
    if not await is_admin(callback.from_user.id):
        await callback.answer("Только для админов.", show_alert=True)
        return
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    period_key = callback.data.removeprefix("stats_csv:")
    if period_key not in _PERIOD_LABELS:
        await callback.answer("Неизвестный период.", show_alert=True)
        return

    label = _PERIOD_LABELS[period_key]
    date_from, date_to = _window(period_key)

    bot = callback.message.bot
    if bot is not None:
        async with ChatActionSender.typing(chat_id=callback.message.chat.id, bot=bot):
            report = await full_report(date_from, date_to, period_label=label)
    else:
        report = await full_report(date_from, date_to, period_label=label)

    content = build_csv_report(report).encode("utf-8-sig")
    today = datetime.now(UTC).date()
    document = BufferedInputFile(
        content,
        filename=f"statistics_{period_key}_{today.isoformat()}.csv",
    )
    await callback.message.answer_document(document)
    await callback.answer()
