"""Tool: persist a per-session client card (mirror of the Pinecone vector).

DI: `storage: StorageAdapter | None` (new) + `db: Client | None` (back-compat).
"""

from typing import Any, cast
from uuid import UUID

from supabase import Client

from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


async def save_client_card(
    *,
    client_id: int,
    session_id: str | UUID,
    summary_text: str,
    pinecone_vector_id: str,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> str:
    if not summary_text.strip():
        raise ValueError("summary_text must not be empty")
    if not pinecone_vector_id.strip():
        raise ValueError("pinecone_vector_id must not be empty")

    store = _storage(storage, db)
    try:
        row = await store.insert_client_card(
            {
                "client_id": client_id,
                "session_id": str(session_id),
                "summary_text": summary_text,
                "pinecone_vector_id": pinecone_vector_id,
            }
        )
    except Exception as exc:
        if "23505" in str(exc):
            raise ValueError(f"client_card already exists for session {session_id}") from exc
        raise
    return str(cast(dict[str, Any], row)["id"])
