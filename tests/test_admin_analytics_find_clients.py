"""Tests for /find and /clients handlers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot_admin.handlers.analytics_commands import cmd_clients, cmd_find


def _mk_message() -> MagicMock:
    msg = MagicMock()
    msg.from_user = SimpleNamespace(id=1, full_name="Tester")
    msg.answer = AsyncMock()
    return msg


def _cmd(args: str | None) -> MagicMock:
    c = MagicMock()
    c.args = args
    return c


# --------------------------------------------------------------------------- #
# /find


async def test_cmd_find_empty_args_shows_usage() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=True),
    ):
        await cmd_find(msg, _cmd(None))
    assert "/find" in msg.answer.call_args.args[0]


async def test_cmd_find_no_matches() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.semantic_search",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await cmd_find(msg, _cmd("клиенты с жалобами"))
    text = msg.answer.call_args.args[0]
    assert "не нашёл" in text.lower() or "не найдено" in text.lower()


async def test_cmd_find_renders_hits() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.semantic_search",
            new=AsyncMock(
                return_value=[
                    {
                        "session_id": "s1",
                        "client_id": 42,
                        "score": 0.91,
                        "summary_text": "Жалоба на скорость подачи",
                        "sentiment": "negative",
                        "started_at": "2026-05-20T10:00:00+00:00",
                    },
                    {
                        "session_id": "s2",
                        "client_id": None,
                        "score": 0.80,
                        "summary_text": "",
                        "sentiment": None,
                        "started_at": None,
                    },
                ]
            ),
        ),
    ):
        await cmd_find(msg, _cmd("медленно"))
    text = msg.answer.call_args.args[0]
    assert "Жалоба" in text
    assert "client=42" in text
    # graceful handling of None client_id / missing date
    assert "client=—" in text


async def test_cmd_find_handles_service_value_error() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.semantic_search",
            new=AsyncMock(side_effect=ValueError("empty")),
        ),
    ):
        await cmd_find(msg, _cmd("x"))
    text = msg.answer.call_args.args[0]
    assert "не удался" in text.lower()


# --------------------------------------------------------------------------- #
# /clients


async def test_cmd_clients_missing_arg_shows_usage() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=True),
    ):
        await cmd_clients(msg, _cmd(None))
    assert "/clients" in msg.answer.call_args.args[0]


async def test_cmd_clients_non_numeric_arg() -> None:
    msg = _mk_message()
    with patch(
        "bot_admin.handlers.analytics_commands.require_admin",
        new=AsyncMock(return_value=True),
    ):
        await cmd_clients(msg, _cmd("not-a-number"))
    text = msg.answer.call_args.args[0]
    assert "числом" in text


async def test_cmd_clients_not_found() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.client_profile",
            new=AsyncMock(side_effect=LookupError("nope")),
        ),
    ):
        await cmd_clients(msg, _cmd("999"))
    text = msg.answer.call_args.args[0]
    assert "не найден" in text.lower()


async def test_cmd_clients_renders_profile() -> None:
    msg = _mk_message()
    with (
        patch(
            "bot_admin.handlers.analytics_commands.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.analytics_commands.client_profile",
            new=AsyncMock(
                return_value={
                    "telegram_id": 42,
                    "name": "Анна",
                    "sessions_count": 3,
                    "last_session_at": "2026-05-21T10:00:00+00:00",
                    "avg_sentiment": 0.5,
                    "recent_cards": [
                        {"summary_text": "Положительная карточка."},
                    ],
                    "top_topics": [{"topic": "food", "count": 2, "avg_sentiment": 1.0}],
                }
            ),
        ),
    ):
        await cmd_clients(msg, _cmd("42"))
    text = msg.answer.call_args.args[0]
    assert "Анна" in text
    assert "Сессий: 3" in text
    assert "food" in text
    assert "Положительная" in text
