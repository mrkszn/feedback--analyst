from typing import Literal

from pydantic import BaseModel

from agent.prompts import build_analyze_prompt
from integrations.openai_chat import chat_completion

Sentiment = Literal["positive", "neutral", "negative"]


class FeedbackSummary(BaseModel):
    summary: str
    sentiment: Sentiment
    topics: list[str]
    emotion: str


def _lc_to_chat_dicts(lc_messages: list) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in lc_messages:
        role_map = {"system": "system", "human": "user", "ai": "assistant"}
        role = role_map.get(getattr(m, "type", "user"), "user")
        out.append({"role": role, "content": str(m.content)})
    return out


async def analyze_feedback(feedback_text: str) -> FeedbackSummary:
    if not feedback_text.strip():
        raise ValueError("feedback_text must not be empty")

    prompt = build_analyze_prompt()
    lc_messages = prompt.format_messages(feedback_text=feedback_text)
    messages = _lc_to_chat_dicts(lc_messages)
    result = await chat_completion(messages, response_model=FeedbackSummary)
    assert isinstance(result, FeedbackSummary)
    return result
