"""Backward-compat entry point — see `bot_guest/__init__.py` for rationale."""

from channels.telegram.guest_bot.__main__ import main as _main

if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
