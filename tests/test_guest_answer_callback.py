"""Unit-тесты для guest_answer_callback и guest_skip_command в bot_guest.handlers.feedback.

Покрытие:
- routing: roster callback и /skip handler зарегистрированы;
- marked_value-конвертер для boolean/number/enum + skip;
- callback boolean→save_answer_with_metric; index продвигается; следующий вопрос задан;
- callback enum/number аналогично;
- callback skip → write НЕ происходит, index +1;
- callback после конца списка → answer("уже завершён"), нет write;
- non-text question → text-handler отвечает «используйте кнопки»;
- text question → text-handler идёт обычным путём (regression);
- /skip команда → index +1 без записи.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot_guest.handlers import feedback as fb

# ----------------------------- fixtures ----------------------------------- #


@pytest.fixture
def state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    return FSMContext(storage=storage, key=key)


def _question(
    expected_type: str,
    *,
    qid: str | None = None,
    metric_key: str = "m1",
    text: str = "Q?",
    enum_values: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": qid or str(uuid4()),
        "text": text,
        "metric_key": metric_key,
        "expected_type": expected_type,
        "enum_values": enum_values,
    }


async def _seed_interview_state(
    state: FSMContext,
    questions: list[dict[str, Any]],
    *,
    index: int = 0,
    session_id: str | None = None,
) -> str:
    sid = session_id or str(uuid4())
    qids = [str(q["id"]) for q in questions]
    qmap = {str(q["id"]): q for q in questions}
    await state.update_data(
        session_id=sid,
        client_id=1,
        question_ids=qids,
        question_index=index,
        questions_map=qmap,
        summary={},
        answers=[],
    )
    return sid


def _make_message_mock() -> MagicMock:
    m = MagicMock()
    m.chat = MagicMock(id=1)
    m.bot = MagicMock()
    m.bot.send_chat_action = AsyncMock()
    m.answer = AsyncMock()
    m.edit_reply_markup = AsyncMock()
    return m


def _make_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user = MagicMock(id=1)
    cb.message = _make_message_mock()
    cb.answer = AsyncMock()
    return cb


# ----------------------------- 1) router smoke --------------------------- #


def test_router_has_callback_and_skip_handler() -> None:
    cb_handlers = fb.router.callback_query.handlers
    msg_handlers = fb.router.message.handlers
    assert len(cb_handlers) >= 1, "guest_answer_callback must be registered"
    # Должен быть skip-command + остальные message-handlers (feedback, voice, answer)
    assert len(msg_handlers) >= 4


# ----------------------------- 2) marked_value converter ----------------- #


@pytest.mark.parametrize(
    "value,expected_type,expected_marked",
    [
        ("yes", "boolean", {"value": True}),
        ("no", "boolean", {"value": False}),
        ("3", "number", {"value": 3}),
        ("Vegan", "enum", {"value": "Vegan"}),
    ],
)
def test_marked_value_from_callback(
    value: str, expected_type: str, expected_marked: dict[str, Any]
) -> None:
    assert fb._marked_value_from_callback(value, expected_type) == expected_marked


def test_marked_value_invalid_boolean() -> None:
    with pytest.raises(ValueError):
        fb._marked_value_from_callback("maybe", "boolean")


def test_marked_value_invalid_type() -> None:
    with pytest.raises(ValueError):
        fb._marked_value_from_callback("x", "text")


def test_answer_text_human_readable() -> None:
    assert fb._answer_text_from_callback("yes", "boolean") == "Да"
    assert fb._answer_text_from_callback("no", "boolean") == "Нет"
    assert fb._answer_text_from_callback("4", "number") == "4"
    assert fb._answer_text_from_callback("Pizza", "enum") == "Pizza"


# ----------------------------- 3) callback boolean → save ---------------- #


async def test_callback_boolean_yes_saves_and_advances(state: FSMContext) -> None:
    q = _question("boolean", qid="q1", metric_key="liked")
    next_q = _question("text", qid="q2", metric_key="comment")
    sid = await _seed_interview_state(state, [q, next_q])

    cb = _make_callback("ans:yes")

    with (
        patch.object(fb, "append_session_message", new=AsyncMock()) as p_append,
        patch.object(fb, "save_answer_with_metric", new=AsyncMock(return_value=1)) as p_save,
    ):
        await fb.guest_answer_callback(cb, state)

    # Сохранено
    p_save.assert_awaited_once()
    assert p_save.await_args is not None
    call_kwargs = p_save.await_args.kwargs
    assert call_kwargs["session_id"] == sid
    assert call_kwargs["question_id"] == "q1"
    assert call_kwargs["answer_text"] == "Да"
    assert call_kwargs["marked_value"] == {"value": True}
    p_append.assert_awaited()

    # Индекс продвинут
    data = await state.get_data()
    assert data["question_index"] == 1
    assert data["answers"][0]["marked_value"] == {"value": True}
    assert data["answers"][0]["answer_text"] == "Да"

    # Клавиатура снята + callback подтверждён
    cb.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
    cb.answer.assert_awaited()
    # Следующий вопрос задан
    cb.message.answer.assert_awaited()


async def test_callback_number_saves_int(state: FSMContext) -> None:
    q = _question("number", qid="q1", metric_key="rating")
    next_q = _question("text", qid="q2", metric_key="why")
    await _seed_interview_state(state, [q, next_q])

    cb = _make_callback("ans:4")

    with (
        patch.object(fb, "append_session_message", new=AsyncMock()),
        patch.object(fb, "save_answer_with_metric", new=AsyncMock(return_value=1)) as p_save,
    ):
        await fb.guest_answer_callback(cb, state)

    assert p_save.await_args is not None
    assert p_save.await_args.kwargs["marked_value"] == {"value": 4}
    data = await state.get_data()
    assert data["answers"][0]["marked_value"] == {"value": 4}


async def test_callback_enum_saves_value(state: FSMContext) -> None:
    q = _question("enum", qid="q1", metric_key="dish", enum_values=["Pizza", "Salad"])
    next_q = _question("text", qid="q2")
    await _seed_interview_state(state, [q, next_q])

    cb = _make_callback("ans:Pizza")

    with (
        patch.object(fb, "append_session_message", new=AsyncMock()),
        patch.object(fb, "save_answer_with_metric", new=AsyncMock(return_value=1)) as p_save,
    ):
        await fb.guest_answer_callback(cb, state)

    assert p_save.await_args is not None
    assert p_save.await_args.kwargs["marked_value"] == {"value": "Pizza"}
    assert p_save.await_args.kwargs["answer_text"] == "Pizza"


# ----------------------------- 4) callback skip → no write --------------- #


async def test_callback_skip_advances_without_write(state: FSMContext) -> None:
    q = _question("boolean", qid="q1")
    next_q = _question("text", qid="q2")
    await _seed_interview_state(state, [q, next_q])

    cb = _make_callback("ans:skip")

    with (
        patch.object(fb, "append_session_message", new=AsyncMock()) as p_append,
        patch.object(fb, "save_answer_with_metric", new=AsyncMock()) as p_save,
    ):
        await fb.guest_answer_callback(cb, state)

    p_save.assert_not_awaited()
    # append может быть вызван _ask_next_question'ом (bot-сообщение со следующим вопросом).
    # Главное — НЕТ append с role='user' (от skip нет пользовательского следа).
    for call in p_append.await_args_list:
        # signature: append_session_message(sid, role, text)
        assert call.args[1] != "user", "skip must not record user message"

    data = await state.get_data()
    assert data["question_index"] == 1
    assert data["answers"] == []  # ничего не добавлено в FSM answers

    cb.answer.assert_awaited()


# ----------------------------- 5) race: callback after end --------------- #


async def test_callback_after_end_alerts_no_write(state: FSMContext) -> None:
    q = _question("boolean", qid="q1")
    # Запустили на индексе уже за концом списка
    await _seed_interview_state(state, [q], index=1)

    cb = _make_callback("ans:yes")

    with (
        patch.object(fb, "append_session_message", new=AsyncMock()),
        patch.object(fb, "save_answer_with_metric", new=AsyncMock()) as p_save,
    ):
        await fb.guest_answer_callback(cb, state)

    p_save.assert_not_awaited()
    cb.answer.assert_awaited_once()
    # alert-текст содержит сигнал «завершён»
    args = cb.answer.await_args
    assert "завершён" in args.args[0] or "завершён" in args.kwargs.get("text", "")


# ----------------------------- 6) text-handler rejects typed ------------- #


async def test_text_handler_rejects_boolean_question(state: FSMContext) -> None:
    q = _question("boolean", qid="q1")
    next_q = _question("text", qid="q2")
    await _seed_interview_state(state, [q, next_q])

    m = MagicMock()
    m.text = "просто текст"
    m.bot = MagicMock()
    m.chat = MagicMock(id=1)
    m.answer = AsyncMock()

    with (
        patch.object(fb, "append_session_message", new=AsyncMock()),
        patch.object(fb, "save_answer_with_metric", new=AsyncMock()) as p_save,
        patch.object(fb, "extract_metric_from_answer", new=AsyncMock()) as p_extract,
    ):
        await fb.guest_answer(m, state)

    p_save.assert_not_awaited()
    p_extract.assert_not_awaited()
    m.answer.assert_awaited_once()
    text = m.answer.await_args.args[0]
    assert "кнопки" in text.lower() or "/skip" in text

    # индекс НЕ продвинут
    data = await state.get_data()
    assert data["question_index"] == 0


async def test_text_handler_accepts_text_question(state: FSMContext) -> None:
    q = _question("text", qid="q1", metric_key="comment")
    next_q = _question("text", qid="q2")
    await _seed_interview_state(state, [q, next_q])

    m = MagicMock()
    m.text = "великолепно"
    m.bot = MagicMock()
    m.chat = MagicMock(id=1)
    m.answer = AsyncMock()

    with (
        patch.object(fb, "append_session_message", new=AsyncMock()),
        patch.object(fb, "save_answer_with_metric", new=AsyncMock(return_value=1)),
        patch.object(
            fb,
            "extract_metric_from_answer",
            new=AsyncMock(return_value={"value": "великолепно"}),
        ),
    ):
        await fb.guest_answer(m, state)

    data = await state.get_data()
    assert data["question_index"] == 1
    assert data["answers"][0]["answer_text"] == "великолепно"


async def test_text_handler_treats_enum_empty_as_text(state: FSMContext) -> None:
    """enum c пустым enum_values rendered как text → text-handler не блокирует."""
    q = _question("enum", qid="q1", metric_key="topic", enum_values=None)
    next_q = _question("text", qid="q2")
    await _seed_interview_state(state, [q, next_q])

    m = MagicMock()
    m.text = "ответ"
    m.bot = MagicMock()
    m.chat = MagicMock(id=1)
    m.answer = AsyncMock()

    with (
        patch.object(fb, "append_session_message", new=AsyncMock()),
        patch.object(fb, "save_answer_with_metric", new=AsyncMock(return_value=1)) as p_save,
        patch.object(
            fb, "extract_metric_from_answer", new=AsyncMock(return_value={"value": "ответ"})
        ),
    ):
        await fb.guest_answer(m, state)

    p_save.assert_awaited_once()


# ----------------------------- 7) /skip command -------------------------- #


async def test_skip_command_advances_without_write(state: FSMContext) -> None:
    q = _question("text", qid="q1")
    next_q = _question("text", qid="q2")
    await _seed_interview_state(state, [q, next_q])

    m = MagicMock()
    m.text = "/skip"
    m.bot = MagicMock()
    m.chat = MagicMock(id=1)
    m.answer = AsyncMock()

    with (
        patch.object(fb, "append_session_message", new=AsyncMock()) as p_append,
        patch.object(fb, "save_answer_with_metric", new=AsyncMock()) as p_save,
    ):
        await fb.guest_skip_command(m, state)

    p_save.assert_not_awaited()
    # append может быть вызван _ask_next_question (bot-сообщение). НЕТ записи role='user'.
    for call in p_append.await_args_list:
        assert call.args[1] != "user", "/skip must not record user message"

    data = await state.get_data()
    assert data["question_index"] == 1
    assert data["answers"] == []


async def test_skip_command_after_end_is_noop(state: FSMContext) -> None:
    q = _question("text", qid="q1")
    await _seed_interview_state(state, [q], index=1)

    m = MagicMock()
    m.text = "/skip"
    m.bot = MagicMock()
    m.chat = MagicMock(id=1)
    m.answer = AsyncMock()

    await fb.guest_skip_command(m, state)
    # ничего не упало; индекс не изменился
    data = await state.get_data()
    assert data["question_index"] == 1
