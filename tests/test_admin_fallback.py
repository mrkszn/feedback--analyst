"""Unit-tests for the admin fallback router.

After Phase 2A.6 the fallback delegates to the conversational admin agent
(via `reply_via_agent`) instead of dumping a static help-list. We assert
on delegation + the require_admin gate.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from bot_admin.handlers.fallback import admin_handle_freetext_fallback, router


def test_fallback_router_smoke() -> None:
    assert router.name == "admin_fallback"
    assert len(router.message.handlers) >= 1


async def test_admin_path_delegates_to_agent() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=42)
    message.text = "сколько у меня вопросов?"
    message.answer = AsyncMock()

    with (
        patch(
            "bot_admin.handlers.questions.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.fallback.reply_via_agent",
            new=AsyncMock(),
        ) as agent,
    ):
        await admin_handle_freetext_fallback(message)

    agent.assert_awaited_once_with(message)


async def test_non_admin_path_blocked_at_gate() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=99)
    message.text = "сколько у меня вопросов?"
    message.answer = AsyncMock()

    with (
        patch(
            "bot_admin.handlers.questions.is_admin",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "bot_admin.handlers.fallback.reply_via_agent",
            new=AsyncMock(),
        ) as agent,
    ):
        await admin_handle_freetext_fallback(message)

    agent.assert_not_awaited()
    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert "Доступ только для админов" in text


async def test_empty_text_no_agent_call() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=42)
    message.text = None
    message.answer = AsyncMock()

    with (
        patch(
            "bot_admin.handlers.questions.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.fallback.reply_via_agent",
            new=AsyncMock(),
        ) as agent,
    ):
        await admin_handle_freetext_fallback(message)

    agent.assert_not_awaited()
