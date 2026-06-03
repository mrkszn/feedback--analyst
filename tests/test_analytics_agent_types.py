"""Tests for agent.analytics_agent.types — pydantic shapes + whitelist guard.

These are LLM structured-output models. The important invariant here is that
`ToolName` is a closed Literal whitelist: if the LLM hallucinates a tool name
outside the set, pydantic must reject it at parse time (so `execute` never gets
a name it can't dispatch). The period is carried inside the free-form `args`
dict as `period_days: int` or `all_time: bool` (resolved later by `execute`).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.analytics_agent.types import (
    AnalysisPlan,
    AnalyticsAnswer,
    DataBlock,
    ToolCall,
)

ALL_TOOL_NAMES = [
    "full_report",
    "aggregate_metric",
    "categorical_distribution",
    "topic_histogram",
    "semantic_search",
    "client_profile",
    "recent_sessions",
]


# --------------------------------------------------------------------------- #
# ToolCall


@pytest.mark.parametrize("name", ALL_TOOL_NAMES)
def test_tool_call_accepts_every_whitelisted_name(name: str) -> None:
    tc = ToolCall(name=name)  # type: ignore[arg-type]
    assert tc.name == name
    assert tc.args == {}
    assert tc.reason == ""


def test_tool_call_rejects_name_outside_whitelist() -> None:
    """LLM hallucination guard — a name not in ToolName must fail to parse."""
    with pytest.raises(ValidationError):
        ToolCall(name="drop_table")  # type: ignore[arg-type]


def test_tool_call_rejects_empty_name() -> None:
    with pytest.raises(ValidationError):
        ToolCall(name="")  # type: ignore[arg-type]


def test_tool_call_carries_free_form_args() -> None:
    tc = ToolCall(
        name="topic_histogram",
        args={"period_days": 7, "sentiment": "negative"},
        reason="жалобы за неделю",
    )
    assert tc.args["period_days"] == 7
    assert tc.args["sentiment"] == "negative"
    assert tc.reason == "жалобы за неделю"


def test_tool_call_all_time_arg() -> None:
    tc = ToolCall(name="full_report", args={"all_time": True})
    assert tc.args["all_time"] is True


# --------------------------------------------------------------------------- #
# AnalysisPlan


def test_analysis_plan_minimal_defaults() -> None:
    p = AnalysisPlan(interpretation="Показываю за последние 7 дней.")
    assert p.clarification_needed is False
    assert p.clarification_question == ""
    assert p.tool_calls == []


def test_analysis_plan_requires_interpretation() -> None:
    with pytest.raises(ValidationError):
        AnalysisPlan()  # type: ignore[call-arg]


def test_analysis_plan_clarification_shape() -> None:
    p = AnalysisPlan(
        interpretation="Неясно, что показать.",
        clarification_needed=True,
        clarification_question="Что именно показать по фидбэку?",
    )
    assert p.clarification_needed is True
    assert p.clarification_question == "Что именно показать по фидбэку?"
    assert p.tool_calls == []


def test_analysis_plan_roundtrip_with_nested_tool_calls() -> None:
    plan = AnalysisPlan(
        interpretation="Сравниваю эту неделю с прошлой.",
        tool_calls=[
            ToolCall(name="topic_histogram", args={"period_days": 7}, reason="эта неделя"),
            ToolCall(name="topic_histogram", args={"period_days": 14}, reason="прошлая неделя"),
        ],
    )
    dumped = plan.model_dump()
    restored = AnalysisPlan.model_validate(dumped)
    assert restored == plan
    assert len(restored.tool_calls) == 2
    assert restored.tool_calls[0].name == "topic_histogram"
    assert restored.tool_calls[1].args["period_days"] == 14


def test_analysis_plan_rejects_bad_nested_tool_name() -> None:
    """A bad tool name nested inside a plan must bubble up as a ValidationError."""
    with pytest.raises(ValidationError):
        AnalysisPlan(
            interpretation="x",
            tool_calls=[{"name": "definitely_not_a_tool", "args": {}}],  # type: ignore[list-item]
        )


def test_analysis_plan_json_roundtrip() -> None:
    plan = AnalysisPlan(
        interpretation="Последний опрошенный клиент.",
        tool_calls=[ToolCall(name="recent_sessions", args={"limit": 1})],
    )
    restored = AnalysisPlan.model_validate_json(plan.model_dump_json())
    assert restored == plan
    assert restored.tool_calls[0].args["limit"] == 1


# --------------------------------------------------------------------------- #
# DataBlock


def test_data_block_ok_shape() -> None:
    db = DataBlock(tool="full_report", args={"period_days": 7}, ok=True, data={"n": 3})
    assert db.tool == "full_report"
    assert db.ok is True
    assert db.data == {"n": 3}
    assert db.error == ""


def test_data_block_error_shape() -> None:
    db = DataBlock(tool="aggregate_metric", ok=False, error="boom")
    assert db.ok is False
    assert db.error == "boom"
    assert db.data is None
    assert db.args == {}


def test_data_block_accepts_any_tool_string() -> None:
    """DataBlock.tool is a free str (not the Literal) — it echoes whatever ran."""
    db = DataBlock(tool="anything-goes-here", ok=True)
    assert db.tool == "anything-goes-here"


# --------------------------------------------------------------------------- #
# AnalyticsAnswer


def test_analytics_answer_minimal_defaults() -> None:
    a = AnalyticsAnswer(answer_text="За неделю 3 жалобы.")
    assert a.interpretation == ""
    assert a.tools_used == []
    assert a.clarification_needed is False
    assert a.chart_text is None


def test_analytics_answer_full_shape() -> None:
    a = AnalyticsAnswer(
        answer_text="Тренд по дням.",
        interpretation="Показываю за 7 дней.",
        tools_used=["aggregate_metric"],
        chart_text="day1 ▆\nday2 █",
    )
    assert a.tools_used == ["aggregate_metric"]
    assert a.chart_text is not None
    assert a.interpretation == "Показываю за 7 дней."


def test_analytics_answer_requires_answer_text() -> None:
    with pytest.raises(ValidationError):
        AnalyticsAnswer()  # type: ignore[call-arg]


def test_analytics_answer_roundtrip() -> None:
    a = AnalyticsAnswer(
        answer_text="ок",
        tools_used=["full_report", "topic_histogram"],
        clarification_needed=False,
    )
    assert AnalyticsAnswer.model_validate(a.model_dump()) == a
