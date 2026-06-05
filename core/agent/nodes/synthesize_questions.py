"""LLM-генерация черновиков вопросов из голосовой расшифровки админа."""

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from core.agent.nodes.analyze import _lc_to_chat_dicts
from core.integrations.openai_chat import chat_completion

ExpectedType = Literal["text", "number", "enum", "boolean"]


class QuestionDraft(BaseModel):
    text: str
    metric_key: str
    expected_type: ExpectedType
    enum_values: list[str] | None = None


class _QuestionDraftList(BaseModel):
    """Container для structured output: LLM возвращает список черновиков."""

    drafts: list[QuestionDraft]


SYNTHESIZE_SYSTEM = (
    "Ты — помощник сервиса доставки еды. Админ надиктовал, какие вопросы хочет задавать "
    "клиентам после доставки. Преобразуй расшифровку в структурированные черновики "
    "вопросов.\n\n"
    "Контекст бизнеса:\n{restaurant_context}\n\n"
    "Помни: впечатление клиента складывается из двух частей — самой еды (вкус, "
    "температура, упаковка) и доставки (скорость курьера, аккуратность, вежливость). "
    "Если расшифровка явно про одну сторону — не выдумывай вопросы про другую.\n\n"
    "Для каждого черновика выбери expected_type по эвристике:\n"
    "- number — оценка по шкале 1..5 («оцените», «насколько», «по шкале»);\n"
    "- boolean — да/нет вопрос («понравилось ли», «хватило ли», «было ли»);\n"
    "- enum — закрытый выбор из 2..5 вариантов (укажи enum_values);\n"
    "- text — открытый свободный ответ.\n\n"
    "metric_key: короткий snake_case-идентификатор (latin), отражающий суть метрики.\n"
    "Не дублируй вопросы. Верни не более {count} черновиков в поле drafts."
)

REGENERATE_SYSTEM = (
    "Ты — помощник сервиса доставки еды. Админ хочет заменить один из черновиков на "
    "другой вопрос той же тематики, но отличающийся от уже существующих.\n\n"
    "Контекст бизнеса:\n{restaurant_context}\n\n"
    "Используй ту же эвристику типов:\n"
    "- number — оценка 1..5;\n"
    "- boolean — да/нет;\n"
    "- enum — закрытый список 2..5 значений (enum_values);\n"
    "- text — свободный ответ.\n\n"
    "Сгенерируй ровно один новый QuestionDraft. Он НЕ должен повторять ни один из "
    "уже существующих черновиков (ни по text, ни по metric_key)."
)


def _build_synthesize_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYNTHESIZE_SYSTEM),
            ("user", "Расшифровка:\n{transcript}\n\nНужно черновиков: {count}"),
        ]
    )


def _build_regenerate_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", REGENERATE_SYSTEM),
            (
                "user",
                "Расшифровка:\n{transcript}\n\n"
                "Заменяемый черновик (JSON):\n{current_draft}\n\n"
                "Все текущие черновики (JSON):\n{all_drafts}",
            ),
        ]
    )


def _normalize_draft(draft: QuestionDraft) -> QuestionDraft | None:
    """Валидация одного черновика. Возвращает None если он невалиден."""
    if not draft.text.strip() or not draft.metric_key.strip():
        return None
    if draft.expected_type == "enum":
        values = [v for v in (draft.enum_values or []) if v and v.strip()]
        if not (2 <= len(values) <= 5):
            return None
        return draft.model_copy(update={"enum_values": values})
    return draft.model_copy(update={"enum_values": None})


async def synthesize_questions(
    transcript: str,
    count: int,
    restaurant_context: str,
) -> list[QuestionDraft]:
    if not transcript.strip():
        raise ValueError("transcript must not be empty")
    if count <= 0:
        raise ValueError("count must be positive")

    prompt = _build_synthesize_prompt()
    lc_messages = prompt.format_messages(
        transcript=transcript,
        count=count,
        restaurant_context=restaurant_context or "(не задан)",
    )
    messages = _lc_to_chat_dicts(lc_messages)
    result = await chat_completion(messages, response_model=_QuestionDraftList)
    assert isinstance(result, _QuestionDraftList)

    drafts: list[QuestionDraft] = []
    for raw in result.drafts:
        normalized = _normalize_draft(raw)
        if normalized is not None:
            drafts.append(normalized)
    return drafts[:count]


async def regenerate_single_question(
    transcript: str,
    current_draft: QuestionDraft,
    all_drafts: list[QuestionDraft],
    restaurant_context: str,
) -> QuestionDraft:
    if not transcript.strip():
        raise ValueError("transcript must not be empty")

    all_drafts_json = "[" + ", ".join(d.model_dump_json() for d in all_drafts) + "]"
    prompt = _build_regenerate_prompt()
    lc_messages = prompt.format_messages(
        transcript=transcript,
        current_draft=current_draft.model_dump_json(),
        all_drafts=all_drafts_json,
        restaurant_context=restaurant_context or "(не задан)",
    )
    messages = _lc_to_chat_dicts(lc_messages)
    result = await chat_completion(messages, response_model=QuestionDraft)
    assert isinstance(result, QuestionDraft)

    normalized = _normalize_draft(result)
    if normalized is None:
        raise ValueError("regenerated draft is invalid")
    return normalized
