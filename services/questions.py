import asyncio
from typing import Any, Literal, TypedDict, cast
from uuid import UUID

from supabase import Client

from db.client import get_supabase

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
) -> QuestionRow:
    if not text.strip():
        raise ValueError("text must not be empty")
    if not metric_key.strip():
        raise ValueError("metric_key must not be empty")
    if expected_type == "enum" and not enum_values:
        raise ValueError("enum question requires non-empty enum_values")

    db = db or get_supabase()
    payload: dict[str, Any] = {
        "text": text,
        "metric_key": metric_key,
        "expected_type": expected_type,
        "enum_values": enum_values,
        "created_by": created_by,
    }
    try:
        resp = await asyncio.to_thread(lambda: db.table("questions").insert(payload).execute())
    except Exception as exc:
        if "23505" in str(exc):
            raise ValueError(f"metric_key {metric_key!r} already exists") from exc
        raise
    return cast(QuestionRow, resp.data[0])


async def update_question(
    question_id: str | UUID,
    *,
    text: str | None = None,
    enum_values: list[str] | None = None,
    is_active: bool | None = None,
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

    db = db or get_supabase()
    resp = await asyncio.to_thread(
        lambda: db.table("questions").update(patch).eq("id", str(question_id)).execute()
    )
    if not resp.data:
        raise LookupError(f"question {question_id} not found")
    return cast(QuestionRow, resp.data[0])


async def delete_question(
    question_id: str | UUID,
    *,
    db: Client | None = None,
) -> None:
    db = db or get_supabase()
    resp = await asyncio.to_thread(
        lambda: (
            db.table("questions").update({"is_active": False}).eq("id", str(question_id)).execute()
        )
    )
    if not resp.data:
        raise LookupError(f"question {question_id} not found")


async def list_questions(
    *,
    active_only: bool = False,
    db: Client | None = None,
) -> list[QuestionRow]:
    db = db or get_supabase()

    def _q() -> Any:
        q = db.table("questions").select("*")
        if active_only:
            q = q.eq("is_active", True)
        return q.order("created_at", desc=True).execute()

    resp = await asyncio.to_thread(_q)
    return list(resp.data or [])
