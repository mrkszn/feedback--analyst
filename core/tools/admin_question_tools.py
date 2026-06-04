"""LangChain tool wrappers around `services.questions` for the admin agent.

Each tool returns a short, LLM-friendly string (not a structured object) so
the agent can fold the result straight into its next reply. Errors are
caught and returned as text rather than raised — letting the LLM apologise
naturally instead of breaking the dialogue.
"""

from __future__ import annotations

from langchain_core.tools import tool

from core.services.questions import (
    create_question,
    delete_question,
    find_question_by_text,
    list_questions,
)


@tool
async def list_active_questions_tool() -> str:
    """Return the pool of active feedback questions as a numbered list.

    Use when the admin asks "what questions are active", "show the pool",
    "сколько у меня вопросов" and similar.
    """
    rows = await list_questions(active_only=True)
    if not rows:
        return "Активных вопросов нет."
    lines = [
        f"{i}. {r['text']} (type={r['expected_type']}, metric={r['metric_key']}, id={r['id']})"
        for i, r in enumerate(rows, 1)
    ]
    return "Активные вопросы:\n" + "\n".join(lines)


@tool
async def find_question_tool(query: str) -> str:
    """Search active questions by substring across text and metric_key.

    Use when the admin refers to a question by its content ("вопрос про
    еду", "тот, где про скорость") and you need its id before acting.
    """
    rows = await find_question_by_text(query)
    if not rows:
        return f"По запросу «{query}» ничего не найдено."
    lines = [
        f"{i}. {r['text']} (type={r['expected_type']}, id={r['id']})" for i, r in enumerate(rows, 1)
    ]
    return "Найдено:\n" + "\n".join(lines)


@tool
async def create_question_tool(
    text: str,
    metric_key: str,
    expected_type: str,
    enum_values: list[str] | None = None,
) -> str:
    """Create a new feedback question.

    `expected_type` must be one of text | number | enum | boolean.
    For `enum`, pass 2..5 string values in `enum_values`.
    """
    try:
        row = await create_question(
            text=text,
            metric_key=metric_key,
            expected_type=expected_type,  # type: ignore[arg-type]
            enum_values=enum_values,
        )
    except ValueError as exc:
        return f"Не удалось создать вопрос: {exc}"
    return f"Создан вопрос id={row['id']}: «{row['text']}» ({row['expected_type']})"


@tool
async def delete_question_tool(question_id: str) -> str:
    """Soft-delete (deactivate) one question by its UUID.

    Use only after you have the exact id — either from the recent listing
    or from `find_question_tool`.
    """
    try:
        await delete_question(question_id)
    except LookupError:
        return f"Вопрос с id={question_id} не найден."
    return f"Вопрос id={question_id} скрыт. История ответов сохранена."


ADMIN_TOOLS = [
    list_active_questions_tool,
    find_question_tool,
    create_question_tool,
    delete_question_tool,
]
