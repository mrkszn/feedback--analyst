from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APITimeoutError, RateLimitError
from pydantic import BaseModel, SecretStr
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings


def get_chat_model(
    *,
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = 30.0,
) -> BaseChatModel:
    return ChatOpenAI(
        model=model or settings.openai_chat_model,
        api_key=SecretStr(settings.openai_api_key) if settings.openai_api_key else None,
        temperature=temperature,
        timeout=timeout,
        default_headers={"X-Usage-Tag": settings.openai_usage_tag},
    )


def _to_lc_messages(
    messages: list[dict[str, str]],
) -> list[SystemMessage | HumanMessage | AIMessage]:
    out: list[SystemMessage | HumanMessage | AIMessage] = []
    for i, m in enumerate(messages):
        if "role" not in m or "content" not in m:
            raise ValueError(f"messages[{i}] must have 'role' and 'content'")
        role = m["role"]
        content = m["content"]
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            raise ValueError(f"messages[{i}].role must be system|user|assistant, got {role!r}")
    return out


async def chat_completion[T: BaseModel](
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = 30.0,  # noqa: ASYNC109
    response_model: type[T] | None = None,
) -> str | T:
    if not messages:
        raise ValueError("messages must not be empty")

    lc_messages = _to_lc_messages(messages)
    llm: BaseChatModel = get_chat_model(model=model, temperature=temperature, timeout=timeout)
    # method="function_calling" — без него langchain-openai 0.3+ использует strict
    # structured-output, где все поля схемы должны быть в `required`. Optional поля
    # (например `insights` в DialogueTurn) вызывают BadRequest 400 от OpenAI, и
    # handler тихо падает (юзер видит «бот зависает»). function_calling снимает
    # этот strict-check и совместим со всеми текущими и будущими pydantic-моделями.
    # Урок live-теста natural-dialogue 2026-05-25 (см. current_changes.md).
    runnable = (
        llm.with_structured_output(response_model, method="function_calling")
        if response_model is not None
        else llm
    )

    retrying = AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
        reraise=True,
    )

    async for attempt in retrying:
        with attempt:
            result = await runnable.ainvoke(lc_messages)

    if response_model is not None:
        return result  # type: ignore[return-value]
    return result.content  # type: ignore[no-any-return,union-attr]
