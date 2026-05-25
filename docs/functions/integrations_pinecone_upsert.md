# integrations.pinecone.upsert_client_card_vector

## Назначение

Кладёт per-session карточку клиента в Pinecone namespace `client-cards` (точнее — namespace из `settings.pinecone_namespace`). vector_id = session_id, metadata содержит `{client_id, session_id, date, sentiment, topics[]}` для top-level фильтрации в будущей аналитике.

Это единственная точка записи в Pinecone в v1 (search/query — отдельные функции Этапа 2).

## Сигнатура

```python
from datetime import datetime

async def upsert_client_card_vector(
    *,
    session_id: str,
    client_id: int,
    vector: list[float],
    sentiment: str | None,
    topics: list[str] | None,
    date: datetime | None = None,
    index_name: str | None = None,
    namespace: str | None = None,
) -> str: ...
```

- `session_id` — UUID-строка из `sessions.id`.
- `client_id` — telegram_id из `clients`.
- `vector` — list[float] длины 1536 (из [[integrations_openai_embed]]).
- `sentiment` / `topics` — extraction-результаты агента (могут быть `None`/`[]`).
- `date` — `datetime`; если `None`, берём `datetime.now(UTC)`.
- `index_name` / `namespace` — переопределение defaults из settings.
- **Возврат:** vector_id (== session_id).
- **Исключения:** `ValueError` (len(vector)!=1536); `pinecone.PineconeApiException` после ретраев.

## Зависимости

- `pinecone.Pinecone` — нативный клиент (есть thread-safe sync, поэтому `await asyncio.to_thread(...)` для асинхронности).
- `config.settings.pinecone_api_key`, `pinecone_index`, `pinecone_namespace`.
- `tenacity` — 3 ретрая.

## Шаги реализации

1. Валидация: `len(vector) == 1536`; иначе `ValueError`.
2. `date_iso = (date or datetime.now(UTC)).isoformat()`.
3. `metadata = {"client_id": client_id, "session_id": session_id, "date": date_iso}`. Если `sentiment` — добавляем; если `topics` непуст — добавляем как `list[str]` (Pinecone metadata поддерживает массивы строк).
4. `pc = Pinecone(api_key=settings.pinecone_api_key)`.
5. `index = pc.Index(index_name or settings.pinecone_index)`.
6. `await asyncio.to_thread(index.upsert, vectors=[{"id": session_id, "values": vector, "metadata": metadata}], namespace=namespace or settings.pinecone_namespace)`.
7. Вернуть `session_id`.

## Edge cases

- **`len(vector) != 1536`** → `ValueError`. Защита от подмешивания не того embedding-модели.
- **Пустые `topics`** → не кладём ключ в metadata (Pinecone не любит пустые массивы в части квот).
- **Сетевые** → retry. После исчерпания — пробрасываем.
- **Конкурентные upsert'ы с одним session_id** → Pinecone делает upsert-by-id; перезапись допустима.

## Тесты

`tests/test_integrations_pinecone_upsert.py`:

- **Unit:**
  - `test_upsert_returns_session_id` — мок `Pinecone().Index().upsert`, проверяем что возвращён `session_id`.
  - `test_invalid_vector_length_raises` — `[0.0]*100` → `ValueError`.
  - `test_metadata_includes_required_fields` — захватываем kwargs `upsert`, проверяем `metadata` имеет client_id, session_id, date.
  - `test_empty_topics_omitted` — `topics=[]` → ключ не присутствует.
  - `test_default_namespace_from_settings` — без override берём `settings.pinecone_namespace`.
- **Интеграция:** `@pytest.mark.live` — реальный upsert в namespace `test-{uuid}` + cleanup.

## /goal

> `upsert_client_card_vector` в `integrations/pinecone.py`; unit зелёные; ruff/mypy чисто; reviewer approve; коммит `feat(integrations): implement upsert_client_card_vector`.

## Команда (TeamCreate)

- **Шаблон:** T2
- **team_name:** `fn-int-pinecone`
- **Состав:** team-lead (claude) + integrator (general-purpose) + tester (general-purpose) + reviewer (Explore)

## Permissions

Наследуются. Сетевые вызовы — только Pinecone (`*.pinecone.io`).

## Next

→ [services_admin_auth.md](services_admin_auth.md)
