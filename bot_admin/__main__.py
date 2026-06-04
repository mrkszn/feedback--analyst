"""Backward-compat entry point — see `bot_admin/__init__.py` for rationale."""

from presentations.telegram_admin.__main__ import main as _main

if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
