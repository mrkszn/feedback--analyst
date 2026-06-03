"""Seed dev DB with ~50 simulated clients to test analytics end-to-end.

Заполняет Supabase + Pinecone правдоподобными данными (75 сессий
от 50 клиентов, разные настроения, темы, типы ответов на активные
вопросы). LLM-узлы НЕ вызываются — feedback_summary и client_card.summary
запекаются прямо в коде. Embeddings — настоящие (OpenAI text-embedding-
3-small, копейки на 75 текстов ~300 токенов).

Идемпотентность: telegram_id 9_000_001..9_000_050. Скрипт сначала
проверяет, есть ли у клиента сессии — если есть, пропускает (re-run safe).
Чтобы перезалить с нуля — `--reset` (удалит сессии + карточки +
векторы Pinecone для этого диапазона).

Использование:
    uv run python -m scripts.seed_demo_data
    uv run python -m scripts.seed_demo_data --reset
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from db.client import get_supabase
from integrations.openai_embed import embed_text
from integrations.pinecone import VECTOR_DIM, upsert_client_card_vector
from services.clients import create_or_get_client
from services.questions import list_questions
from services.sessions import (
    append_session_message,
    end_session,
    save_feedback_summary,
    start_session,
)
from tools.answers import save_answer_with_metric
from tools.client_cards import save_client_card

logger = logging.getLogger(__name__)

SEED_RANGE = range(9_000_001, 9_000_051)  # 50 inclusive

NAMES = [
    "Анна Петрова",
    "Иван Сидоров",
    "Мария Иванова",
    "Сергей Кузнецов",
    "Елена Смирнова",
    "Дмитрий Попов",
    "Ольга Васильева",
    "Алексей Соколов",
    "Наталья Лебедева",
    "Андрей Новиков",
    "Татьяна Морозова",
    "Михаил Волков",
    "Юлия Алексеева",
    "Артём Лазарев",
    "Светлана Орлова",
    "Денис Фёдоров",
    "Ирина Михайлова",
    "Павел Захаров",
    "Дарья Егорова",
    "Николай Беляев",
    "Анастасия Соловьёва",
    "Виталий Гусев",
    "Ксения Романова",
    "Роман Степанов",
    "Полина Карпова",
]

# --------------------------------------------------------------------------- #
# Feedback templates
# Каждый шаблон: raw — что сказал гость, summary — что бы извлёк LLM,
# topics — темы для агрегации, emotion — эмоция, followup — реплика гостя на
# первый bot-турн.

POSITIVE_TEMPLATES: list[dict[str, Any]] = [
    {
        "raw": "Очень понравилось! Подача на высоте, официанты внимательные, "
        "повара явно знают своё дело. Вернёмся обязательно!",
        "summary": "Гость в восторге от подачи и сервиса; явно вернётся.",
        "topics": ["еда", "сервис", "подача"],
        "emotion": "восторг",
        "followup": "Особенно тартар — пять звёзд.",
    },
    {
        "raw": "Прекрасный вечер. Атмосфера уютная, музыка не громкая, еда вкусная.",
        "summary": "Понравилась атмосфера и звук, еда хорошая.",
        "topics": ["атмосфера", "музыка", "еда"],
        "emotion": "удовлетворение",
        "followup": "Жаль, что не было свободных мест у окна.",
    },
    {
        "raw": "Кофе — лучший в городе. Десерт тоже не подвёл.",
        "summary": "Гость хвалит кофе и десерт.",
        "topics": ["кофе", "десерт"],
        "emotion": "удовольствие",
        "followup": "Капучино на овсяном — отдельная любовь.",
    },
    {
        "raw": "Принесли быстро, всё горячее, всё свежее. Хороший сервис.",
        "summary": "Скорость подачи и качество — на уровне.",
        "topics": ["сервис", "скорость", "еда"],
        "emotion": "довольство",
        "followup": "Так держать!",
    },
    {
        "raw": "Интерьер шикарный, как в Питере. И вино отличное по совету сомелье.",
        "summary": "Восхищён интерьером, вино подобрали удачно.",
        "topics": ["интерьер", "вино", "сервис"],
        "emotion": "восторг",
        "followup": "Спасибо сомелье за пино нуар.",
    },
]

NEUTRAL_TEMPLATES: list[dict[str, Any]] = [
    {
        "raw": "В целом норм. Еда обычная, сервис обычный, ничего особенного не запомнилось.",
        "summary": "Гость без особых эмоций — всё среднее.",
        "topics": ["еда", "сервис"],
        "emotion": "равнодушие",
        "followup": "Просто пообедал.",
    },
    {
        "raw": "Понравилось, но цена кусается за такие порции.",
        "summary": "Качество хорошее, но порции мелковаты для цены.",
        "topics": ["цена", "порции"],
        "emotion": "сомнение",
        "followup": "Возможно вернусь по акции.",
    },
    {
        "raw": "Атмосфера ок, но шумно было — соседний стол громко обсуждал работу.",
        "summary": "Уютно, но мешал шум от соседей.",
        "topics": ["атмосфера", "шум"],
        "emotion": "досада",
        "followup": "Сами повара тут ни при чём.",
    },
    {
        "raw": "Еда хорошая, обслуживание норм, но парковки нет вообще.",
        "summary": "Хвалит кухню, парковка — проблема.",
        "topics": ["еда", "парковка"],
        "emotion": "нейтрально",
        "followup": "Приходится оставлять во дворах.",
    },
]

NEGATIVE_TEMPLATES: list[dict[str, Any]] = [
    {
        "raw": "Ждали заказ 45 минут, в зале при этом было полупусто. Никто "
        "не извинился. Больше не приду.",
        "summary": "Долгое ожидание заказа, нет реакции от персонала.",
        "topics": ["ожидание", "сервис"],
        "emotion": "раздражение",
        "followup": "Не понимаю что у вас происходит на кухне.",
    },
    {
        "raw": "Холодная паста, пересоленный суп. Деньги выкинул на ветер.",
        "summary": "Еда холодная и пересоленная, гость в негодовании.",
        "topics": ["еда", "качество"],
        "emotion": "негодование",
        "followup": "Жаловался официанту — пожали плечами.",
    },
    {
        "raw": "Туалет в ужасном состоянии. Это первое впечатление от заведения.",
        "summary": "Жалоба на состояние туалета.",
        "topics": ["туалет", "чистота"],
        "emotion": "отвращение",
        "followup": "Хотя сама еда была неплохая.",
    },
    {
        "raw": "Цены конские, а порции игрушечные. Не стоит того.",
        "summary": "Соотношение цена/порция не устроило.",
        "topics": ["цена", "порции"],
        "emotion": "разочарование",
        "followup": "За эти деньги в соседнем месте кормят втрое больше.",
    },
]


# --------------------------------------------------------------------------- #
# Random data helpers


def _pick_template(rng: random.Random) -> tuple[str, dict[str, Any]]:
    bucket = rng.random()
    if bucket < 0.50:
        return "positive", rng.choice(POSITIVE_TEMPLATES)
    if bucket < 0.80:
        return "neutral", rng.choice(NEUTRAL_TEMPLATES)
    return "negative", rng.choice(NEGATIVE_TEMPLATES)


def _random_marked_value(
    question: dict[str, Any],
    rng: random.Random,
    sentiment: str,
) -> tuple[str, Any]:
    """Возвращает (answer_text, marked_value) — marked_value в виде
    {"value": ...} как у extract_metric_from_answer.
    """
    expected_type = question.get("expected_type")
    enum_values = question.get("enum_values") or []

    if expected_type == "number":
        # Скос по настроению: positive → 4-5, negative → 1-2, neutral → 3
        if sentiment == "positive":
            v = rng.randint(4, 5)
        elif sentiment == "negative":
            v = rng.randint(1, 2)
        else:
            v = rng.choice([2, 3, 3, 4])
        return str(v), {"value": v}

    if expected_type == "boolean":
        v = sentiment != "negative"
        return ("Да" if v else "Нет"), {"value": v}

    if expected_type == "enum":
        if not enum_values:
            return "—", None
        # Не равномерный выбор: даём вес первому значению чаще
        weights = [3] + [1] * (len(enum_values) - 1)
        v = rng.choices(enum_values, weights=weights, k=1)[0]
        return str(v), {"value": v}

    # text question — короткий ответ из заготовок
    text_pool = [
        "паста",
        "стейк",
        "ризотто",
        "тирамису",
        "капучино",
        "сёмга",
        "брускетта",
    ]
    answer = rng.choice(text_pool)
    return answer, {"value": answer}


# --------------------------------------------------------------------------- #
# DB ops


async def _has_existing_session(telegram_id: int) -> bool:
    db = get_supabase()

    def _q() -> Any:
        return db.table("sessions").select("id").eq("client_id", telegram_id).limit(1).execute()

    resp = await asyncio.to_thread(_q)
    return bool(resp.data)


async def _set_session_timestamps(
    session_id: UUID,
    started_at: datetime,
    ended_at: datetime,
) -> None:
    db = get_supabase()

    def _q() -> Any:
        return (
            db.table("sessions")
            .update(
                {
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                }
            )
            .eq("id", str(session_id))
            .execute()
        )

    await asyncio.to_thread(_q)


async def _backdate_card(session_id: UUID, started_at: datetime) -> None:
    """Подгоняем client_cards.created_at под started_at сессии,
    чтобы recent_cards выглядели реалистично.
    """
    db = get_supabase()

    def _q() -> Any:
        return (
            db.table("client_cards")
            .update({"created_at": started_at.isoformat()})
            .eq("session_id", str(session_id))
            .execute()
        )

    await asyncio.to_thread(_q)


async def reset_seed_data() -> None:
    """Удаляет всё, что относится к seed-диапазону (50 клиентов)."""
    db = get_supabase()
    ids = list(SEED_RANGE)

    def _q_sessions() -> Any:
        return db.table("sessions").select("id").in_("client_id", ids).execute()

    sessions_resp = await asyncio.to_thread(_q_sessions)
    session_ids = [str(r["id"]) for r in sessions_resp.data or []]
    logger.info("reset: %d sessions to delete", len(session_ids))

    # cascading deletes: session_answers / session_messages / client_cards
    # отлетают FK on delete cascade в schema 0001_init.sql.
    if session_ids:

        def _del_sessions() -> Any:
            return db.table("sessions").delete().in_("id", session_ids).execute()

        await asyncio.to_thread(_del_sessions)

    def _del_clients() -> Any:
        return db.table("clients").delete().in_("telegram_id", ids).execute()

    await asyncio.to_thread(_del_clients)
    logger.info("reset: %d clients deleted", len(ids))


# --------------------------------------------------------------------------- #
# Per-session seeding


async def seed_session(
    telegram_id: int,
    rng: random.Random,
    questions: list[dict[str, Any]],
) -> None:
    sentiment, tpl = _pick_template(rng)
    raw_text = str(tpl["raw"])
    topics = list(tpl["topics"])
    emotion = str(tpl["emotion"])
    summary_text = str(tpl["summary"])
    followup = str(tpl.get("followup") or "Спасибо, что спросили.")

    # Распределяем сессии за последние 60 дней
    days_ago = rng.randint(0, 60)
    started_at = datetime.now(UTC) - timedelta(days=days_ago, hours=rng.randint(0, 23))
    # Сессия длилась 1-3 минуты в условном диалоге
    ended_at = started_at + timedelta(minutes=rng.randint(1, 4))

    session_id = await start_session(client_id=telegram_id)

    # Транскрипт: user (raw) → bot (empathy) → user (followup) → bot (survey)
    await append_session_message(session_id, "user", raw_text)
    await append_session_message(
        session_id,
        "bot",
        "Спасибо, что поделились. Расскажите ещё немного — что именно понравилось/не понравилось?",
    )
    await append_session_message(session_id, "user", followup)
    await append_session_message(
        session_id,
        "bot",
        "Хочу задать пару вопросов от ресторана — это поможет улучшить сервис. Окей?",
    )

    summary_payload = {
        "summary": summary_text,
        "sentiment": sentiment,
        "topics": topics,
        "emotion": emotion,
    }
    await save_feedback_summary(
        session_id,
        raw_text=raw_text,
        source="text",
        summary=summary_payload,  # type: ignore[arg-type]
    )

    # Ответы на 2-4 случайные вопросы (если в пуле есть)
    if questions:
        n_answers = min(rng.randint(2, 4), len(questions))
        chosen = rng.sample(questions, n_answers)
        for q in chosen:
            answer_text, marked_value = _random_marked_value(q, rng, sentiment)
            await append_session_message(session_id, "bot", str(q["text"]))
            await append_session_message(session_id, "user", answer_text)
            try:
                await save_answer_with_metric(
                    session_id=session_id,
                    question_id=q["id"],
                    answer_text=answer_text,
                    marked_value=marked_value,
                )
            except ValueError as exc:
                logger.warning("skip answer for q=%s: %s", q["id"], exc)

    # Карточка + Pinecone
    card_text = f"{summary_text} Контекст: {followup}".strip()
    try:
        vector = await embed_text(card_text)
    except Exception as exc:
        logger.warning("embed failed (using zero vector): %s", exc)
        vector = [0.0] * VECTOR_DIM
    vector_id = await upsert_client_card_vector(
        session_id=str(session_id),
        client_id=telegram_id,
        vector=vector,
        sentiment=sentiment,
        topics=topics,
        date=started_at,
    )
    await save_client_card(
        client_id=telegram_id,
        session_id=session_id,
        summary_text=card_text,
        pinecone_vector_id=vector_id,
    )

    await end_session(session_id)
    await _set_session_timestamps(session_id, started_at, ended_at)
    await _backdate_card(session_id, started_at)


async def seed_client(
    index: int,
    telegram_id: int,
    rng: random.Random,
    questions: list[dict[str, Any]],
) -> int:
    name = NAMES[index % len(NAMES)]
    await create_or_get_client(telegram_id=telegram_id, name=name)
    # Распределение числа сессий: 60% — 1, 30% — 2, 10% — 3
    n_sessions = rng.choices([1, 2, 3], weights=[60, 30, 10], k=1)[0]
    for _ in range(n_sessions):
        await seed_session(telegram_id, rng, questions)
    return n_sessions


# --------------------------------------------------------------------------- #
# Main


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed dev DB with ~50 fake clients")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Удалить все seed-данные перед заливкой",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed для воспроизводимости (default 42)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    rng = random.Random(args.seed)

    if args.reset:
        logger.info("--reset → удаляю seed-диапазон…")
        await reset_seed_data()

    questions_raw = await list_questions(active_only=True)
    questions: list[dict[str, Any]] = [dict(q) for q in questions_raw]
    if not questions:
        logger.warning(
            "В пуле нет активных вопросов — ответы (session_answers) "
            "не будут созданы. Метрики в /statistics будут пустыми."
        )
    else:
        logger.info("Активных вопросов в пуле: %d", len(questions))

    total_sessions = 0
    for i, telegram_id in enumerate(SEED_RANGE):
        if not args.reset and await _has_existing_session(telegram_id):
            logger.info("[%d/50] %d: уже есть сессии — пропуск", i + 1, telegram_id)
            continue
        n = await seed_client(i, telegram_id, rng, questions)
        total_sessions += n
        logger.info("[%d/50] %d → %d сессий", i + 1, telegram_id, n)

    logger.info("DONE. Всего сессий создано: %d", total_sessions)


if __name__ == "__main__":
    asyncio.run(main())
