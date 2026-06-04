from pydantic import BaseModel

from core.agent.nodes.analyze import FeedbackSummary, _lc_to_chat_dicts
from core.agent.prompts import build_select_prompt
from core.integrations.openai_chat import chat_completion


class SelectedQuestions(BaseModel):
    question_ids: list[str]
    reasoning: str = ""


async def select_adaptive_questions(
    summary: FeedbackSummary,
    pool: list[dict],
    *,
    min_questions: int = 3,
    max_questions: int = 5,
) -> SelectedQuestions:
    if not pool:
        return SelectedQuestions(question_ids=[], reasoning="empty pool")

    pool_str = "\n".join(f"- {q['id']} [{q['metric_key']}]: {q['text']}" for q in pool)
    prompt = build_select_prompt()
    lc_messages = prompt.format_messages(
        feedback_summary=summary.model_dump_json(),
        pool=pool_str,
        min=min_questions,
        max=max_questions,
    )
    messages = _lc_to_chat_dicts(lc_messages)
    result = await chat_completion(messages, response_model=SelectedQuestions)
    assert isinstance(result, SelectedQuestions)

    pool_ids = {str(q["id"]) for q in pool}
    deduped: list[str] = []
    seen: set[str] = set()
    for qid in result.question_ids:
        if qid in pool_ids and qid not in seen:
            deduped.append(qid)
            seen.add(qid)
    deduped = deduped[:max_questions]
    if len(deduped) < min_questions:
        for q in pool:
            qid = str(q["id"])
            if qid not in seen:
                deduped.append(qid)
                seen.add(qid)
                if len(deduped) >= min_questions:
                    break
    return SelectedQuestions(question_ids=deduped, reasoning=result.reasoning)
