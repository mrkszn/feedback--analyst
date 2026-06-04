"""Phase 1 — interpret an owner's question into a structured `AnalysisPlan`.

Thin: assemble messages (system + history + question), one LLM call with
`response_model=AnalysisPlan`, return the model. Tool/arg validation belongs to
`execute`, not here.
"""

from __future__ import annotations

from core.agent.analytics_agent.prompts import INTERPRET_SYSTEM
from core.agent.analytics_agent.types import AnalysisPlan
from core.integrations.openai_chat import chat_completion


async def interpret(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> AnalysisPlan:
    if not question.strip():
        return AnalysisPlan(
            interpretation="Пустой вопрос.",
            clarification_needed=True,
            clarification_question="Задайте вопрос — что показать по фидбэку?",
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": INTERPRET_SYSTEM}]
    for h in history or []:
        role = h.get("role")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": h.get("content") or ""})
    messages.append({"role": "user", "content": question.strip()})

    result = await chat_completion(messages, response_model=AnalysisPlan, temperature=0.1)
    assert isinstance(result, AnalysisPlan)
    return result
