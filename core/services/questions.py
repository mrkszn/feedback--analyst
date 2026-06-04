"""Questions service — business logic over the questions table.

DI: every public fn takes `storage: StorageAdapter | None` (the new seam) and
keeps `db: Client | None` for back-compat; internally
`storage = storage or SupabaseStorage(db or get_supabase())`. Storage access goes
through the adapter — no `.table()` here.
"""

from typing import Any, Literal, TypedDict, cast
from uuid import UUID

from supabase import Client

from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter

ExpectedType = Literal["text", "number", "enum", "boolean"]


class QuestionRow(TypedDict, total=False):
    id: str
    text: str
    metric_key: str
    expected_type: ExpectedType
    enum_values: list[str] | None
    is_active: bool
    created_by: int | None


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


async def create_question(
    *,
    text: str,
    metric_key: str,
    expected_type: ExpectedType,
    enum_values: list[str] | None = None,
    created_by: int | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> QuestionRow:
    if not text.strip():
        raise ValueError("text must not be empty")
    if not metric_key.strip():
        raise ValueError("metric_key must not be empty")
    if expected_type == "enum" and not enum_values:
        raise ValueError("enum question requires non-empty enum_values")

    store = _storage(storage, db)
    payload: dict[str, Any] = {
        "text": text,
        "metric_key": metric_key,
        "expected_type": expected_type,
        "enum_values": enum_values,
        "created_by": created_by,
    }
    try:
        row = await store.insert_question(payload)
    except Exception as exc:
        if "23505" in str(exc):
            raise ValueError(f"metric_key {metric_key!r} already exists") from exc
        raise
    return cast(QuestionRow, row)


async def update_question(
    question_id: str | UUID,
    *,
    text: str | None = None,
    enum_values: list[str] | None = None,
    is_active: bool | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> QuestionRow:
    patch: dict[str, Any] = {}
    if text is not None:
        patch["text"] = text
    if enum_values is not None:
        patch["enum_values"] = enum_values
    if is_active is not None:
        patch["is_active"] = is_active
    if not patch:
        raise ValueError("nothing to update")

    store = _storage(storage, db)
    rows = await store.update_question(question_id, patch)
    if not rows:
        raise LookupError(f"question {question_id} not found")
    return cast(QuestionRow, rows[0])


async def delete_question(
    question_id: str | UUID,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> None:
    store = _storage(storage, db)
    rows = await store.update_question(question_id, {"is_active": False})
    if not rows:
        raise LookupError(f"question {question_id} not found")


async def deactivate_all_questions(
    *,
    restaurant_id: UUID | str | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> int:
    """Soft-delete (set is_active=false) для всех активных вопросов.

    Возвращает количество затронутых строк. История ответов сохраняется —
    деактивация не каскадит. `restaurant_id` пока зарезервирован под
    будущий multi-tenant (схема единственного ресторана сейчас).
    """
    store = _storage(storage, db)
    rows = await store.deactivate_questions(
        restaurant_id=str(restaurant_id) if restaurant_id is not None else None
    )
    return len(rows)


async def find_question_by_text(
    query: str,
    *,
    active_only: bool = True,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> list[QuestionRow]:
    """Поиск вопросов по подстроке (ILIKE) в text или metric_key."""
    if not query.strip():
        return []
    store = _storage(storage, db)
    pattern = f"%{query.strip()}%"
    rows = await store.find_questions_by_text(pattern=pattern, active_only=active_only)
    return [cast(QuestionRow, r) for r in rows]


async def list_questions(
    *,
    active_only: bool = False,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> list[QuestionRow]:
    store = _storage(storage, db)
    rows = await store.list_questions(active_only=active_only)
    return [cast(QuestionRow, r) for r in rows]


async def get_question_expected_type(
    metric_key: str,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> str | None:
    """Return the `expected_type` of the question with `metric_key`, or None.

    Small read used by the HTTP /admin/metrics route so presentations don't reach
    into storage directly (CLAUDE.md invariant 5).
    """
    store = _storage(storage, db)
    row = await store.get_question_by_metric_key(metric_key)
    if row is None:
        return None
    et = row.get("expected_type")
    return str(et) if et is not None else None
