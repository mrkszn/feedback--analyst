"""Phase 2 — execute an `AnalysisPlan` against real service functions.

Pure Python, no LLM. Each `ToolCall` becomes a `DataBlock` (one tool failing
does not abort the rest). Period args (`period_days` / `all_time`) are resolved
to a `[date_from, date_to]` window here; only `full_report` accepts
`date_from=None`, so non-full_report tools get a wide concrete window for
`all_time`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.agent.analytics_agent.defaults import (
    DEFAULT_PERIOD_DAYS,
    RECENT_DEFAULT_LIMIT,
    SEMANTIC_DEFAULT_TOP_K,
)
from core.agent.analytics_agent.types import AnalysisPlan, DataBlock
from core.services.analytics import (
    aggregate_metric,
    categorical_distribution,
    client_profile,
    semantic_search,
    topic_histogram,
)
from core.services.statistics import full_report, recent_sessions

_WIDE_DAYS = 3650  # ≈10 лет — «всё время» для функций, не принимающих date_from=None


def _days_of(args: dict[str, Any]) -> int:
    return max(int(args.get("period_days", DEFAULT_PERIOD_DAYS)), 1)


def _window(args: dict[str, Any]) -> tuple[datetime | None, datetime]:
    """Период для full_report: all_time → date_from=None."""
    now = datetime.now(UTC)
    if args.get("all_time"):
        return None, now
    return now - timedelta(days=_days_of(args)), now


def _window_or_wide(args: dict[str, Any]) -> tuple[datetime, datetime]:
    """Период для функций без поддержки date_from=None: all_time → широкое окно."""
    now = datetime.now(UTC)
    if args.get("all_time"):
        return now - timedelta(days=_WIDE_DAYS), now
    return now - timedelta(days=_days_of(args)), now


async def execute_plan(plan: AnalysisPlan) -> dict[str, Any]:
    if plan.clarification_needed:
        return {
            "interpretation": plan.interpretation,
            "clarification_needed": True,
            "clarification_question": plan.clarification_question,
            "blocks": [],
            "tools_used": [],
        }

    blocks: list[DataBlock] = []
    tools_used: list[str] = []

    for call in plan.tool_calls:
        name = call.name
        args = call.args
        tools_used.append(name)
        try:
            block = await _dispatch(name, args)
        except Exception as exc:  # одна тулза не должна ронять весь execute
            block = DataBlock(tool=name, args=args, ok=False, error=str(exc))
        blocks.append(block)

    return {
        "interpretation": plan.interpretation,
        "clarification_needed": False,
        "clarification_question": plan.clarification_question,
        "blocks": blocks,
        "tools_used": tools_used,
    }


async def _dispatch(name: str, args: dict[str, Any]) -> DataBlock:
    if name == "full_report":
        date_from, date_to = _window(args)
        if args.get("all_time"):
            period_label = args.get("period_label") or "всё время"
        else:
            period_label = args.get("period_label") or f"{_days_of(args)} дн."
        data: Any = await full_report(date_from, date_to, period_label=period_label)
        return DataBlock(tool=name, args=args, ok=True, data=data)

    if name == "aggregate_metric":
        metric_key = str(args.get("metric_key") or "").strip()
        if not metric_key:
            return DataBlock(tool=name, args=args, ok=False, error="metric_key обязателен")
        group_by = args.get("group_by", "day")
        if group_by not in ("day", "week", "none"):
            return DataBlock(
                tool=name,
                args=args,
                ok=False,
                error=f"group_by must be day|week|none, got {group_by!r}",
            )
        date_from, date_to = _window_or_wide(args)
        data = await aggregate_metric(metric_key, date_from, date_to, group_by=group_by)
        return DataBlock(tool=name, args=args, ok=True, data=data)

    if name == "categorical_distribution":
        metric_key = str(args.get("metric_key") or "").strip()
        if not metric_key:
            return DataBlock(tool=name, args=args, ok=False, error="metric_key обязателен")
        date_from, date_to = _window_or_wide(args)
        data = await categorical_distribution(metric_key, date_from, date_to)
        return DataBlock(tool=name, args=args, ok=True, data=data)

    if name == "topic_histogram":
        sentiment = args.get("sentiment")
        if sentiment is not None and sentiment not in ("positive", "neutral", "negative"):
            return DataBlock(
                tool=name,
                args=args,
                ok=False,
                error=f"sentiment must be positive|neutral|negative|None, got {sentiment!r}",
            )
        date_from, date_to = _window_or_wide(args)
        data = await topic_histogram(date_from, date_to, sentiment_filter=sentiment)
        return DataBlock(tool=name, args=args, ok=True, data=data)

    if name == "semantic_search":
        query_text = str(args.get("query_text") or args.get("query") or "").strip()
        if not query_text:
            return DataBlock(tool=name, args=args, ok=False, error="query_text обязателен")
        top_k = int(args.get("top_k", SEMANTIC_DEFAULT_TOP_K))
        data = await semantic_search(query_text, top_k=top_k)
        return DataBlock(tool=name, args=args, ok=True, data=data)

    if name == "client_profile":
        telegram_id = args.get("telegram_id")
        if telegram_id is None:
            return DataBlock(tool=name, args=args, ok=False, error="telegram_id обязателен")
        try:
            tid = int(telegram_id)
        except (TypeError, ValueError):
            return DataBlock(tool=name, args=args, ok=False, error="telegram_id обязателен")
        try:
            data = await client_profile(tid)
        except LookupError:
            return DataBlock(tool=name, args=args, ok=False, error=f"клиент {tid} не найден")
        return DataBlock(tool=name, args=args, ok=True, data=data)

    if name == "recent_sessions":
        limit = int(args.get("limit", RECENT_DEFAULT_LIMIT))
        sentiment = args.get("sentiment")
        data = await recent_sessions(limit=limit, sentiment=sentiment)
        return DataBlock(tool=name, args=args, ok=True, data=data)

    return DataBlock(tool=name, args=args, ok=False, error=f"unknown tool {name}")
