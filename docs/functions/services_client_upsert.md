# services.clients.create_or_get_client

## Назначение

При первом сообщении гостя — создать строку в `clients`. Если уже есть — вернуть существующую. Используется на каждом `/start` и при получении voice/text-feedback.

## Сигнатура

```python
async def create_or_get_client(
    telegram_id: int,
    *,
    name: str | None = None,
    db: Client | None = None,
) -> dict: ...
```

- Возврат: dict со столбцами `telegram_id`, `name`, `created_at` (как вернул Supabase).

## Зависимости

- `db.client.get_supabase()`.
- Таблица `clients` (telegram_id PK).

## Шаги реализации

1. `db = db or get_supabase()`.
2. Попробовать `db.table("clients").select("*").eq("telegram_id", telegram_id).limit(1).execute()` — если есть, вернуть `resp.data[0]`.
3. Иначе `db.table("clients").insert({"telegram_id": telegram_id, "name": name}).execute()` → вернуть `resp.data[0]`.
4. Wrap blocking-вызовы в `await asyncio.to_thread(...)`.

## Edge cases

- **Race: два конкурентных insert** → ловим `APIError` с code `23505` (unique violation) и повторяем select.
- **`name` None** → так и пишем NULL.

## Тесты

- `test_create_when_missing` — мок: select → пусто, insert → возвращает row.
- `test_returns_existing` — select → row.
- `test_race_unique_violation_recovers` — insert бросает 23505, повторный select возвращает row.

## /goal

> `create_or_get_client` в `services/clients.py`; тесты зелёные; ruff/mypy чисто; коммит `feat(services): implement create_or_get_client`.

## Команда

T1; `fn-svc-client-upsert`.

## Next

→ [services_session_start.md](services_session_start.md)
