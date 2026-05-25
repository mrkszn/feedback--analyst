# tools.get_active_questions

## Назначение

Thin tool для агента/LangGraph-узла: возвращает только активные вопросы (через `services.questions.list_questions(active_only=True)`). Этот слой отделяет «инструменты, которые видит агент» от внутренних сервисов БД.

## Сигнатура

```python
async def get_active_questions(*, db: Client | None = None) -> list[dict]: ...
```

- Возвращает список с полями `id`, `text`, `metric_key`, `expected_type`, `enum_values`.

## Шаги реализации

1. Вызвать `list_questions(active_only=True, db=db)`.
2. Проекция: оставить только нужные поля (агент не должен видеть `created_by`, `updated_at`).
3. Преобразовать `id` к str (UUID → str).

## Edge cases

- **Пустой пул** → пустой list (caller решает, что делать — обычно завершить сессию без интервью).

## Тесты

- `test_returns_only_active`
- `test_strips_internal_fields`
- `test_empty_pool_returns_empty_list`

## /goal

> `get_active_questions` в `tools/questions.py`; тесты зелёные; коммит `feat(tools): implement get_active_questions`.

## Команда

T1; `fn-tool-questions`.

## Next

→ [tools_save_answer_metric.md](tools_save_answer_metric.md)
