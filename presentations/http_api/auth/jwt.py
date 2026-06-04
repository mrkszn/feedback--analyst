"""Thin JWT issue/verify wrapper around PyJWT.

Fail-loud: пустой секрет → RuntimeError. Подделка / истёкший токен → ValueError.
"""

from __future__ import annotations

import time
from typing import Any

import jwt

_ALG = "HS256"


def _require_secret(secret: str) -> None:
    if not secret:
        raise RuntimeError(
            "MINI_APP_SESSION_SECRET is empty — refusing to issue/verify JWT. "
            "Set MINI_APP_SESSION_SECRET in your environment."
        )


def issue_token(
    telegram_id: int,
    secret: str,
    *,
    ttl_seconds: int = 86400,
) -> str:
    _require_secret(secret)
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(telegram_id),
        "telegram_id": telegram_id,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(payload, secret, algorithm=_ALG)


def verify_token(token: str, secret: str) -> dict[str, Any]:
    _require_secret(secret)
    if not token:
        raise ValueError("token is empty")
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALG])
    except jwt.ExpiredSignatureError as exc:
        raise ValueError(f"token expired: {exc}") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"invalid token: {exc}") from exc
    if "telegram_id" not in payload:
        raise ValueError("token missing telegram_id claim")
    return payload
