"""Tests for agent.analytics_agent.interpret — question → AnalysisPlan.

The LLM is mocked at `agent.analytics_agent.interpret.chat_completion` (patched
where it is used, per the service-mock invariant). Since the model is mocked,
these tests verify the *contract*: interpret assembles messages correctly, asks
for `response_model=AnalysisPlan`, and returns exactly what the LLM produced —
without re-asking on a well-formed question.

The "7 golden questions" block feeds interpret a *plausible* plan (the plan a
good interpreter is expected to emit) and asserts interpret returns it intact.
The expected plans double as executable documentation of target behavior. We
test against the *real* arg shape (`period_days: int` / `all_time: bool` inside
`ToolCall.args`), not the earlier draft's string `period_label`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.agent.analytics_agent.interpret import interpret
from core.agent.analytics_agent.types import AnalysisPlan, ToolCall

# --------------------------------------------------------------------------- #
# empty question — no LLM call


async def test_interpret_empty_question_short_circuits() -> None:
    with patch(
        "core.agent.analytics_agent.interpret.chat_completion", new=AsyncMock()
    ) as mock_chat:
        plan = await interpret("   ")
    mock_chat.assert_not_called()
    assert plan.clarification_needed is True
    assert plan.clarification_question
    assert plan.tool_calls == []


async def test_interpret_returns_exactly_what_llm_produced() -> None:
    expected = AnalysisPlan(
        interpretation="Показываю топ топиков за 7 дней.",
        tool_calls=[ToolCall(name="topic_histogram", args={"period_days": 7})],
    )
    with patch(
        "core.agent.analytics_agent.interpret.chat_completion",
        new=AsyncMock(return_value=expected),
    ):
        plan = await interpret("что по топикам")
    assert plan is expected


async def test_interpret_requests_analysis_plan_response_model() -> None:
    mock_chat = AsyncMock(return_value=AnalysisPlan(interpretation="x"))
    with patch("core.agent.analytics_agent.interpret.chat_completion", new=mock_chat):
        await interpret("вопрос")
    _, kwargs = mock_chat.call_args
    assert kwargs["response_model"] is AnalysisPlan


async def test_interpret_uses_low_temperature() -> None:
    mock_chat = AsyncMock(return_value=AnalysisPlan(interpretation="x"))
    with patch("core.agent.analytics_agent.interpret.chat_completion", new=mock_chat):
        await interpret("вопрос")
    _, kwargs = mock_chat.call_args
    assert kwargs["temperature"] == pytest.approx(0.1)


# --------------------------------------------------------------------------- #
# message assembly


async def test_interpret_message_order_system_first_question_last() -> None:
    mock_chat = AsyncMock(return_value=AnalysisPlan(interpretation="x"))
    with patch("core.agent.analytics_agent.interpret.chat_completion", new=mock_chat):
        await interpret("сколько жалоб за неделю")
    args, _ = mock_chat.call_args
    messages = args[0]
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "сколько жалоб за неделю"


async def test_interpret_strips_question_whitespace() -> None:
    mock_chat = AsyncMock(return_value=AnalysisPlan(interpretation="x"))
    with patch("core.agent.analytics_agent.interpret.chat_completion", new=mock_chat):
        await interpret("  топ жалоб  ")
    args, _ = mock_chat.call_args
    assert args[0][-1]["content"] == "топ жалоб"


async def test_interpret_threads_history_user_and_assistant() -> None:
    mock_chat = AsyncMock(return_value=AnalysisPlan(interpretation="x"))
    history = [
        {"role": "user", "content": "первый вопрос"},
        {"role": "assistant", "content": "первый ответ"},
        {"role": "system", "content": "should be dropped"},
        {"role": "tool", "content": "also dropped"},
    ]
    with patch("core.agent.analytics_agent.interpret.chat_completion", new=mock_chat):
        await interpret("второй вопрос", history)
    messages = mock_chat.call_args.args[0]
    roles = [m["role"] for m in messages]
    # system, user(hist), assistant(hist), user(current)
    assert roles == ["system", "user", "assistant", "user"]
    contents = [m["content"] for m in messages]
    assert "первый вопрос" in contents
    assert "первый ответ" in contents
    assert "should be dropped" not in contents
    assert "also dropped" not in contents


async def test_interpret_none_history_is_fine() -> None:
    mock_chat = AsyncMock(return_value=AnalysisPlan(interpretation="x"))
    with patch("core.agent.analytics_agent.interpret.chat_completion", new=mock_chat):
        await interpret("вопрос", None)
    messages = mock_chat.call_args.args[0]
    assert [m["role"] for m in messages] == ["system", "user"]


# --------------------------------------------------------------------------- #
# 7 golden questions — meaning-level contract
#
# Each entry: (question, expected AnalysisPlan). We mock the LLM to return the
# expected plan and assert interpret surfaces it without re-asking. The asserts
# encode the *semantic* target (right tool name, right period/sentiment args),
# tolerant of the exact plan a real interpreter might pick.

GOLDEN = {
    "satisfaction_today": (
        "сколько недовольных гостей сегодня",
        AnalysisPlan(
            interpretation="Считаю недовольных гостей за сегодня.",
            tool_calls=[
                ToolCall(
                    name="topic_histogram",
                    args={"period_days": 1, "sentiment": "negative"},
                    reason="жалобы сегодня",
                )
            ],
        ),
    ),
    "last_client": (
        "покажи последнего опрошенного клиента",
        AnalysisPlan(
            interpretation="Показываю последнюю опрошенную сессию.",
            tool_calls=[ToolCall(name="recent_sessions", args={"limit": 1})],
        ),
    ),
    "all_time_count": (
        "сколько клиентов оставили отзыв за всё время",
        AnalysisPlan(
            interpretation="Считаю всех опрошенных за всё время.",
            tool_calls=[ToolCall(name="full_report", args={"all_time": True})],
        ),
    ),
    "service_week": (
        "что у нас по сервису за неделю",
        AnalysisPlan(
            interpretation="Дашборд за последние 7 дней.",
            tool_calls=[ToolCall(name="full_report", args={"period_days": 7})],
        ),
    ),
    "top3_month": (
        "топ-3 жалобы за месяц",
        AnalysisPlan(
            interpretation="Топ жалоб за 30 дней.",
            tool_calls=[
                ToolCall(
                    name="topic_histogram",
                    args={"period_days": 30, "sentiment": "negative"},
                )
            ],
        ),
    ),
    "compare_weeks": (
        "сравни эту неделю с прошлой",
        AnalysisPlan(
            interpretation="Сравниваю две недели.",
            tool_calls=[
                ToolCall(name="topic_histogram", args={"period_days": 7}, reason="эта неделя"),
                ToolCall(name="topic_histogram", args={"period_days": 14}, reason="прошлая неделя"),
            ],
        ),
    ),
    "semantic_wait": (
        "найди гостей которые жаловались на ожидание",
        AnalysisPlan(
            interpretation="Ищу сессии про ожидание.",
            tool_calls=[
                ToolCall(name="semantic_search", args={"query_text": "жалобы на ожидание"})
            ],
        ),
    ),
}


@pytest.mark.parametrize("key", list(GOLDEN.keys()))
async def test_interpret_golden_question_no_reask(key: str) -> None:
    question, expected_plan = GOLDEN[key]
    with patch(
        "core.agent.analytics_agent.interpret.chat_completion",
        new=AsyncMock(return_value=expected_plan),
    ):
        plan = await interpret(question)
    assert plan.clarification_needed is False
    assert len(plan.tool_calls) >= 1


async def test_interpret_golden_last_client_limit_one() -> None:
    question, expected = GOLDEN["last_client"]
    with patch(
        "core.agent.analytics_agent.interpret.chat_completion",
        new=AsyncMock(return_value=expected),
    ):
        plan = await interpret(question)
    assert plan.tool_calls[0].name == "recent_sessions"
    assert plan.tool_calls[0].args["limit"] == 1


async def test_interpret_golden_all_time_uses_all_time_flag() -> None:
    question, expected = GOLDEN["all_time_count"]
    with patch(
        "core.agent.analytics_agent.interpret.chat_completion",
        new=AsyncMock(return_value=expected),
    ):
        plan = await interpret(question)
    assert plan.tool_calls[0].name == "full_report"
    assert plan.tool_calls[0].args.get("all_time") is True


async def test_interpret_golden_top_complaints_negative_sentiment() -> None:
    question, expected = GOLDEN["top3_month"]
    with patch(
        "core.agent.analytics_agent.interpret.chat_completion",
        new=AsyncMock(return_value=expected),
    ):
        plan = await interpret(question)
    tc = plan.tool_calls[0]
    assert tc.name == "topic_histogram"
    assert tc.args["sentiment"] == "negative"
    assert tc.args["period_days"] == 30


async def test_interpret_golden_compare_has_two_calls() -> None:
    question, expected = GOLDEN["compare_weeks"]
    with patch(
        "core.agent.analytics_agent.interpret.chat_completion",
        new=AsyncMock(return_value=expected),
    ):
        plan = await interpret(question)
    assert len(plan.tool_calls) >= 2


async def test_interpret_golden_semantic_query_mentions_topic() -> None:
    question, expected = GOLDEN["semantic_wait"]
    with patch(
        "core.agent.analytics_agent.interpret.chat_completion",
        new=AsyncMock(return_value=expected),
    ):
        plan = await interpret(question)
    tc = plan.tool_calls[0]
    assert tc.name == "semantic_search"
    # stem match — tolerant of declension (ожидание/ожидания/ожиданий)
    assert "ожидани" in tc.args["query_text"].lower()


# --------------------------------------------------------------------------- #
# negative: re-asking is allowed only for a genuinely ambiguous question


async def test_interpret_passes_through_clarification_plan() -> None:
    """A bare "покажи" — interpreter may legitimately ask for clarification."""
    clarify = AnalysisPlan(
        interpretation="Неясно, что именно показать.",
        clarification_needed=True,
        clarification_question="Что показать по фидбэку?",
    )
    with patch(
        "core.agent.analytics_agent.interpret.chat_completion",
        new=AsyncMock(return_value=clarify),
    ):
        plan = await interpret("покажи")
    assert plan.clarification_needed is True
    assert plan.clarification_question == "Что показать по фидбэку?"
    assert plan.tool_calls == []
