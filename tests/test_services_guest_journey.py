"""Unit tests for core/services/guest_journey — backed by InMemoryStorage.

The journey is seeded once per test (3 beats: arrival, food, service; 2 tags
on food). LLM-side dependencies (`dig_guesses_for_beat`, `analyze_feedback`)
are patched in the tests that need them.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from core.agent.nodes.analyze import FeedbackSummary
from core.services.guest_journey import (
    beat_transcription_uk,
    compute_prize,
    dig_for_beat,
    finalize_session,
    get_default_journey,
    get_journey,
    get_prize_tiers,
    identify_guest,
    record_dig_answer,
    restore_session,
    save_beat,
    score_for_session,
    set_prize_tier_config,
    start_anonymous_session,
    tier_for_points,
)
from core.storage.adapters.in_memory import InMemoryStorage


def _seed_journey(mem: InMemoryStorage) -> dict[str, str]:
    template_id = str(uuid4())
    arrival_id = str(uuid4())
    food_id = str(uuid4())
    service_id = str(uuid4())
    mem.journey_templates.append(
        {
            "id": template_id,
            "name": "restaurant",
            "label_uk": "Ресторан",
            "label_en": "Restaurant",
            "is_default": True,
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    common = {
        "template_id": template_id,
        "input_type": "mood_slider",
        "created_at": "2026-06-01T00:00:00+00:00",
    }
    mem.journey_beats += [
        {
            "id": arrival_id,
            "position": 1,
            "beat_key": "arrival",
            "label_uk": "Прихід",
            "label_en": "Arrival",
            "icon": "🚪",
            **common,
        },
        {
            "id": food_id,
            "position": 2,
            "beat_key": "food",
            "label_uk": "Їжа",
            "label_en": "Food",
            "icon": "🍽️",
            **common,
        },
        {
            "id": service_id,
            "position": 3,
            "beat_key": "service",
            "label_uk": "Сервіс",
            "label_en": "Service",
            "icon": "💁",
            **common,
        },
    ]
    mem.beat_tags += [
        {
            "id": str(uuid4()),
            "beat_id": food_id,
            "position": 1,
            "tag_key": "cold",
            "label_uk": "Холодна",
            "label_en": "Cold",
        },
        {
            "id": str(uuid4()),
            "beat_id": food_id,
            "position": 2,
            "tag_key": "small",
            "label_uk": "Мала порція",
            "label_en": "Small",
        },
    ]
    return {
        "template_id": template_id,
        "arrival_id": arrival_id,
        "food_id": food_id,
        "service_id": service_id,
    }


def _seed_delivery(mem: InMemoryStorage) -> dict[str, str]:
    """A second, non-default 'delivery' journey with one beat ('courier')."""
    template_id = str(uuid4())
    courier_id = str(uuid4())
    mem.journey_templates.append(
        {
            "id": template_id,
            "name": "delivery",
            "label_uk": "Доставка",
            "label_en": "Delivery",
            "is_default": False,
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    mem.journey_beats.append(
        {
            "id": courier_id,
            "template_id": template_id,
            "position": 1,
            "beat_key": "courier",
            "label_uk": "Кур'єр",
            "label_en": "Courier",
            "icon": "🛵",
            "input_type": "mood_slider",
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    return {"template_id": template_id, "courier_id": courier_id}


def _seed_dig(mem: InMemoryStorage, *, sid: str, beat_id: str, dig_id: str = "d1") -> str:
    mem.session_digs.append(
        {
            "id": dig_id,
            "session_id": sid,
            "beat_id": beat_id,
            "guesses": [{"id": "g1", "text_uk": "Холодна", "text_en": "Cold", "emoji": "🥶"}],
            "accepted_guess_id": None,
            "free_text": None,
            "voice_object_key": None,
            "created_at": "2026-06-15T18:00:00+00:00",
        }
    )
    return dig_id


# --------------------------------------------------------------------------- #
# get_default_journey


async def test_get_default_journey_returns_template_and_beats() -> None:
    mem = InMemoryStorage()
    _seed_journey(mem)
    journey = await get_default_journey(storage=mem)
    assert journey is not None
    assert journey["template"]["name"] == "restaurant"
    assert [b["beat_key"] for b in journey["beats"]] == ["arrival", "food", "service"]
    food = next(b for b in journey["beats"] if b["beat_key"] == "food")
    assert {t["tag_key"] for t in food["tags"]} == {"cold", "small"}


async def test_get_default_journey_none_when_unconfigured() -> None:
    mem = InMemoryStorage()
    assert await get_default_journey(storage=mem) is None


# --------------------------------------------------------------------------- #
# get_journey (by name)


async def test_get_journey_by_name_returns_named_template() -> None:
    mem = InMemoryStorage()
    _seed_journey(mem)  # restaurant (default)
    _seed_delivery(mem)
    journey = await get_journey("delivery", storage=mem)
    assert journey is not None
    assert journey["template"]["name"] == "delivery"
    assert [b["beat_key"] for b in journey["beats"]] == ["courier"]


async def test_get_journey_no_name_returns_default() -> None:
    mem = InMemoryStorage()
    _seed_journey(mem)
    _seed_delivery(mem)
    journey = await get_journey(storage=mem)
    assert journey is not None
    assert journey["template"]["name"] == "restaurant"


async def test_get_journey_unknown_name_returns_none() -> None:
    mem = InMemoryStorage()
    _seed_journey(mem)
    assert await get_journey("spaceship", storage=mem) is None


# --------------------------------------------------------------------------- #
# start_anonymous_session


async def test_start_anonymous_session_creates_web_anon_row() -> None:
    mem = InMemoryStorage()
    sid = await start_anonymous_session(storage=mem)
    assert sid
    row = mem.sessions[0]
    assert row["feedback_source"] == "web_anon"
    assert row["client_id"] is None
    # defaults captured on the row
    assert row["journey_template_name"] == "restaurant"
    assert row["mode"] == "non_targeted"
    assert row["meal_occasion"] is None


async def test_start_anonymous_session_captures_delivery_targeted() -> None:
    mem = InMemoryStorage()
    sid = await start_anonymous_session("delivery", "targeted", "dinner", storage=mem)
    assert sid
    row = mem.sessions[0]
    assert row["journey_template_name"] == "delivery"
    assert row["mode"] == "targeted"
    # meal_occasion is restaurant-only; dropped for delivery
    assert row["meal_occasion"] is None


async def test_start_anonymous_session_keeps_meal_occasion_for_restaurant() -> None:
    mem = InMemoryStorage()
    await start_anonymous_session("restaurant", "non_targeted", "breakfast", storage=mem)
    assert mem.sessions[0]["meal_occasion"] == "breakfast"


# --------------------------------------------------------------------------- #
# restore_session


async def test_restore_session_includes_beats_and_digs() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    await save_beat(sid, ids["food_id"], score=2, tags=["cold"], storage=mem)
    _seed_dig(mem, sid=sid, beat_id=ids["food_id"])

    state = await restore_session(sid, storage=mem)
    assert state["session_id"] == sid
    assert state["feedback_source"] == "web_anon"
    food = next(b for b in state["beats"] if b["beat_id"] == ids["food_id"])
    assert food["score"] == 2
    assert food["tags"] == ["cold"]
    assert state["digs"][0]["id"] == "d1"


async def test_restore_session_missing_raises() -> None:
    mem = InMemoryStorage()
    with pytest.raises(LookupError):
        await restore_session(str(uuid4()), storage=mem)


async def test_restore_session_non_web_raises() -> None:
    mem = InMemoryStorage()
    sid = str(uuid4())
    mem.sessions.append(
        {
            "id": sid,
            "client_id": 1,
            "feedback_source": "text",
            "started_at": "2026-06-15T18:00:00+00:00",
            "ended_at": None,
        }
    )
    with pytest.raises(LookupError):
        await restore_session(sid, storage=mem)


# --------------------------------------------------------------------------- #
# save_beat


async def test_save_beat_validates_score_range() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    with pytest.raises(ValueError, match="score"):
        await save_beat(sid, ids["food_id"], score=0, storage=mem)
    with pytest.raises(ValueError, match="score"):
        await save_beat(sid, ids["food_id"], score=6, storage=mem)


async def test_save_beat_requires_at_least_one_field() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    with pytest.raises(ValueError, match="at least one"):
        await save_beat(sid, ids["food_id"], storage=mem)


async def test_save_beat_upserts_in_place() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    first = await save_beat(sid, ids["food_id"], score=4, storage=mem)
    assert first["score"] == 4
    second = await save_beat(sid, ids["food_id"], tags=["cold"], storage=mem)
    assert second["tags"] == ["cold"]
    # one beat row, not two
    assert len(mem.session_beats) == 1


# --------------------------------------------------------------------------- #
# dig_for_beat


async def test_dig_for_beat_persists_guesses_and_returns_state() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    await save_beat(sid, ids["food_id"], score=2, tags=["cold"], storage=mem)
    fake_guesses: list[dict[str, str]] = [
        {"id": "g1", "text_uk": "Холодна", "text_en": "Cold", "emoji": "🥶"},
        {"id": "g2", "text_uk": "Мала порція", "text_en": "Small", "emoji": "🍽️"},
    ]
    with patch(
        "core.services.guest_journey.dig_guesses_for_beat",
        new=AsyncMock(return_value=fake_guesses),
    ) as m:
        dig = await dig_for_beat(sid, ids["food_id"], storage=mem)
    m.assert_awaited_once()
    assert m.await_args is not None
    kwargs = m.await_args.kwargs
    assert kwargs["beat_label"] == "Їжа"
    assert kwargs["score"] == 2
    assert kwargs["tags"] == ["cold"]
    assert dig["guesses"] == fake_guesses
    assert len(mem.session_digs) == 1


async def test_dig_for_beat_unknown_beat_raises() -> None:
    mem = InMemoryStorage()
    _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    with patch(
        "core.services.guest_journey.dig_guesses_for_beat",
        new=AsyncMock(),
    ):
        with pytest.raises(LookupError, match="beat"):
            await dig_for_beat(sid, str(uuid4()), storage=mem)


async def test_dig_for_beat_defaults_score_when_unscored() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    fake_guesses: list[dict[str, str]] = [
        {"id": "g1", "text_uk": "A", "text_en": "A", "emoji": "🤷"},
        {"id": "g2", "text_uk": "B", "text_en": "B", "emoji": "🕒"},
    ]
    with patch(
        "core.services.guest_journey.dig_guesses_for_beat",
        new=AsyncMock(return_value=fake_guesses),
    ) as m:
        await dig_for_beat(sid, ids["food_id"], storage=mem)
    assert m.await_args is not None
    assert m.await_args.kwargs["score"] == 3
    assert m.await_args.kwargs["tags"] == []


# --------------------------------------------------------------------------- #
# record_dig_answer


async def test_record_dig_answer_accepted_guess() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    _seed_dig(mem, sid=sid, beat_id=ids["food_id"])
    dig = await record_dig_answer(sid, "d1", accepted_guess_id="g1", storage=mem)
    assert dig["accepted_guess_id"] == "g1"
    assert dig["free_text"] is None


async def test_record_dig_answer_free_text() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    _seed_dig(mem, sid=sid, beat_id=ids["food_id"])
    dig = await record_dig_answer(sid, "d1", free_text="було несвіже", storage=mem)
    assert dig["free_text"] == "було несвіже"
    assert dig["accepted_guess_id"] is None


async def test_record_dig_answer_xor_rule() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    _seed_dig(mem, sid=sid, beat_id=ids["food_id"])
    with pytest.raises(ValueError, match="exactly one"):
        await record_dig_answer(sid, "d1", storage=mem)
    with pytest.raises(ValueError, match="exactly one"):
        await record_dig_answer(sid, "d1", accepted_guess_id="g1", free_text="x", storage=mem)


async def test_record_dig_answer_unknown_guess_id() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    _seed_dig(mem, sid=sid, beat_id=ids["food_id"])
    with pytest.raises(ValueError, match="not in this dig"):
        await record_dig_answer(sid, "d1", accepted_guess_id="gZ", storage=mem)


# --------------------------------------------------------------------------- #
# finalize_session


async def test_finalize_session_synthesizes_and_updates() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    await save_beat(sid, ids["arrival_id"], score=5, storage=mem)
    await save_beat(sid, ids["food_id"], score=2, tags=["cold"], storage=mem)

    summary = FeedbackSummary(
        summary="Гостю не сподобалось у їжі.",
        sentiment="negative",
        topics=["еда"],
        emotion="disappointed",
    )
    with patch(
        "core.services.guest_journey.analyze_feedback",
        new=AsyncMock(return_value=summary),
    ) as m:
        await finalize_session(sid, storage=mem)

    m.assert_awaited_once()
    assert m.await_args is not None
    raw_text: str = m.await_args.args[0]
    # the synthesized text should mention beat labels, the score, and the tag
    assert "Прихід" in raw_text
    assert "Їжа" in raw_text
    assert "Холодна" in raw_text
    assert "5/5" in raw_text and "2/5" in raw_text

    row = mem.sessions[0]
    assert row.get("ended_at")
    assert row.get("feedback_summary") == summary.model_dump()
    assert row.get("language") == "uk"


async def test_finalize_session_is_idempotent() -> None:
    mem = InMemoryStorage()
    _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    mem.sessions[0]["ended_at"] = "2026-06-15T19:00:00+00:00"
    spy: Any = AsyncMock()
    with patch("core.services.guest_journey.analyze_feedback", new=spy):
        await finalize_session(sid, storage=mem)
    spy.assert_not_awaited()


async def test_finalize_session_uses_the_sessions_own_journey() -> None:
    """A delivery session must synthesize against the delivery journey, not the
    default restaurant one — its beat ids only exist in the delivery template."""
    mem = InMemoryStorage()
    _seed_journey(mem)  # restaurant is the default
    delivery = _seed_delivery(mem)
    sid = await start_anonymous_session("delivery", storage=mem)
    await save_beat(sid, delivery["courier_id"], score=2, storage=mem)

    summary = FeedbackSummary(
        summary="Кур'єр запізнився.",
        sentiment="negative",
        topics=["доставка"],
        emotion="annoyed",
    )
    with patch(
        "core.services.guest_journey.analyze_feedback",
        new=AsyncMock(return_value=summary),
    ) as m:
        await finalize_session(sid, storage=mem)

    assert m.await_args is not None
    raw_text: str = m.await_args.args[0]
    assert "Кур'єр" in raw_text
    assert "2/5" in raw_text


# --------------------------------------------------------------------------- #
# scoring (pure functions)


def test_score_for_session_counts_all_signals() -> None:
    beats: list[dict[str, Any]] = [
        {"beat_id": "b1", "score": 4, "tags": ["x", "y"], "skipped": False},  # 5 + 2*3
        {"beat_id": "b2", "score": 2, "tags": [], "skipped": False},  # 5
        {"beat_id": "b3", "score": None, "tags": [], "skipped": True},  # 0
    ]
    digs: list[dict[str, Any]] = [
        {"accepted_guess_id": "g1", "free_text": None, "voice_object_key": None},  # 15
        {"accepted_guess_id": None, "free_text": "x" * 60, "voice_object_key": None},  # 35
        {"accepted_guess_id": None, "free_text": None, "voice_object_key": "v.ogg"},  # 30
    ]
    assert score_for_session(beats, digs, has_email=False) == 96
    assert score_for_session(beats, digs, has_email=True) == 136


def test_score_for_session_short_text_gets_no_long_bonus() -> None:
    digs: list[dict[str, Any]] = [
        {"accepted_guess_id": None, "free_text": "коротко", "voice_object_key": None}
    ]
    assert score_for_session([], digs, has_email=False) == 15


def test_tier_for_points_boundaries() -> None:
    assert tier_for_points(0) == "small"
    assert tier_for_points(40) == "small"
    assert tier_for_points(41) == "medium"
    assert tier_for_points(120) == "medium"
    assert tier_for_points(121) == "large"


def test_beat_transcription_uk() -> None:
    assert beat_transcription_uk(score=5, skipped=False) == "захоплення"
    assert beat_transcription_uk(score=1, skipped=False) == "розчарування"
    assert beat_transcription_uk(score=None, skipped=False) == "без оцінки"
    assert beat_transcription_uk(score=3, skipped=True) == "пропустив"


# --------------------------------------------------------------------------- #
# identify_guest


async def test_identify_guest_persists_and_trims() -> None:
    mem = InMemoryStorage()
    _seed_journey(mem)
    sid = await start_anonymous_session("restaurant", "targeted", storage=mem)
    out = await identify_guest(
        sid, name="  Іван  ", email="ivan@example.com", phone="+380501112233", storage=mem
    )
    assert out["name"] == "Іван"
    assert out["email"] == "ivan@example.com"
    row = mem.sessions[0]
    assert row["guest_name"] == "Іван"
    assert row["guest_email"] == "ivan@example.com"
    assert row["guest_phone"] == "+380501112233"


async def test_identify_guest_requires_name() -> None:
    mem = InMemoryStorage()
    _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    with pytest.raises(ValueError, match="name"):
        await identify_guest(sid, name="   ", storage=mem)


async def test_identify_guest_rejects_bad_email() -> None:
    mem = InMemoryStorage()
    _seed_journey(mem)
    sid = await start_anonymous_session(storage=mem)
    with pytest.raises(ValueError, match="email"):
        await identify_guest(sid, name="Іван", email="not-an-email", storage=mem)


# --------------------------------------------------------------------------- #
# finalize: points + tier + transcription


async def test_finalize_computes_points_tier_and_transcription() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session("restaurant", "targeted", storage=mem)
    await save_beat(sid, ids["arrival_id"], score=5, storage=mem)
    await save_beat(sid, ids["food_id"], score=2, tags=["cold"], storage=mem)

    summary = FeedbackSummary(summary="s", sentiment="negative", topics=["еда"], emotion="annoyed")
    with patch(
        "core.services.guest_journey.analyze_feedback",
        new=AsyncMock(return_value=summary),
    ):
        await finalize_session(sid, storage=mem)

    row = mem.sessions[0]
    assert row["points"] == 13  # arrival 5 + food 5 + 1 tag * 3
    assert row["prize_tier"] == "small"
    arrival = next(b for b in mem.session_beats if b["beat_id"] == ids["arrival_id"])
    food = next(b for b in mem.session_beats if b["beat_id"] == ids["food_id"])
    assert arrival["emoji_transcription_uk"] == "захоплення"
    assert food["emoji_transcription_uk"] == "не сподобалось"


# --------------------------------------------------------------------------- #
# compute_prize + prize-tier config


async def test_compute_prize_resolves_tier_and_config() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    mem.prize_tiers.append(
        {"tier": "small", "code": "WELCOME10", "label_uk": "Бонус", "label_en": "Bonus"}
    )
    sid = await start_anonymous_session("restaurant", "targeted", storage=mem)
    await save_beat(sid, ids["food_id"], score=2, storage=mem)
    summary = FeedbackSummary(summary="s", sentiment="neutral", topics=[], emotion="ok")
    with patch(
        "core.services.guest_journey.analyze_feedback",
        new=AsyncMock(return_value=summary),
    ):
        await finalize_session(sid, storage=mem)

    prize = await compute_prize(sid, storage=mem)
    assert prize["tier"] == "small"
    assert prize["points"] == 5
    assert prize["code"] == "WELCOME10"
    assert prize["label_uk"] == "Бонус"


async def test_compute_prize_works_before_finalize_live() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session("restaurant", "targeted", storage=mem)
    await save_beat(sid, ids["food_id"], score=3, storage=mem)
    prize = await compute_prize(sid, storage=mem)
    assert prize["tier"] == "small"
    assert prize["points"] == 5
    assert prize["code"] == ""  # no config seeded


async def test_prize_tier_config_set_and_get_ordered() -> None:
    mem = InMemoryStorage()
    await set_prize_tier_config("large", code="BIG", label_uk="Великий", storage=mem)
    await set_prize_tier_config("small", code="SM", storage=mem)
    tiers = await get_prize_tiers(storage=mem)
    assert [t["tier"] for t in tiers] == ["small", "large"]
    assert next(t for t in tiers if t["tier"] == "large")["code"] == "BIG"


async def test_set_prize_tier_rejects_unknown_tier() -> None:
    mem = InMemoryStorage()
    with pytest.raises(ValueError, match="tier"):
        await set_prize_tier_config("huge", code="X", storage=mem)


# --------------------------------------------------------------------------- #
# dig: meal_occasion as AI context (targeted restaurant only)


async def test_dig_passes_meal_occasion_for_targeted_restaurant() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session("restaurant", "targeted", "dinner", storage=mem)
    await save_beat(sid, ids["food_id"], score=2, storage=mem)
    guesses = [
        {"id": "g1", "text_uk": "a", "text_en": "a", "emoji": "🤷"},
        {"id": "g2", "text_uk": "b", "text_en": "b", "emoji": "🕒"},
    ]
    with patch(
        "core.services.guest_journey.dig_guesses_for_beat",
        new=AsyncMock(return_value=guesses),
    ) as m:
        await dig_for_beat(sid, ids["food_id"], storage=mem)
    assert m.await_args is not None
    assert m.await_args.kwargs["meal_occasion"] == "dinner"


async def test_dig_omits_meal_occasion_for_non_targeted() -> None:
    mem = InMemoryStorage()
    ids = _seed_journey(mem)
    sid = await start_anonymous_session("restaurant", "non_targeted", "dinner", storage=mem)
    await save_beat(sid, ids["food_id"], score=2, storage=mem)
    guesses = [
        {"id": "g1", "text_uk": "a", "text_en": "a", "emoji": "🤷"},
        {"id": "g2", "text_uk": "b", "text_en": "b", "emoji": "🕒"},
    ]
    with patch(
        "core.services.guest_journey.dig_guesses_for_beat",
        new=AsyncMock(return_value=guesses),
    ) as m:
        await dig_for_beat(sid, ids["food_id"], storage=mem)
    assert m.await_args is not None
    assert m.await_args.kwargs["meal_occasion"] == ""
