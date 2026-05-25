# services.sessions.end_session

## Назначение

Закрывает сессию — выставляет `ended_at = now()`. Вызывается из агента после финализации (карточка клиента создана, vector upsert'нут) или при `/cancel`.

## Сигнатура

```python
async def end_session(
    session_id: str | UUID,
    *,
    db: Client | None = None,
) -> None: ...
```

## Шаги реализации

1. `db.table("sessions").update({"ended_at": "now()"}).eq("id", str(session_id)).execute()` через `asyncio.to_thread`.
   - Альтернатива: использовать `datetime.now(UTC).isoformat()` — supabase-py принимает strings.
2. Если `resp.data` пуст → `LookupError`.

## Edge cases

- **Повторный end_session** — допустим: просто перезапишем `ended_at`.
- **session_id не существует** → `LookupError`.

## Тесты

- `test_sets_ended_at`
- `test_session_not_found_raises`
- `test_idempotent_end_session`

## /goal

> `end_session` в `services/sessions.py`; коммит `feat(services): implement end_session`.

## Команда

T1; `fn-svc-session-end`.

## Next

→ [services_questions_crud.md](services_questions_crud.md)
