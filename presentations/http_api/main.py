"""FastAPI app — admin Mini App backend (Phase 4A) + public guest webapp (Phase 5).

Factory pattern: `create_app()` reads `settings` at call time, so tests can
configure CORS origins via monkeypatch and then build a fresh app.

Both APIs share one uvicorn process and one port: admin lives under `/admin/*`
behind the admin JWT, guest lives under `/guest/*` behind its own JWT. CORS
allowlists are kept independent — a guest-webapp origin should not get blanket
access to admin endpoints.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from presentations.http_api.routes.admin import router as admin_router
from presentations.http_guest_api.routes.guest import router as guest_router


def _parse_origins(raw: str) -> list[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app() -> FastAPI:
    app = FastAPI(title="telegram-waiter API", version="0.1.0")

    cors_origins = sorted(
        set(
            _parse_origins(settings.allowed_mini_app_origins)
            + _parse_origins(settings.allowed_guest_origins)
        )
    )
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    app.include_router(admin_router)
    app.include_router(guest_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
