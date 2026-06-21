"""HTTP tests for /guest/* — JWT auth + route shape + service error mapping.

Services are mocked at `presentations.http_guest_api.routes.guest.*`; the JWT
is real (signed with a test secret via `issue_session_token`), so the auth
dep, header parsing, and path-vs-token enforcement all run.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from config import settings
from presentations.http_api.main import create_app
from presentations.http_guest_api.auth.jwt import issue_session_token

SECRET = "test-guest-secret-32-bytes-or-more-aaa"


@pytest.fixture(autouse=True)
def _patched_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "guest_session_secret", SECRET)
    monkeypatch.setattr(settings, "allowed_guest_origins", "https://guest.test")
    monkeypatch.setattr(settings, "mini_app_session_secret", "x" * 40)
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _auth_for(session_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_session_token(session_id, SECRET)}"}


# --------------------------------------------------------------------------- #
# POST /guest/sessions  (anonymous start, no auth required)


def test_start_session_returns_id_and_token(client: TestClient) -> None:
    sid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.start_anonymous_session",
        return_value=sid,
    ):
        resp = client.post("/guest/sessions")
    assert resp.status_code == 201
    body = resp.json()
    assert body["session_id"] == sid
    assert body["token"]


def test_start_session_with_body_passes_journey_mode_meal(client: TestClient) -> None:
    sid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.start_anonymous_session",
        return_value=sid,
    ) as m:
        resp = client.post(
            "/guest/sessions",
            json={"journey": "delivery", "mode": "targeted", "meal_occasion": "dinner"},
        )
    assert resp.status_code == 201
    assert m.await_args is not None
    assert m.await_args.kwargs == {
        "journey": "delivery",
        "mode": "targeted",
        "meal_occasion": "dinner",
    }


def test_start_session_rejects_unknown_journey(client: TestClient) -> None:
    resp = client.post("/guest/sessions", json={"journey": "spaceship"})
    assert resp.status_code == 422  # Literal["restaurant", "delivery"]


# --------------------------------------------------------------------------- #
# POST /guest/auth — 501 stub


def test_auth_stub_is_501(client: TestClient) -> None:
    assert client.post("/guest/auth").status_code == 501


# --------------------------------------------------------------------------- #
# GET /guest/journey


def test_journey_returns_template_and_beats(client: TestClient) -> None:
    sid = str(uuid4())
    fake = {
        "template": {"id": "t1", "name": "restaurant", "label_uk": "Р", "label_en": "R"},
        "beats": [
            {
                "id": "b1",
                "beat_key": "food",
                "position": 1,
                "label_uk": "Їжа",
                "label_en": "Food",
                "icon": "🍽️",
                "input_type": "mood_slider",
                "tags": [
                    {
                        "id": "t1",
                        "tag_key": "cold",
                        "position": 1,
                        "label_uk": "Х",
                        "label_en": "C",
                    }
                ],
            }
        ],
    }
    with patch(
        "presentations.http_guest_api.routes.guest.get_journey",
        return_value=fake,
    ):
        resp = client.get("/guest/journey", headers=_auth_for(sid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["template"]["name"] == "restaurant"
    assert body["beats"][0]["beat_key"] == "food"


def test_journey_by_name_passes_through(client: TestClient) -> None:
    sid = str(uuid4())
    fake = {
        "template": {"id": "t2", "name": "delivery", "label_uk": "Д", "label_en": "D"},
        "beats": [],
    }
    with patch(
        "presentations.http_guest_api.routes.guest.get_journey",
        return_value=fake,
    ) as m:
        resp = client.get("/guest/journey?name=delivery", headers=_auth_for(sid))
    assert resp.status_code == 200
    assert resp.json()["template"]["name"] == "delivery"
    assert m.await_args is not None
    assert m.await_args.args == ("delivery",)


def test_journey_by_name_404_when_missing(client: TestClient) -> None:
    sid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.get_journey",
        return_value=None,
    ):
        resp = client.get("/guest/journey?name=delivery", headers=_auth_for(sid))
    assert resp.status_code == 404


def test_journey_requires_auth(client: TestClient) -> None:
    assert client.get("/guest/journey").status_code == 401


def test_journey_500_when_unconfigured(client: TestClient) -> None:
    sid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.get_journey",
        return_value=None,
    ):
        resp = client.get("/guest/journey", headers=_auth_for(sid))
    assert resp.status_code == 500


# --------------------------------------------------------------------------- #
# GET /guest/sessions/{id}


def test_session_get_enforces_path_matches_token(client: TestClient) -> None:
    token_sid = str(uuid4())
    other_sid = str(uuid4())
    resp = client.get(f"/guest/sessions/{other_sid}", headers=_auth_for(token_sid))
    assert resp.status_code == 403


def test_session_restore_404_on_missing(client: TestClient) -> None:
    sid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.restore_session",
        side_effect=LookupError("nope"),
    ):
        resp = client.get(f"/guest/sessions/{sid}", headers=_auth_for(sid))
    assert resp.status_code == 404


def test_session_restore_ok(client: TestClient) -> None:
    sid = str(uuid4())
    fake = {
        "session_id": sid,
        "feedback_source": "web_anon",
        "started_at": "2026-06-15T18:00:00+00:00",
        "ended_at": None,
        "beats": [{"beat_id": "b1", "score": 4, "tags": ["cold"], "skipped": False}],
        "digs": [
            {
                "id": "d1",
                "beat_id": "b1",
                "guesses": [{"id": "g1", "text_uk": "Х", "text_en": "C", "emoji": "🥶"}],
                "accepted_guess_id": None,
                "free_text": None,
            }
        ],
    }
    with patch(
        "presentations.http_guest_api.routes.guest.restore_session",
        return_value=fake,
    ):
        resp = client.get(f"/guest/sessions/{sid}", headers=_auth_for(sid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["beats"][0]["score"] == 4
    assert body["digs"][0]["id"] == "d1"


# --------------------------------------------------------------------------- #
# PATCH /guest/sessions/{id}/beats/{beat_id}


def test_patch_beat_ok(client: TestClient) -> None:
    sid = str(uuid4())
    bid = str(uuid4())
    fake = {"beat_id": bid, "score": 4, "tags": ["cold"], "skipped": False}
    with patch(
        "presentations.http_guest_api.routes.guest.save_beat",
        return_value=fake,
    ):
        resp = client.patch(
            f"/guest/sessions/{sid}/beats/{bid}",
            json={"score": 4, "tags": ["cold"]},
            headers=_auth_for(sid),
        )
    assert resp.status_code == 200
    assert resp.json()["score"] == 4


def test_patch_beat_score_out_of_range_is_422(client: TestClient) -> None:
    sid = str(uuid4())
    bid = str(uuid4())
    resp = client.patch(
        f"/guest/sessions/{sid}/beats/{bid}",
        json={"score": 9},
        headers=_auth_for(sid),
    )
    assert resp.status_code == 422  # pydantic Field(ge=1, le=5)


def test_patch_beat_400_on_value_error(client: TestClient) -> None:
    sid = str(uuid4())
    bid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.save_beat",
        side_effect=ValueError("bad"),
    ):
        resp = client.patch(
            f"/guest/sessions/{sid}/beats/{bid}",
            json={"score": 3},
            headers=_auth_for(sid),
        )
    assert resp.status_code == 400


def test_patch_beat_404_on_lookup_error(client: TestClient) -> None:
    sid = str(uuid4())
    bid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.save_beat",
        side_effect=LookupError("nope"),
    ):
        resp = client.patch(
            f"/guest/sessions/{sid}/beats/{bid}",
            json={"score": 3},
            headers=_auth_for(sid),
        )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# POST /guest/sessions/{id}/dig


def test_post_dig_ok(client: TestClient) -> None:
    sid = str(uuid4())
    bid = str(uuid4())
    fake = {
        "id": "d1",
        "beat_id": bid,
        "guesses": [
            {"id": "g1", "text_uk": "Х", "text_en": "C", "emoji": "🥶"},
            {"id": "g2", "text_uk": "М", "text_en": "S", "emoji": "🍽️"},
        ],
        "accepted_guess_id": None,
        "free_text": None,
    }
    with patch(
        "presentations.http_guest_api.routes.guest.dig_for_beat",
        return_value=fake,
    ):
        resp = client.post(
            f"/guest/sessions/{sid}/dig",
            json={"beat_id": bid},
            headers=_auth_for(sid),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dig_id"] == "d1"
    assert len(body["guesses"]) == 2


# --------------------------------------------------------------------------- #
# POST /guest/sessions/{id}/dig/answer


def test_post_dig_answer_ok(client: TestClient) -> None:
    sid = str(uuid4())
    fake = {
        "id": "d1",
        "beat_id": "b1",
        "guesses": [{"id": "g1", "text_uk": "Х", "text_en": "C", "emoji": "🥶"}],
        "accepted_guess_id": "g1",
        "free_text": None,
    }
    with patch(
        "presentations.http_guest_api.routes.guest.record_dig_answer",
        return_value=fake,
    ):
        resp = client.post(
            f"/guest/sessions/{sid}/dig/answer",
            json={"dig_id": "d1", "accepted_guess_id": "g1"},
            headers=_auth_for(sid),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted_guess_id"] == "g1"
    assert body["next_dig"] is None


def test_post_dig_answer_400_on_value_error(client: TestClient) -> None:
    sid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.record_dig_answer",
        side_effect=ValueError("exactly one"),
    ):
        resp = client.post(
            f"/guest/sessions/{sid}/dig/answer",
            json={"dig_id": "d1"},
            headers=_auth_for(sid),
        )
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# POST /guest/sessions/{id}/voice — 501 stub


def test_voice_stub_is_501(client: TestClient) -> None:
    sid = str(uuid4())
    resp = client.post(f"/guest/sessions/{sid}/voice", headers=_auth_for(sid))
    assert resp.status_code == 501


# --------------------------------------------------------------------------- #
# POST /guest/sessions/{id}/finalize


def test_finalize_ok_202(client: TestClient) -> None:
    sid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.finalize_session",
        return_value=None,
    ):
        resp = client.post(f"/guest/sessions/{sid}/finalize", headers=_auth_for(sid))
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_finalize_404_on_lookup_error(client: TestClient) -> None:
    sid = str(uuid4())
    with patch(
        "presentations.http_guest_api.routes.guest.finalize_session",
        side_effect=LookupError("nope"),
    ):
        resp = client.post(f"/guest/sessions/{sid}/finalize", headers=_auth_for(sid))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# auth-layer guards


def test_no_auth_returns_401(client: TestClient) -> None:
    sid = str(uuid4())
    assert client.get(f"/guest/sessions/{sid}").status_code == 401


def test_bad_token_returns_401(client: TestClient) -> None:
    sid = str(uuid4())
    resp = client.get(
        f"/guest/sessions/{sid}",
        headers={"Authorization": "Bearer not-a-token"},
    )
    assert resp.status_code == 401


def test_path_session_id_must_match_token(client: TestClient) -> None:
    token_sid = str(uuid4())
    other = str(uuid4())
    resp = client.patch(
        f"/guest/sessions/{other}/beats/{uuid4()}",
        json={"score": 3},
        headers=_auth_for(token_sid),
    )
    assert resp.status_code == 403
