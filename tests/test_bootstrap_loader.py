"""Tests for core.bootstrap.loader — config parsing, deep-merge, adapter wiring.

`load_client` must build an `AppContext` from a client dir WITHOUT touching env
secrets or connecting to storage (adapters lazy-connect later, in `run()`).

Template lookup is anchored at the real `REPO_ROOT/templates/`, so the happy
path uses the shipped `tg-restaurant` template; error paths build throwaway
client dirs under `tmp_path`. We do not mock yaml — real YAML round-trips.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from core.bootstrap.context import AppContext
from core.bootstrap.loader import (
    REPO_ROOT,
    build_storage,
    build_vector,
    deep_merge,
    load_client,
)

# --------------------------------------------------------------------------- #
# deep_merge — pure


def test_deep_merge_nested_dicts_merge() -> None:
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    override = {"nested": {"y": 20, "z": 30}}
    out = deep_merge(base, override)
    assert out == {"a": 1, "nested": {"x": 1, "y": 20, "z": 30}}


def test_deep_merge_scalar_and_list_replace() -> None:
    base = {"name": "old", "items": [1, 2, 3]}
    override = {"name": "new", "items": [9]}
    out = deep_merge(base, override)
    assert out["name"] == "new"
    assert out["items"] == [9]


def test_deep_merge_does_not_mutate_base() -> None:
    base = {"nested": {"x": 1}}
    override = {"nested": {"x": 2}}
    deep_merge(base, override)
    assert base["nested"]["x"] == 1


# --------------------------------------------------------------------------- #
# build_storage / build_vector — selection + fail-loud on unknown type


def test_build_storage_supabase_returns_factory() -> None:
    from core.storage.adapters.supabase import SupabaseStorage

    # Returns the adapter class as a zero-arg factory — construction is deferred
    # to run() so load_client stays secret-free. No live adapter built here.
    factory = build_storage({"primary": {"type": "supabase"}})
    assert factory is SupabaseStorage
    assert callable(factory)


def test_build_storage_unknown_type_raises() -> None:
    with pytest.raises(RuntimeError, match="Unknown storage type"):
        build_storage({"primary": {"type": "mysql"}})


def test_build_vector_pinecone_returns_factory() -> None:
    from core.storage.vector.pinecone import PineconeVectorStore

    factory = build_vector({"type": "pinecone"})
    assert factory is PineconeVectorStore
    assert callable(factory)


def test_build_vector_unknown_type_raises() -> None:
    with pytest.raises(RuntimeError, match="Unknown vector store type"):
        build_vector({"type": "weaviate"})


# --------------------------------------------------------------------------- #
# load_client — happy path against the shipped tg-restaurant template


def _write_client(dir_: Path, cfg: dict[str, Any]) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return dir_


def test_load_client_happy_path(tmp_path: Path) -> None:
    client_dir = _write_client(
        tmp_path / "acme",
        {"template": "tg-restaurant", "name": "Acme Diner"},
    )
    ctx = load_client(client_dir)

    assert isinstance(ctx, AppContext)
    assert ctx.client_dir == client_dir.resolve()
    assert ctx.template_dir.name == "tg-restaurant"
    # merged config carries template's channels + presentations
    assert [c["id"] for c in ctx.config["channels"]] == ["telegram_guest"]
    assert [p["id"] for p in ctx.config["presentations"]] == [
        "telegram_admin",
        "http_api",
    ]
    # Pre-run: factories recorded, live adapters NOT built (secret-free load).
    from core.storage.adapters.supabase import SupabaseStorage
    from core.storage.vector.pinecone import PineconeVectorStore

    assert ctx.storage is None
    assert ctx.vector is None
    assert ctx.storage_factory is SupabaseStorage
    assert ctx.vector_factory is PineconeVectorStore


def test_load_client_overrides_merge_onto_template(tmp_path: Path) -> None:
    client_dir = _write_client(
        tmp_path / "acme",
        {
            "template": "tg-restaurant",
            "name": "Acme Diner",
            "overrides": {"branding": {"bot_name": "Acme Bot"}},
        },
    )
    ctx = load_client(client_dir)
    # override key lands in merged config
    assert ctx.config["branding"]["bot_name"] == "Acme Bot"
    # template default still present alongside the override
    assert ctx.config["version"] == "1.0"


def test_load_client_is_secret_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression lock for the R3 blocker: load_client must NOT require storage
    secrets. With Supabase creds blanked (clean-checkout sim), loading the shipped
    `clients/_example` must return an AppContext without raising — adapters are
    only constructed later in run()."""
    from config import settings

    monkeypatch.setattr(settings, "supabase_url", "", raising=False)
    monkeypatch.setattr(settings, "supabase_service_role_key", "", raising=False)

    ctx = load_client(REPO_ROOT / "clients" / "_example")
    assert isinstance(ctx, AppContext)
    assert ctx.storage is None  # not built at load time
    assert callable(ctx.storage_factory)


def test_load_client_resolves_template_prompts(tmp_path: Path) -> None:
    client_dir = _write_client(
        tmp_path / "acme",
        {"template": "tg-restaurant"},
    )
    ctx = load_client(client_dir)
    prompts = ctx.config["prompts"]
    for key in ("dialogue", "analyze", "card"):
        rel = prompts[key]
        text = (ctx.template_dir / rel).read_text(encoding="utf-8")
        assert text.strip(), f"prompt {key} resolved to empty file"


# --------------------------------------------------------------------------- #
# load_client — error paths


def test_load_client_missing_config_raises(tmp_path: Path) -> None:
    empty_dir = tmp_path / "no_config"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        load_client(empty_dir)


def test_load_client_unknown_template_raises(tmp_path: Path) -> None:
    client_dir = _write_client(
        tmp_path / "acme",
        {"template": "does-not-exist-industry"},
    )
    with pytest.raises(FileNotFoundError):
        load_client(client_dir)
