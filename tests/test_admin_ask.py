"""Tests for the admin_ask agent + its analytics-tool wrappers."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from agent.nodes.admin_ask import AdminAnswer, _split_chart, answer_admin_question
from tools.admin_analytics_tools import (
    aggregate_metric_tool,
    client_profile_tool,
    semantic_search_tool,
    summary_overview_tool,
    topic_histogram_tool,
)

# --------------------------------------------------------------------------- #
# tool wrappers


async def test_summary_overview_tool_formats_dashboard() -> None:
    with patch(
        "tools.admin_analytics_tools.summary_overview",
        new=AsyncMock(
            return_value={
                "sessions_count": 12,
                "avg_sentiment": 0.5,
                "top_positive_topics": [
                    {"topic": "food", "count": 5, "avg_sentiment": 1.0},
                ],
                "top_negative_topics": [
                    {"topic": "speed", "count": 2, "avg_sentiment": -1.0},
                ],
            }
        ),
    ):
        out = await summary_overview_tool.ainvoke({"days": 7})
    assert "Сессий: 12" in out
    assert "food" in out
    assert "speed" in out


async def test_aggregate_metric_tool_handles_no_data() -> None:
    with patch(
        "tools.admin_analytics_tools.aggregate_metric",
        new=AsyncMock(return_value=[]),
    ):
        out = await aggregate_metric_tool.ainvoke({"metric_key": "speed", "days": 7})
    assert "данных нет" in out.lower()


async def test_aggregate_metric_tool_renders_buckets() -> None:
    with patch(
        "tools.admin_analytics_tools.aggregate_metric",
        new=AsyncMock(
            return_value=[
                {"bucket": "2026-05-20", "count": 2, "avg": 4.0, "min": 3.0, "max": 5.0},
                {"bucket": "2026-05-21", "count": 1, "avg": 4.0, "min": 4.0, "max": 4.0},
            ]
        ),
    ):
        out = await aggregate_metric_tool.ainvoke({"metric_key": "speed", "days": 7})
    assert "2026-05-20" in out
    assert "n=2" in out
    assert "4.00" in out


async def test_aggregate_metric_tool_bad_group_by_returns_text() -> None:
    out = await aggregate_metric_tool.ainvoke({"metric_key": "speed", "group_by": "month"})
    assert "group_by" in out.lower()


async def test_topic_histogram_tool_bad_sentiment_returns_text() -> None:
    out = await topic_histogram_tool.ainvoke({"sentiment": "amazing"})
    assert "sentiment" in out.lower()


async def test_topic_histogram_tool_renders_rows() -> None:
    with patch(
        "tools.admin_analytics_tools.topic_histogram",
        new=AsyncMock(
            return_value=[
                {"topic": "service", "count": 5, "avg_sentiment": -0.5},
            ]
        ),
    ):
        out = await topic_histogram_tool.ainvoke({"days": 7, "sentiment": "negative"})
    assert "service" in out
    assert "n=5" in out


async def test_semantic_search_tool_empty_query() -> None:
    out = await semantic_search_tool.ainvoke({"query": "   "})
    assert "пустой" in out.lower()


async def test_semantic_search_tool_renders_hits() -> None:
    with patch(
        "tools.admin_analytics_tools.semantic_search",
        new=AsyncMock(
            return_value=[
                {
                    "session_id": "s1",
                    "client_id": 42,
                    "score": 0.91,
                    "summary_text": "Жалоба на скорость подачи",
                    "sentiment": "negative",
                    "started_at": "2026-05-20T10:00:00+00:00",
                }
            ]
        ),
    ):
        out = await semantic_search_tool.ainvoke({"query": "медленно", "top_k": 5})
    assert "Жалоба" in out
    assert "client=42" in out


async def test_client_profile_tool_not_found() -> None:
    with patch(
        "tools.admin_analytics_tools.client_profile",
        new=AsyncMock(side_effect=LookupError("nope")),
    ):
        out = await client_profile_tool.ainvoke({"telegram_id": 404})
    assert "не найден" in out.lower()


async def test_client_profile_tool_renders_profile() -> None:
    with patch(
        "tools.admin_analytics_tools.client_profile",
        new=AsyncMock(
            return_value={
                "telegram_id": 42,
                "name": "Анна",
                "sessions_count": 3,
                "last_session_at": "2026-05-21T10:00:00+00:00",
                "avg_sentiment": 0.5,
                "recent_cards": [{"summary_text": "Положительный."}],
                "top_topics": [{"topic": "food", "count": 2, "avg_sentiment": 1.0}],
            }
        ),
    ):
        out = await client_profile_tool.ainvoke({"telegram_id": 42})
    assert "Анна" in out
    assert "Сессий: 3" in out
    assert "food" in out


# --------------------------------------------------------------------------- #
# _split_chart helper


def test_split_chart_no_codeblock() -> None:
    answer, chart = _split_chart("Просто текст.")
    assert answer == "Просто текст."
    assert chart is None


def test_split_chart_extracts_codeblock() -> None:
    text = "Тренд по дням:\n```\nMon ##\nTue ###\n```\nИтого: рост."
    answer, chart = _split_chart(text)
    assert "Тренд по дням" in answer
    assert "Итого" in answer
    assert chart is not None
    assert "Mon" in chart
    assert "Tue" in chart


# --------------------------------------------------------------------------- #
# answer_admin_question loop


class _FakeLLM:
    def __init__(self, responses: list[AIMessage]) -> None:
        self._responses = list(responses)
        self.calls: list = []

    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        if not self._responses:
            return AIMessage(content="fallback")
        return self._responses.pop(0)


async def test_answer_admin_question_empty_input() -> None:
    out = await answer_admin_question("   ")
    assert isinstance(out, AdminAnswer)
    assert "Слушаю" in out.answer_text
    assert out.tools_used == []


async def test_answer_admin_question_direct_reply() -> None:
    fake = _FakeLLM([AIMessage(content="За неделю было 12 сессий.")])
    with patch("agent.nodes.admin_ask.get_chat_model", return_value=fake):
        out = await answer_admin_question("сколько сессий за неделю?")
    assert isinstance(out, AdminAnswer)
    assert "12 сессий" in out.answer_text
    assert out.tools_used == []
    assert out.chart_text is None


async def test_answer_admin_question_tool_call_then_reply() -> None:
    tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "summary_overview_tool",
                "args": {"days": 7},
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )
    final = AIMessage(content="Сводка: 12 сессий, sentiment +0.5.")
    fake = _FakeLLM([tool_call, final])
    with (
        patch("agent.nodes.admin_ask.get_chat_model", return_value=fake),
        patch(
            "tools.admin_analytics_tools.summary_overview",
            new=AsyncMock(
                return_value={
                    "sessions_count": 12,
                    "avg_sentiment": 0.5,
                    "top_positive_topics": [],
                    "top_negative_topics": [],
                }
            ),
        ),
    ):
        out = await answer_admin_question("дай сводку за неделю")
    assert "12 сессий" in out.answer_text
    assert "summary_overview_tool" in out.tools_used
    # The second LLM call must have included a ToolMessage from the result
    second_call = fake.calls[1]
    assert any(isinstance(m, ToolMessage) for m in second_call)


async def test_answer_admin_question_uses_conversation_history() -> None:
    fake = _FakeLLM([AIMessage(content="Помню, что вы спрашивали о скорости.")])
    with patch("agent.nodes.admin_ask.get_chat_model", return_value=fake):
        out = await answer_admin_question(
            "а в среднем?",
            conversation_history=[
                {"role": "user", "content": "что по скорости?"},
                {"role": "assistant", "content": "Скорость в норме."},
            ],
        )
    assert "скорости" in out.answer_text.lower()
    # history should have been threaded into the first LLM call
    first_call = fake.calls[0]
    roles = [type(m).__name__ for m in first_call]
    # SystemMessage + 2 history + 1 question
    assert roles.count("HumanMessage") >= 2


async def test_answer_admin_question_extracts_chart_from_codeblock() -> None:
    text = "Тренд за 3 дня:\n```\nMon ##\nTue ###\nWed ####\n```"
    fake = _FakeLLM([AIMessage(content=text)])
    with patch("agent.nodes.admin_ask.get_chat_model", return_value=fake):
        out = await answer_admin_question("покажи тренд")
    assert out.chart_text is not None
    assert "Mon" in out.chart_text


@pytest.mark.parametrize("rounds_overflow", [10])
async def test_answer_admin_question_bounded_loop(rounds_overflow: int) -> None:
    # LLM keeps emitting tool_calls — handler must stop after _MAX_TOOL_ROUNDS
    forever_tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "summary_overview_tool",
                "args": {"days": 7},
                "id": "loop",
                "type": "tool_call",
            }
        ],
    )
    fake = _FakeLLM([forever_tool_call] * rounds_overflow)
    with (
        patch("agent.nodes.admin_ask.get_chat_model", return_value=fake),
        patch(
            "tools.admin_analytics_tools.summary_overview",
            new=AsyncMock(
                return_value={
                    "sessions_count": 0,
                    "avg_sentiment": None,
                    "top_positive_topics": [],
                    "top_negative_topics": [],
                }
            ),
        ),
    ):
        out = await answer_admin_question("loop")
    assert "разумное" in out.answer_text.lower() or "сузить" in out.answer_text.lower()
