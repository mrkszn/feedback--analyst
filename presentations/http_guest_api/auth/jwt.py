"""JWT issue/verify for the public guest webapp.

Separate secret from the admin JWT (`MINI_APP_SESSION_SECRET`): a different
trust domain. The token's `sub` is the session_id, so the deps layer can match
the URL path against the token in one cheap check.

Fail-loud: empty secret → RuntimeError. Forged / expired token → ValueError.
"""

from __future__ import annotations

import time
from typing import Any

import jwt

_ALG = "HS256"


def _require_secret(secret: str) -> None:
    if not secret:
        raise RuntimeError(
            "GUEST_SESSION_SECRET is empty — refusing to issue/verify JWT. "
            "Set GUEST_SESSION_SECRET in your environment."
        )


def issue_session_token(
    session_id: str,
    secret: str,
    *,
    ttl_seconds: int = 86400 * 7,
) -> str:
    _require_secret(secret)
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": session_id,
        "session_id": session_id,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(payload, secret, algorithm=_ALG)


def verify_session_token(token: str, secret: str) -> dict[str, Any]:
    _require_secret(secret)
    if not token:
        raise ValueError("token is empty")
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALG])
    except jwt.ExpiredSignatureError as exc:
        raise ValueError(f"token expired: {exc}") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"invalid token: {exc}") from exc
    if "session_id" not in payload:
        raise ValueError("token missing session_id claim")
    return payload
