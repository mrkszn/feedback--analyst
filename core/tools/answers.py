"""Tool: persist an interview answer with its extracted metric.

DI: `storage: StorageAdapter | None` (new) + `db: Client | None` (back-compat).
"""

from typing import Any, cast
from uuid import UUID

from supabase import Client

from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


async def save_answer_with_metric(
    *,
    session_id: str | UUID,
    question_id: str | UUID,
    answer_text: str,
    marked_value: Any,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> int:
    if not answer_text.strip():
        raise ValueError("answer_text must not be empty")

    store = _storage(storage, db)
    row = await store.insert_answer(
        {
            "session_id": str(session_id),
            "question_id": str(question_id),
            "answer_text": answer_text,
            "marked_value": marked_value,
        }
    )
    return int(cast(dict[str, Any], row)["id"])
