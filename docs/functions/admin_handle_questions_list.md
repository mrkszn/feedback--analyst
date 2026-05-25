# bot_admin.handlers.questions.admin_questions_list

## Назначение

`/questions` — выводит весь пул (включая деактивированные) в одно сообщение. Каждая строка: флаг ✓/·, id, metric_key, тип, текст.

## Шаги

1. `_require_admin` гейт.
2. `list_questions()` (без `active_only`).
3. Формирование строк, ответ.

## /goal

Команда возвращает текущий список. Пустой пул → подсказка.

## Next

→ [admin_handle_question_add.md](admin_handle_question_add.md)
