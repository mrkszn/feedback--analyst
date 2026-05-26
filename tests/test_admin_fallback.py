"""Unit-tests for the admin fallback router.

After Phase 3.5 the fallback router routes free-text by the FSM `admin_mode`
key: `admin` → `reply_via_agent` (questions CRUD), `analytics` →
`reply_via_admin_ask` (analytics agent).
"""

from unittest.mock import AsyncMock, MagicMock, patch

from bot_admin.handlers.fallback import admin_handle_freetext_fallback, router


def _state(mode: str | None = None) -> MagicMock:
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"admin_mode": mode} if mode else {})
    return state


def test_fallback_router_smoke() -> None:
    assert router.name == "admin_fallback"
    assert len(router.message.handlers) >= 1


async def test_admin_mode_routes_to_questions_agent() -> None:
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
        patch(
            "bot_admin.handlers.fallback.reply_via_admin_ask",
            new=AsyncMock(),
        ) as ask,
    ):
        await admin_handle_freetext_fallback(message, _state(mode="admin"))

    agent.assert_awaited_once_with(message)
    ask.assert_not_awaited()


async def test_default_mode_routes_to_questions_agent() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=42)
    message.text = "что у меня в пуле?"
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
        patch(
            "bot_admin.handlers.fallback.reply_via_admin_ask",
            new=AsyncMock(),
        ) as ask,
    ):
        # No admin_mode set → default to "admin"
        await admin_handle_freetext_fallback(message, _state(mode=None))

    agent.assert_awaited_once_with(message)
    ask.assert_not_awaited()


async def test_analytics_mode_routes_to_admin_ask() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=42)
    message.text = "какие топ-3 жалобы за неделю?"
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
        patch(
            "bot_admin.handlers.fallback.reply_via_admin_ask",
            new=AsyncMock(),
        ) as ask,
    ):
        await admin_handle_freetext_fallback(message, _state(mode="analytics"))

    ask.assert_awaited_once_with(message)
    agent.assert_not_awaited()


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
        patch(
            "bot_admin.handlers.fallback.reply_via_admin_ask",
            new=AsyncMock(),
        ) as ask,
    ):
        await admin_handle_freetext_fallback(message, _state(mode="analytics"))

    agent.assert_not_awaited()
    ask.assert_not_awaited()
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
        patch(
            "bot_admin.handlers.fallback.reply_via_admin_ask",
            new=AsyncMock(),
        ) as ask,
    ):
        await admin_handle_freetext_fallback(message, _state(mode="analytics"))

    agent.assert_not_awaited()
    ask.assert_not_awaited()
