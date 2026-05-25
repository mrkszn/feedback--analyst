# services.sessions.start_session

## Назначение

Создаёт новую строку в `sessions` для гостя — стартовая точка одного диалога. Возвращает `session_id` для использования в LangGraph state и FSM.

## Сигнатура

```python
from uuid import UUID

async def start_session(
    client_id: int,
    *,
    db: Client | None = None,
) -> UUID: ...
```

## Зависимости

- `clients.telegram_id` (FK).
- Таблица `sessions` (`id` UUID PK, `started_at` default now()).

## Шаги реализации

1. `db = db or get_supabase()`.
2. `await asyncio.to_thread(db.table("sessions").insert({"client_id": client_id}).execute)`.
3. Парсим `UUID(resp.data[0]["id"])` и возвращаем.

## Edge cases

- **Несуществующий client_id** → FK violation 23503 — пробрасываем (caller должен вызвать `create_or_get_client` сначала).
- **Параллельный старт** — допустим, каждый `insert` создаёт новый id.

## Тесты

- `test_returns_uuid` — мок insert → fake row → проверяем тип UUID.
- `test_fk_error_propagates` — мок бросает APIError 23503.

## /goal

> `start_session` в `services/sessions.py`; тесты зелёные; коммит `feat(services): implement start_session`.

## Команда

T1; `fn-svc-session-start`.

## Next

→ [services_session_append_message.md](services_session_append_message.md)
