"""Tests for /ask handler — wires admin_ask agent into the admin bot."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from agent.nodes.admin_ask import AdminAnswer
from bot_admin.handlers.analytics_commands import cmd_ask


def _mk_message() -> MagicMock:
    msg = MagicMock()
    msg.from_user = SimpleNamespace(id=1, full_name="Tester")
    msg.answer = AsyncMock()
    return msg


def _cmd(args: str | None) -> MagicMock:
    c = MagicMock()
    c.args = args
    return c


async def test_cmd_ask_empty_arg_shows_usage() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=True),
    ):
        await cmd_ask(msg, _cmd(None))
    text = msg.answer.call_args.args[0]
    assert "/ask" in text


async def test_cmd_ask_sends_plain_answer() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.answer_admin_question",
            new=AsyncMock(return_value=AdminAnswer(answer_text="12 сессий, sentiment +0.5")),
        ),
    ):
        await cmd_ask(msg, _cmd("сколько сессий за неделю?"))
    assert msg.answer.await_count == 1
    text = msg.answer.call_args.args[0]
    assert "12 сессий" in text
    assert msg.answer.call_args.kwargs.get("parse_mode") is None


async def test_cmd_ask_renders_chart_with_markdown() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.answer_admin_question",
            new=AsyncMock(
                return_value=AdminAnswer(
                    answer_text="Тренд за 3 дня:",
                    chart_text="Mon ##\nTue ###\nWed ####",
                )
            ),
        ),
    ):
        await cmd_ask(msg, _cmd("покажи тренд"))
    text = msg.answer.call_args.args[0]
    assert "```" in text
    assert "Mon" in text
    assert msg.answer.call_args.kwargs.get("parse_mode") == "Markdown"


async def test_cmd_ask_requires_admin() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=False),
    ):
        await cmd_ask(msg, _cmd("hi"))
    msg.answer.assert_not_awaited()
