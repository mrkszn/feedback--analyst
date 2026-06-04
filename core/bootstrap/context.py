"""AppContext — the assembled runtime for one client instance.

`load_client` (see `loader.py`) parses the merged template+client config and
produces an `AppContext`. Calling `run()` starts every channel and presentation
declared in the config concurrently. The bootstrap path is *parallel* to the
legacy per-component entry points (`channels/.../__main__.py` etc.) which keep
working unchanged for dev; this is the single-command "run one client" path.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.storage.protocol import StorageAdapter
from core.storage.vector.protocol import VectorStore


@dataclass
class AppContext:
    # Factories, not live adapters: construction reads secrets from env and must
    # NOT happen at load time (`load_client` stays secret-free). `run()` calls
    # these once, where env is expected to be populated.
    storage_factory: Callable[[], StorageAdapter]
    vector_factory: Callable[[], VectorStore]
    template_dir: Path
    client_dir: Path
    config: dict[str, Any]
    storage: StorageAdapter | None = field(default=None, init=False)
    vector: VectorStore | None = field(default=None, init=False)

    async def run(self) -> None:
        """Start every configured channel and presentation concurrently.

        Builds the live storage/vector adapters first (here, not at load, because
        their constructors need env secrets), then resolves each configured
        channel/presentation to a long-running coroutine via the registry; they
        all run under a single `asyncio.gather`, so the process stays alive until
        one of them exits or raises.
        """
        from core.bootstrap.registry import resolve_runner

        self.storage = self.storage_factory()
        self.vector = self.vector_factory()

        runners = []
        for spec in self.config.get("channels", []):
            runners.append(resolve_runner("channel", spec["id"], self, spec))
        for spec in self.config.get("presentations", []):
            runners.append(resolve_runner("presentation", spec["id"], self, spec))

        if not runners:
            raise RuntimeError("No channels or presentations configured for this client")

        await asyncio.gather(*runners)
