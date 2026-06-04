from pydantic import BaseModel

from core.agent.nodes.analyze import FeedbackSummary, _lc_to_chat_dicts
from core.agent.prompts import build_card_prompt
from core.integrations.openai_chat import chat_completion


class ClientCard(BaseModel):
    summary_text: str
    sentiment: str = ""
    topics: list[str] = []


async def build_client_card(
    *,
    feedback_summary: FeedbackSummary,
    answers: list[dict],
) -> ClientCard:
    dialog = (
        "\n".join(
            f"- [{a.get('metric_key', '?')}] {a.get('question_text', '?')} → "
            f"{a.get('answer_text', '')!r} (marked={a.get('marked_value')})"
            for a in answers
        )
        or "(нет ответов на вопросы)"
    )
    prompt = build_card_prompt()
    lc_messages = prompt.format_messages(
        feedback_summary=feedback_summary.model_dump_json(),
        dialog=dialog,
    )
    messages = _lc_to_chat_dicts(lc_messages)
    result = await chat_completion(messages, response_model=ClientCard)
    assert isinstance(result, ClientCard)

    if len(result.summary_text.strip()) < 20:
        raise ValueError("client card summary_text too short")

    if not result.sentiment:
        result.sentiment = feedback_summary.sentiment
    if not result.topics:
        result.topics = list(feedback_summary.topics)
    return result
