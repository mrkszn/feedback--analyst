"""Admin Q&A agent — natural-language вопросы по аналитике через tool-calling.

Это отдельный узел от `bot_admin/handlers/admin_agent.py` (тот управляет
вопросами CRUD). Здесь LLM получает analytics-tools и сам выбирает, какие
вызвать. Возвращает `AdminAnswer`: текст ответа + список использованных
инструментов + опциональный ASCII-блок (если LLM сам сгенерировал график).
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import BaseModel, Field

from integrations.openai_chat import get_chat_model
from tools.admin_analytics_tools import ADMIN_ANALYTICS_TOOLS

ADMIN_ASK_SYSTEM = (
    "Ты — analytics-ассистент владельца ресторана. Отвечаешь на вопросы об "
    "обратной связи гостей: метрики, топики, конкретные клиенты, поиск.\n\n"
    "Тон: профессионально-тёплый, как ассистент в бизнесе. Без guest-style "
    "эмодзи, без панибратства. Один уместный эмодзи на сообщение — максимум. "
    "Краткость лучше многословности; сразу к делу.\n\n"
    "У тебя есть analytics-инструменты:\n"
    "- summary_overview_tool(days) — дашборд за период;\n"
    "- aggregate_metric_tool(metric_key, days, group_by) — динамика метрики;\n"
    "- topic_histogram_tool(days, sentiment) — топ-топики, опц. с фильтром "
    "тональности;\n"
    "- semantic_search_tool(query, top_k) — найти похожие сессии по фразе;\n"
    "- client_profile_tool(telegram_id) — профиль конкретного клиента.\n\n"
    "Правила:\n"
    "1. Не выдумывай числа — если данных нет, скажи об этом честно.\n"
    "2. Для «жалоб» используй topic_histogram_tool с sentiment='negative'.\n"
    "3. Если уместен ASCII-график (тренд по дням 3-7 точек) — нарисуй его "
    "плоским текстом ниже основного ответа.\n"
    "4. Если запрос неоднозначный — кратко переспроси, не вызывай инструменты "
    "наугад."
)

_MAX_TOOL_ROUNDS = 5


class AdminAnswer(BaseModel):
    answer_text: str = Field(description="Готовый ответ админу")
    tools_used: list[str] = Field(default_factory=list, description="Имена вызванных tools")
    chart_text: str | None = Field(
        default=None, description="Опциональный ASCII-блок (тренд/распределение)"
    )


def _tools_by_name() -> dict[str, Any]:
    return {t.name: t for t in ADMIN_ANALYTICS_TOOLS}


def _split_chart(text: str) -> tuple[str, str | None]:
    """Если LLM включил ```...``` code-block — выделяем его как chart_text."""
    if "```" not in text:
        return text.strip(), None
    parts = text.split("```")
    if len(parts) < 3:
        return text.strip(), None
    pre = parts[0].strip()
    chart = parts[1]
    # strip optional language tag (e.g. ```text\n...)
    chart_lines = chart.splitlines()
    if chart_lines and not chart_lines[0].strip().startswith(" "):
        chart_body = "\n".join(chart_lines[1:]).strip()
    else:
        chart_body = chart.strip()
    post = "```".join(parts[2:]).strip()
    answer = (pre + ("\n" + post if post else "")).strip() or pre
    return answer, chart_body or None


async def answer_admin_question(
    question_text: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> AdminAnswer:
    """Один turn: задать вопрос, дать LLM проитерироваться с tools, вернуть
    структурированный AdminAnswer.
    """
    if not question_text.strip():
        return AdminAnswer(answer_text="Слушаю — задайте вопрос.")

    llm = get_chat_model(temperature=0.3).bind_tools(ADMIN_ANALYTICS_TOOLS)
    messages: list[BaseMessage] = [SystemMessage(content=ADMIN_ASK_SYSTEM)]
    for h in conversation_history or []:
        role = h.get("role")
        content = h.get("content") or ""
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=question_text.strip()))

    tools = _tools_by_name()
    used: list[str] = []

    for _ in range(_MAX_TOOL_ROUNDS):
        response = await llm.ainvoke(messages)
        if not isinstance(response, AIMessage):
            text = str(getattr(response, "content", "")) or "Не удалось обработать запрос."
            answer, chart = _split_chart(text)
            return AdminAnswer(answer_text=answer, tools_used=used, chart_text=chart)

        messages.append(response)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            text = str(response.content or "").strip() or "Готов помочь дальше."
            answer, chart = _split_chart(text)
            return AdminAnswer(answer_text=answer, tools_used=used, chart_text=chart)

        for call in tool_calls:
            name = call.get("name", "")
            args = call.get("args", {}) or {}
            tool_id = call.get("id", "")
            used.append(name)
            t = tools.get(name)
            if t is None:
                messages.append(ToolMessage(content=f"Tool {name} not found", tool_call_id=tool_id))
                continue
            try:
                result = await t.ainvoke(args)
            except Exception as exc:  # surface to LLM, not the admin
                result = f"Tool {name} failed: {exc}"
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

    return AdminAnswer(
        answer_text="Не получилось закончить за разумное число шагов — попробуйте сузить вопрос.",
        tools_used=used,
    )
