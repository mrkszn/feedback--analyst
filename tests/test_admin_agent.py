"""Tests for the conversational admin agent + its tool wrappers."""

from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from core.tools.admin_question_tools import (
    create_question_tool,
    delete_question_tool,
    find_question_tool,
    list_active_questions_tool,
)
from presentations.telegram_admin.handlers.admin_agent import reply_via_agent, run_admin_agent

# --------------------------------------------------------------------------- #
# tool wrappers (return LLM-friendly strings)


async def test_list_active_tool_empty() -> None:
    with patch(
        "core.tools.admin_question_tools.list_questions",
        new=AsyncMock(return_value=[]),
    ):
        out = await list_active_questions_tool.ainvoke({})
    assert "нет" in out.lower()


async def test_list_active_tool_renders_rows() -> None:
    rows = [
        {
            "id": "u1",
            "text": "Понравилась ли еда?",
            "metric_key": "food_liked",
            "expected_type": "boolean",
        }
    ]
    with patch(
        "core.tools.admin_question_tools.list_questions",
        new=AsyncMock(return_value=rows),
    ):
        out = await list_active_questions_tool.ainvoke({})
    assert "Понравилась ли еда?" in out
    assert "food_liked" in out
    assert "u1" in out


async def test_find_tool_no_results() -> None:
    with patch(
        "core.tools.admin_question_tools.find_question_by_text",
        new=AsyncMock(return_value=[]),
    ):
        out = await find_question_tool.ainvoke({"query": "еда"})
    assert "ничего не найдено" in out.lower()


async def test_create_tool_handles_value_error() -> None:
    with patch(
        "core.tools.admin_question_tools.create_question",
        new=AsyncMock(side_effect=ValueError("dup")),
    ):
        out = await create_question_tool.ainvoke(
            {"text": "q", "metric_key": "k", "expected_type": "text"}
        )
    assert "не удалось" in out.lower()


async def test_create_tool_success() -> None:
    with patch(
        "core.tools.admin_question_tools.create_question",
        new=AsyncMock(return_value={"id": "u1", "text": "q", "expected_type": "boolean"}),
    ):
        out = await create_question_tool.ainvoke(
            {"text": "q", "metric_key": "k", "expected_type": "boolean"}
        )
    assert "u1" in out


async def test_delete_tool_lookup_error() -> None:
    with patch(
        "core.tools.admin_question_tools.delete_question",
        new=AsyncMock(side_effect=LookupError("nope")),
    ):
        out = await delete_question_tool.ainvoke({"question_id": "u404"})
    assert "не найден" in out.lower()


async def test_delete_tool_success() -> None:
    with patch(
        "core.tools.admin_question_tools.delete_question",
        new=AsyncMock(return_value=None),
    ):
        out = await delete_question_tool.ainvoke({"question_id": "u1"})
    assert "скрыт" in out.lower()


# --------------------------------------------------------------------------- #
# agent loop


class _FakeLLM:
    """Mock LLM that returns a queued list of AIMessages on each ainvoke."""

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


async def test_run_admin_agent_returns_direct_reply() -> None:
    fake = _FakeLLM([AIMessage(content="Активных вопросов 3.")])
    with patch(
        "presentations.telegram_admin.handlers.admin_agent.get_chat_model",
        return_value=fake,
    ):
        reply = await run_admin_agent("сколько вопросов?")
    assert reply == "Активных вопросов 3."


async def test_run_admin_agent_executes_tool_then_replies() -> None:
    tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "list_active_questions_tool",
                "args": {},
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )
    final = AIMessage(content="У вас 2 активных вопроса.")
    fake = _FakeLLM([tool_call, final])
    with (
        patch(
            "presentations.telegram_admin.handlers.admin_agent.get_chat_model",
            return_value=fake,
        ),
        patch(
            "core.tools.admin_question_tools.list_questions",
            new=AsyncMock(
                return_value=[
                    {
                        "id": "u1",
                        "text": "Q1",
                        "metric_key": "m1",
                        "expected_type": "boolean",
                    },
                    {
                        "id": "u2",
                        "text": "Q2",
                        "metric_key": "m2",
                        "expected_type": "text",
                    },
                ]
            ),
        ),
    ):
        reply = await run_admin_agent("покажи вопросы")
    assert "2 активных" in reply
    # Second LLM call must have seen a ToolMessage from the tool result
    second_call_messages = fake.calls[1]
    roles = [type(m).__name__ for m in second_call_messages]
    assert "ToolMessage" in roles


async def test_run_admin_agent_empty_input() -> None:
    out = await run_admin_agent("   ")
    assert "Слушаю" in out


async def test_reply_via_agent_sends_answer() -> None:
    msg = MagicMock()
    msg.text = "привет"
    msg.bot = None
    msg.chat = MagicMock(id=1)
    msg.answer = AsyncMock()

    with patch(
        "presentations.telegram_admin.handlers.admin_agent.run_admin_agent",
        new=AsyncMock(return_value="hi"),
    ):
        await reply_via_agent(msg)

    msg.answer.assert_awaited_once_with("hi")
