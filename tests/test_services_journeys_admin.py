"""Unit tests for core/services/journeys_admin — backed by InMemoryStorage.

Covers template/beat/tag CRUD, the single-default invariant, the delete guard
(default journey + referencing sessions), and input_type validation.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.services.journeys_admin import (
    create_journey,
    delete_beat_tag,
    delete_journey,
    delete_journey_beat,
    list_journeys,
    update_journey,
    upsert_beat_tag,
    upsert_journey_beat,
)
from core.storage.adapters.in_memory import InMemoryStorage


def _seed_restaurant(mem: InMemoryStorage) -> dict[str, str]:
    """Default 'restaurant' journey: one beat ('food') with one tag ('cold')."""
    template_id = str(uuid4())
    food_id = str(uuid4())
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
    mem.journey_beats.append(
        {
            "id": food_id,
            "template_id": template_id,
            "position": 1,
            "beat_key": "food",
            "label_uk": "Їжа",
            "label_en": "Food",
            "icon": "🍽️",
            "input_type": "mood_slider",
            "created_at": "2026-06-01T00:00:00+00:00",
        }
    )
    mem.beat_tags.append(
        {
            "id": str(uuid4()),
            "beat_id": food_id,
            "position": 1,
            "tag_key": "cold",
            "label_uk": "Холодна",
            "label_en": "Cold",
        }
    )
    return {"template_id": template_id, "food_id": food_id}


# --------------------------------------------------------------------------- #
# list


async def test_list_journeys_default_first() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    await create_journey(name="delivery", label_uk="Доставка", label_en="Delivery", storage=mem)
    journeys = await list_journeys(storage=mem)
    assert [j["template"]["name"] for j in journeys] == ["restaurant", "delivery"]
    food = journeys[0]["beats"][0]
    assert food["beat_key"] == "food"
    assert food["tags"][0]["tag_key"] == "cold"


# --------------------------------------------------------------------------- #
# create


async def test_create_journey_inserts_template() -> None:
    mem = InMemoryStorage()
    row = await create_journey(
        name="delivery", label_uk="Доставка", label_en="Delivery", storage=mem
    )
    assert row["name"] == "delivery"
    assert row["is_default"] is False
    assert len(mem.journey_templates) == 1


async def test_create_journey_default_unsets_previous_default() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    await create_journey(
        name="delivery",
        label_uk="Доставка",
        label_en="Delivery",
        is_default=True,
        storage=mem,
    )
    defaults = [t["name"] for t in mem.journey_templates if t.get("is_default")]
    assert defaults == ["delivery"]


async def test_create_journey_rejects_duplicate_name() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    with pytest.raises(ValueError, match="already exists"):
        await create_journey(name="restaurant", label_uk="X", label_en="Y", storage=mem)


async def test_create_journey_rejects_blank_name() -> None:
    mem = InMemoryStorage()
    with pytest.raises(ValueError, match="name is required"):
        await create_journey(name="   ", label_uk="X", label_en="Y", storage=mem)


# --------------------------------------------------------------------------- #
# update


async def test_update_journey_patches_labels() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    row = await update_journey(name="restaurant", label_uk="Кафе", storage=mem)
    assert row["label_uk"] == "Кафе"
    assert row["label_en"] == "Restaurant"  # untouched


async def test_update_journey_promote_default_demotes_others() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    await create_journey(name="delivery", label_uk="Доставка", label_en="Delivery", storage=mem)
    await update_journey(name="delivery", is_default=True, storage=mem)
    defaults = [t["name"] for t in mem.journey_templates if t.get("is_default")]
    assert defaults == ["delivery"]


async def test_update_journey_cannot_unset_default() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    with pytest.raises(ValueError, match="cannot unset default"):
        await update_journey(name="restaurant", is_default=False, storage=mem)


async def test_update_journey_missing_raises_lookup() -> None:
    mem = InMemoryStorage()
    with pytest.raises(LookupError, match="not found"):
        await update_journey(name="ghost", label_uk="X", storage=mem)


async def test_update_journey_nothing_to_update() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    with pytest.raises(ValueError, match="nothing to update"):
        await update_journey(name="restaurant", storage=mem)


# --------------------------------------------------------------------------- #
# delete


async def test_delete_journey_removes_template_and_cascades() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    await create_journey(name="delivery", label_uk="Доставка", label_en="Delivery", storage=mem)
    await upsert_journey_beat(
        journey_name="delivery", beat_key="order", label_uk="Замовлення", storage=mem
    )
    await delete_journey(name="delivery", storage=mem)
    assert all(t["name"] != "delivery" for t in mem.journey_templates)
    # the beat we added cascaded away
    assert not any(b.get("beat_key") == "order" for b in mem.journey_beats)


async def test_delete_journey_refuses_default() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    with pytest.raises(ValueError, match="default journey"):
        await delete_journey(name="restaurant", storage=mem)


async def test_delete_journey_refuses_when_referenced() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    await create_journey(name="delivery", label_uk="Доставка", label_en="Delivery", storage=mem)
    mem.sessions.append({"id": str(uuid4()), "journey_template_name": "delivery"})
    with pytest.raises(ValueError, match="referenced by 1 session"):
        await delete_journey(name="delivery", storage=mem)


async def test_delete_journey_missing_raises_lookup() -> None:
    mem = InMemoryStorage()
    with pytest.raises(LookupError, match="not found"):
        await delete_journey(name="ghost", storage=mem)


# --------------------------------------------------------------------------- #
# beats


async def test_upsert_journey_beat_inserts() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    beat = await upsert_journey_beat(
        journey_name="restaurant",
        beat_key="service",
        position=2,
        label_uk="Сервіс",
        label_en="Service",
        icon="💁",
        input_type="chip_pick",
        storage=mem,
    )
    assert beat["beat_key"] == "service"
    assert beat["input_type"] == "chip_pick"
    assert beat["position"] == 2


async def test_upsert_journey_beat_updates_existing() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    beat = await upsert_journey_beat(
        journey_name="restaurant", beat_key="food", label_uk="Страви", storage=mem
    )
    assert beat["label_uk"] == "Страви"
    assert beat["icon"] == "🍽️"  # untouched
    assert sum(1 for b in mem.journey_beats if b["beat_key"] == "food") == 1


async def test_upsert_journey_beat_rejects_bad_input_type() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    with pytest.raises(ValueError, match="unknown input_type"):
        await upsert_journey_beat(
            journey_name="restaurant",
            beat_key="food",
            input_type="slider_xxx",
            storage=mem,
        )


async def test_upsert_journey_beat_missing_journey_raises_lookup() -> None:
    mem = InMemoryStorage()
    with pytest.raises(LookupError, match="not found"):
        await upsert_journey_beat(journey_name="ghost", beat_key="food", label_uk="X", storage=mem)


async def test_upsert_journey_beat_nothing_to_update() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    with pytest.raises(ValueError, match="nothing to update"):
        await upsert_journey_beat(journey_name="restaurant", beat_key="food", storage=mem)


async def test_delete_journey_beat_removes_beat_and_tags() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    await delete_journey_beat(journey_name="restaurant", beat_key="food", storage=mem)
    assert not any(b.get("beat_key") == "food" for b in mem.journey_beats)
    assert mem.beat_tags == []  # tag cascaded


async def test_delete_journey_beat_missing_raises_lookup() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    with pytest.raises(LookupError, match="not found"):
        await delete_journey_beat(journey_name="restaurant", beat_key="ghost", storage=mem)


# --------------------------------------------------------------------------- #
# tags


async def test_upsert_beat_tag_inserts() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    tag = await upsert_beat_tag(
        journey_name="restaurant",
        beat_key="food",
        tag_key="small",
        position=2,
        label_uk="Мала порція",
        label_en="Small",
        storage=mem,
    )
    assert tag["tag_key"] == "small"
    assert tag["position"] == 2


async def test_upsert_beat_tag_updates_existing() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    tag = await upsert_beat_tag(
        journey_name="restaurant",
        beat_key="food",
        tag_key="cold",
        label_uk="Зовсім холодна",
        storage=mem,
    )
    assert tag["label_uk"] == "Зовсім холодна"
    assert sum(1 for t in mem.beat_tags if t["tag_key"] == "cold") == 1


async def test_upsert_beat_tag_missing_beat_raises_lookup() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    with pytest.raises(LookupError, match="not found"):
        await upsert_beat_tag(
            journey_name="restaurant",
            beat_key="ghost",
            tag_key="cold",
            label_uk="X",
            storage=mem,
        )


async def test_delete_beat_tag_removes_tag() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    await delete_beat_tag(journey_name="restaurant", beat_key="food", tag_key="cold", storage=mem)
    assert mem.beat_tags == []


async def test_delete_beat_tag_missing_raises_lookup() -> None:
    mem = InMemoryStorage()
    _seed_restaurant(mem)
    with pytest.raises(LookupError, match="not found"):
        await delete_beat_tag(
            journey_name="restaurant", beat_key="food", tag_key="ghost", storage=mem
        )
