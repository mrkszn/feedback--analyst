"""Tests for the FSM sticky-state exit hatch on AWAITING_QUESTION_TEXT."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message

from bot_admin.handlers.questions import (
    _natural_language_exit_check,
    admin_fsm_exit_cancel,
    admin_fsm_exit_keep,
    admin_question_add_save,
)


def test_heuristic_pipe_format_is_not_nl() -> None:
    assert _natural_language_exit_check("metric|text|какой вопрос?") is False


def test_heuristic_single_token_is_not_nl() -> None:
    # Likely an aborted attempt at metric_key — let existing parser handle.
    assert _natural_language_exit_check("service_speed") is False


def test_heuristic_empty_is_not_nl() -> None:
    assert _natural_language_exit_check("   ") is False


def test_heuristic_nl_triggers() -> None:
    assert _natural_language_exit_check("как у тебя дела?") is True
    assert _natural_language_exit_check("покажи мне вопросы") is True


def _mk_message(text: str) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(id=1)
    msg.text = text
    msg.answer = AsyncMock()
    return msg


def _mk_state(initial: dict | None = None) -> MagicMock:
    state = MagicMock()
    store = dict(initial or {})
    state.set_state = AsyncMock()
    state.update_data = AsyncMock(side_effect=lambda **kw: store.update(kw))
    state.get_data = AsyncMock(side_effect=lambda: dict(store))
    state.clear = AsyncMock(side_effect=store.clear)
    return state


def _mk_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.data = data
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    return cb


async def test_nl_input_offers_exit_hatch_and_keeps_state() -> None:
    msg = _mk_message("как у тебя дела?")
    state = _mk_state()
    await admin_question_add_save(msg, state)
    msg.answer.assert_awaited_once()
    text, kwargs = msg.answer.await_args.args[0], msg.answer.await_args.kwargs
    assert "Выйти" in text or "обычное сообщение" in text
    kb = kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "fsmexit:cancel" in cbs
    assert "fsmexit:keep" in cbs
    # state.clear NOT called yet
    state.clear.assert_not_called()
    # text stashed for cancel path
    data = await state.get_data()
    assert data["_pending_nl"] == "как у тебя дела?"


async def test_structured_input_still_creates_question() -> None:
    msg = _mk_message("food_liked|boolean|Понравилась ли еда?")
    state = _mk_state()
    with patch(
        "bot_admin.handlers.questions.create_question",
        new=AsyncMock(return_value={"id": "u1"}),
    ) as cq:
        await admin_question_add_save(msg, state)
    cq.assert_awaited_once()
    state.clear.assert_awaited_once()


async def test_exit_cancel_clears_state_and_forwards_to_agent() -> None:
    cb = _mk_callback("fsmexit:cancel")
    state = _mk_state(initial={"_pending_nl": "сколько у меня вопросов?"})
    with (
        patch("bot_admin.handlers.questions.is_admin", new=AsyncMock(return_value=True)),
        patch(
            "bot_admin.handlers.admin_agent.run_admin_agent",
            new=AsyncMock(return_value="Активных вопросов 3."),
        ) as agent,
    ):
        await admin_fsm_exit_cancel(cb, state)
    state.clear.assert_awaited_once()
    agent.assert_awaited_once_with("сколько у меня вопросов?")
    # Final agent reply gets surfaced to admin
    assert any("Активных вопросов 3." in c.args[0] for c in cb.message.answer.await_args_list)


async def test_exit_cancel_without_pending_text_just_clears() -> None:
    cb = _mk_callback("fsmexit:cancel")
    state = _mk_state()
    with patch("bot_admin.handlers.questions.is_admin", new=AsyncMock(return_value=True)):
        await admin_fsm_exit_cancel(cb, state)
    state.clear.assert_awaited_once()


async def test_exit_keep_stays_in_state_and_reprompts() -> None:
    cb = _mk_callback("fsmexit:keep")
    state = _mk_state(initial={"_pending_nl": "..."})
    with patch("bot_admin.handlers.questions.is_admin", new=AsyncMock(return_value=True)):
        await admin_fsm_exit_keep(cb, state)
    state.clear.assert_not_called()
    # Re-prompt sent
    cb.message.answer.assert_awaited_once()
    assert "metric_key" in cb.message.answer.await_args.args[0]
