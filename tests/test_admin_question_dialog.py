"""Tests for the in-dialog AI-assisted question creation flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.nodes.admin_assistant import draft_question_from_nl
from agent.nodes.synthesize_questions import QuestionDraft
from bot_admin.handlers.admin_question_dialog import (
    admin_question_dialog_cancel,
    admin_question_dialog_confirm,
    admin_question_dialog_describe,
    admin_question_dialog_retry,
    admin_question_dialog_start,
)
from bot_common.fsm.states import AdminFlow


def _mk_message(text: str | None = None) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock(id=1)
    msg.text = text
    msg.bot = None  # ChatActionSender is bypassed when bot is None
    msg.chat = MagicMock(id=10)
    msg.answer = AsyncMock()
    return msg


def _mk_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.data = data
    from aiogram.types import Message as _Msg

    cb.message = MagicMock(spec=_Msg)
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def _mk_state(initial: dict | None = None) -> MagicMock:
    state = MagicMock()
    store = dict(initial or {})
    state.set_state = AsyncMock()
    state.update_data = AsyncMock(side_effect=lambda **kw: store.update(kw))
    state.get_data = AsyncMock(side_effect=lambda: dict(store))
    state.clear = AsyncMock(side_effect=store.clear)
    return state


# --------------------------------------------------------------------------- #
# agent/nodes/admin_assistant.py


async def test_draft_question_from_nl_empty_raises() -> None:
    with pytest.raises(ValueError):
        await draft_question_from_nl("   ")


async def test_draft_question_from_nl_returns_draft() -> None:
    fake = QuestionDraft(
        text="Понравилась ли еда?",
        metric_key="food_liked",
        expected_type="boolean",
    )
    with patch(
        "agent.nodes.admin_assistant.chat_completion",
        new=AsyncMock(return_value=fake),
    ):
        out = await draft_question_from_nl("спрашивай нравится ли еда")
    assert out.metric_key == "food_liked"
    assert out.expected_type == "boolean"


async def test_draft_question_from_nl_invalid_enum_raises() -> None:
    # _normalize_draft rejects enum with <2 values
    bad = QuestionDraft(
        text="Что выберете?",
        metric_key="choice",
        expected_type="enum",
        enum_values=["один"],
    )
    with patch(
        "agent.nodes.admin_assistant.chat_completion",
        new=AsyncMock(return_value=bad),
    ):
        with pytest.raises(ValueError, match="invalid"):
            await draft_question_from_nl("вопрос")


# --------------------------------------------------------------------------- #
# handlers


async def test_dialog_start_sets_state_and_prompts() -> None:
    cb = _mk_callback("addq:dialog")
    state = _mk_state()
    with patch(
        "bot_admin.handlers.admin_question_dialog.is_admin",
        new=AsyncMock(return_value=True),
    ):
        await admin_question_dialog_start(cb, state)
    state.set_state.assert_awaited_once_with(AdminFlow.AWAITING_NL_DESCRIPTION)
    cb.message.answer.assert_awaited_once()


async def test_dialog_describe_drafts_and_moves_to_confirmation() -> None:
    msg = _mk_message("спроси нравится ли еда")
    state = _mk_state()
    fake = QuestionDraft(
        text="Понравилась ли еда?",
        metric_key="food_liked",
        expected_type="boolean",
    )
    with patch(
        "bot_admin.handlers.admin_question_dialog.draft_question_from_nl",
        new=AsyncMock(return_value=fake),
    ):
        await admin_question_dialog_describe(msg, state)

    state.set_state.assert_awaited_with(AdminFlow.AWAITING_NL_CONFIRMATION)
    msg.answer.assert_awaited_once()
    text = msg.answer.await_args.args[0]
    assert "Понравилась ли еда" in text
    assert "boolean" in text
    assert "food_liked" in text
    # Confirm kb has yes/edit/no
    kb = msg.answer.await_args.kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert {"nldraft:yes", "nldraft:edit", "nldraft:no"} <= set(cbs)


async def test_dialog_describe_llm_error_keeps_state() -> None:
    msg = _mk_message("что-то непонятное")
    state = _mk_state()
    with patch(
        "bot_admin.handlers.admin_question_dialog.draft_question_from_nl",
        new=AsyncMock(side_effect=ValueError("invalid")),
    ):
        await admin_question_dialog_describe(msg, state)
    msg.answer.assert_awaited_once()
    assert "распарсить" in msg.answer.await_args.args[0].lower()
    # state did NOT move to confirmation
    confirmation_calls = [
        c
        for c in state.set_state.await_args_list
        if c.args and c.args[0] == AdminFlow.AWAITING_NL_CONFIRMATION
    ]
    assert not confirmation_calls


async def test_dialog_confirm_creates_question() -> None:
    cb = _mk_callback("nldraft:yes")
    state = _mk_state(
        initial={
            "nl_draft": {
                "text": "Понравилась ли еда?",
                "metric_key": "food_liked",
                "expected_type": "boolean",
                "enum_values": None,
            }
        }
    )
    with (
        patch(
            "bot_admin.handlers.admin_question_dialog.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "bot_admin.handlers.admin_question_dialog.create_question",
            new=AsyncMock(return_value={"id": "abc", "text": "Понравилась ли еда?"}),
        ) as cq,
    ):
        await admin_question_dialog_confirm(cb, state)
    cq.assert_awaited_once()
    state.clear.assert_awaited_once()
    cb.message.edit_text.assert_awaited_once()
    assert "Создан" in cb.message.edit_text.await_args.args[0]


async def test_dialog_confirm_lost_draft() -> None:
    cb = _mk_callback("nldraft:yes")
    state = _mk_state()
    with patch(
        "bot_admin.handlers.admin_question_dialog.is_admin",
        new=AsyncMock(return_value=True),
    ):
        await admin_question_dialog_confirm(cb, state)
    cb.answer.assert_awaited()
    state.clear.assert_awaited()


async def test_dialog_retry_reenters_description() -> None:
    cb = _mk_callback("nldraft:edit")
    state = _mk_state(initial={"nl_draft": {"text": "x"}})
    with patch(
        "bot_admin.handlers.admin_question_dialog.is_admin",
        new=AsyncMock(return_value=True),
    ):
        await admin_question_dialog_retry(cb, state)
    state.set_state.assert_awaited_with(AdminFlow.AWAITING_NL_DESCRIPTION)
    cb.message.answer.assert_awaited_once()


async def test_dialog_cancel_clears_state() -> None:
    cb = _mk_callback("nldraft:no")
    state = _mk_state(initial={"nl_draft": {"text": "x"}})
    await admin_question_dialog_cancel(cb, state)
    state.clear.assert_awaited_once()
    cb.message.edit_text.assert_awaited_once()
