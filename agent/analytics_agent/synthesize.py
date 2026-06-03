"""Phase 3 — synthesize execute results into a human `AnalyticsAnswer`.

One LLM call: original question + interpretation + collected data blocks →
final answer. When the plan asked for clarification, no LLM call is made.
"""

from __future__ import annotations

import json
from typing import Any

from agent.analytics_agent.prompts import SYNTHESIZE_SYSTEM
from agent.analytics_agent.types import AnalyticsAnswer
from integrations.openai_chat import chat_completion


def _block_to_dict(block: Any) -> Any:
    dump = getattr(block, "model_dump", None)
    if callable(dump):
        return dump()
    return block


async def synthesize(
    question: str,
    execution: dict[str, Any],
) -> AnalyticsAnswer:
    interpretation = execution.get("interpretation", "")
    if execution.get("clarification_needed"):
        return AnalyticsAnswer(
            answer_text=execution.get("clarification_question")
            or "Уточните, пожалуйста, что показать.",
            interpretation=interpretation,
            clarification_needed=True,
            tools_used=[],
        )

    blocks = [_block_to_dict(b) for b in execution.get("blocks", [])]
    blocks_json = json.dumps(blocks, ensure_ascii=False, default=str)

    user = (
        f"Вопрос владельца: {question}\n"
        f"Как поняли вопрос: {interpretation}\n"
        f"Собранные данные (JSON-блоки результатов инструментов):\n{blocks_json}\n"
        "Сформулируй ответ строго по схеме AnalyticsAnswer."
    )
    messages = [
        {"role": "system", "content": SYNTHESIZE_SYSTEM},
        {"role": "user", "content": user},
    ]

    result = await chat_completion(messages, response_model=AnalyticsAnswer, temperature=0.3)
    assert isinstance(result, AnalyticsAnswer)

    tools_used = execution.get("tools_used", [])
    if not result.tools_used and tools_used:
        result.tools_used = list(tools_used)
    if not result.interpretation:
        result.interpretation = interpretation
    result.clarification_needed = False
    return result
