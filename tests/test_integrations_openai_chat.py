"""Unit-тесты для integrations.openai_chat.

Мокаем `ChatOpenAI` целиком — реальная сеть OpenAI не дёргается.
Структурированные ответы проверяются через `with_structured_output`,
ретраи — через подмену `ainvoke` на AsyncMock с side_effect.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from langchain_core.messages import AIMessage
from openai import RateLimitError
from pydantic import BaseModel
from pytest_mock import MockerFixture

from config import settings
from integrations import openai_chat


class _Sentiment(BaseModel):
    label: str
    score: float


def _make_rate_limit_error() -> RateLimitError:
    response = httpx.Response(
        status_code=429,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    return RateLimitError(message="rate", response=response, body=None)


async def test_chat_completion_plain_text(mocker: MockerFixture) -> None:
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="hi"))
    mocker.patch.object(openai_chat, "get_chat_model", return_value=llm)

    result = await openai_chat.chat_completion([{"role": "user", "content": "hello"}])

    assert result == "hi"
    llm.ainvoke.assert_awaited_once()


async def test_chat_completion_structured(mocker: MockerFixture) -> None:
    payload = _Sentiment(label="pos", score=0.9)
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=payload)
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured)
    mocker.patch.object(openai_chat, "get_chat_model", return_value=llm)

    result = await openai_chat.chat_completion(
        [{"role": "user", "content": "rate it"}],
        response_model=_Sentiment,
    )

    assert isinstance(result, _Sentiment)
    assert result.label == "pos"
    assert result.score == 0.9
    llm.with_structured_output.assert_called_once_with(_Sentiment)


async def test_empty_messages_raises() -> None:
    with pytest.raises(ValueError, match="messages must not be empty"):
        await openai_chat.chat_completion([])


async def test_invalid_role_raises() -> None:
    with pytest.raises(ValueError, match="role"):
        await openai_chat.chat_completion([{"role": "bot", "content": "x"}])


async def test_missing_content_raises() -> None:
    with pytest.raises(ValueError, match=r"role.*content"):
        await openai_chat.chat_completion([{"role": "user"}])


async def test_retry_on_rate_limit(mocker: MockerFixture) -> None:
    err = _make_rate_limit_error()
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=[err, err, AIMessage(content="ok")])
    mocker.patch.object(openai_chat, "get_chat_model", return_value=llm)
    # Убираем реальные паузы exponential backoff.
    mocker.patch("integrations.openai_chat.wait_exponential", return_value=lambda _rs: 0)

    result = await openai_chat.chat_completion([{"role": "user", "content": "hi"}])

    assert result == "ok"
    assert llm.ainvoke.await_count == 3


async def test_retry_exhausted_propagates(mocker: MockerFixture) -> None:
    err = _make_rate_limit_error()
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=[err, err, err])
    mocker.patch.object(openai_chat, "get_chat_model", return_value=llm)
    mocker.patch("integrations.openai_chat.wait_exponential", return_value=lambda _rs: 0)

    with pytest.raises(RateLimitError):
        await openai_chat.chat_completion([{"role": "user", "content": "hi"}])

    assert llm.ainvoke.await_count == 3


def test_usage_tag_in_headers(mocker: MockerFixture) -> None:
    captured: dict[str, Any] = {}

    def _fake_init(self: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    mocker.patch.object(openai_chat.ChatOpenAI, "__init__", _fake_init)

    openai_chat.get_chat_model()

    assert captured["default_headers"] == {"X-Usage-Tag": settings.openai_usage_tag}
    assert captured["model"] == settings.openai_chat_model
    assert captured["temperature"] == 0.2
    assert captured["timeout"] == 30.0


def test_get_chat_model_overrides(mocker: MockerFixture) -> None:
    captured: dict[str, Any] = {}

    def _fake_init(self: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    mocker.patch.object(openai_chat.ChatOpenAI, "__init__", _fake_init)

    openai_chat.get_chat_model(model="gpt-5.1-mini", temperature=0.7, timeout=10.0)

    assert captured["model"] == "gpt-5.1-mini"
    assert captured["temperature"] == 0.7
    assert captured["timeout"] == 10.0
