# integrations.openai_chat.chat_completion

## Назначение

Тонкая обёртка над `langchain-openai` для всех чат-вызовов GPT-5.x. Используется агентскими узлами (analyze_feedback, select_questions, extract_metric, build_client_card) для получения структурированных ответов через `with_structured_output` либо чистого текста. Скрывает: загрузку ключа из `settings`, дефолтную модель из `OPENAI_CHAT_MODEL`, таймауты, ретраи на транзиентные ошибки, тег биллинга (`OPENAI_USAGE_TAG`).

Это **единственная** точка вызова OpenAI Chat Completions в проекте — нигде больше `openai.OpenAI()` или `ChatOpenAI(...)` напрямую не инстанцируется.

## Сигнатура

```python
from typing import Any, TypeVar
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

def get_chat_model(
    *,
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = 30.0,
) -> BaseChatModel: ...

async def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = 30.0,
    response_model: type[T] | None = None,
) -> str | T: ...
```

- `messages` — список `{"role": "system|user|assistant", "content": "..."}`.
- `model` — slug; если `None`, берём `settings.openai_chat_model`.
- `response_model` — если задан, возвращается экземпляр Pydantic-модели через `with_structured_output`.
- **Возврат:** `str` (если без `response_model`) или экземпляр `T`.
- **Исключения:**
  - `openai.APIError` / `openai.RateLimitError` — после исчерпания ретраев пробрасывается.
  - `ValueError` — пустой `messages`.

## Зависимости

- `langchain_openai.ChatOpenAI`
- `tenacity` — `retry(stop_after_attempt=3, wait=exponential)` на `RateLimitError`/`APIConnectionError`/`APITimeoutError`.
- `config.settings`: `openai_api_key`, `openai_chat_model`, `openai_usage_tag`.

## Шаги реализации

1. `get_chat_model()`: возвращает `ChatOpenAI(model=..., api_key=settings.openai_api_key.get_secret_value() or settings.openai_api_key, temperature=..., timeout=..., default_headers={"X-Usage-Tag": settings.openai_usage_tag})`.
2. `chat_completion(messages, ...)`:
   - валидация `messages` (не пусто, все элементы имеют `role`/`content`);
   - `llm = get_chat_model(...)`;
   - если `response_model is not None`: `llm = llm.with_structured_output(response_model)`;
   - конвертация `messages` в `langchain_core.messages.{SystemMessage,HumanMessage,AIMessage}`;
   - `result = await llm.ainvoke(lc_messages)`;
   - вернуть `result.content` (str) или `result` (Pydantic), в зависимости от ветки.
3. Декоратор `@retry` оборачивает внутренний `ainvoke` через `tenacity.retry_with` (или `AsyncRetrying`).

## Edge cases

- **Пустой `messages`** → `ValueError("messages must not be empty")`.
- **RateLimitError** → 3 ретрая с exponential backoff (1s, 2s, 4s).
- **Таймаут** → пробрасывается после ретраев.
- **`response_model` указан, но LLM вернул невалидный JSON** → `langchain` бросит `ValidationError` — не глотаем.
- **Секреты в логах** — `api_key` НИКОГДА не логируем; в `repr`/`str` модели LangChain маскирует.

## Тесты

`tests/test_integrations_openai_chat.py`:

- **Unit (mock):**
  - `test_chat_completion_plain_text` — мок `ChatOpenAI.ainvoke` возвращает `AIMessage(content="hi")`, проверяем `result == "hi"`.
  - `test_chat_completion_structured` — мок возвращает Pydantic-модель, проверяем тип.
  - `test_empty_messages_raises` — `ValueError`.
  - `test_retry_on_rate_limit` — мок бросает `RateLimitError` дважды, потом успех — проверяем что вызов прошёл и было 3 попытки.
  - `test_usage_tag_in_headers` — проверяем что `default_headers["X-Usage-Tag"] == settings.openai_usage_tag`.
- **Интеграция:** **skip** в CI; локальный smoke с реальным ключом — отдельный маркер `@pytest.mark.live`.

## /goal

> Функция `chat_completion` имплементирована в `integrations/openai_chat.py` по сигнатуре; `get_chat_model` экспортируется; все unit-тесты зелёные; `uv run ruff check .` и `uv run mypy .` без новых ошибок; reviewer ✅ approve; коммит `feat(integrations): implement chat_completion` по формату `docs/GIT.md §4-5`.

## Команда (TeamCreate)

- **Шаблон:** **T2 — Integration**
- **team_name:** `fn-int-openai-chat`
- **Состав:**
  - `team-lead` — `subagent_type: claude`
  - `integrator` — `subagent_type: general-purpose`
  - `tester` — `subagent_type: general-purpose`
  - `reviewer` — `subagent_type: Explore`

## Permissions

Наследуются. Сетевые вызовы — только OpenAI (allow в red-lines).

## Next

→ [integrations_whisper_transcribe.md](integrations_whisper_transcribe.md)
