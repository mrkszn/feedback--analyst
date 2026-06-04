import asyncio
from typing import Any, cast
from uuid import UUID

from supabase import Client

from core.storage.supabase_client import get_supabase


async def save_client_card(
    *,
    client_id: int,
    session_id: str | UUID,
    summary_text: str,
    pinecone_vector_id: str,
    db: Client | None = None,
) -> str:
    if not summary_text.strip():
        raise ValueError("summary_text must not be empty")
    if not pinecone_vector_id.strip():
        raise ValueError("pinecone_vector_id must not be empty")

    db = db or get_supabase()
    try:
        resp = await asyncio.to_thread(
            lambda: (
                db.table("client_cards")
                .insert(
                    {
                        "client_id": client_id,
                        "session_id": str(session_id),
                        "summary_text": summary_text,
                        "pinecone_vector_id": pinecone_vector_id,
                    }
                )
                .execute()
            )
        )
    except Exception as exc:
        if "23505" in str(exc):
            raise ValueError(f"client_card already exists for session {session_id}") from exc
        raise
    row = cast(dict[str, Any], resp.data[0])
    return str(row["id"])
