"""Single-question LLM helper for the admin /add_question dialog mode.

Takes a natural-language description from the admin ("задавай гостям вопрос,
понравилось ли им как готовят") and turns it into a single structured
`QuestionDraft` ready for `create_question`. Distinct from
`synthesize_questions` which produces a list from a voice transcript — here
the admin describes ONE question at a time in a chat.
"""

from langchain_core.prompts import ChatPromptTemplate

from core.agent.nodes.analyze import _lc_to_chat_dicts
from core.agent.nodes.synthesize_questions import QuestionDraft, _normalize_draft
from core.integrations.openai_chat import chat_completion

ADMIN_ASSISTANT_SYSTEM = (
    "Ты — помощник владельца ресторана. Админ описал в свободной форме ОДИН вопрос, "
    "который хочет задавать гостям. Преобразуй описание в один структурированный "
    "QuestionDraft.\n\n"
    "Контекст ресторана:\n{restaurant_context}\n\n"
    "Выбери expected_type по эвристике:\n"
    "- number — оценка 1..5 («оцените», «насколько», «по шкале»);\n"
    "- boolean — да/нет («понравилось ли», «хватило ли», «было ли»);\n"
    "- enum — закрытый выбор 2..5 вариантов (укажи enum_values);\n"
    "- text — открытый свободный ответ.\n\n"
    "metric_key — короткий snake_case-идентификатор (latin), отражающий суть.\n"
    "Если описание двусмысленное — выбери наиболее естественное прочтение."
)


def _build_admin_assistant_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", ADMIN_ASSISTANT_SYSTEM),
            ("user", "Описание от админа:\n{description}"),
        ]
    )


async def draft_question_from_nl(
    description: str,
    *,
    restaurant_context: str = "",
) -> QuestionDraft:
    if not description.strip():
        raise ValueError("description must not be empty")

    prompt = _build_admin_assistant_prompt()
    lc_messages = prompt.format_messages(
        description=description.strip(),
        restaurant_context=restaurant_context or "(не задан)",
    )
    messages = _lc_to_chat_dicts(lc_messages)
    result = await chat_completion(messages, response_model=QuestionDraft)
    assert isinstance(result, QuestionDraft)

    normalized = _normalize_draft(result)
    if normalized is None:
        raise ValueError("LLM returned invalid draft")
    return normalized
