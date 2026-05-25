# bot_admin.handlers.auth.admin_start

## Назначение

`/start` admin-бота. Гейт через `is_admin`. Не-админам — подсказка про `/claim`. Админам — список доступных команд.

## Шаги

1. `is_admin(user.id)` → если нет, ответ-подсказка.
2. Если да — справка.

## /goal

`/start` для не-админа выдаёт `CLAIM_HINT`, для админа — меню команд.

## Next

→ [admin_handle_questions_list.md](admin_handle_questions_list.md)
