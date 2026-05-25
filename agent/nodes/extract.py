from typing import Any

from pydantic import BaseModel

from agent.nodes.analyze import _lc_to_chat_dicts
from agent.prompts import build_extract_prompt
from integrations.openai_chat import chat_completion


class _TextValue(BaseModel):
    value: str | None


class _NumberValue(BaseModel):
    value: float | None


class _EnumValue(BaseModel):
    value: str | None


class _BoolValue(BaseModel):
    value: bool | None


_MODEL_BY_TYPE: dict[str, type[BaseModel]] = {
    "text": _TextValue,
    "number": _NumberValue,
    "enum": _EnumValue,
    "boolean": _BoolValue,
}


async def extract_metric_from_answer(
    *,
    question: dict,
    answer_text: str,
) -> Any:
    if not answer_text.strip():
        raise ValueError("answer_text must not be empty")

    expected_type = question["expected_type"]
    if expected_type not in _MODEL_BY_TYPE:
        raise ValueError(f"unknown expected_type {expected_type!r}")

    enum_values = question.get("enum_values")
    if expected_type == "enum" and not enum_values:
        raise ValueError("enum question must have non-empty enum_values")

    response_model = _MODEL_BY_TYPE[expected_type]
    prompt = build_extract_prompt()
    lc_messages = prompt.format_messages(
        question_text=question["text"],
        expected_type=expected_type,
        enum_values=enum_values,
        answer_text=answer_text,
    )
    messages = _lc_to_chat_dicts(lc_messages)
    result = await chat_completion(messages, response_model=response_model)
    value = getattr(result, "value", None)

    if expected_type == "enum" and value is not None and value not in (enum_values or []):
        return None
    return value
