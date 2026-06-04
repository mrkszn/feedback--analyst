"""Entry point — chain the three phases: interpret → execute → synthesize."""

from __future__ import annotations

from core.agent.analytics_agent.execute import execute_plan
from core.agent.analytics_agent.interpret import interpret
from core.agent.analytics_agent.synthesize import synthesize
from core.agent.analytics_agent.types import AnalyticsAnswer


async def answer_v2(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> AnalyticsAnswer:
    plan = await interpret(question, history)
    execution = await execute_plan(plan)
    answer = await synthesize(question, execution)
    return answer
