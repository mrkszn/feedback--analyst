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
from collections.abc import Mapping
from typing import Any
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


def verify_login_widget(
    payload: Mapping[str, Any],
    bot_token: str,
    *,
    max_age_seconds: int = 86400,
) -> TelegramUser:
    """Validate a Telegram Login Widget callback payload (web OAuth on a plain
    browser), per https://core.telegram.org/widgets/login#checking-authorization

    Differs from Mini App initData in two ways: the payload is a JSON object (not
    a query string), and `secret_key = SHA256(bot_token)` raw bytes (initData
    instead uses HMAC(key="WebAppData", msg=bot_token)). The data-check string is
    every field except `hash`, sorted by key, joined `key=value` with `\\n` —
    only the fields that were actually sent (no None placeholders).

    Raises ValueError on missing/bad hash, expired/future auth_date, or missing
    id. Returns the parsed TelegramUser on success.
    """
    if not bot_token:
        raise ValueError("bot_token is empty")

    data = {k: v for k, v in payload.items() if v is not None}
    received_hash = data.pop("hash", None)
    if not received_hash or not isinstance(received_hash, str):
        raise ValueError("widget payload missing hash")

    data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    computed = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        raise ValueError("widget hash mismatch")

    auth_date_raw = data.get("auth_date")
    if auth_date_raw is None:
        raise ValueError("widget payload missing auth_date")
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"auth_date not int: {auth_date_raw!r}") from exc
    age = int(time.time()) - auth_date
    if age > max_age_seconds:
        raise ValueError("auth_data_expired")
    if age < -300:
        # >5 min in the future is suspicious (small clock-skew window allowed)
        raise ValueError("auth_date is in the future")

    if "id" not in data:
        raise ValueError("widget payload missing id")
    return TelegramUser.model_validate(data)


def parse_admin_ids(raw: str) -> set[int]:
    """Parse the ADMIN_TELEGRAM_IDS CSV env into a set of ints. Empty/blank →
    empty set (nobody may web-login). Non-int tokens are skipped."""
    out: set[int] = set()
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.add(int(tok))
        except ValueError:
            continue
    return out
