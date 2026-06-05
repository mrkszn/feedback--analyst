from typing import Literal

from pydantic import BaseModel, Field

from core.agent.nodes.analyze import _lc_to_chat_dicts
from core.agent.prompts import build_dialogue_prompt
from core.integrations.openai_chat import chat_completion


class DialogueTurn(BaseModel):
    bot_reply: str = Field(
        ...,
        description="Живой эмпатичный ответ клиенту, 1-3 предложения, эмодзи (не >2 на сообщение). Не вопросительная анкета.",
    )
    transition: Literal["continue", "offer_survey"]
    insights: dict[str, str] = Field(default_factory=dict)


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "(диалог только начинается)"
    lines: list[str] = []
    for msg in history:
        role = msg.get("role", "user")
        speaker = "Клиент" if role == "user" else "Бот"
        lines.append(f"{speaker}: {msg.get('content', '')}")
    return "\n".join(lines)


async def continue_dialogue(
    *,
    feedback_summary: str,
    history: list[dict[str, str]],
    restaurant_context: str,
    turn_count: int,
    max_turns: int = 5,
) -> DialogueTurn:
    prompt = build_dialogue_prompt()
    lc_messages = prompt.format_messages(
        restaurant_context=restaurant_context or "(контекст сервиса доставки не задан)",
        feedback_summary=feedback_summary,
        history=_format_history(history),
        turn_count=turn_count,
        max_turns=max_turns,
    )
    messages = _lc_to_chat_dicts(lc_messages)
    result = await chat_completion(messages, response_model=DialogueTurn)
    assert isinstance(result, DialogueTurn)

    # Hard cap: when we've already had max_turns exchanges, force a survey offer
    # even if the LLM still wants to keep talking. Prevents infinite chitchat.
    if turn_count >= max_turns:
        result.transition = "offer_survey"
    return result
