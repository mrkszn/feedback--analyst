"""Validate Telegram Mini App initData per
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

Schema: каждый ключ=значение в initData (порядок при подписи — сортировка по
ключу), исключая `hash`, склеивается через `\n`. Секрет для HMAC =
HMAC_SHA256(key="WebAppData", msg=bot_token).hex_digest равен на hmac
key для второго прохода HMAC_SHA256(secret, data_check_string).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from pydantic import BaseModel


class TelegramUser(BaseModel):
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    is_premium: bool | None = None
    photo_url: str | None = None


def _data_check_string(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"{k}={v}" for k, v in sorted(pairs, key=lambda p: p[0]))


def validate_initdata(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86400,
) -> TelegramUser:
    """Validate the raw initData query string from Telegram.WebApp.

    Raises ValueError if signature is bad, hash is missing, auth_date is too
    old, or the user field can't be parsed. Returns parsed TelegramUser on
    success.
    """
    if not init_data:
        raise ValueError("init_data is empty")
    if not bot_token:
        raise ValueError("bot_token is empty")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    payload = dict(pairs)
    received_hash = payload.pop("hash", None)
    if not received_hash:
        raise ValueError("init_data missing hash")

    data_check_pairs = [(k, v) for k, v in pairs if k != "hash"]
    data_check_string = _data_check_string(data_check_pairs)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        raise ValueError("init_data hash mismatch")

    auth_date_raw = payload.get("auth_date")
    if not auth_date_raw:
        raise ValueError("init_data missing auth_date")
    try:
        auth_date = int(auth_date_raw)
    except ValueError as exc:
        raise ValueError(f"auth_date not int: {auth_date_raw!r}") from exc
    age = int(time.time()) - auth_date
    if age > max_age_seconds:
        raise ValueError(f"init_data is too old ({age}s > {max_age_seconds}s)")
    if age < -300:
        # small clock-skew window; >5 min in the future is suspicious
        raise ValueError(f"init_data auth_date is in the future ({-age}s)")

    user_raw = payload.get("user")
    if not user_raw:
        raise ValueError("init_data missing user field")
    try:
        user_dict = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"init_data user is not JSON: {exc}") from exc
    if not isinstance(user_dict, dict) or "id" not in user_dict:
        raise ValueError("init_data user missing id")

    return TelegramUser.model_validate(user_dict)
