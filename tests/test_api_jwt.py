"""Tests for api.auth.jwt issue_token / verify_token."""

from __future__ import annotations

import time

import jwt as pyjwt
import pytest

from api.auth.jwt import issue_token, verify_token

SECRET = "test-secret-very-long-and-random-32-bytes-min"


def test_issue_then_verify_roundtrip() -> None:
    token = issue_token(12345, SECRET)
    payload = verify_token(token, SECRET)
    assert payload["telegram_id"] == 12345
    assert payload["sub"] == "12345"
    assert payload["exp"] > payload["iat"]


def test_verify_rejects_wrong_secret() -> None:
    token = issue_token(1, SECRET)
    with pytest.raises(ValueError, match="invalid token"):
        verify_token(token, "different-secret")


def test_verify_rejects_expired_token() -> None:
    token = issue_token(1, SECRET, ttl_seconds=-10)
    with pytest.raises(ValueError, match="expired"):
        verify_token(token, SECRET)


def test_verify_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="invalid token"):
        verify_token("not.a.jwt", SECRET)


def test_verify_rejects_empty_token() -> None:
    with pytest.raises(ValueError, match="token is empty"):
        verify_token("", SECRET)


def test_issue_fails_loud_on_empty_secret() -> None:
    with pytest.raises(RuntimeError, match="MINI_APP_SESSION_SECRET is empty"):
        issue_token(1, "")


def test_verify_fails_loud_on_empty_secret() -> None:
    token = issue_token(1, SECRET)
    with pytest.raises(RuntimeError, match="MINI_APP_SESSION_SECRET is empty"):
        verify_token(token, "")


def test_verify_rejects_token_missing_telegram_id_claim() -> None:
    # craft a token with the same secret but without our claim
    token = pyjwt.encode({"sub": "1", "exp": int(time.time()) + 60}, SECRET, algorithm="HS256")
    with pytest.raises(ValueError, match="missing telegram_id"):
        verify_token(token, SECRET)
