"""Tests for api.auth.telegram_webapp.validate_initdata."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from presentations.http_api.auth.telegram_webapp import TelegramUser, validate_initdata

BOT_TOKEN = "1234567890:ABCDEF-fake-token-for-test"


def _sign(payload: dict[str, str], bot_token: str = BOT_TOKEN) -> str:
    """Build a properly signed initData string from a dict (no `hash` key)."""
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**payload, "hash": h})


def _user_field(telegram_id: int = 42, username: str = "alice") -> str:
    return json.dumps(
        {"id": telegram_id, "username": username, "first_name": "Alice"},
        separators=(",", ":"),
    )


def test_validate_initdata_returns_user_for_valid_signature() -> None:
    payload = {
        "auth_date": str(int(time.time())),
        "user": _user_field(42, "alice"),
        "query_id": "AAH-test",
    }
    init_data = _sign(payload)
    user = validate_initdata(init_data, BOT_TOKEN)
    assert isinstance(user, TelegramUser)
    assert user.id == 42
    assert user.username == "alice"
    assert user.first_name == "Alice"


def test_validate_initdata_rejects_bad_hash() -> None:
    payload = {
        "auth_date": str(int(time.time())),
        "user": _user_field(),
    }
    init_data = _sign(payload)
    # corrupt the hash
    bad = init_data.replace("hash=", "hash=0000")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_initdata(bad, BOT_TOKEN)


def test_validate_initdata_rejects_wrong_bot_token() -> None:
    payload = {
        "auth_date": str(int(time.time())),
        "user": _user_field(),
    }
    init_data = _sign(payload, BOT_TOKEN)
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_initdata(init_data, "different-token")


def test_validate_initdata_rejects_old_auth_date() -> None:
    payload = {
        "auth_date": str(int(time.time()) - 100_000),
        "user": _user_field(),
    }
    init_data = _sign(payload)
    with pytest.raises(ValueError, match="too old"):
        validate_initdata(init_data, BOT_TOKEN, max_age_seconds=3600)


def test_validate_initdata_rejects_future_auth_date() -> None:
    payload = {
        "auth_date": str(int(time.time()) + 10_000),
        "user": _user_field(),
    }
    init_data = _sign(payload)
    with pytest.raises(ValueError, match="future"):
        validate_initdata(init_data, BOT_TOKEN)


def test_validate_initdata_missing_hash() -> None:
    init_data = urlencode({"auth_date": str(int(time.time())), "user": _user_field()})
    with pytest.raises(ValueError, match="missing hash"):
        validate_initdata(init_data, BOT_TOKEN)


def test_validate_initdata_missing_user() -> None:
    payload = {"auth_date": str(int(time.time()))}
    init_data = _sign(payload)
    with pytest.raises(ValueError, match="missing user"):
        validate_initdata(init_data, BOT_TOKEN)


def test_validate_initdata_empty_inputs() -> None:
    with pytest.raises(ValueError, match="init_data is empty"):
        validate_initdata("", BOT_TOKEN)
    with pytest.raises(ValueError, match="bot_token is empty"):
        validate_initdata("auth_date=1&hash=x", "")
