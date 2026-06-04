"""Bootstrap entry point — run one client instance.

    python -m core.bootstrap clients/_example

Reads the client config, resolves its template, builds storage + vector
adapters, and starts every configured channel and presentation concurrently.
This is the parallel single-command path; the legacy per-component entry points
(`python -m channels.telegram.guest_bot`, etc.) still work unchanged for dev.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from config import settings
from core.bootstrap.loader import load_client


def main() -> None:
    logging.basicConfig(level=settings.log_level)
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m core.bootstrap <client_dir>")

    client_dir = Path(sys.argv[1])
    ctx = load_client(client_dir)
    asyncio.run(ctx.run())


if __name__ == "__main__":
    main()
