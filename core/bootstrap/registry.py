"""Registry — maps a config component `id` to the coroutine that runs it.

Each runner reuses the existing per-component startup logic (the legacy
`__main__.main()` for the two bots, a programmatic `uvicorn.Server` for the
HTTP API) so the bootstrap path shares one code path with dev and adds no
duplicated router/dispatcher wiring.

To add a new channel/presentation: implement its runner here and register the
`id` in `_CHANNELS` / `_PRESENTATIONS`. The config's `id` is the contract.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.bootstrap.context import AppContext

Runner = Callable[["AppContext", dict[str, Any]], Awaitable[None]]


async def _run_telegram_guest(ctx: AppContext, spec: dict[str, Any]) -> None:
    from channels.telegram.guest_bot.__main__ import main

    await main()


async def _run_telegram_admin(ctx: AppContext, spec: dict[str, Any]) -> None:
    from presentations.telegram_admin.__main__ import main

    await main()


async def _run_http_api(ctx: AppContext, spec: dict[str, Any]) -> None:
    import os

    import uvicorn

    from presentations.http_api.main import create_app

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get(spec.get("port_env", "API_PORT"), "8000"))
    server = uvicorn.Server(uvicorn.Config(create_app(), host=host, port=port, reload=False))
    await server.serve()


_CHANNELS: dict[str, Runner] = {
    "telegram_guest": _run_telegram_guest,
}

_PRESENTATIONS: dict[str, Runner] = {
    "telegram_admin": _run_telegram_admin,
    "http_api": _run_http_api,
}


def resolve_runner(
    kind: str, component_id: str, ctx: AppContext, spec: dict[str, Any]
) -> Awaitable[None]:
    table = _CHANNELS if kind == "channel" else _PRESENTATIONS
    runner = table.get(component_id)
    if runner is None:
        raise RuntimeError(f"Unknown {kind} id: {component_id!r}")
    return runner(ctx, spec)
