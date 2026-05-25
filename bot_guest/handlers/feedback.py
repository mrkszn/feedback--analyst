from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from agent.nodes.analyze import analyze_feedback
from agent.nodes.card import build_client_card
from agent.nodes.extract import extract_metric_from_answer
from agent.nodes.select import select_adaptive_questions
from bot_common.fsm.states import GuestFlow
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
from tools.questions import get_active_questions
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
    # (LLM analyze + DB writes + LLM select). Telegram продлевает «typing…»
    # каждые ~5 сек автоматически.
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

        pool = await get_active_questions()
        selected = await select_adaptive_questions(summary, pool)

    if not selected.question_ids:
        # Пул вопросов пуст ИЛИ селектор не выбрал ни одного.
        # Не молчим — даём пользователю явный сигнал и закрываем сессию
        # без интервью (но summary уже сохранён в Supabase).
        # TODO: в будущей итерации — синтезировать ad-hoc вопросы через LLM,
        # если pool пуст и admin ещё ничего не настроил.
        if not pool:
            await message.answer(
                "Спасибо за отзыв — я его сохранил и передам владельцу. "
                "Уточняющих вопросов пока нет: владелец их ещё не настроил "
                "через админ-бота. Хорошего дня!"
            )
        else:
            await message.answer(
                "Спасибо, отзыв сохранён. Уточняющих вопросов под этот "
                "контекст у меня нет. Хорошего дня!"
            )
        # Финалайз молча — прощание мы уже отправили выше.
        await state.update_data(finalize_message_sent=True)
        await _finalize_session(message, state, summary=summary, answers=[])
        return

    await state.update_data(
        question_ids=selected.question_ids,
        question_index=0,
        questions_map={str(q["id"]): q for q in pool},
        summary=summary.model_dump(),
        answers=[],
    )
    await state.set_state(GuestFlow.IN_INTERVIEW)
    await _ask_next_question(message, state)


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
    await message.answer(text)


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
