import asyncio
from typing import Any, cast
from uuid import UUID

from supabase import Client

from db.client import get_supabase


async def save_answer_with_metric(
    *,
    session_id: str | UUID,
    question_id: str | UUID,
    answer_text: str,
    marked_value: Any,
    db: Client | None = None,
) -> int:
    if not answer_text.strip():
        raise ValueError("answer_text must not be empty")

    db = db or get_supabase()
    resp = await asyncio.to_thread(
        lambda: (
            db.table("session_answers")
            .insert(
                {
                    "session_id": str(session_id),
                    "question_id": str(question_id),
                    "answer_text": answer_text,
                    "marked_value": marked_value,
                }
            )
            .execute()
        )
    )
    row = cast(dict[str, Any], resp.data[0])
    return int(row["id"])
