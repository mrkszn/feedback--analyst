# tools.save_answer_with_metric

## Назначение

Сохраняет в `session_answers` ответ гостя + извлечённый агентом структурированный `marked_value`. Вызывается из узла `extract_metric_node` LangGraph.

## Сигнатура

```python
from typing import Any
from uuid import UUID

async def save_answer_with_metric(
    *,
    session_id: str | UUID,
    question_id: str | UUID,
    answer_text: str,
    marked_value: Any,
    db: Client | None = None,
) -> int: ...
```

- Возврат: `id` строки.

## Шаги реализации

1. Валидация: `answer_text` непустой.
2. `db.table("session_answers").insert({...}).execute()` через `asyncio.to_thread`. `marked_value` сериализуется как jsonb (supabase-py принимает Python-объекты).
3. Вернуть `resp.data[0]["id"]`.

## Edge cases

- **Пустой answer_text** → `ValueError`.
- **Несуществующий question_id/session_id** → FK violation — пробрасываем.

## Тесты

- `test_saves_answer_with_text_metric`
- `test_saves_answer_with_dict_metric`
- `test_empty_answer_raises`

## /goal

> `save_answer_with_metric` в `tools/answers.py`; тесты зелёные; коммит `feat(tools): implement save_answer_with_metric`.

## Команда

T1; `fn-tool-answer`.

## Next

→ [tools_save_client_card.md](tools_save_client_card.md)
