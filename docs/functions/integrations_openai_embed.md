# integrations.openai_embed.embed_text

## Назначение

Превращает строку (карточку клиента) в float-вектор через OpenAI Embeddings (`text-embedding-3-small`, dim=1536). Используется в [[agent_build_client_card]] перед upsert'ом в Pinecone. Также может вызываться поштучно где угодно.

Единственная точка вызова Embeddings — поверх не должно быть прямых `OpenAIEmbeddings()`.

## Сигнатура

```python
async def embed_text(
    text: str,
    *,
    model: str | None = None,
    timeout: float = 30.0,
) -> list[float]: ...

async def embed_texts(
    texts: list[str],
    *,
    model: str | None = None,
    timeout: float = 30.0,
) -> list[list[float]]: ...
```

- `text` / `texts` — строка(и). Пустые/whitespace → `ValueError`.
- **Возврат:** список float (один) или список списков (batch).
- **Исключения:** `ValueError` для пустого ввода; `openai.APIError` после ретраев.

## Зависимости

- `langchain_openai.OpenAIEmbeddings` — `aembed_query`, `aembed_documents`.
- `tenacity` — 3 ретрая на транзиентные.
- `config.settings.openai_api_key`, `openai_embed_model`.

## Шаги реализации

1. Валидация: `text.strip()` пустой → `ValueError`. Для batch: каждый элемент.
2. `emb = OpenAIEmbeddings(model=model or settings.openai_embed_model, api_key=settings.openai_api_key, timeout=timeout)`.
3. `embed_text`: `await emb.aembed_query(text)` → `list[float]`.
4. `embed_texts`: `await emb.aembed_documents(texts)` → `list[list[float]]`.
5. Оба обёрнуты в retry.

## Edge cases

- **Пустая строка / whitespace** → `ValueError`.
- **Очень длинный текст (>8192 token)** → API вернёт 400 — НЕ ретраим.
- **Batch с пустым списком** → `ValueError("texts must not be empty")`.

## Тесты

`tests/test_integrations_openai_embed.py`:

- **Unit:**
  - `test_embed_text_returns_list_floats` — мок `aembed_query` возвращает `[0.1]*1536`, проверяем тип и длину.
  - `test_embed_texts_batch` — `aembed_documents` возвращает list of lists.
  - `test_empty_text_raises` — `""`/`"  "` → `ValueError`.
  - `test_empty_batch_raises` — `[]` → `ValueError`.
  - `test_retry_on_rate_limit` — 2 фейла, успех.
- **Интеграция:** `@pytest.mark.live` — реальный ключ, ожидаем `len(vec)==1536`.

## /goal

> `embed_text` и `embed_texts` в `integrations/openai_embed.py`; unit зелёные; ruff/mypy чисто; reviewer approve; коммит `feat(integrations): implement embed_text`.

## Команда (TeamCreate)

- **Шаблон:** T2
- **team_name:** `fn-int-embed`
- **Состав:** team-lead (claude) + integrator (general-purpose) + tester (general-purpose) + reviewer (Explore)

## Permissions

Наследуются. Сетевые вызовы — только OpenAI.

## Next

→ [integrations_pinecone_upsert.md](integrations_pinecone_upsert.md)
