"""HTTP tests for GET/PUT /admin/prizes — in-app gamification prize config."""

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


def test_prizes_requires_authorization(client: TestClient) -> None:
    assert client.get("/admin/prizes").status_code == 401


def test_get_prizes_returns_list(client: TestClient) -> None:
    token = _admin_token()
    fake = [
        {"tier": "small", "code": "S10", "label_uk": "Бонус", "label_en": "Bonus"},
        {"tier": "large", "code": "BIG", "label_uk": "Гранд", "label_en": "Grand"},
    ]
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin.get_prize_tiers", return_value=fake),
    ):
        resp = client.get("/admin/prizes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert [p["tier"] for p in body["prizes"]] == ["small", "large"]
    assert body["prizes"][0]["code"] == "S10"


def test_put_prize_updates_tier(client: TestClient) -> None:
    token = _admin_token()
    fake = {"tier": "medium", "code": "SAVE20", "label_uk": "Приз", "label_en": "Prize"}
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin.set_prize_tier_config", return_value=fake) as m,
    ):
        resp = client.put(
            "/admin/prizes/medium",
            json={"code": "SAVE20"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["code"] == "SAVE20"
    args, kwargs = m.call_args
    assert args[0] == "medium"
    assert kwargs["code"] == "SAVE20"
    assert kwargs["label_uk"] is None  # not supplied → unchanged


def test_put_prize_unknown_tier_maps_to_400(client: TestClient) -> None:
    token = _admin_token()
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch(
            "presentations.http_api.routes.admin.set_prize_tier_config",
            side_effect=ValueError("unknown tier 'huge'"),
        ),
    ):
        resp = client.put(
            "/admin/prizes/huge",
            json={"code": "X"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400
    assert "unknown tier" in resp.json()["detail"]
