"""HTTP tests for the admin drill-down endpoints.

Services are mocked at `presentations.http_api.routes.admin.*`; auth is faked at
`presentations.http_api.deps.auth.is_admin` (mirrors test_api_admin_routes.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from config import settings
from core.storage.adapters.in_memory import InMemoryStorage
from presentations.http_api.auth.jwt import issue_token
from presentations.http_api.main import create_app

SECRET = "test-jwt-secret-32-bytes-or-more-aaaa"
_RANGE = {"date_from": "2026-06-01T00:00:00", "date_to": "2026-06-30T00:00:00"}
_CLIENT_ROWS = [
    {
        "telegram_id": 1,
        "name": "Alice",
        "sessions_count": 2,
        "last_session_at": "2026-06-10T12:00:00+00:00",
        "avg_sentiment": 1.0,
    }
]


@pytest.fixture(autouse=True)
def _patched_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "mini_app_session_secret", SECRET)
    monkeypatch.setattr(settings, "allowed_mini_app_origins", "https://miniapp.test")
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _auth(telegram_id: int = 7) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(telegram_id, SECRET)}"}


# --------------------------------------------------------------------------- #
# GET /admin/sessions


def test_sessions_requires_auth(client: TestClient) -> None:
    assert client.get("/admin/sessions", params=_RANGE).status_code == 401


def test_sessions_list_ok(client: TestClient) -> None:
    fake = [
        {
            "id": "s1",
            "client_id": 1,
            "client_name": "Alice",
            "started_at": "2026-06-10T12:00:00+00:00",
            "ended_at": None,
            "sentiment": "positive",
            "topics": ["сервис"],
            "source": "text",
        }
    ]
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin.list_sessions", return_value=fake) as m,
    ):
        resp = client.get("/admin/sessions", params=_RANGE, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["sessions"][0]["id"] == "s1"
    assert m.call_args.kwargs["limit"] == 50


def test_sessions_list_bad_range(client: TestClient) -> None:
    with patch("presentations.http_api.deps.auth.is_admin", return_value=True):
        resp = client.get(
            "/admin/sessions",
            params={"date_from": "2026-06-30T00:00:00", "date_to": "2026-06-01T00:00:00"},
            headers=_auth(),
        )
    assert resp.status_code == 400


def test_sessions_list_bad_limit(client: TestClient) -> None:
    with patch("presentations.http_api.deps.auth.is_admin", return_value=True):
        resp = client.get("/admin/sessions", params={**_RANGE, "limit": 0}, headers=_auth())
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# GET /admin/sessions/{session_id}


def test_session_detail_ok(client: TestClient) -> None:
    fake = {
        "id": "s1",
        "client_id": 1,
        "client_name": "Alice",
        "started_at": None,
        "ended_at": None,
        "sentiment": "positive",
        "topics": ["сервис"],
        "source": "text",
        "summary": "great",
        "messages": [{"role": "user", "content": "hi", "created_at": None}],
        "answers": [{"question_text": "Q?", "answer_text": "A", "marked_value": "Больше года"}],
        "card_summary": "card",
    }
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin.session_detail", return_value=fake),
    ):
        resp = client.get("/admin/sessions/s1", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["messages"][0]["content"] == "hi"
    assert body["answers"][0]["question_text"] == "Q?"


def test_session_detail_404(client: TestClient) -> None:
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch(
            "presentations.http_api.routes.admin.session_detail",
            side_effect=LookupError("nope"),
        ),
    ):
        resp = client.get("/admin/sessions/x", headers=_auth())
    assert resp.status_code == 404


def test_session_detail_marked_value_is_scalar_string(client: TestClient) -> None:
    """End-to-end: a dict-shaped marked_value in storage is flattened to a
    scalar string in the JSON response (guards against React error #31). Runs
    the real service against a seeded InMemoryStorage."""
    mem = InMemoryStorage()
    mem.clients.append(
        {"telegram_id": 1, "name": "Alice", "created_at": "2026-06-01T00:00:00+00:00"}
    )
    mem.questions.append(
        {
            "id": "q1",
            "text": "Как давно были у нас?",
            "metric_key": "visit_recency",
            "expected_type": "enum",
            "enum_values": ["Больше года"],
            "is_active": True,
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    mem.sessions.append(
        {
            "id": "s1",
            "client_id": 1,
            "started_at": "2026-06-10T12:00:00+00:00",
            "ended_at": None,
            "feedback_summary": {"summary": "ok", "sentiment": "positive", "topics": ["сервис"]},
            "feedback_source": "text",
        }
    )
    mem.session_answers.append(
        {
            "id": 1,
            "session_id": "s1",
            "question_id": "q1",
            "answer_text": "Был год назад",
            "marked_value": {"value": "Больше года"},
            "created_at": "2026-06-10T12:01:00+00:00",
        }
    )
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("core.services.sessions.SupabaseStorage", return_value=mem),
    ):
        resp = client.get("/admin/sessions/s1", headers=_auth())
    assert resp.status_code == 200
    marked = resp.json()["answers"][0]["marked_value"]
    assert marked == "Больше года"
    assert isinstance(marked, str)


# --------------------------------------------------------------------------- #
# GET /admin/topics/{topic}/clients


def test_topic_clients_ok(client: TestClient) -> None:
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch(
            "presentations.http_api.routes.admin.list_clients_by_topic",
            return_value=_CLIENT_ROWS,
        ) as m,
    ):
        resp = client.get("/admin/topics/сервис/clients", params=_RANGE, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["clients"][0]["telegram_id"] == 1
    assert m.call_args.args[0] == "сервис"


# --------------------------------------------------------------------------- #
# GET /admin/metrics/{metric_key}/clients


def test_metric_clients_ok(client: TestClient) -> None:
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch(
            "presentations.http_api.routes.admin.list_clients_by_enum_answer",
            return_value=_CLIENT_ROWS,
        ) as m,
    ):
        resp = client.get(
            "/admin/metrics/visit_recency/clients",
            params={**_RANGE, "value": "Больше года"},
            headers=_auth(),
        )
    assert resp.status_code == 200
    assert m.call_args.args[:2] == ("visit_recency", "Больше года")


def test_metric_clients_404(client: TestClient) -> None:
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch(
            "presentations.http_api.routes.admin.list_clients_by_enum_answer",
            side_effect=LookupError("no question"),
        ),
    ):
        resp = client.get(
            "/admin/metrics/nope/clients", params={**_RANGE, "value": "x"}, headers=_auth()
        )
    assert resp.status_code == 404


def test_metric_clients_missing_value(client: TestClient) -> None:
    with patch("presentations.http_api.deps.auth.is_admin", return_value=True):
        resp = client.get("/admin/metrics/visit_recency/clients", params=_RANGE, headers=_auth())
    assert resp.status_code == 422  # `value` is required


# --------------------------------------------------------------------------- #
# GET /admin/clients  (search / multi-topic filter)


def test_clients_search_by_query(client: TestClient) -> None:
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch("presentations.http_api.routes.admin.search_clients", return_value=_CLIENT_ROWS) as m,
    ):
        resp = client.get("/admin/clients", params={"query": "alice"}, headers=_auth())
    assert resp.status_code == 200
    assert m.call_args.args[0] == "alice"


def test_clients_filter_by_topics(client: TestClient) -> None:
    with (
        patch("presentations.http_api.deps.auth.is_admin", return_value=True),
        patch(
            "presentations.http_api.routes.admin.filter_clients_by_topics",
            return_value=_CLIENT_ROWS,
        ) as m,
    ):
        resp = client.get(
            "/admin/clients", params={"topics": ["сервис", "еда"], "match": "and"}, headers=_auth()
        )
    assert resp.status_code == 200
    assert m.call_args.args[0] == ["сервис", "еда"]
    assert m.call_args.kwargs["match"] == "and"


def test_clients_requires_a_filter(client: TestClient) -> None:
    with patch("presentations.http_api.deps.auth.is_admin", return_value=True):
        resp = client.get("/admin/clients", headers=_auth())
    assert resp.status_code == 400


def test_clients_rejects_both_filters(client: TestClient) -> None:
    with patch("presentations.http_api.deps.auth.is_admin", return_value=True):
        resp = client.get("/admin/clients", params={"query": "a", "topics": ["x"]}, headers=_auth())
    assert resp.status_code == 400


def test_clients_bad_match(client: TestClient) -> None:
    with patch("presentations.http_api.deps.auth.is_admin", return_value=True):
        resp = client.get(
            "/admin/clients", params={"topics": ["x"], "match": "xor"}, headers=_auth()
        )
    assert resp.status_code == 422  # match is Literal["and", "or"]
