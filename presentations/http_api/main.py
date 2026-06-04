"""FastAPI app — admin Mini App backend (Phase 4A).

Factory pattern: `create_app()` reads `settings` at call time, so tests can
configure CORS origins via monkeypatch and then build a fresh app.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from presentations.http_api.routes.admin import router as admin_router


def create_app() -> FastAPI:
    app = FastAPI(title="telegram-waiter API", version="0.1.0")

    origins = [o.strip() for o in settings.allowed_mini_app_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    app.include_router(admin_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
