"""Client loader — turns a `clients/<name>/` directory into an `AppContext`.

Flow:
1. Read `clients/<name>/config.yaml`; it names a `template`.
2. Read `templates/<template>/config.yaml` (the industry default).
3. Deep-merge the client's `overrides` on top of the template config.
4. Build the storage + vector adapters from the merged `storage` section.
5. Return an `AppContext` ready to `run()`.

Adapters read their own credentials from env via `config.settings`; the config
file only selects *which* adapter (`type:`) and documents the env var names, it
never holds secrets.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from core.bootstrap.context import AppContext
from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter
from core.storage.vector.pinecone import PineconeVectorStore
from core.storage.vector.protocol import VectorStore

REPO_ROOT = Path(__file__).resolve().parents[2]


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `override` onto a copy of `base`; dicts merge, scalars/lists replace."""
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def build_storage(storage_cfg: dict[str, Any]) -> Callable[[], StorageAdapter]:
    """Validate the storage `type` at load time; return a factory that builds the
    live adapter on first `run()`. Construction is deferred because adapters read
    secrets (`SUPABASE_URL`/key) from env — `load_client` must stay secret-free."""
    kind = storage_cfg["primary"]["type"]
    if kind == "supabase":
        return SupabaseStorage
    raise RuntimeError(f"Unknown storage type: {kind!r}")


def build_vector(vector_cfg: dict[str, Any]) -> Callable[[], VectorStore]:
    """Validate the vector-store `type` at load time; defer construction to `run()`."""
    kind = vector_cfg["type"]
    if kind == "pinecone":
        return PineconeVectorStore
    raise RuntimeError(f"Unknown vector store type: {kind!r}")


def load_client(client_dir: Path) -> AppContext:
    client_dir = client_dir.resolve()
    client_cfg = yaml.safe_load((client_dir / "config.yaml").read_text(encoding="utf-8"))

    template_name = client_cfg["template"]
    template_dir = REPO_ROOT / "templates" / template_name
    template_cfg = yaml.safe_load((template_dir / "config.yaml").read_text(encoding="utf-8"))

    merged = deep_merge(template_cfg, client_cfg.get("overrides", {}))

    # Type-validated at load (fail-loud on unknown type); adapters are NOT
    # constructed here — that would require secrets. `run()` calls the factories.
    storage_factory = build_storage(merged["storage"])
    vector_factory = build_vector(merged["storage"]["vector"])

    return AppContext(
        storage_factory=storage_factory,
        vector_factory=vector_factory,
        template_dir=template_dir,
        client_dir=client_dir,
        config=merged,
    )
