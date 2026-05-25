import asyncio
import hmac

from supabase import Client

from config import settings
from db.client import get_supabase


async def is_admin(telegram_id: int, *, db: Client | None = None) -> bool:
    db = db or get_supabase()
    resp = await asyncio.to_thread(
        lambda: (
            db.table("admin_users")
            .select("telegram_id")
            .eq("telegram_id", telegram_id)
            .limit(1)
            .execute()
        )
    )
    return bool(resp.data)


async def claim_admin(
    telegram_id: int,
    token: str,
    *,
    name: str | None = None,
    db: Client | None = None,
) -> bool:
    expected = settings.admin_bootstrap_token
    if not expected:
        return False
    if not hmac.compare_digest(token, expected):
        return False

    db = db or get_supabase()
    count_resp = await asyncio.to_thread(
        lambda: (
            db.table("admin_users")
            .select("telegram_id", count="exact")  # type: ignore[arg-type]
            .limit(1)
            .execute()
        )
    )
    if (count_resp.count or 0) > 0:
        return False

    try:
        await asyncio.to_thread(
            lambda: (
                db.table("admin_users").insert({"telegram_id": telegram_id, "name": name}).execute()
            )
        )
    except Exception as exc:
        # Race: another admin claimed between count and insert → unique violation.
        if "23505" in str(exc):
            return False
        raise
    return True
