"""FastAPI dependency: extract the guest session_id from the Authorization
header. Route handlers compare it against the URL path's session_id to
enforce ownership (the dep returns just the token-bound id)."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from config import settings
from presentations.http_guest_api.auth.jwt import verify_session_token


async def current_guest_session(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = verify_session_token(token, settings.guest_session_secret)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return str(payload["session_id"])
