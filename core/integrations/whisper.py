"""Тонкая обёртка над OpenAI Whisper API для расшифровки voice-сообщений.

Используется в `guest_handle_feedback_voice`: принимает локальный файл (скачанный
через `utils.voice_download.download_voice_to_tmp`) и возвращает текст-расшифровку.

LangChain не имеет first-class Whisper-обёртки, поэтому используем native SDK.
"""

from pathlib import Path

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings


async def transcribe_voice(
    file_path: Path | str,
    *,
    model: str | None = None,
    language: str | None = None,
    timeout: float = 60.0,  # noqa: ASYNC109  # пробрасываем в HTTP-клиент OpenAI
) -> str:
    """Расшифровывает локальный audio-файл через OpenAI Whisper.

    Args:
        file_path: Путь к локальному audio (ogg/oga/mp3/wav/m4a).
        model: Slug Whisper-модели; если None — берём `settings.openai_whisper_model`.
        language: ISO-639-1 (`ru`, `uk`, `en`); если None — Whisper определит сам.
        timeout: HTTP-таймаут одного запроса к OpenAI, секунды.

    Returns:
        Строка-расшифровка (возможно пустая, если ничего не расслышал).

    Raises:
        FileNotFoundError: Если файла нет по указанному пути.
        openai.APIError: После исчерпания ретраев на сетевых/rate-limit ошибках.
        openai.BadRequestError: Сразу, без ретраев (битый/неподдерживаемый файл).
    """
    # Path-операции синхронные, но дешёвые (resolve/exists/open) — приемлемо
    # для не-throughput-критичного пути. Файл маленький (<25MB Whisper-лимит).
    path = Path(file_path).resolve()  # noqa: ASYNC240
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)
    effective_model = model or settings.openai_whisper_model

    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1),
        reraise=True,
    ):
        with attempt:
            with path.open("rb") as f:
                # `language` опционален: SDK ожидает `str | Omit`, поэтому передаём
                # ключ только когда явно задан — иначе Whisper детектит язык сам.
                if language is None:
                    resp = await client.audio.transcriptions.create(
                        model=effective_model,
                        file=f,
                    )
                else:
                    resp = await client.audio.transcriptions.create(
                        model=effective_model,
                        file=f,
                        language=language,
                    )
            return resp.text

    # Недостижимо: reraise=True гарантирует исключение, если все попытки упали.
    raise RuntimeError("unreachable: AsyncRetrying exited without result")
