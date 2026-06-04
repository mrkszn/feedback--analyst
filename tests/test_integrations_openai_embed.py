"""Unit-тесты для integrations.openai_embed.

Сетевые вызовы OpenAI замоканы через подмену класса OpenAIEmbeddings
на уровне модуля integrations.openai_embed.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import APIConnectionError, RateLimitError
from pydantic import SecretStr

from core.integrations import openai_embed


def _make_emb_instance(
    *,
    query_return: Any = None,
    docs_return: Any = None,
    query_side_effect: Any = None,
    docs_side_effect: Any = None,
) -> MagicMock:
    instance = MagicMock()
    instance.aembed_query = AsyncMock(return_value=query_return, side_effect=query_side_effect)
    instance.aembed_documents = AsyncMock(return_value=docs_return, side_effect=docs_side_effect)
    return instance


def _patch_embeddings(monkeypatch: pytest.MonkeyPatch, instance: MagicMock) -> MagicMock:
    factory = MagicMock(return_value=instance)
    monkeypatch.setattr(openai_embed, "OpenAIEmbeddings", factory)
    return factory


async def test_embed_text_returns_list_floats(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [0.1] * 1536
    instance = _make_emb_instance(query_return=expected)
    _patch_embeddings(monkeypatch, instance)

    result = await openai_embed.embed_text("привет")

    assert isinstance(result, list)
    assert len(result) == 1536
    assert all(isinstance(x, float) for x in result)
    instance.aembed_query.assert_awaited_once_with("привет")


async def test_embed_texts_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
    instance = _make_emb_instance(docs_return=expected)
    _patch_embeddings(monkeypatch, instance)

    result = await openai_embed.embed_texts(["a", "b", "c"])

    assert isinstance(result, list)
    assert len(result) == 3
    assert all(len(v) == 1536 for v in result)
    instance.aembed_documents.assert_awaited_once_with(["a", "b", "c"])


@pytest.mark.parametrize("bad", ["", "   ", "\n\t"])
async def test_empty_text_raises(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    instance = _make_emb_instance(query_return=[0.0])
    _patch_embeddings(monkeypatch, instance)

    with pytest.raises(ValueError):
        await openai_embed.embed_text(bad)

    instance.aembed_query.assert_not_awaited()


async def test_empty_batch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _make_emb_instance(docs_return=[])
    _patch_embeddings(monkeypatch, instance)

    with pytest.raises(ValueError):
        await openai_embed.embed_texts([])

    instance.aembed_documents.assert_not_awaited()


async def test_batch_with_empty_item_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _make_emb_instance(docs_return=[])
    _patch_embeddings(monkeypatch, instance)

    with pytest.raises(ValueError):
        await openai_embed.embed_texts(["ok", "  "])

    instance.aembed_documents.assert_not_awaited()


async def test_retry_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [0.5] * 1536

    response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com"))
    rate_err = RateLimitError(message="slow down", response=response, body=None)
    conn_err = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))

    instance = _make_emb_instance(
        query_side_effect=[rate_err, conn_err, expected],
    )
    _patch_embeddings(monkeypatch, instance)

    # Без реального ожидания между ретраями.
    monkeypatch.setattr(openai_embed, "wait_exponential", lambda **_: lambda *_a, **_k: 0)

    result = await openai_embed.embed_text("hi")

    assert result == expected
    assert instance.aembed_query.await_count == 3


async def test_factory_called_with_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _make_emb_instance(query_return=[0.0] * 1536)
    factory = _patch_embeddings(monkeypatch, instance)

    from config import settings

    monkeypatch.setattr(settings, "openai_embed_model", "text-embedding-3-small")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    await openai_embed.embed_text("hello", timeout=12.5)

    factory.assert_called_once_with(
        model="text-embedding-3-small",
        api_key=SecretStr("sk-test"),
        timeout=12.5,
    )


async def test_embed_text_custom_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _make_emb_instance(query_return=[0.0] * 1536)
    factory = _patch_embeddings(monkeypatch, instance)

    await openai_embed.embed_text("hi", model="text-embedding-3-large")

    assert factory.call_args.kwargs["model"] == "text-embedding-3-large"
