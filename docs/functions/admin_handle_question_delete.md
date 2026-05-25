# bot_admin.handlers.questions.admin_question_delete

## Назначение

`/delete_question <id>` — soft-delete (выставляет `is_active=false`). Хард-делит не делаем, чтобы не порвать FK у `session_answers`.

## Шаги

1. `_require_admin`.
2. `delete_question(qid)` → пробрасывает `LookupError` для несуществующего.
3. Ответ.

## /goal

Вопрос становится `is_active=false`; в active-листе исчезает, исторические `session_answers` остаются.

## Next

→ [admin_handle_invite_admin.md](admin_handle_invite_admin.md)
