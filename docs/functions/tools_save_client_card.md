# tools.save_client_card

## Назначение

Записывает строку в `client_cards` (per-session карточка клиента, зеркало Pinecone-вектора). Используется в узле `build_client_card_node` после получения embedding и upsert'а в Pinecone.

## Сигнатура

```python
from uuid import UUID

async def save_client_card(
    *,
    client_id: int,
    session_id: str | UUID,
    summary_text: str,
    pinecone_vector_id: str,
    db: Client | None = None,
) -> str: ...
```

- Возврат: `id` записи (UUID-строка).

## Шаги реализации

1. Валидация: `summary_text` непустой; `pinecone_vector_id` непустой.
2. `db.table("client_cards").insert({...}).execute()` через `asyncio.to_thread`.
3. Вернуть `resp.data[0]["id"]`.

## Edge cases

- **Дубль session_id** (UNIQUE на `session_id`) → unique violation 23505 — пробрасываем как `ValueError("client_card already exists for session")`.
- **FK на client/session** — пробрасываем.

## Тесты

- `test_saves_client_card`
- `test_empty_summary_raises`
- `test_duplicate_session_raises`

## /goal

> `save_client_card` в `tools/client_cards.py`; тесты зелёные; коммит `feat(tools): implement save_client_card`.

## Команда

T1; `fn-tool-card`.

## Next

→ [agent_build_interview_prompt.md](agent_build_interview_prompt.md)
