"""Admin settings service — per-admin Mini App preferences.

Theme / language / notifications for the admin Mini App. One row per admin in
`admin_settings`; a missing row means "all defaults" — the service never forces
a write on read. Mirrors `core/services/clients.py`: every public function takes
`storage`/`db` for testability and depends on the StorageAdapter Protocol.
"""

from __future__ import annotations

from typing import Any

from supabase import Client

from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter

VALID_THEMES = ("light", "dark", "system")
VALID_LANGUAGES = ("uk", "en")

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "system",
    "language": "uk",
    "notifications_enabled": True,
}


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


def _with_defaults(row: dict[str, Any] | None) -> dict[str, Any]:
    """Project a stored row (or None) onto the canonical settings shape."""
    merged = dict(DEFAULT_SETTINGS)
    if row:
        for key in DEFAULT_SETTINGS:
            if row.get(key) is not None:
                merged[key] = row[key]
    return merged


async def get_admin_settings(
    telegram_id: int,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> dict[str, Any]:
    """Effective settings for an admin: stored row merged over defaults."""
    store = _storage(storage, db)
    row = await store.get_admin_settings(telegram_id)
    return _with_defaults(row)


async def update_admin_settings(
    telegram_id: int,
    *,
    theme: str | None = None,
    language: str | None = None,
    notifications_enabled: bool | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> dict[str, Any]:
    """Patch the provided fields (others untouched) and return effective settings.

    Raises ValueError for an out-of-range theme/language. An empty patch is a
    no-op read — it does not touch storage.
    """
    patch: dict[str, Any] = {}
    if theme is not None:
        if theme not in VALID_THEMES:
            raise ValueError(f"invalid theme {theme!r}; expected one of {VALID_THEMES}")
        patch["theme"] = theme
    if language is not None:
        if language not in VALID_LANGUAGES:
            raise ValueError(f"invalid language {language!r}; expected one of {VALID_LANGUAGES}")
        patch["language"] = language
    if notifications_enabled is not None:
        patch["notifications_enabled"] = notifications_enabled

    if not patch:
        return await get_admin_settings(telegram_id, storage=storage, db=db)

    store = _storage(storage, db)
    row = await store.upsert_admin_settings(telegram_id=telegram_id, patch=patch)
    return _with_defaults(row)
