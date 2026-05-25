# bot_admin.handlers.questions.admin_question_edit

## Назначение

`/edit_question <id>|<new_text>[|on|off]` — изменить текст и/или активность вопроса.

## Шаги

1. `_require_admin`.
2. Парсинг: `id`, `new_text`, опционально `on`/`off` → `is_active`.
3. `update_question(qid, text=..., is_active=...)`.
4. Ответ с обновлённым `id` или с ошибкой (`ValueError`/`LookupError`).

## /goal

Изменения сохраняются; повторный `/questions` показывает обновление.

## Next

→ [admin_handle_question_delete.md](admin_handle_question_delete.md)
