# integrations.whisper.transcribe_voice

## Назначение

Принимает локальный `Path` к voice-файлу (скачанному через [[utils_voice_download]]) и возвращает расшифровку текста через OpenAI Whisper API. Используется в [[guest_handle_feedback_voice]] — чтобы превратить voice-отзыв гостя в `feedback_raw_text` для дальнейшего анализа агентом.

## Сигнатура

```python
from pathlib import Path

async def transcribe_voice(
    file_path: Path | str,
    *,
    model: str | None = None,
    language: str | None = None,
    timeout: float = 60.0,
) -> str: ...
```

- `file_path` — путь к локальному audio (ogg/oga/mp3/wav/m4a).
- `model` — slug Whisper; если `None`, берём `settings.openai_whisper_model`.
- `language` — ISO-639-1 (`ru`, `uk`, `en`); если `None`, Whisper определит автоматически.
- **Возврат:** строка-расшифровка (может быть пустой, если ничего не услышал).
- **Исключения:**
  - `FileNotFoundError` — файла нет.
  - `openai.APIError` — после исчерпания ретраев.

## Зависимости

- `openai.AsyncOpenAI` (используем native SDK — у LangChain нет first-class Whisper-обёртки).
- `tenacity` — ретраи на `RateLimitError`/`APIConnectionError`/`APITimeoutError` (3 попытки, exp backoff).
- `config.settings.openai_api_key`, `openai_whisper_model`.

## Шаги реализации

1. `path = Path(file_path).resolve()`; если `not path.exists()` → `FileNotFoundError`.
2. `client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)`.
3. Открыть файл `with path.open("rb") as f`.
4. `resp = await client.audio.transcriptions.create(model=model or settings.openai_whisper_model, file=f, language=language)`.
5. Вернуть `resp.text`.
6. Обернуть весь шаг 4 в `tenacity.AsyncRetrying` на `RateLimitError|APIConnectionError|APITimeoutError`.

## Edge cases

- **Файл отсутствует** → `FileNotFoundError`.
- **Пустой/неподдерживаемый формат** → OpenAI вернёт `BadRequestError` (4xx) — НЕ ретраим, пробрасываем.
- **Длинный файл (>25MB)** → OpenAI отклонит. Обрезка — за вызывающим (вне scope v1).
- **Whisper ничего не расслышал** → пустая строка; обработка в caller'е.

## Тесты

`tests/test_integrations_whisper_transcribe.py`:

- **Unit:**
  - `test_transcribe_returns_text` — мок `AsyncOpenAI.audio.transcriptions.create` возвращает объект с `.text="привет"`, проверяем результат.
  - `test_file_not_found_raises` — несуществующий путь → `FileNotFoundError`.
  - `test_default_model_from_settings` — без `model` берём `settings.openai_whisper_model`.
  - `test_language_param_passed` — `language="ru"` доходит до create-вызова.
  - `test_retry_on_rate_limit` — два `RateLimitError`, потом успех.
  - `test_bad_request_not_retried` — `BadRequestError` пробрасывается сразу.
- **Интеграция:** `@pytest.mark.live` — реальный короткий ogg → ожидаем непустой text.

## /goal

> `transcribe_voice` имплементирована в `integrations/whisper.py`; unit-тесты зелёные; ruff/mypy чисто; reviewer approve; коммит `feat(integrations): implement transcribe_voice`.

## Команда (TeamCreate)

- **Шаблон:** T2
- **team_name:** `fn-int-whisper`
- **Состав:** team-lead (claude) + integrator (general-purpose) + tester (general-purpose) + reviewer (Explore)

## Permissions

Наследуются. Сетевые вызовы — только OpenAI.

## Next

→ [integrations_openai_embed.md](integrations_openai_embed.md)
