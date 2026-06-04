"""Clients service — create-or-get over the clients table.

DI: `storage: StorageAdapter | None` (new) + `db: Client | None` (back-compat).
"""

from typing import Any, cast

from supabase import Client

from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


async def create_or_get_client(
    telegram_id: int,
    *,
    name: str | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> dict[str, Any]:
    store = _storage(storage, db)

    existing = await store.get_client(telegram_id)
    if existing is not None:
        return cast(dict[str, Any], existing)

    try:
        return cast(dict[str, Any], await store.insert_client(telegram_id=telegram_id, name=name))
    except Exception as exc:
        # Race: another insert happened first → fall back to select.
        if "23505" not in str(exc):
            raise
        retry = await store.get_client(telegram_id)
        return cast(dict[str, Any], retry)
