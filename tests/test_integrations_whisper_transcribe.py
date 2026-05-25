"""Unit-тесты для integrations.whisper.transcribe_voice.

Сетевые вызовы OpenAI замоканы через AsyncMock на `AsyncOpenAI`-конструкторе
внутри namespace `integrations.whisper`. Реальный сетевой вызов выполняется только
в `@pytest.mark.live` (отдельно, не часть unit-suite).
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIConnectionError, BadRequestError, RateLimitError

from integrations.whisper import transcribe_voice


def _make_client(create_mock: AsyncMock) -> MagicMock:
    """Собирает MagicMock-клиент с `client.audio.transcriptions.create`."""
    client = MagicMock()
    client.audio.transcriptions.create = create_mock
    return client


def _make_audio_file(tmp_path: Path) -> Path:
    """Создаёт пустой .oga-файл — Whisper API замокан, содержимое не важно."""
    p = tmp_path / "voice.oga"
    p.write_bytes(b"")
    return p


def _rate_limit_error() -> RateLimitError:
    """Конструирует RateLimitError с минимально валидным response."""
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


def _bad_request_error() -> BadRequestError:
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
    response = httpx.Response(400, request=request)
    return BadRequestError("bad audio", response=response, body=None)


async def test_transcribe_returns_text(tmp_path: Path) -> None:
    audio = _make_audio_file(tmp_path)
    create = AsyncMock(return_value=SimpleNamespace(text="привет"))
    client = _make_client(create)

    with patch("integrations.whisper.AsyncOpenAI", return_value=client):
        result = await transcribe_voice(audio)

    assert result == "привет"
    create.assert_awaited_once()


async def test_file_not_found_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.oga"

    with pytest.raises(FileNotFoundError):
        await transcribe_voice(missing)


async def test_default_model_from_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from config import settings

    monkeypatch.setattr(settings, "openai_whisper_model", "whisper-test-default")
    audio = _make_audio_file(tmp_path)
    create = AsyncMock(return_value=SimpleNamespace(text=""))
    client = _make_client(create)

    with patch("integrations.whisper.AsyncOpenAI", return_value=client):
        await transcribe_voice(audio)

    assert create.await_args is not None
    kwargs = create.await_args.kwargs
    assert kwargs["model"] == "whisper-test-default"


async def test_language_param_passed(tmp_path: Path) -> None:
    audio = _make_audio_file(tmp_path)
    create = AsyncMock(return_value=SimpleNamespace(text="ok"))
    client = _make_client(create)

    with patch("integrations.whisper.AsyncOpenAI", return_value=client):
        await transcribe_voice(audio, language="ru")

    assert create.await_args is not None
    kwargs = create.await_args.kwargs
    assert kwargs["language"] == "ru"


async def test_language_omitted_when_none(tmp_path: Path) -> None:
    audio = _make_audio_file(tmp_path)
    create = AsyncMock(return_value=SimpleNamespace(text="ok"))
    client = _make_client(create)

    with patch("integrations.whisper.AsyncOpenAI", return_value=client):
        await transcribe_voice(audio)

    assert create.await_args is not None
    assert "language" not in create.await_args.kwargs


async def test_retry_on_rate_limit(tmp_path: Path) -> None:
    audio = _make_audio_file(tmp_path)
    create = AsyncMock(
        side_effect=[
            _rate_limit_error(),
            _rate_limit_error(),
            SimpleNamespace(text="finally"),
        ]
    )
    client = _make_client(create)

    # Подменяем wait_exponential на нулевое ожидание, чтобы тест не висел.
    with (
        patch("integrations.whisper.AsyncOpenAI", return_value=client),
        patch("integrations.whisper.wait_exponential", lambda **_: lambda _r: 0),
    ):
        result = await transcribe_voice(audio)

    assert result == "finally"
    assert create.await_count == 3


async def test_retry_on_connection_error(tmp_path: Path) -> None:
    audio = _make_audio_file(tmp_path)
    request = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
    create = AsyncMock(
        side_effect=[
            APIConnectionError(request=request),
            SimpleNamespace(text="ok"),
        ]
    )
    client = _make_client(create)

    with (
        patch("integrations.whisper.AsyncOpenAI", return_value=client),
        patch("integrations.whisper.wait_exponential", lambda **_: lambda _r: 0),
    ):
        result = await transcribe_voice(audio)

    assert result == "ok"
    assert create.await_count == 2


async def test_bad_request_not_retried(tmp_path: Path) -> None:
    audio = _make_audio_file(tmp_path)
    create = AsyncMock(side_effect=_bad_request_error())
    client = _make_client(create)

    with patch("integrations.whisper.AsyncOpenAI", return_value=client):
        with pytest.raises(BadRequestError):
            await transcribe_voice(audio)

    assert create.await_count == 1


async def test_retry_exhausted_reraises(tmp_path: Path) -> None:
    audio = _make_audio_file(tmp_path)
    create = AsyncMock(side_effect=_rate_limit_error())
    client = _make_client(create)

    with (
        patch("integrations.whisper.AsyncOpenAI", return_value=client),
        patch("integrations.whisper.wait_exponential", lambda **_: lambda _r: 0),
    ):
        with pytest.raises(RateLimitError):
            await transcribe_voice(audio)

    assert create.await_count == 3
