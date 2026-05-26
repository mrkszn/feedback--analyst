"""FastAPI dependency: extract & verify admin JWT from Authorization header."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from api.auth.jwt import verify_token
from config import settings
from services.admin_auth import is_admin


async def current_admin(authorization: str | None = Header(default=None)) -> int:
    """Verify `Authorization: Bearer <jwt>` and confirm the user is in admin_users.

    Returns telegram_id on success. Raises 401 on missing/invalid/expired token
    or if the user is no longer in admin_users (revoked).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = verify_token(token, settings.mini_app_session_secret)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    telegram_id = int(payload["telegram_id"])
    if not await is_admin(telegram_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not an admin",
        )
    return telegram_id
