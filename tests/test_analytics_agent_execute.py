"""Tests for agent.analytics_agent.execute — AnalysisPlan → results, NO LLM.

`execute_plan` dispatches each `ToolCall` to a real service function and wraps
the result in a `DataBlock`. We patch the service functions where execute
imports them (`agent.analytics_agent.execute.<fn>`), so no DB/Pinecone is hit.

Contract under test (the real one, confirmed by reading execute.py):
`execute_plan` returns a *dict*:
    {interpretation, clarification_needed, clarification_question,
     blocks: list[DataBlock], tools_used: list[str]}
Period args live in `ToolCall.args` as `period_days: int` or `all_time: bool`.
Only `full_report` accepts `date_from=None` for all-time; the other tools get a
wide concrete window (~10 years) instead.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from core.agent.analytics_agent.execute import execute_plan
from core.agent.analytics_agent.types import AnalysisPlan, DataBlock, ToolCall


def _plan(*calls: ToolCall, interpretation: str = "тест") -> AnalysisPlan:
    return AnalysisPlan(interpretation=interpretation, tool_calls=list(calls))


def _only_block(execution: dict[str, Any]) -> DataBlock:
    blocks = execution["blocks"]
    assert len(blocks) == 1
    block = blocks[0]
    assert isinstance(block, DataBlock)
    return block


# --------------------------------------------------------------------------- #
# clarification short-circuit — no service is called


async def test_execute_clarification_calls_no_services() -> None:
    plan = AnalysisPlan(
        interpretation="неясно",
        clarification_needed=True,
        clarification_question="что показать?",
        tool_calls=[ToolCall(name="full_report", args={"period_days": 7})],
    )
    with patch("core.agent.analytics_agent.execute.full_report", new=AsyncMock()) as mock_fr:
        execution = await execute_plan(plan)
    mock_fr.assert_not_called()
    assert execution["clarification_needed"] is True
    assert execution["clarification_question"] == "что показать?"
    assert execution["blocks"] == []
    assert execution["tools_used"] == []


# --------------------------------------------------------------------------- #
# full_report — window resolution


async def test_execute_full_report_period_days_window() -> None:
    plan = _plan(ToolCall(name="full_report", args={"period_days": 7}))
    mock_fr = AsyncMock(return_value={"activity": {"sessions_started": 3}})
    with patch("core.agent.analytics_agent.execute.full_report", new=mock_fr):
        execution = await execute_plan(plan)

    block = _only_block(execution)
    assert block.ok is True
    assert block.tool == "full_report"
    assert block.data == {"activity": {"sessions_started": 3}}

    args, kwargs = mock_fr.call_args
    date_from, date_to = args[0], args[1]
    assert isinstance(date_from, datetime) and date_from < date_to
    assert "7" in kwargs["period_label"]
    assert execution["tools_used"] == ["full_report"]


async def test_execute_full_report_all_time_passes_none_date_from() -> None:
    plan = _plan(ToolCall(name="full_report", args={"all_time": True}))
    mock_fr = AsyncMock(return_value={})
    with patch("core.agent.analytics_agent.execute.full_report", new=mock_fr):
        await execute_plan(plan)

    args, kwargs = mock_fr.call_args
    assert args[0] is None  # date_from=None → "all time"
    assert isinstance(args[1], datetime)
    assert kwargs["period_label"] == "всё время"


async def test_execute_full_report_default_period_when_unspecified() -> None:
    plan = _plan(ToolCall(name="full_report", args={}))
    mock_fr = AsyncMock(return_value={})
    with patch("core.agent.analytics_agent.execute.full_report", new=mock_fr):
        await execute_plan(plan)
    args, _ = mock_fr.call_args
    assert args[0] is not None  # default 7-day window, not all-time


# --------------------------------------------------------------------------- #
# topic_histogram — all_time gives a wide concrete window (not None)


async def test_execute_topic_histogram_all_time_wide_window_not_none() -> None:
    plan = _plan(ToolCall(name="topic_histogram", args={"all_time": True}))
    mock_th = AsyncMock(return_value=[])
    with patch("core.agent.analytics_agent.execute.topic_histogram", new=mock_th):
        await execute_plan(plan)
    args, kwargs = mock_th.call_args
    date_from, date_to = args[0], args[1]
    assert isinstance(date_from, datetime)  # NOT None
    # wide window: more than a year back
    assert (date_to - date_from).days > 365
    assert kwargs["sentiment_filter"] is None


async def test_execute_topic_histogram_forwards_sentiment() -> None:
    plan = _plan(
        ToolCall(name="topic_histogram", args={"period_days": 30, "sentiment": "negative"})
    )
    mock_th = AsyncMock(return_value=[{"topic": "ожидание", "count": 4, "avg_sentiment": -1.0}])
    with patch("core.agent.analytics_agent.execute.topic_histogram", new=mock_th):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is True
    _, kwargs = mock_th.call_args
    assert kwargs["sentiment_filter"] == "negative"


async def test_execute_topic_histogram_bad_sentiment_marks_error() -> None:
    plan = _plan(ToolCall(name="topic_histogram", args={"sentiment": "furious"}))
    mock_th = AsyncMock()
    with patch("core.agent.analytics_agent.execute.topic_histogram", new=mock_th):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is False
    assert "sentiment" in block.error
    mock_th.assert_not_called()


# --------------------------------------------------------------------------- #
# aggregate_metric — required metric_key + group_by validation


async def test_execute_aggregate_metric_happy() -> None:
    plan = _plan(ToolCall(name="aggregate_metric", args={"metric_key": "speed", "period_days": 7}))
    mock_am = AsyncMock(return_value=[{"bucket": "2026-05-01", "count": 2, "avg": 4.0}])
    with patch("core.agent.analytics_agent.execute.aggregate_metric", new=mock_am):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is True
    args, kwargs = mock_am.call_args
    assert args[0] == "speed"
    assert kwargs["group_by"] == "day"


async def test_execute_aggregate_metric_missing_key_errors_without_call() -> None:
    plan = _plan(ToolCall(name="aggregate_metric", args={"period_days": 7}))
    mock_am = AsyncMock()
    with patch("core.agent.analytics_agent.execute.aggregate_metric", new=mock_am):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is False
    assert "metric_key" in block.error
    mock_am.assert_not_called()


async def test_execute_aggregate_metric_bad_group_by_errors_without_call() -> None:
    plan = _plan(
        ToolCall(name="aggregate_metric", args={"metric_key": "speed", "group_by": "month"})
    )
    mock_am = AsyncMock()
    with patch("core.agent.analytics_agent.execute.aggregate_metric", new=mock_am):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is False
    assert "group_by" in block.error
    mock_am.assert_not_called()


# --------------------------------------------------------------------------- #
# categorical_distribution — required metric_key


async def test_execute_categorical_distribution_happy() -> None:
    plan = _plan(ToolCall(name="categorical_distribution", args={"metric_key": "age_group"}))
    mock_cd = AsyncMock(return_value={"metric_key": "age_group", "total": 5})
    with patch("core.agent.analytics_agent.execute.categorical_distribution", new=mock_cd):
        execution = await execute_plan(plan)
    assert _only_block(execution).ok is True
    args, _ = mock_cd.call_args
    assert args[0] == "age_group"


async def test_execute_categorical_distribution_missing_key_errors() -> None:
    plan = _plan(ToolCall(name="categorical_distribution", args={}))
    mock_cd = AsyncMock()
    with patch("core.agent.analytics_agent.execute.categorical_distribution", new=mock_cd):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is False
    assert "metric_key" in block.error
    mock_cd.assert_not_called()


# --------------------------------------------------------------------------- #
# semantic_search — query_text (or query) required


async def test_execute_semantic_search_happy_query_text() -> None:
    plan = _plan(ToolCall(name="semantic_search", args={"query_text": "ожидание", "top_k": 5}))
    mock_ss = AsyncMock(return_value=[{"session_id": "s1", "score": 0.9}])
    with patch("core.agent.analytics_agent.execute.semantic_search", new=mock_ss):
        execution = await execute_plan(plan)
    assert _only_block(execution).ok is True
    args, kwargs = mock_ss.call_args
    assert args[0] == "ожидание"
    assert kwargs["top_k"] == 5


async def test_execute_semantic_search_accepts_query_alias() -> None:
    plan = _plan(ToolCall(name="semantic_search", args={"query": "сервис"}))
    mock_ss = AsyncMock(return_value=[])
    with patch("core.agent.analytics_agent.execute.semantic_search", new=mock_ss):
        execution = await execute_plan(plan)
    assert _only_block(execution).ok is True
    assert mock_ss.call_args.args[0] == "сервис"


async def test_execute_semantic_search_empty_query_errors_without_call() -> None:
    plan = _plan(ToolCall(name="semantic_search", args={"query_text": "  "}))
    mock_ss = AsyncMock()
    with patch("core.agent.analytics_agent.execute.semantic_search", new=mock_ss):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is False
    assert "query_text" in block.error
    mock_ss.assert_not_called()


# --------------------------------------------------------------------------- #
# client_profile — telegram_id required + LookupError → ok=False


async def test_execute_client_profile_happy_int_id() -> None:
    plan = _plan(ToolCall(name="client_profile", args={"telegram_id": 42}))
    mock_cp = AsyncMock(return_value={"telegram_id": 42, "name": "Анна"})
    with patch("core.agent.analytics_agent.execute.client_profile", new=mock_cp):
        execution = await execute_plan(plan)
    assert _only_block(execution).ok is True
    assert mock_cp.call_args.args[0] == 42


async def test_execute_client_profile_missing_id_errors_without_call() -> None:
    plan = _plan(ToolCall(name="client_profile", args={}))
    mock_cp = AsyncMock()
    with patch("core.agent.analytics_agent.execute.client_profile", new=mock_cp):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is False
    assert "telegram_id" in block.error
    mock_cp.assert_not_called()


async def test_execute_client_profile_non_int_id_errors_without_call() -> None:
    plan = _plan(ToolCall(name="client_profile", args={"telegram_id": "не-число"}))
    mock_cp = AsyncMock()
    with patch("core.agent.analytics_agent.execute.client_profile", new=mock_cp):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is False
    assert "telegram_id" in block.error
    mock_cp.assert_not_called()


async def test_execute_client_profile_lookup_error_marks_not_found() -> None:
    plan = _plan(ToolCall(name="client_profile", args={"telegram_id": 7}))
    mock_cp = AsyncMock(side_effect=LookupError("client 7 not found"))
    with patch("core.agent.analytics_agent.execute.client_profile", new=mock_cp):
        execution = await execute_plan(plan)
    block = _only_block(execution)
    assert block.ok is False
    assert "7" in block.error


# --------------------------------------------------------------------------- #
# recent_sessions — forwards limit + sentiment


async def test_execute_recent_sessions_forwards_args() -> None:
    plan = _plan(ToolCall(name="recent_sessions", args={"limit": 1, "sentiment": "negative"}))
    mock_rs = AsyncMock(return_value=[{"client_id": 3, "summary": "x"}])
    with patch("core.agent.analytics_agent.execute.recent_sessions", new=mock_rs):
        execution = await execute_plan(plan)
    assert _only_block(execution).ok is True
    _, kwargs = mock_rs.call_args
    assert kwargs["limit"] == 1
    assert kwargs["sentiment"] == "negative"


async def test_execute_recent_sessions_default_limit() -> None:
    plan = _plan(ToolCall(name="recent_sessions", args={}))
    mock_rs = AsyncMock(return_value=[])
    with patch("core.agent.analytics_agent.execute.recent_sessions", new=mock_rs):
        await execute_plan(plan)
    _, kwargs = mock_rs.call_args
    assert kwargs["limit"] >= 1
    assert kwargs["sentiment"] is None


# --------------------------------------------------------------------------- #
# error isolation — one failing tool does not abort the rest


async def test_execute_tool_exception_isolated_to_its_block() -> None:
    plan = _plan(
        ToolCall(name="full_report", args={"period_days": 7}),
        ToolCall(name="topic_histogram", args={"period_days": 7}),
    )
    mock_fr = AsyncMock(side_effect=ValueError("boom"))
    mock_th = AsyncMock(return_value=[{"topic": "еда", "count": 2, "avg_sentiment": 1.0}])
    with (
        patch("core.agent.analytics_agent.execute.full_report", new=mock_fr),
        patch("core.agent.analytics_agent.execute.topic_histogram", new=mock_th),
    ):
        execution = await execute_plan(plan)

    blocks = execution["blocks"]
    assert len(blocks) == 2
    assert blocks[0].tool == "full_report"
    assert blocks[0].ok is False
    assert blocks[0].error == "boom"
    assert blocks[1].tool == "topic_histogram"
    assert blocks[1].ok is True  # second tool still ran
    assert execution["tools_used"] == ["full_report", "topic_histogram"]


# --------------------------------------------------------------------------- #
# multiple calls of the same tool — order preserved, both present


async def test_execute_two_same_tool_calls_both_present_in_order() -> None:
    plan = _plan(
        ToolCall(name="topic_histogram", args={"period_days": 7}),
        ToolCall(name="topic_histogram", args={"period_days": 14}),
    )
    mock_th = AsyncMock(side_effect=[["week"], ["fortnight"]])
    with patch("core.agent.analytics_agent.execute.topic_histogram", new=mock_th):
        execution = await execute_plan(plan)
    blocks = execution["blocks"]
    assert [b.tool for b in blocks] == ["topic_histogram", "topic_histogram"]
    assert blocks[0].data == ["week"]
    assert blocks[1].data == ["fortnight"]
    assert blocks[0].args["period_days"] == 7
    assert blocks[1].args["period_days"] == 14


# --------------------------------------------------------------------------- #
# empty plan — no blocks, no tools


async def test_execute_empty_plan_returns_empty_blocks() -> None:
    plan = _plan(interpretation="ничего делать не надо")
    execution = await execute_plan(plan)
    assert execution["blocks"] == []
    assert execution["tools_used"] == []
    assert execution["clarification_needed"] is False
    assert execution["interpretation"] == "ничего делать не надо"
