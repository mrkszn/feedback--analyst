# bot_admin.handlers.auth.admin_claim

## Назначение

`/claim <token>` — разовая регистрация первого админа. Делегирует в [[services_admin_auth]] `claim_admin`.

## Шаги

1. Извлечь `command.args`.
2. Если пусто — usage-подсказка.
3. `claim_admin(user.id, token, name=user.full_name)` → bool.
4. Ответ «готово» / «не удалось».

## Edge

- Если admin_users непустая или токен не совпал → отказ (без раскрытия причины).

## /goal

Первый юзер с правильным токеном попадает в admin_users; последующие — отказ.

## Next

→ [admin_handle_start.md](admin_handle_start.md)
