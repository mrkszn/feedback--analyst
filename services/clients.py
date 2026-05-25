import asyncio
from typing import Any, cast

from supabase import Client

from db.client import get_supabase


async def create_or_get_client(
    telegram_id: int,
    *,
    name: str | None = None,
    db: Client | None = None,
) -> dict[str, Any]:
    db = db or get_supabase()

    existing = await asyncio.to_thread(
        lambda: db.table("clients").select("*").eq("telegram_id", telegram_id).limit(1).execute()
    )
    if existing.data:
        return cast(dict[str, Any], existing.data[0])

    try:
        inserted = await asyncio.to_thread(
            lambda: db.table("clients").insert({"telegram_id": telegram_id, "name": name}).execute()
        )
        return cast(dict[str, Any], inserted.data[0])
    except Exception as exc:
        # Race: another insert happened first → fall back to select.
        if "23505" not in str(exc):
            raise
        retry = await asyncio.to_thread(
            lambda: (
                db.table("clients").select("*").eq("telegram_id", telegram_id).limit(1).execute()
            )
        )
        return cast(dict[str, Any], retry.data[0])
