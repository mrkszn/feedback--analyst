# services.sessions.append_session_message

## Назначение

Сохраняет одну реплику в `session_messages` (роль user|bot + текст). Используется и хэндлером, и агентом — каждое сообщение по обе стороны.

## Сигнатура

```python
from typing import Literal

async def append_session_message(
    session_id: str | UUID,
    role: Literal["user", "bot"],
    content: str,
    *,
    db: Client | None = None,
) -> int: ...
```

- Возврат: bigserial `id` строки.

## Шаги реализации

1. Привести `session_id` к `str`.
2. Валидация: `role in {"user","bot"}`, `content` не пуст после strip.
3. `db.table("session_messages").insert({"session_id": str(session_id), "role": role, "content": content}).execute()` (через `asyncio.to_thread`).
4. Вернуть `resp.data[0]["id"]`.

## Edge cases

- **Невалидная роль** → `ValueError`.
- **Пустой content** → `ValueError`.
- **Несуществующий session_id** → FK violation — пробрасываем.

## Тесты

- `test_appends_user_message`
- `test_appends_bot_message`
- `test_empty_content_raises`
- `test_invalid_role_raises`

## /goal

> `append_session_message` в `services/sessions.py` (тот же модуль); коммит `feat(services): implement append_session_message`.

## Команда

T1; `fn-svc-session-msg`.

## Next

→ [services_session_save_feedback.md](services_session_save_feedback.md)
