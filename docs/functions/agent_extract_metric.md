# agent.nodes.extract_metric_from_answer

## Назначение

LangGraph node: для одного ответа гостя на конкретный вопрос — извлечь структурированное значение в соответствии с `expected_type` вопроса (text|number|enum|boolean). Возвращает значение, которое потом пишется в `session_answers.marked_value`.

## Сигнатура

```python
from typing import Any

async def extract_metric_from_answer(
    *,
    question: dict,  # {id, text, metric_key, expected_type, enum_values}
    answer_text: str,
) -> Any: ...
```

- Возврат: тип зависит от `expected_type`:
  - `text` → `str` (саммари ответа, не дословный)
  - `number` → `float | None`
  - `enum` → `str` (одно из `enum_values`) или `None`
  - `boolean` → `bool | None`
- `None` означает «не удалось извлечь».

## Зависимости

- `agent.prompts.build_extract_prompt`.
- `integrations.openai_chat.chat_completion`.

## Шаги реализации

1. Валидация: `answer_text` непустой.
2. Сборка Pydantic-модели ответа динамически по `expected_type` (или 4 типа моделей-обёрток с полем `value: T | None`).
3. `prompt.format_messages(question_text=q["text"], expected_type=q["expected_type"], enum_values=q.get("enum_values"), answer_text=answer_text)`.
4. `result = await chat_completion(messages, response_model=<подходящая модель>)`.
5. Для `enum`: проверить что значение в `enum_values`, иначе `None`.
6. Вернуть `result.value`.

## Edge cases

- **Пустой ответ** → `ValueError`.
- **`enum` без enum_values в вопросе** → `ValueError("enum question must have enum_values")`.
- **Числовой ответ не парсится** → `None`.
- **Boolean неоднозначен** → `None`.

## Тесты

- `test_extract_text`
- `test_extract_number_valid`
- `test_extract_number_invalid_returns_none`
- `test_extract_enum_in_values`
- `test_extract_enum_out_of_values_returns_none`
- `test_extract_boolean`
- `test_empty_answer_raises`

## /goal

> `extract_metric_from_answer` в `agent/nodes/extract.py`; тесты зелёные; коммит `feat(agent): implement extract_metric_from_answer`.

## Команда

T1; `fn-agent-extract`.

## Next

→ [agent_build_client_card.md](agent_build_client_card.md)
