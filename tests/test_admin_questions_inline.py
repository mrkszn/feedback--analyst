"""Tests for the readable /questions rendering and inline edit/delete callbacks."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import InlineKeyboardMarkup, Message

from presentations.telegram_admin.handlers.questions import (
    admin_question_delete_all_apply,
    admin_question_delete_all_confirm,
    admin_question_delete_apply,
    admin_question_delete_cancel,
    admin_question_delete_confirm,
    admin_question_edit_save,
    admin_question_edit_start,
    admin_questions_list,
)


def _mk_admin_message() -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(id=1)
    msg.answer = AsyncMock()
    return msg


def _mk_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.data = data
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    return cb


async def test_questions_list_renders_numbered_without_uuid_or_metric_key() -> None:
    """The visible text must NOT include UUIDs nor [metric_key, type] tags."""
    rows = [
        {
            "id": "uuid-1",
            "text": "Понравилась ли еда?",
            "metric_key": "food_liked",
            "expected_type": "boolean",
            "is_active": True,
        },
        {
            "id": "uuid-2",
            "text": "Оцените скорость",
            "metric_key": "service_speed",
            "expected_type": "number",
            "is_active": True,
        },
    ]
    message = _mk_admin_message()
    with (
        patch(
            "presentations.telegram_admin.handlers.questions.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.questions.list_questions",
            new=AsyncMock(return_value=rows),
        ),
    ):
        await admin_questions_list(message)

    # 1 header + 2 per-item + 1 footer = 4 messages
    assert message.answer.await_count == 4
    calls = message.answer.await_args_list

    # Header
    header_text = calls[0].args[0]
    assert "2" in header_text and "Активные" in header_text

    # Per-item messages: numbered, with text + (type), no UUID, no metric_key
    item1_text = calls[1].args[0]
    assert item1_text.startswith("1. ")
    assert "Понравилась ли еда?" in item1_text
    assert "(boolean)" in item1_text
    assert "uuid-1" not in item1_text
    assert "food_liked" not in item1_text

    item2_text = calls[2].args[0]
    assert item2_text.startswith("2. ")
    assert "service_speed" not in item2_text

    # Each per-item carries an inline keyboard with edit + delete callbacks
    kb1 = calls[1].kwargs["reply_markup"]
    assert isinstance(kb1, InlineKeyboardMarkup)
    cbs = [b.callback_data for row in kb1.inline_keyboard for b in row]
    assert "qedit:uuid-1" in cbs
    assert "qdel:uuid-1" in cbs

    # Footer
    footer_text = calls[3].args[0]
    footer_kb = calls[3].kwargs["reply_markup"]
    assert "Удалить все" in footer_kb.inline_keyboard[0][0].text
    assert footer_kb.inline_keyboard[0][0].callback_data == "qdelall"
    assert footer_text  # not empty


async def test_questions_list_empty_pool() -> None:
    message = _mk_admin_message()
    with (
        patch(
            "presentations.telegram_admin.handlers.questions.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.questions.list_questions",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await admin_questions_list(message)
    message.answer.assert_awaited_once()
    assert "пуст" in message.answer.await_args.args[0].lower()


async def test_qedit_callback_sets_state_and_prompts() -> None:
    cb = _mk_callback("qedit:uuid-42")
    state = MagicMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    with patch(
        "presentations.telegram_admin.handlers.questions.is_admin", new=AsyncMock(return_value=True)
    ):
        await admin_question_edit_start(cb, state)
    state.set_state.assert_awaited_once()
    state.update_data.assert_awaited_once_with(edit_qid="uuid-42")
    cb.message.answer.assert_awaited_once()
    assert "новый текст" in cb.message.answer.await_args.args[0].lower()


async def test_qedit_save_updates_question() -> None:
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=1)
    message.text = "новый текст вопроса"
    message.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"edit_qid": "uuid-42"})
    state.clear = AsyncMock()
    with patch(
        "presentations.telegram_admin.handlers.questions.update_question",
        new=AsyncMock(return_value={"id": "uuid-42", "text": "новый текст вопроса"}),
    ) as upd:
        await admin_question_edit_save(message, state)
    upd.assert_awaited_once()
    state.clear.assert_awaited_once()
    assert "Обновлено" in message.answer.await_args.args[0]


async def test_qdel_callback_shows_confirm_buttons() -> None:
    cb = _mk_callback("qdel:uuid-9")
    with patch(
        "presentations.telegram_admin.handlers.questions.is_admin", new=AsyncMock(return_value=True)
    ):
        await admin_question_delete_confirm(cb)
    cb.message.answer.assert_awaited_once()
    kb = cb.message.answer.await_args.kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "qdelyes:uuid-9" in cbs
    assert "qdelno" in cbs


async def test_qdelyes_calls_delete_question() -> None:
    cb = _mk_callback("qdelyes:uuid-9")
    with (
        patch(
            "presentations.telegram_admin.handlers.questions.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.questions.delete_question",
            new=AsyncMock(return_value=None),
        ) as dq,
    ):
        await admin_question_delete_apply(cb)
    dq.assert_awaited_once_with("uuid-9")
    cb.message.edit_text.assert_awaited_once()
    assert "Удалено" in cb.message.edit_text.await_args.args[0]


async def test_qdelno_cancels() -> None:
    cb = _mk_callback("qdelno")
    await admin_question_delete_cancel(cb)
    cb.message.edit_text.assert_awaited_once()
    assert "Отменено" in cb.message.edit_text.await_args.args[0]


async def test_qdelallyes_calls_service_and_reports_count() -> None:
    cb = _mk_callback("qdelallyes")
    with (
        patch(
            "presentations.telegram_admin.handlers.questions.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.questions.deactivate_all_questions",
            new=AsyncMock(return_value=5),
        ) as svc,
    ):
        await admin_question_delete_all_apply(cb)
    svc.assert_awaited_once()
    cb.message.edit_text.assert_awaited_once()
    text = cb.message.edit_text.await_args.args[0]
    assert "5" in text


async def test_qdelallyes_empty_pool_message() -> None:
    cb = _mk_callback("qdelallyes")
    with (
        patch(
            "presentations.telegram_admin.handlers.questions.is_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.questions.deactivate_all_questions",
            new=AsyncMock(return_value=0),
        ),
    ):
        await admin_question_delete_all_apply(cb)
    text = cb.message.edit_text.await_args.args[0]
    assert "нечего" in text.lower() or "нет" in text.lower()


async def test_qdelall_shows_confirm() -> None:
    cb = _mk_callback("qdelall")
    with patch(
        "presentations.telegram_admin.handlers.questions.is_admin", new=AsyncMock(return_value=True)
    ):
        await admin_question_delete_all_confirm(cb)
    cb.message.answer.assert_awaited_once()
    text = cb.message.answer.await_args.args[0]
    assert "ВСЕ" in text or "все" in text.lower()
    kb = cb.message.answer.await_args.kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "qdelallyes" in cbs
    assert "qdelno" in cbs
