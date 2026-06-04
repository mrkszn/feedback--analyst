"""Conversational admin agent — replaces the rigid help-text fallback.

The agent is a thin loop around a chat LLM with four tools wrapping
question CRUD: list, search, create, delete. Tone is professional and
warm — like an assistant in a business, not a restaurant guest. Minimal
emoji.

When the LLM responds with `tool_calls`, we execute them, append the
tool results to the history, and ask the LLM again. Bounded to 4 turns
to avoid runaway loops. If the LLM returns plain content, that's the
final reply to the admin.
"""

from __future__ import annotations

from typing import Any

from aiogram.utils.chat_action import ChatActionSender
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from core.integrations.openai_chat import get_chat_model
from core.tools.admin_question_tools import ADMIN_TOOLS

ADMIN_AGENT_SYSTEM = (
    "Ты — ассистент владельца ресторана внутри Telegram-бота. Помогаешь админу "
    "управлять пулом вопросов, которые задают гостям при сборе отзывов.\n\n"
    "Тон: профессионально-тёплый, как ассистент в бизнесе. Без панибратства, "
    "без guest-style эмодзи. Один уместный эмодзи на сообщение допустим — "
    "не больше. Краткость лучше многословности.\n\n"
    "У тебя есть инструменты для работы с пулом вопросов:\n"
    "- list_active_questions_tool — показать активные вопросы;\n"
    "- find_question_tool(query) — найти вопрос по подстроке;\n"
    "- create_question_tool(text, metric_key, expected_type[, enum_values]) — создать;\n"
    "- delete_question_tool(question_id) — скрыть один вопрос по id.\n\n"
    "Правила:\n"
    "1. Прежде чем удалить — убедись, что речь идёт об одном конкретном "
    "вопросе. Если запрос неоднозначный («удали про еду»), сначала покажи "
    "найденные совпадения и переспроси.\n"
    "2. Если админ просит «удалить все» — НЕ вызывай delete_question_tool "
    "в цикле. Подскажи кнопку [🗑 Удалить все] под /questions.\n"
    "3. Если intent не понятен или это болтовня — отвечай по-человечески, "
    "коротко, без инструментов.\n"
    "4. Не выдумывай факты о ресторане сверх того, что вернули инструменты."
)


_MAX_TOOL_ROUNDS = 4


def _tools_by_name() -> dict[str, Any]:
    return {t.name: t for t in ADMIN_TOOLS}


async def run_admin_agent(user_text: str) -> str:
    """Run one turn of the admin agent over `user_text` and return its reply."""
    if not user_text.strip():
        return "Слушаю — задайте вопрос или опишите задачу."

    llm = get_chat_model(temperature=0.3).bind_tools(ADMIN_TOOLS)
    messages: list[BaseMessage] = [
        SystemMessage(content=ADMIN_AGENT_SYSTEM),
        HumanMessage(content=user_text.strip()),
    ]

    tools = _tools_by_name()
    for _ in range(_MAX_TOOL_ROUNDS):
        response = await llm.ainvoke(messages)
        if not isinstance(response, AIMessage):
            # Defensive: bind_tools should always return AIMessage; surface
            # the raw content if something exotic comes back.
            return str(getattr(response, "content", "")) or "Не удалось обработать запрос."

        messages.append(response)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return str(response.content or "").strip() or "Готов помочь дальше."

        for call in tool_calls:
            name = call.get("name", "")
            args = call.get("args", {}) or {}
            tool_id = call.get("id", "")
            t = tools.get(name)
            if t is None:
                messages.append(ToolMessage(content=f"Tool {name} not found", tool_call_id=tool_id))
                continue
            try:
                result = await t.ainvoke(args)
            except Exception as exc:  # surface to LLM, not the admin
                result = f"Tool {name} failed: {exc}"
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

    return "Не получилось завершить шаг за разумное число итераций — попробуйте переформулировать."


async def reply_via_agent(message: Any) -> None:
    """Send the agent's reply, with a typing indicator while the LLM thinks."""
    if not message.text:
        return
    bot = getattr(message, "bot", None)
    if bot is not None:
        async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
            reply = await run_admin_agent(message.text)
    else:
        reply = await run_admin_agent(message.text)
    await message.answer(reply)
