"""Tests for presentations.http_api.auth.telegram_webapp.verify_login_widget
and parse_admin_ids (the Telegram Login Widget web-OAuth path)."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import pytest

from presentations.http_api.auth.telegram_webapp import (
    TelegramUser,
    parse_admin_ids,
    verify_login_widget,
)

BOT_TOKEN = "999:fake-admin-bot-token"


def _sign_widget(data: dict[str, Any], bot_token: str = BOT_TOKEN) -> dict[str, Any]:
    """Build a properly signed Login Widget payload from a dict (no `hash`)."""
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(bot_token.encode()).digest()
    h = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {**data, "hash": h}


def _now() -> int:
    return int(time.time())


# --------------------------------------------------------------------------- #
# verify_login_widget


def test_verify_widget_returns_user_for_valid_signature() -> None:
    payload = _sign_widget(
        {"id": 42, "first_name": "Alice", "username": "alice", "auth_date": _now()}
    )
    user = verify_login_widget(payload, BOT_TOKEN)
    assert isinstance(user, TelegramUser)
    assert user.id == 42
    assert user.username == "alice"
    assert user.first_name == "Alice"


def test_verify_widget_data_check_is_sorted_without_hash() -> None:
    # Sign in scrambled insertion order; verification must still pass because the
    # data-check string is sorted by key and excludes `hash`.
    payload = _sign_widget({"username": "z", "id": 1, "auth_date": _now(), "first_name": "A"})
    assert verify_login_widget(payload, BOT_TOKEN).id == 1


def test_verify_widget_rejects_bad_hash() -> None:
    payload = _sign_widget({"id": 42, "auth_date": _now()})
    payload["hash"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_login_widget(payload, BOT_TOKEN)


def test_verify_widget_rejects_wrong_bot_token() -> None:
    payload = _sign_widget({"id": 42, "auth_date": _now()}, BOT_TOKEN)
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_login_widget(payload, "different-token")


def test_verify_widget_rejects_expired_auth_date() -> None:
    payload = _sign_widget({"id": 42, "auth_date": _now() - 100_000})
    with pytest.raises(ValueError, match="auth_data_expired"):
        verify_login_widget(payload, BOT_TOKEN, max_age_seconds=3600)


def test_verify_widget_rejects_future_auth_date() -> None:
    payload = _sign_widget({"id": 42, "auth_date": _now() + 10_000})
    with pytest.raises(ValueError, match="future"):
        verify_login_widget(payload, BOT_TOKEN)


def test_verify_widget_missing_hash() -> None:
    with pytest.raises(ValueError, match="missing hash"):
        verify_login_widget({"id": 42, "auth_date": _now()}, BOT_TOKEN)


def test_verify_widget_missing_id() -> None:
    payload = _sign_widget({"auth_date": _now()})
    with pytest.raises(ValueError, match="missing id"):
        verify_login_widget(payload, BOT_TOKEN)


def test_verify_widget_empty_bot_token() -> None:
    with pytest.raises(ValueError, match="bot_token is empty"):
        verify_login_widget({"id": 1, "auth_date": _now(), "hash": "x"}, "")


def test_verify_widget_ignores_none_optional_fields() -> None:
    # The frontend may forward last_name=None; it must not be folded into the
    # data-check string (Telegram omits absent fields when signing).
    payload = _sign_widget({"id": 42, "first_name": "Alice", "auth_date": _now()})
    payload["last_name"] = None
    assert verify_login_widget(payload, BOT_TOKEN).id == 42


# --------------------------------------------------------------------------- #
# parse_admin_ids


def test_parse_admin_ids_basic() -> None:
    assert parse_admin_ids("123,456") == {123, 456}


def test_parse_admin_ids_trims_and_skips_blanks() -> None:
    assert parse_admin_ids(" 123 , , 456 ") == {123, 456}


def test_parse_admin_ids_skips_non_int() -> None:
    assert parse_admin_ids("123,abc,456") == {123, 456}


def test_parse_admin_ids_empty_is_empty_set() -> None:
    assert parse_admin_ids("") == set()
    assert parse_admin_ids("   ") == set()
