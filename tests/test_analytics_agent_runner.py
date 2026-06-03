"""End-to-end tests for agent.analytics_agent.runner.answer_v2.

`answer_v2` chains interpret → execute_plan → synthesize. Both LLM calls are
mocked at their own modules (`interpret.chat_completion`,
`synthesize.chat_completion`), and the service functions execute would reach are
mocked at `execute.<fn>`. No network, no DB.

Key path under test: on a clarification plan, execute short-circuits (no service
call) and synthesize returns the clarification *without* invoking its LLM — so
the synthesize mock must stay un-called in that scenario.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from agent.analytics_agent.runner import answer_v2
from agent.analytics_agent.types import AnalysisPlan, AnalyticsAnswer, ToolCall

# --------------------------------------------------------------------------- #
# happy path — both LLMs run, the planned service runs


async def test_answer_v2_happy_chains_all_three_phases() -> None:
    plan = AnalysisPlan(
        interpretation="Топ жалоб за 7 дней.",
        tool_calls=[
            ToolCall(name="topic_histogram", args={"period_days": 7, "sentiment": "negative"})
        ],
    )
    final = AnalyticsAnswer(
        answer_text="За неделю 3 жалобы на ожидание.",
        tools_used=["topic_histogram"],
    )
    interpret_chat = AsyncMock(return_value=plan)
    synth_chat = AsyncMock(return_value=final)
    service = AsyncMock(return_value=[{"topic": "ожидание", "count": 3, "avg_sentiment": -1.0}])

    with (
        patch("agent.analytics_agent.interpret.chat_completion", new=interpret_chat),
        patch("agent.analytics_agent.synthesize.chat_completion", new=synth_chat),
        patch("agent.analytics_agent.execute.topic_histogram", new=service),
    ):
        answer = await answer_v2("сколько жалоб за неделю")

    assert isinstance(answer, AnalyticsAnswer)
    assert answer.answer_text == "За неделю 3 жалобы на ожидание."
    interpret_chat.assert_called_once()
    synth_chat.assert_called_once()
    service.assert_called_once()


async def test_answer_v2_passes_history_into_interpret() -> None:
    plan = AnalysisPlan(
        interpretation="ок",
        tool_calls=[ToolCall(name="recent_sessions", args={"limit": 1})],
    )
    interpret_chat = AsyncMock(return_value=plan)
    synth_chat = AsyncMock(return_value=AnalyticsAnswer(answer_text="ок"))
    service = AsyncMock(return_value=[])
    history = [
        {"role": "user", "content": "ранее спрашивал"},
        {"role": "assistant", "content": "ранее отвечал"},
    ]

    with (
        patch("agent.analytics_agent.interpret.chat_completion", new=interpret_chat),
        patch("agent.analytics_agent.synthesize.chat_completion", new=synth_chat),
        patch("agent.analytics_agent.execute.recent_sessions", new=service),
    ):
        await answer_v2("последний клиент", history)

    sent_messages = interpret_chat.call_args.args[0]
    contents = [m["content"] for m in sent_messages]
    assert "ранее спрашивал" in contents
    assert "ранее отвечал" in contents


# --------------------------------------------------------------------------- #
# clarification path — synthesize LLM is NOT called, no service runs


async def test_answer_v2_clarification_skips_synthesize_llm_and_services() -> None:
    clarify_plan = AnalysisPlan(
        interpretation="Неясно, что показать.",
        clarification_needed=True,
        clarification_question="Что показать по фидбэку?",
    )
    interpret_chat = AsyncMock(return_value=clarify_plan)
    synth_chat = AsyncMock()  # must stay un-called
    service = AsyncMock()

    with (
        patch("agent.analytics_agent.interpret.chat_completion", new=interpret_chat),
        patch("agent.analytics_agent.synthesize.chat_completion", new=synth_chat),
        patch("agent.analytics_agent.execute.full_report", new=service),
        patch("agent.analytics_agent.execute.topic_histogram", new=service),
    ):
        answer = await answer_v2("покажи")

    assert answer.clarification_needed is True
    assert answer.answer_text == "Что показать по фидбэку?"
    interpret_chat.assert_called_once()
    synth_chat.assert_not_called()
    service.assert_not_called()


async def test_answer_v2_empty_question_no_llm_at_all() -> None:
    """Blank question short-circuits in interpret → neither LLM is invoked."""
    interpret_chat = AsyncMock()
    synth_chat = AsyncMock()
    with (
        patch("agent.analytics_agent.interpret.chat_completion", new=interpret_chat),
        patch("agent.analytics_agent.synthesize.chat_completion", new=synth_chat),
    ):
        answer = await answer_v2("   ")
    assert answer.clarification_needed is True
    assert answer.answer_text  # the interpret fallback question
    interpret_chat.assert_not_called()
    synth_chat.assert_not_called()


# --------------------------------------------------------------------------- #
# empty data — synthesize still runs and produces an answer


async def test_answer_v2_empty_data_still_synthesizes() -> None:
    plan = AnalysisPlan(
        interpretation="Дашборд за 7 дней.",
        tool_calls=[ToolCall(name="full_report", args={"period_days": 7})],
    )
    final = AnalyticsAnswer(answer_text="За неделю отзывов не было.", tools_used=["full_report"])
    interpret_chat = AsyncMock(return_value=plan)
    synth_chat = AsyncMock(return_value=final)
    # full_report returns an "empty" report
    empty_report = {"activity": {"sessions_started": 0}, "recent_sessions": []}
    service = AsyncMock(return_value=empty_report)

    with (
        patch("agent.analytics_agent.interpret.chat_completion", new=interpret_chat),
        patch("agent.analytics_agent.synthesize.chat_completion", new=synth_chat),
        patch("agent.analytics_agent.execute.full_report", new=service),
    ):
        answer = await answer_v2("что у нас за неделю")

    service.assert_called_once()
    synth_chat.assert_called_once()
    assert answer.answer_text == "За неделю отзывов не было."
    # the data blocks reached synthesize's prompt
    user_msg = synth_chat.call_args.args[0][-1]["content"]
    assert "full_report" in user_msg


async def test_answer_v2_service_failure_does_not_crash_run() -> None:
    """A failing service becomes an ok=False block; the run still produces an answer."""
    plan = AnalysisPlan(
        interpretation="Дашборд.",
        tool_calls=[ToolCall(name="full_report", args={"period_days": 7})],
    )
    final = AnalyticsAnswer(answer_text="Не удалось получить часть данных.")
    interpret_chat = AsyncMock(return_value=plan)
    synth_chat = AsyncMock(return_value=final)
    service = AsyncMock(side_effect=ValueError("db down"))

    with (
        patch("agent.analytics_agent.interpret.chat_completion", new=interpret_chat),
        patch("agent.analytics_agent.synthesize.chat_completion", new=synth_chat),
        patch("agent.analytics_agent.execute.full_report", new=service),
    ):
        answer = await answer_v2("что у нас")

    synth_chat.assert_called_once()
    assert answer.answer_text == "Не удалось получить часть данных."
    # the error block was serialized into synthesize input
    user_msg = synth_chat.call_args.args[0][-1]["content"]
    assert "db down" in user_msg
