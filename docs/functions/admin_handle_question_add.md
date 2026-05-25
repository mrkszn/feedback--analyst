# bot_admin.handlers.questions.admin_question_add

## Назначение

`/add_question` — двухшаговый FSM: вход → запрос формата → парсинг → `create_question`.

## Шаги

1. `_require_admin`.
2. `state.set_state(AdminFlow.AWAITING_QUESTION_TEXT)`.
3. Подсказка по формату `<metric_key>|<expected_type>|<text>[|enum1,enum2]`.
4. В следующем сообщении (`AWAITING_QUESTION_TEXT`):
   - Парсим `|`-разделённые поля.
   - `create_question(...)`.
   - `state.clear()`, ответ с `id`.

## Edge

- < 3 полей → подсказка.
- `enum` без 4-го поля → `ValueError` от services, ответ с ошибкой.

## /goal

Можно создать вопрос через бот; пишется в `questions` с правильным `created_by`.

## Next

→ [admin_handle_question_edit.md](admin_handle_question_edit.md)
