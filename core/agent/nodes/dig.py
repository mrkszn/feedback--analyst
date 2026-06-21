"""LLM dig node — surface 2–3 "what likely went wrong" guesses for a weak beat.

The guest webapp's UX intervenes only on low-scored beats. Instead of opening a
free-form chat box, we offer the guest a small set of structured guess cards
they can tap ("yes, this" / "not quite" / "I'll tell you"). This node generates
those cards from the beat label, current score, optional chip tags the guest
already picked, and the restaurant context.

The cards are surfaced bilingually (uk + en) so the frontend can render in the
guest's chosen UI language without a roundtrip translation. The guess `id`s are
stable short strings (`g1`, `g2`, `g3`) assigned here, not by the LLM — used by
the dig/answer endpoint to record which one the guest picked.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.integrations.openai_chat import chat_completion

DIG_SYSTEM = (
    "Ты — тёплый, наблюдательный собеседник от лица сервиса доставки еды или "
    "ресторана. Гость только что прошёл короткую визуальную ленту впечатлений "
    "о вечере и поставил низкую оценку одному из этапов. Твоя задача — "
    "предложить 2–3 коротких варианта-гипотезы, что именно могло пойти не так, "
    "чтобы гость мог тапнуть один и не печатать.\n\n"
    "Каждая гипотеза — это карточка с эмодзи и короткой подписью (≤ 50 знаков). "
    "Подписи дай сразу на украинском (`text_uk`) и английском (`text_en`).\n\n"
    "Правила:\n"
    "1. От 2 до 3 гипотез. Никогда 0 и никогда 4+.\n"
    "2. Гипотезы должны быть РАЗНЫЕ — не вариации одной (плохо: «холодно» и "
    "«не горячее»; хорошо: «холодно», «маленькая порция», «не как ожидал»).\n"
    "3. Учитывай теги, которые гость уже выбрал — расширяй их, не дублируй.\n"
    "4. Тон — не обвиняй персонал, не оправдывай сервис. Простая констатация: "
    "«долго ждали», «порция мала», «не объяснили меню».\n"
    "5. Эмодзи — один на гипотезу, уместный (🕒 для долгого ожидания, 🥶 для "
    "холода, 🍽️ для размера порции, 🤷 для непонимания и т.п.). Без 🎉, 🥰, 😢.\n"
    "6. Никаких вопросительных формулировок («может, было…?») — только утверждения.\n\n"
    "Верни строго JSON по схеме GuessSet."
)


class Guess(BaseModel):
    text_uk: str = Field(description="Коротка підпись (≤ 50 символів), українською.")
    text_en: str = Field(description="Short caption (≤ 50 chars), English.")
    emoji: str = Field(description="Один уместный эмодзи.")


class GuessSet(BaseModel):
    guesses: list[Guess] = Field(min_length=2, max_length=3)


def _format_tags(tags: list[str]) -> str:
    if not tags:
        return "(тегов нет)"
    return ", ".join(tags)


async def dig_guesses_for_beat(
    *,
    beat_label: str,
    score: int,
    tags: list[str],
    restaurant_context: str = "",
) -> list[dict[str, str]]:
    """Generate 2–3 structured "guess" cards for a weak beat.

    Returns a list of dicts ready for storage: `[{id, text_uk, text_en, emoji}]`.
    The `id` is a stable short string (`g1`, `g2`, `g3`).
    """
    user_prompt = (
        f"Контекст сервиса: {restaurant_context or '(не задан)'}\n"
        f"Этап вечера: {beat_label}\n"
        f"Оценка гостя: {score}/5\n"
        f"Уже выбранные теги: {_format_tags(tags)}\n\n"
        "Сгенерируй 2–3 гипотезы карточек, как договорились."
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": DIG_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    result = await chat_completion(messages, response_model=GuessSet)
    assert isinstance(result, GuessSet)
    return [
        {
            "id": f"g{idx + 1}",
            "text_uk": g.text_uk,
            "text_en": g.text_en,
            "emoji": g.emoji,
        }
        for idx, g in enumerate(result.guesses)
    ]
