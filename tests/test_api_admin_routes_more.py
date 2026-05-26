"""HTTP tests for /admin/semantic, /admin/clients/{id}, /admin/ask."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth.jwt import issue_token
from api.main import create_app
from config import settings

SECRET = "test-jwt-secret-32-bytes-or-more-aaaa"


@pytest.fixture(autouse=True)
def _patched_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "mini_app_session_secret", SECRET)
    monkeypatch.setattr(settings, "allowed_mini_app_origins", "")
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _token(telegram_id: int = 7) -> str:
    return issue_token(telegram_id, SECRET)


# --------------------------------------------------------------------------- #
# /admin/semantic


def test_semantic_returns_hits(client: TestClient) -> None:
    token = _token()
    fake_hits = [
        {
            "session_id": "abc-1",
            "client_id": 42,
            "score": 0.91,
            "summary_text": "Гость хвалил пасту",
            "sentiment": "positive",
            "started_at": "2026-01-15T12:00:00+00:00",
        },
    ]
    with (
        patch("api.deps.auth.is_admin", return_value=True),
        patch("api.routes.admin.semantic_search", return_value=fake_hits) as m,
    ):
        resp = client.post(
            "/admin/semantic",
            json={"query": "паста", "top_k": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["hits"][0]["session_id"] == "abc-1"
    assert body["hits"][0]["score"] == 0.91
    args, kwargs = m.call_args
    assert args[0] == "паста" and kwargs["top_k"] == 5


def test_semantic_requires_auth(client: TestClient) -> None:
    resp = client.post("/admin/semantic", json={"query": "x"})
    assert resp.status_code == 401


def test_semantic_rejects_invalid_top_k(client: TestClient) -> None:
    token = _token()
    with patch("api.deps.auth.is_admin", return_value=True):
        resp = client.post(
            "/admin/semantic",
            json={"query": "x", "top_k": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# /admin/clients/{telegram_id}


def test_client_profile_returns_profile(client: TestClient) -> None:
    token = _token()
    fake = {
        "telegram_id": 99,
        "name": "Alice",
        "sessions_count": 4,
        "last_session_at": "2026-01-20T18:00:00+00:00",
        "avg_sentiment": 0.5,
        "recent_cards": [{"summary_text": "Хорошее обслуживание"}],
        "top_topics": [{"topic": "service", "count": 3, "avg_sentiment": 1.0}],
    }
    with (
        patch("api.deps.auth.is_admin", return_value=True),
        patch("api.routes.admin.client_profile", return_value=fake),
    ):
        resp = client.get(
            "/admin/clients/99",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["telegram_id"] == 99
    assert body["name"] == "Alice"
    assert body["top_topics"][0]["topic"] == "service"


def test_client_profile_returns_404_on_lookup_error(client: TestClient) -> None:
    token = _token()
    with (
        patch("api.deps.auth.is_admin", return_value=True),
        patch("api.routes.admin.client_profile", side_effect=LookupError("client 1 not found")),
    ):
        resp = client.get(
            "/admin/clients/1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


# --------------------------------------------------------------------------- #
# /admin/ask


def test_ask_returns_answer(client: TestClient) -> None:
    token = _token()
    fake_answer = SimpleNamespace(
        answer_text="За неделю поступило 3 жалобы на ожидание.",
        tools_used=["topic_histogram_tool"],
        chart_text=None,
    )
    with (
        patch("api.deps.auth.is_admin", return_value=True),
        patch(
            "agent.nodes.admin_ask.answer_admin_question",
            return_value=fake_answer,
        ) as m,
    ):
        resp = client.post(
            "/admin/ask",
            json={"question": "Что чаще всего жалуются?", "history": []},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "жалобы" in body["answer_text"]
    assert body["tools_used"] == ["topic_histogram_tool"]
    assert body["chart_text"] is None
    m.assert_called_once()


def test_ask_requires_auth(client: TestClient) -> None:
    resp = client.post("/admin/ask", json={"question": "x"})
    assert resp.status_code == 401
