from langchain_openai import OpenAIEmbeddings
from openai import APIConnectionError, APITimeoutError, RateLimitError
from pydantic import SecretStr
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings


def _get_embeddings(*, model: str | None, timeout: float) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=model or settings.openai_embed_model,
        api_key=SecretStr(settings.openai_api_key),
        timeout=timeout,
    )


def _retrying() -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
        reraise=True,
    )


async def embed_text(
    text: str,
    *,
    model: str | None = None,
    timeout: float = 30.0,  # noqa: ASYNC109 — пробрасывается в HTTP-клиент OpenAI
) -> list[float]:
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    emb = _get_embeddings(model=model, timeout=timeout)
    vector: list[float] = []
    async for attempt in _retrying():
        with attempt:
            vector = await emb.aembed_query(text)
    return vector


async def embed_texts(
    texts: list[str],
    *,
    model: str | None = None,
    timeout: float = 30.0,  # noqa: ASYNC109 — пробрасывается в HTTP-клиент OpenAI
) -> list[list[float]]:
    if not texts:
        raise ValueError("texts must not be empty")
    for i, t in enumerate(texts):
        if not t or not t.strip():
            raise ValueError(f"texts[{i}] must not be empty")

    emb = _get_embeddings(model=model, timeout=timeout)
    vectors: list[list[float]] = []
    async for attempt in _retrying():
        with attempt:
            vectors = await emb.aembed_documents(texts)
    return vectors
