# bot_admin.handlers.questions.admin_invite_admin

## Назначение

`/invite_admin <telegram_id>` — добавляет ещё одного админа. Доступно только существующим админам. Записывает `invited_by = current user`.

## Шаги

1. `_require_admin`.
2. Парсим `int(args)`; невалид → подсказка.
3. `db.table("admin_users").insert({"telegram_id": target_id, "invited_by": inviter}).execute()` через `asyncio.to_thread`.
4. На unique violation (23505) — «уже админ».
5. Любая другая ошибка — отчёт текстом.

## Edge

- Невалидный int → подсказка.
- Дубль → понятный ответ.

## /goal

Существующий админ может расширить пул `admin_users` без bootstrap-токена.

## Next

→ [api_health.md](api_health.md)
