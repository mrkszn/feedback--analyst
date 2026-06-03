"""Tests for agent.analytics_agent.synthesize — execute results → AnalyticsAnswer.

LLM mocked at `agent.analytics_agent.synthesize.chat_completion`. The input is
the *dict* `execute_plan` produces (interpretation, clarification flags, blocks,
tools_used). On a clarification execution no LLM call is made. Otherwise the
data blocks are JSON-serialized into the user message (DataBlock or plain dict;
datetimes survive via `default=str`), and the model's answer is returned with
`tools_used`/`interpretation` backfilled from the execution when the LLM left
them blank.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from agent.analytics_agent.synthesize import synthesize
from agent.analytics_agent.types import AnalyticsAnswer, DataBlock


def _execution(
    *,
    blocks: list[Any] | None = None,
    tools_used: list[str] | None = None,
    interpretation: str = "Показываю за 7 дней.",
    clarification_needed: bool = False,
    clarification_question: str = "",
) -> dict[str, Any]:
    return {
        "interpretation": interpretation,
        "clarification_needed": clarification_needed,
        "clarification_question": clarification_question,
        "blocks": blocks or [],
        "tools_used": tools_used or [],
    }


# --------------------------------------------------------------------------- #
# clarification — no LLM call


async def test_synthesize_clarification_skips_llm() -> None:
    execution = _execution(
        clarification_needed=True,
        clarification_question="Что показать по фидбэку?",
        interpretation="Неясно.",
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=AsyncMock()) as mock_chat:
        answer = await synthesize("покажи", execution)
    mock_chat.assert_not_called()
    assert answer.clarification_needed is True
    assert answer.answer_text == "Что показать по фидбэку?"
    assert answer.interpretation == "Неясно."
    assert answer.tools_used == []


async def test_synthesize_clarification_without_question_has_fallback() -> None:
    execution = _execution(clarification_needed=True, clarification_question="")
    with patch("agent.analytics_agent.synthesize.chat_completion", new=AsyncMock()):
        answer = await synthesize("покажи", execution)
    assert answer.clarification_needed is True
    assert answer.answer_text  # non-empty fallback prompt


# --------------------------------------------------------------------------- #
# normal path — LLM called with the right contract


async def test_synthesize_requests_analytics_answer_response_model() -> None:
    mock_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="ок"))
    execution = _execution(
        blocks=[DataBlock(tool="full_report", ok=True, data={"n": 3})],
        tools_used=["full_report"],
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        await synthesize("что у нас", execution)
    _, kwargs = mock_chat.call_args
    assert kwargs["response_model"] is AnalyticsAnswer


async def test_synthesize_user_message_carries_question_interpretation_blocks() -> None:
    mock_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="ок"))
    execution = _execution(
        blocks=[DataBlock(tool="topic_histogram", ok=True, data=[{"topic": "ожидание"}])],
        interpretation="Топ жалоб за 7 дней.",
        tools_used=["topic_histogram"],
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        await synthesize("топ жалоб", execution)

    messages = mock_chat.call_args.args[0]
    assert messages[0]["role"] == "system"
    user = messages[-1]["content"]
    assert "топ жалоб" in user  # original question
    assert "Топ жалоб за 7 дней." in user  # interpretation
    assert "ожидание" in user  # serialized block data
    assert "topic_histogram" in user


async def test_synthesize_returns_llm_answer() -> None:
    expected = AnalyticsAnswer(answer_text="За неделю 3 жалобы.", tools_used=["topic_histogram"])
    execution = _execution(
        blocks=[DataBlock(tool="topic_histogram", ok=True, data=[])],
        tools_used=["topic_histogram"],
    )
    with patch(
        "agent.analytics_agent.synthesize.chat_completion",
        new=AsyncMock(return_value=expected),
    ):
        answer = await synthesize("сколько жалоб", execution)
    assert answer.answer_text == "За неделю 3 жалобы."


# --------------------------------------------------------------------------- #
# block serialization — DataBlock and plain dict both work; datetime survives


async def test_synthesize_serializes_datablock_objects() -> None:
    mock_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="ок"))
    execution = _execution(
        blocks=[DataBlock(tool="full_report", args={"period_days": 7}, ok=True, data={"x": 1})],
        tools_used=["full_report"],
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        await synthesize("q", execution)
    user = mock_chat.call_args.args[0][-1]["content"]
    assert "full_report" in user


async def test_synthesize_serializes_plain_dict_blocks() -> None:
    mock_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="ок"))
    execution = _execution(
        blocks=[{"tool": "recent_sessions", "ok": True, "data": [{"client_id": 9}]}],
        tools_used=["recent_sessions"],
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        await synthesize("q", execution)
    user = mock_chat.call_args.args[0][-1]["content"]
    assert "recent_sessions" in user
    assert "9" in user


async def test_synthesize_handles_datetime_in_block_data() -> None:
    """`json.dumps(..., default=str)` must not choke on datetime payloads."""
    mock_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="ок"))
    execution = _execution(
        blocks=[
            DataBlock(
                tool="recent_sessions",
                ok=True,
                data=[{"started_at": datetime(2026, 5, 1, 12, 0, tzinfo=UTC)}],
            )
        ],
        tools_used=["recent_sessions"],
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        answer = await synthesize("последние", execution)  # must not raise
    assert answer.answer_text == "ок"
    assert "2026-05-01" in mock_chat.call_args.args[0][-1]["content"]


# --------------------------------------------------------------------------- #
# post-conditions — backfill + forced flags


async def test_synthesize_backfills_tools_used_when_llm_omits() -> None:
    # LLM returns an answer with empty tools_used → synthesize fills from execution
    mock_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="ок"))
    execution = _execution(
        blocks=[DataBlock(tool="full_report", ok=True, data={})],
        tools_used=["full_report", "topic_histogram"],
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        answer = await synthesize("q", execution)
    assert answer.tools_used == ["full_report", "topic_histogram"]


async def test_synthesize_keeps_llm_tools_used_when_present() -> None:
    mock_chat = AsyncMock(
        return_value=AnalyticsAnswer(answer_text="ок", tools_used=["semantic_search"])
    )
    execution = _execution(
        blocks=[DataBlock(tool="full_report", ok=True, data={})],
        tools_used=["full_report"],
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        answer = await synthesize("q", execution)
    assert answer.tools_used == ["semantic_search"]


async def test_synthesize_backfills_interpretation_when_llm_omits() -> None:
    mock_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="ок"))
    execution = _execution(
        blocks=[DataBlock(tool="full_report", ok=True, data={})],
        interpretation="Показываю за 7 дней.",
        tools_used=["full_report"],
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        answer = await synthesize("q", execution)
    assert answer.interpretation == "Показываю за 7 дней."


async def test_synthesize_forces_clarification_needed_false_on_data_path() -> None:
    # even if the LLM hallucinates clarification_needed=True, the data path forces False
    mock_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="ок", clarification_needed=True))
    execution = _execution(
        blocks=[DataBlock(tool="full_report", ok=True, data={})],
        tools_used=["full_report"],
    )
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        answer = await synthesize("q", execution)
    assert answer.clarification_needed is False


async def test_synthesize_empty_blocks_still_calls_llm() -> None:
    mock_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="Данных нет."))
    execution = _execution(blocks=[], tools_used=[])
    with patch("agent.analytics_agent.synthesize.chat_completion", new=mock_chat):
        answer = await synthesize("q", execution)
    mock_chat.assert_called_once()
    assert answer.answer_text == "Данных нет."
