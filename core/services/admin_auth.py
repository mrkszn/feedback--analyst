"""Admin auth service — whitelist checks + bootstrap/invite over admin_users.

DI: `storage: StorageAdapter | None` (new) + `db: Client | None` (back-compat).
"""

import hmac

from supabase import Client

from config import settings
from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


async def is_admin(
    telegram_id: int,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> bool:
    store = _storage(storage, db)
    return await store.is_admin(telegram_id)


async def claim_admin(
    telegram_id: int,
    token: str,
    *,
    name: str | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> bool:
    expected = settings.admin_bootstrap_token
    if not expected:
        return False
    if not hmac.compare_digest(token, expected):
        return False

    store = _storage(storage, db)
    if await store.count_admins() > 0:
        return False

    try:
        await store.insert_admin(telegram_id=telegram_id, name=name)
    except Exception as exc:
        # Race: another admin claimed between count and insert → unique violation.
        if "23505" in str(exc):
            return False
        raise
    return True


async def add_admin(
    telegram_id: int,
    *,
    invited_by: int | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> None:
    """Insert an admin (used by /invite_admin). Raises ValueError if already an
    admin (Postgres unique violation 23505), so the caller can reply nicely.
    """
    store = _storage(storage, db)
    try:
        await store.insert_admin(telegram_id=telegram_id, invited_by=invited_by)
    except Exception as exc:
        if "23505" in str(exc):
            raise ValueError(f"telegram_id {telegram_id} is already an admin") from exc
        raise
