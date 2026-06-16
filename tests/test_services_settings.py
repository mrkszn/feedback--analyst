"""Unit tests for the admin settings service (backed by InMemoryStorage)."""

from __future__ import annotations

import pytest

from core.services.settings import (
    DEFAULT_SETTINGS,
    get_admin_settings,
    update_admin_settings,
)
from core.storage.adapters.in_memory import InMemoryStorage


def _mem() -> InMemoryStorage:
    return InMemoryStorage()


async def test_get_returns_defaults_when_no_row() -> None:
    mem = _mem()
    result = await get_admin_settings(7, storage=mem)
    assert result == DEFAULT_SETTINGS
    # Reading must not create a row.
    assert mem.admin_settings == []


async def test_update_persists_and_returns_effective() -> None:
    mem = _mem()
    result = await update_admin_settings(7, theme="dark", storage=mem)
    assert result["theme"] == "dark"
    # Untouched fields fall back to defaults.
    assert result["language"] == DEFAULT_SETTINGS["language"]
    assert result["notifications_enabled"] is True

    # And the change is durable.
    again = await get_admin_settings(7, storage=mem)
    assert again["theme"] == "dark"


async def test_update_partial_leaves_other_fields() -> None:
    mem = _mem()
    await update_admin_settings(7, theme="dark", storage=mem)
    result = await update_admin_settings(7, language="en", storage=mem)
    assert result["theme"] == "dark"  # preserved from the earlier patch
    assert result["language"] == "en"


async def test_update_notifications_toggle() -> None:
    mem = _mem()
    result = await update_admin_settings(7, notifications_enabled=False, storage=mem)
    assert result["notifications_enabled"] is False


async def test_update_rejects_invalid_theme() -> None:
    mem = _mem()
    with pytest.raises(ValueError, match="invalid theme"):
        await update_admin_settings(7, theme="neon", storage=mem)
    assert mem.admin_settings == []


async def test_update_rejects_invalid_language() -> None:
    mem = _mem()
    with pytest.raises(ValueError, match="invalid language"):
        await update_admin_settings(7, language="fr", storage=mem)
    assert mem.admin_settings == []


async def test_empty_update_is_noop_read() -> None:
    mem = _mem()
    result = await update_admin_settings(7, storage=mem)
    assert result == DEFAULT_SETTINGS
    assert mem.admin_settings == []  # no write on an empty patch
