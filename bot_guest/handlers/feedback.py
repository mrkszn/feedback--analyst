import json

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from agent.nodes.analyze import analyze_feedback
from agent.nodes.card import build_client_card
from agent.nodes.dialogue import continue_dialogue
from agent.nodes.extract import extract_metric_from_answer
from bot_common.fsm.states import GuestFlow
from bot_guest.keyboards import build_question_keyboard
from config import settings
from integrations.openai_embed import embed_text
from integrations.pinecone import upsert_client_card_vector
from integrations.whisper import transcribe_voice
from services.clients import create_or_get_client
from services.sessions import (
    append_session_message,
    end_session,
    save_feedback_summary,
    start_session,
)
from tools.answers import save_answer_with_metric
from tools.client_cards import save_client_card
from utils.voice_download import download_voice_to_tmp

router = Router(name="guest_feedback")


async def _process_feedback(
    message: Message,
    state: FSMContext,
    *,
    raw_text: str,
    source: str,
) -> None:
    user = message.from_user
    bot = message.bot
    if user is None or bot is None:
        return

    # Typing-индикатор работает, пока выполняется тяжёлый блок ниже
    # (LLM analyze + DB writes + первый LLM-турн диалога). Telegram продлевает
    # «typing…» каждые ~5 сек автоматически.
    async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
        client = await create_or_get_client(telegram_id=user.id, name=user.full_name)
        session_id = await start_session(client_id=client["telegram_id"])
        await state.update_data(session_id=str(session_id), client_id=client["telegram_id"])

        await append_session_message(session_id, "user", raw_text)

        summary = await analyze_feedback(raw_text)
        await save_feedback_summary(
            session_id,
            raw_text=raw_text,
            source=source,  # type: ignore[arg-type]
            summary=summary.model_dump(),  # type: ignore[arg-type]
        )

        # Persist summary dict under both keys for downstream compat
        # (`survey_consent` reads `feedback_summary`; legacy `_finalize_with_state`
        # reads `summary`).
        summary_dict = summary.model_dump()
        feedback_summary_json = json.dumps(summary_dict, ensure_ascii=False)

        await state.update_data(
            history=[],
            turn_count=0,
            running_context={},
            feedback_summary=summary_dict,
            summary=summary_dict,
            answers=[],
        )

        # First bot turn — empathic reaction + organic clarifying question.
        first_turn = await continue_dialogue(
            feedback_summary=feedback_summary_json,
            history=[],
            restaurant_context=settings.restaurant_context,
            turn_count=0,
            max_turns=5,
        )

    # End of typing-indicator block. Persist bot turn + send.
    await append_session_message(
        session_id,
        "bot",
        first_turn.bot_reply,
    )
    await state.update_data(
        history=[{"role": "bot", "content": first_turn.bot_reply}],
        turn_count=0,  # User hasn't replied yet
    )
    await state.set_state(GuestFlow.IN_DIALOGUE)
    await message.answer(first_turn.bot_reply)


async def _ask_next_question(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    idx = data["question_index"]
    qids = data["question_ids"]
    if idx >= len(qids):
        await _finalize_with_state(message, state)
        return
    q = data["questions_map"][qids[idx]]
    text = q["text"]
    sid = data["session_id"]
    await append_session_message(sid, "bot", text)
    keyboard = build_question_keyboard(q)
    if keyboard is None:
        await message.answer(text)
    else:
        await message.answer(text, reply_markup=keyboard)


def _marked_value_from_callback(value: str, expected_type: str) -> dict[str, object]:
    """Convert callback payload (`ans:<value>`) into marked_value per expected_type."""
    if expected_type == "boolean":
        if value == "yes":
            return {"value": True}
        if value == "no":
            return {"value": False}
        raise ValueError(f"boolean callback expects yes/no, got {value!r}")
    if expected_type == "number":
        return {"value": int(value)}
    if expected_type == "enum":
        return {"value": value}
    raise ValueError(f"callback answer not supported for expected_type={expected_type!r}")


def _answer_text_from_callback(value: str, expected_type: str) -> str:
    """Human-readable answer_text persisted alongside marked_value."""
    if expected_type == "boolean":
        return "Да" if value == "yes" else "Нет"
    return value


@router.message(GuestFlow.AWAITING_FEEDBACK, F.text)
async def guest_feedback_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Похоже, сообщение пустое — попробуйте ещё раз.")
        return
    await _process_feedback(message, state, raw_text=text, source="text")


@router.message(GuestFlow.AWAITING_FEEDBACK, F.voice)
async def guest_feedback_voice(message: Message, state: FSMContext) -> None:
    voice = message.voice
    bot = message.bot
    if voice is None or bot is None:
        return
    async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
        path = await download_voice_to_tmp(voice.file_id, bot)
        try:
            text = await transcribe_voice(path)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    if not text.strip():
        await message.answer("Не удалось разобрать голос. Можете отправить текстом?")
        return
    await _process_feedback(message, state, raw_text=text, source="voice")


@router.message(GuestFlow.IN_INTERVIEW, Command("skip"))
async def guest_skip_command(message: Message, state: FSMContext) -> None:
    """/skip: advance index without writing to session_answers."""
    data = await state.get_data()
    idx = data["question_index"]
    qids = data["question_ids"]
    if idx >= len(qids):
        return
    await state.update_data(question_index=idx + 1)
    await _ask_next_question(message, state)


@router.message(GuestFlow.IN_INTERVIEW, F.text)
async def guest_answer(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or message.bot is None:
        return
    data = await state.get_data()
    sid = data["session_id"]
    idx = data["question_index"]
    qids = data["question_ids"]
    q = data["questions_map"][qids[idx]]

    # Non-text questions: гость прислал свободный текст вместо клика.
    # `enum` с пустым enum_values рендерится как text-вопрос (fallback в keyboards.py),
    # потому считаем его text-вопросом и здесь — обрабатываем как свободный ввод.
    expected_type = q.get("expected_type")
    is_text_like = expected_type == "text" or (expected_type == "enum" and not q.get("enum_values"))
    if not is_text_like:
        await message.answer("Пожалуйста, используйте кнопки выше или /skip.")
        return

    async with ChatActionSender.typing(chat_id=message.chat.id, bot=message.bot):
        await append_session_message(sid, "user", text)
        marked = await extract_metric_from_answer(question=q, answer_text=text)
        await save_answer_with_metric(
            session_id=sid,
            question_id=q["id"],
            answer_text=text,
            marked_value=marked,
        )

    answers = list(data["answers"])
    answers.append(
        {
            "question_text": q["text"],
            "metric_key": q["metric_key"],
            "answer_text": text,
            "marked_value": marked,
        }
    )
    await state.update_data(answers=answers, question_index=idx + 1)
    await _ask_next_question(message, state)


@router.callback_query(GuestFlow.IN_INTERVIEW, F.data.startswith("ans:"))
async def guest_answer_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle inline-button answer for typed questions (boolean/number/enum) or skip."""
    if callback.data is None or callback.message is None:
        return
    payload = callback.data.removeprefix("ans:")

    data = await state.get_data()
    idx = data["question_index"]
    qids = data["question_ids"]

    # Race: гость кликает по старой клавиатуре, индекс уже продвинут.
    if idx >= len(qids):
        await callback.answer("Этот вопрос уже завершён.", show_alert=False)
        return

    q = data["questions_map"][qids[idx]]
    expected_type = q.get("expected_type")

    # Снимаем клавиатуру у уже-отвеченного сообщения, чтобы не было повторных кликов.
    try:
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
    except Exception:
        # Если Telegram отказал (старое сообщение / уже без клавиатуры) — игнор.
        pass

    if payload == "skip":
        await callback.answer("Пропущено.")
        await state.update_data(question_index=idx + 1)
        await _ask_next_question_from_callback(callback, state)
        return

    # Защита от click по callback на text-вопрос (теоретически не должно случиться,
    # т.к. для text не рендерим клавиатуру) — fail closed.
    if expected_type not in ("boolean", "number", "enum"):
        await callback.answer("Ответьте текстом, пожалуйста.", show_alert=True)
        return

    try:
        marked = _marked_value_from_callback(payload, expected_type)
    except ValueError:
        await callback.answer("Не понял ответ, попробуйте ещё раз.", show_alert=True)
        return

    sid = data["session_id"]
    answer_text = _answer_text_from_callback(payload, expected_type)

    await append_session_message(sid, "user", answer_text)
    await save_answer_with_metric(
        session_id=sid,
        question_id=q["id"],
        answer_text=answer_text,
        marked_value=marked,
    )

    answers = list(data["answers"])
    answers.append(
        {
            "question_text": q["text"],
            "metric_key": q["metric_key"],
            "answer_text": answer_text,
            "marked_value": marked,
        }
    )
    await state.update_data(answers=answers, question_index=idx + 1)
    await callback.answer()
    await _ask_next_question_from_callback(callback, state)


async def _ask_next_question_from_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Bridge: _ask_next_question expects a Message; CallbackQuery carries one."""
    msg = callback.message
    if msg is None:
        return
    await _ask_next_question(msg, state)  # type: ignore[arg-type]


async def _finalize_with_state(message: Message, state: FSMContext) -> None:
    from agent.nodes.analyze import FeedbackSummary

    data = await state.get_data()
    summary = FeedbackSummary.model_validate(data["summary"])
    answers = data.get("answers", [])
    await _finalize_session(message, state, summary=summary, answers=answers)


async def _finalize_session(
    message: Message,
    state: FSMContext,
    *,
    summary,
    answers: list[dict],
) -> None:
    data = await state.get_data()
    session_id = data["session_id"]
    client_id = data["client_id"]
    bot = message.bot

    await state.set_state(GuestFlow.FINALIZING)

    # Build card + embed + Pinecone upsert — ещё один долгий блок.
    if bot is not None:
        async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
            card = await build_client_card(feedback_summary=summary, answers=answers)
            vector = await embed_text(card.summary_text)
            vector_id = await upsert_client_card_vector(
                session_id=session_id,
                client_id=client_id,
                vector=vector,
                sentiment=card.sentiment,
                topics=card.topics,
            )
            await save_client_card(
                client_id=client_id,
                session_id=session_id,
                summary_text=card.summary_text,
                pinecone_vector_id=vector_id,
            )
            await end_session(session_id)
    else:
        card = await build_client_card(feedback_summary=summary, answers=answers)
        vector = await embed_text(card.summary_text)
        vector_id = await upsert_client_card_vector(
            session_id=session_id,
            client_id=client_id,
            vector=vector,
            sentiment=card.sentiment,
            topics=card.topics,
        )
        await save_client_card(
            client_id=client_id,
            session_id=session_id,
            summary_text=card.summary_text,
            pinecone_vector_id=vector_id,
        )
        await end_session(session_id)

    await state.clear()
    # Если ранее уже отправили finalize-сообщение (empty-pool case) — не дублируем.
    if not data.get("finalize_message_sent"):
        await message.answer("Спасибо за отзыв! Хорошего дня.")


@router.message(Command("cancel"))
async def guest_cancel(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    sid = data.get("session_id")
    if sid:
        try:
            await end_session(sid)
        except LookupError:
            pass
    await state.clear()
    await message.answer("Хорошо, сворачиваюсь. Если захотите вернуться — нажмите /start.")
