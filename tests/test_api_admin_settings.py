"""HTTP tests for GET/PUT /admin/settings."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from config import settings
from presentations.http_api.auth.jwt import issue_token
from presentations.http_api.main import create_app

SECRET = "test-jwt-secret-32-bytes-or-more-aaaa"


@pytest.fixture(autouse=True)
def _patched_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "mini_app_session_secret", SECRET)
    monkeypatch.setattr(settings, "allowed_mini_app_origins", "https://miniapp.test")
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _admin_token(telegram_id: int = 7) -> str:
    return issue_token(telegram_id, SECRET)


# --------------------------------------------------------------------------- #
# auth


def test_settings_requires_authorization(client: TestClient) -> None:
    resp = client.get("/admin/settings")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


# --------------------------------------------------------------------------- #
# GET /admin/settings


def test_get_settings_returns_effective(client: TestClient) -> None:
    token = _admin_token(7)
    fake = {"theme": "dark", "language": "en", "notifications_enabled": False}
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin.get_admin_settings", return_value=fake) as m,
    ):
        resp = client.get("/admin/settings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == fake
    # Scoped to the authenticated admin (telegram_id from the JWT).
    assert m.call_args.args[0] == 7


# --------------------------------------------------------------------------- #
# PUT /admin/settings


def test_put_settings_updates(client: TestClient) -> None:
    token = _admin_token(7)
    fake = {"theme": "dark", "language": "ru", "notifications_enabled": True}
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin.update_admin_settings", return_value=fake) as m,
    ):
        resp = client.put(
            "/admin/settings",
            json={"theme": "dark"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["theme"] == "dark"
    _, kwargs = m.call_args
    assert kwargs["theme"] == "dark"
    assert kwargs["language"] is None  # not supplied → no change


def test_put_settings_rejects_invalid_value(client: TestClient) -> None:
    token = _admin_token(7)
    with patch("presentations.http_api.deps.auth.is_admin", return_value=True):
        resp = client.put(
            "/admin/settings",
            json={"theme": "neon"},
            headers={"Authorization": f"Bearer {token}"},
        )
    # pydantic Literal rejects the value before the route body runs.
    assert resp.status_code == 422


def test_put_settings_maps_value_error_to_400(client: TestClient) -> None:
    token = _admin_token(7)
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch(
            "presentations.http_api.routes.admin.update_admin_settings",
            side_effect=ValueError("invalid theme 'x'"),
        ),
    ):
        resp = client.put(
            "/admin/settings",
            json={"theme": "dark"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400
    assert "invalid theme" in resp.json()["detail"]


# --------------------------------------------------------------------------- #
# CORS


def test_settings_cors_preflight_allows_put(client: TestClient) -> None:
    resp = client.options(
        "/admin/settings",
        headers={
            "Origin": "https://miniapp.test",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://miniapp.test"
