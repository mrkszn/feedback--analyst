"""Pydantic models for the analytics agent (v2).

These are LLM structured-output shapes (interpret → plan, execute → data
blocks, synthesize → answer), so they are pydantic `BaseModel`s rather than
the `TypedDict`s used by `services/*`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ToolName = Literal[
    "full_report",
    "aggregate_metric",
    "categorical_distribution",
    "topic_histogram",
    "semantic_search",
    "client_profile",
    "recent_sessions",
]


class ToolCall(BaseModel):
    name: ToolName
    args: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "kwargs для service-функции. Период задаётся как period_days: int "
            "ИЛИ all_time: bool (execute сам переведёт в date_from/date_to). "
            "Плюс tool-специфичные ключи: metric_key, group_by, sentiment, "
            "query_text, top_k, telegram_id, limit, period_label."
        ),
    )
    reason: str = Field(default="", description="Зачем этот вызов (debug + контекст synthesize).")


class AnalysisPlan(BaseModel):
    interpretation: str = Field(
        description=(
            "Как агент понял вопрос. Всегда заполнено; если делал допущение — "
            "проговори его здесь («Показываю за последние 7 дней»)."
        )
    )
    clarification_needed: bool = False
    clarification_question: str = Field(
        default="", description="Заполнено только если clarification_needed=True."
    )
    tool_calls: list[ToolCall] = Field(default_factory=list)


class DataBlock(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    ok: bool
    data: Any = None
    error: str = ""


class AnalyticsAnswer(BaseModel):
    answer_text: str
    interpretation: str = Field(default="", description="Эхо из плана (прозрачность).")
    tools_used: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    chart_text: str | None = Field(
        default=None,
        description=(
            "Опциональный график. Первая строка — тег `[template:<id>]`, далее "
            "заголовок и строки данных (см. docs/CHART_TEMPLATES.md)."
        ),
    )
