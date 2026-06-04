"""Unit-тесты для bot_admin.handlers.question_voice."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from channels.telegram.common.fsm.states import AdminFlow
from core.agent.nodes.synthesize_questions import QuestionDraft
from presentations.telegram_admin.handlers import question_voice as qv

# ----------------------------- fixtures ------------------------------------ #


@pytest.fixture
def state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    return FSMContext(storage=storage, key=key)


def _make_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_chat_action = AsyncMock()
    bot.edit_message_text = AsyncMock()
    return bot


def _make_message(text: str | None = None, has_voice: bool = False) -> MagicMock:
    # spec=Message → isinstance(m, Message) → True (нужно для handlers)
    m = MagicMock(spec=Message)
    m.text = text
    m.from_user = MagicMock(id=42)
    m.chat = MagicMock(id=1)
    m.bot = _make_bot()
    m.answer = AsyncMock()
    m.edit_text = AsyncMock()
    if has_voice:
        m.voice = MagicMock(file_id="voice123")
    else:
        m.voice = None
    return m


def _make_callback(data: str, message: MagicMock | None = None) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user = MagicMock(id=42)
    cb.message = message or _make_message()
    cb.bot = _make_bot()
    cb.answer = AsyncMock()
    return cb


def _sent_message_mock(message_id: int = 1001) -> MagicMock:
    """Mock of Message that callback.message.answer returns (has .message_id)."""
    sent = MagicMock(spec=Message)
    sent.message_id = message_id
    return sent


# ----------------------------- 1) router smoke ----------------------------- #


def test_router_smoke() -> None:
    assert qv.router.name == "admin_question_voice"
    assert len(qv.router.callback_query.handlers) >= 5  # 5 callbacks
    assert len(qv.router.message.handlers) >= 4  # 4 message handlers


# ----------------------------- 2-4) count ---------------------------------- #


async def test_voice_count_invalid_letters(state: FSMContext) -> None:
    await state.set_state(AdminFlow.AWAITING_QUESTION_COUNT)
    msg = _make_message(text="abc")
    await qv.admin_handle_voice_count(msg, state)
    assert await state.get_state() == AdminFlow.AWAITING_QUESTION_COUNT.state
    assert "1" in msg.answer.await_args.args[0] and "10" in msg.answer.await_args.args[0]


@pytest.mark.parametrize("bad", ["0", "11", "-1", "100"])
async def test_voice_count_out_of_range(bad: str, state: FSMContext) -> None:
    await state.set_state(AdminFlow.AWAITING_QUESTION_COUNT)
    msg = _make_message(text=bad)
    await qv.admin_handle_voice_count(msg, state)
    assert await state.get_state() == AdminFlow.AWAITING_QUESTION_COUNT.state
    msg.answer.assert_awaited_once()


async def test_voice_count_valid(state: FSMContext) -> None:
    await state.set_state(AdminFlow.AWAITING_QUESTION_COUNT)
    msg = _make_message(text="5")
    await qv.admin_handle_voice_count(msg, state)
    assert await state.get_state() == AdminFlow.AWAITING_QUESTION_VOICE.state
    data = await state.get_data()
    assert data["voice_count"] == 5
    msg.answer.assert_awaited_once()


# ----------------------------- 5) text reject ------------------------------ #


async def test_voice_text_reject() -> None:
    msg = _make_message(text="привет")
    await qv.admin_handle_voice_text_reject(msg)
    msg.answer.assert_awaited_once()
    assert "голос" in msg.answer.await_args.args[0].lower()


# ----------------------------- 6-8) voice intake --------------------------- #


async def test_voice_intake_full_flow(state: FSMContext) -> None:
    await state.set_state(AdminFlow.AWAITING_QUESTION_VOICE)
    await state.update_data(voice_count=3)
    msg = _make_message(has_voice=True)
    msg.answer.side_effect = [
        _sent_message_mock(1001),
        _sent_message_mock(1002),
        _sent_message_mock(1003),
    ]

    path = MagicMock(spec=Path)
    path.unlink = MagicMock()
    drafts = [
        QuestionDraft(text="Q1?", metric_key="m1", expected_type="text"),
        QuestionDraft(text="Q2?", metric_key="m2", expected_type="number"),
        QuestionDraft(text="Q3?", metric_key="m3", expected_type="boolean"),
    ]
    with (
        patch(
            "presentations.telegram_admin.handlers.question_voice.download_voice_to_tmp",
            new=AsyncMock(return_value=path),
        ),
        patch(
            "presentations.telegram_admin.handlers.question_voice.transcribe_voice",
            new=AsyncMock(return_value="о скорости и качестве"),
        ),
        patch(
            "presentations.telegram_admin.handlers.question_voice.synthesize_questions",
            new=AsyncMock(return_value=drafts),
        ),
    ):
        await qv.admin_handle_voice_intake(msg, state)

    assert msg.answer.await_count == 3
    assert await state.get_state() is None
    data = await state.get_data()
    assert len(data["drafts"]) == 3
    # message_id сохранён
    for d in data["drafts"].values():
        assert d["message_id"] in {1001, 1002, 1003}
    assert data["transcript"] == "о скорости и качестве"
    path.unlink.assert_called_once_with(missing_ok=True)


async def test_voice_intake_partial(state: FSMContext) -> None:
    await state.set_state(AdminFlow.AWAITING_QUESTION_VOICE)
    await state.update_data(voice_count=5)
    msg = _make_message(has_voice=True)
    msg.answer.side_effect = [
        _sent_message_mock(1001),
        _sent_message_mock(1002),
        _sent_message_mock(1003),
        MagicMock(spec=Message),  # notice
    ]

    path = MagicMock(spec=Path)
    path.unlink = MagicMock()
    drafts = [
        QuestionDraft(text="Q1?", metric_key="m1", expected_type="text"),
        QuestionDraft(text="Q2?", metric_key="m2", expected_type="text"),
        QuestionDraft(text="Q3?", metric_key="m3", expected_type="text"),
    ]
    with (
        patch(
            "presentations.telegram_admin.handlers.question_voice.download_voice_to_tmp",
            new=AsyncMock(return_value=path),
        ),
        patch(
            "presentations.telegram_admin.handlers.question_voice.transcribe_voice",
            new=AsyncMock(return_value="t"),
        ),
        patch(
            "presentations.telegram_admin.handlers.question_voice.synthesize_questions",
            new=AsyncMock(return_value=drafts),
        ),
    ):
        await qv.admin_handle_voice_intake(msg, state)

    # 3 drafts + 1 notice
    assert msg.answer.await_count == 4
    notice = msg.answer.await_args_list[-1].args[0]
    assert "3" in notice and "5" in notice


async def test_voice_intake_empty_transcript(state: FSMContext) -> None:
    await state.set_state(AdminFlow.AWAITING_QUESTION_VOICE)
    await state.update_data(voice_count=3)
    msg = _make_message(has_voice=True)
    path = MagicMock(spec=Path)
    path.unlink = MagicMock()

    with (
        patch(
            "presentations.telegram_admin.handlers.question_voice.download_voice_to_tmp",
            new=AsyncMock(return_value=path),
        ),
        patch(
            "presentations.telegram_admin.handlers.question_voice.transcribe_voice",
            new=AsyncMock(return_value="  "),
        ),
    ):
        await qv.admin_handle_voice_intake(msg, state)

    msg.answer.assert_awaited_once()
    assert "не удалось" in msg.answer.await_args.args[0].lower()
    assert await state.get_state() is None
    path.unlink.assert_called_once_with(missing_ok=True)


async def test_voice_intake_no_drafts(state: FSMContext) -> None:
    await state.set_state(AdminFlow.AWAITING_QUESTION_VOICE)
    await state.update_data(voice_count=3)
    msg = _make_message(has_voice=True)
    path = MagicMock(spec=Path)
    path.unlink = MagicMock()

    with (
        patch(
            "presentations.telegram_admin.handlers.question_voice.download_voice_to_tmp",
            new=AsyncMock(return_value=path),
        ),
        patch(
            "presentations.telegram_admin.handlers.question_voice.transcribe_voice",
            new=AsyncMock(return_value="t"),
        ),
        patch(
            "presentations.telegram_admin.handlers.question_voice.synthesize_questions",
            new=AsyncMock(return_value=[]),
        ),
    ):
        await qv.admin_handle_voice_intake(msg, state)

    assert await state.get_state() is None
    assert "валидного" in msg.answer.await_args.args[0]


# ----------------------------- 9-11) confirm/cancel ------------------------ #


async def test_draft_confirm(state: FSMContext) -> None:
    draft_id = "abc12345"
    draft_data = {
        "text": "Q?",
        "metric_key": "m1",
        "expected_type": "text",
        "enum_values": None,
        "message_id": 1001,
    }
    await state.update_data(drafts={draft_id: draft_data})
    msg = _make_message()
    cb = _make_callback(f"draft:confirm:{draft_id}", message=msg)

    with patch(
        "presentations.telegram_admin.handlers.question_voice.create_question",
        new=AsyncMock(return_value={"id": "qid-1"}),
    ) as create_mock:
        await qv.admin_handle_draft_confirm(cb, state)

    create_mock.assert_awaited_once()
    assert create_mock.await_args is not None
    _, kwargs = create_mock.await_args
    assert kwargs["text"] == "Q?"
    assert kwargs["metric_key"] == "m1"
    assert kwargs["created_by"] == 42
    msg.edit_text.assert_awaited_once()
    assert "qid-1" in msg.edit_text.await_args.args[0]
    data = await state.get_data()
    assert draft_id not in data.get("drafts", {})


async def test_draft_confirm_race(state: FSMContext) -> None:
    """Second click on already-confirmed draft → alert."""
    await state.update_data(drafts={})
    cb = _make_callback("draft:confirm:gone1234")
    await qv.admin_handle_draft_confirm(cb, state)
    cb.answer.assert_awaited_once()
    assert cb.answer.await_args is not None
    _, kwargs = cb.answer.await_args
    assert kwargs.get("show_alert") is True
    assert "уже" in cb.answer.await_args.args[0].lower()


async def test_draft_cancel(state: FSMContext) -> None:
    draft_id = "abc12345"
    draft_data = {
        "text": "Q?",
        "metric_key": "m1",
        "expected_type": "text",
        "enum_values": None,
        "message_id": 1001,
    }
    await state.update_data(drafts={draft_id: draft_data})
    msg = _make_message()
    cb = _make_callback(f"draft:cancel:{draft_id}", message=msg)
    with patch(
        "presentations.telegram_admin.handlers.question_voice.create_question",
        new=AsyncMock(),
    ) as create_mock:
        await qv.admin_handle_draft_cancel(cb, state)
    create_mock.assert_not_awaited()
    msg.edit_text.assert_awaited_once()
    assert "Отменено" in msg.edit_text.await_args.args[0]
    data = await state.get_data()
    assert draft_id not in data.get("drafts", {})


# ----------------------------- 12) regen ----------------------------------- #


async def test_draft_regen(state: FSMContext) -> None:
    draft_id = "abc12345"
    draft_data = {
        "text": "OldQ?",
        "metric_key": "old",
        "expected_type": "text",
        "enum_values": None,
        "message_id": 1001,
    }
    await state.update_data(
        drafts={draft_id: draft_data},
        transcript="расшифровка",
    )
    msg = _make_message()
    cb = _make_callback(f"draft:regen:{draft_id}", message=msg)
    new = QuestionDraft(text="NewQ?", metric_key="new", expected_type="number")

    with patch(
        "presentations.telegram_admin.handlers.question_voice.regenerate_single_question",
        new=AsyncMock(return_value=new),
    ) as regen_mock:
        await qv.admin_handle_draft_regen(cb, state)

    regen_mock.assert_awaited_once()
    msg.edit_text.assert_awaited_once()
    assert "NewQ?" in msg.edit_text.await_args.args[0]
    data = await state.get_data()
    assert data["drafts"][draft_id]["metric_key"] == "new"
    assert data["drafts"][draft_id]["message_id"] == 1001


# ----------------------------- 13-14) edit start/input --------------------- #


async def test_draft_edit_start(state: FSMContext) -> None:
    draft_id = "abc12345"
    draft_data: dict[str, Any] = {
        "text": "Q?",
        "metric_key": "m1",
        "expected_type": "text",
        "enum_values": None,
        "message_id": 1001,
    }
    await state.update_data(drafts={draft_id: draft_data})
    msg = _make_message()
    cb = _make_callback(f"draft:edit:{draft_id}", message=msg)
    await qv.admin_handle_draft_edit(cb, state)
    assert await state.get_state() == AdminFlow.AWAITING_DRAFT_EDIT.state
    data = await state.get_data()
    assert data["editing_draft_id"] == draft_id
    msg.answer.assert_awaited_once()


async def test_draft_edit_input_valid_text(state: FSMContext) -> None:
    draft_id = "abc12345"
    draft_data: dict[str, Any] = {
        "text": "Q?",
        "metric_key": "old",
        "expected_type": "text",
        "enum_values": None,
        "message_id": 1001,
    }
    await state.update_data(drafts={draft_id: draft_data}, editing_draft_id=draft_id)
    await state.set_state(AdminFlow.AWAITING_DRAFT_EDIT)
    msg = _make_message(text="speed|number")
    await qv.admin_handle_draft_edit_input(msg, state)
    assert await state.get_state() is None
    data = await state.get_data()
    assert data["drafts"][draft_id]["metric_key"] == "speed"
    assert data["drafts"][draft_id]["expected_type"] == "number"
    msg.bot.edit_message_text.assert_awaited_once()
    msg.answer.assert_awaited_once()
    assert "Обновлено" in msg.answer.await_args.args[0]


# ----------------------------- 15) enum ok --------------------------------- #


async def test_draft_edit_input_enum_ok(state: FSMContext) -> None:
    draft_id = "abc12345"
    draft_data: dict[str, Any] = {
        "text": "Q?",
        "metric_key": "old",
        "expected_type": "text",
        "enum_values": None,
        "message_id": 1001,
    }
    await state.update_data(drafts={draft_id: draft_data}, editing_draft_id=draft_id)
    await state.set_state(AdminFlow.AWAITING_DRAFT_EDIT)
    msg = _make_message(text="topic|enum|a,b,c")
    await qv.admin_handle_draft_edit_input(msg, state)
    data = await state.get_data()
    assert data["drafts"][draft_id]["expected_type"] == "enum"
    assert data["drafts"][draft_id]["enum_values"] == ["a", "b", "c"]


# ----------------------------- 16-17) edit errors -------------------------- #


@pytest.mark.parametrize(
    "bad_text",
    [
        "topic|enum",  # enum без значений
        "topic|enum|x",  # enum с 1 значением
    ],
)
async def test_draft_edit_input_enum_missing_values(bad_text: str, state: FSMContext) -> None:
    draft_id = "abc12345"
    draft_data: dict[str, Any] = {
        "text": "Q?",
        "metric_key": "old",
        "expected_type": "text",
        "enum_values": None,
        "message_id": 1001,
    }
    await state.update_data(drafts={draft_id: draft_data}, editing_draft_id=draft_id)
    await state.set_state(AdminFlow.AWAITING_DRAFT_EDIT)
    msg = _make_message(text=bad_text)
    await qv.admin_handle_draft_edit_input(msg, state)
    assert await state.get_state() == AdminFlow.AWAITING_DRAFT_EDIT.state
    msg.answer.assert_awaited_once()
    assert "ошибка" in msg.answer.await_args.args[0].lower()


async def test_draft_edit_input_bad_type(state: FSMContext) -> None:
    draft_id = "abc12345"
    draft_data: dict[str, Any] = {
        "text": "Q?",
        "metric_key": "old",
        "expected_type": "text",
        "enum_values": None,
        "message_id": 1001,
    }
    await state.update_data(drafts={draft_id: draft_data}, editing_draft_id=draft_id)
    await state.set_state(AdminFlow.AWAITING_DRAFT_EDIT)
    msg = _make_message(text="key|unknown")
    await qv.admin_handle_draft_edit_input(msg, state)
    assert await state.get_state() == AdminFlow.AWAITING_DRAFT_EDIT.state
    msg.answer.assert_awaited_once()
    assert "ошибка" in msg.answer.await_args.args[0].lower()
