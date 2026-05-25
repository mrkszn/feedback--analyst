# services.questions — CRUD по пулу вопросов

## Назначение

4 операции для admin-бота: создать, обновить, удалить (soft через `is_active=false`), список активных. Источник пула вопросов для интервью гостя.

## Сигнатура

```python
from typing import Literal, TypedDict
from uuid import UUID

ExpectedType = Literal["text", "number", "enum", "boolean"]

class QuestionRow(TypedDict, total=False):
    id: str
    text: str
    metric_key: str
    expected_type: ExpectedType
    enum_values: list[str] | None
    is_active: bool
    created_by: int | None

async def create_question(
    *,
    text: str,
    metric_key: str,
    expected_type: ExpectedType,
    enum_values: list[str] | None = None,
    created_by: int | None = None,
    db: Client | None = None,
) -> QuestionRow: ...

async def update_question(
    question_id: str | UUID,
    *,
    text: str | None = None,
    enum_values: list[str] | None = None,
    is_active: bool | None = None,
    db: Client | None = None,
) -> QuestionRow: ...

async def delete_question(
    question_id: str | UUID,
    *,
    db: Client | None = None,
) -> None: ...

async def list_questions(
    *,
    active_only: bool = False,
    db: Client | None = None,
) -> list[QuestionRow]: ...
```

## Шаги реализации

- `create_question`:
  - Валидация: `text`/`metric_key` непустые; если `expected_type == "enum"`, `enum_values` — непустой list.
  - `insert` → возврат вставленной row.
- `update_question`:
  - Собрать dict только из переданных не-None полей; `update().eq("id", ...).execute()`.
  - Пустой patch → `ValueError("nothing to update")`.
- `delete_question`:
  - Soft delete: `update({"is_active": False}).eq("id", ...)`. (Hard delete = риск нарушить FK у `session_answers`.)
- `list_questions`:
  - `select("*")`; если `active_only` → `.eq("is_active", True)`.
  - Сортировка по `created_at desc`.

Все blocking через `asyncio.to_thread`.

## Edge cases

- **enum без enum_values** → `ValueError`.
- **Дубль `metric_key`** → unique violation 23505 — пробрасываем как `ValueError("metric_key already exists")`.
- **`update_question` с несуществующим id** — resp.data пустой → `LookupError`.

## Тесты

- `test_create_question_text_type`
- `test_create_enum_requires_values`
- `test_create_duplicate_metric_key_raises`
- `test_update_partial`
- `test_update_empty_patch_raises`
- `test_delete_marks_inactive`
- `test_list_all`
- `test_list_active_only`

## /goal

> 4 функции в `services/questions.py`; тесты зелёные; коммит `feat(services): implement questions CRUD`.

## Команда

T1; `fn-svc-questions-crud`.

## Next

→ [tools_get_questions_pool.md](tools_get_questions_pool.md)
