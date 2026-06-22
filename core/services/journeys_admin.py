"""Admin journey CRUD — manage guest journeys (templates + beats + tags).

The admin app's counterpart to the read-only `core/services/guest_journey.py`
helpers: create/update/delete journey templates, and upsert/delete their beats
and chip tags. All business rules live here (single-default invariant, allowed
`input_type` values, delete guards); storage only fetches and mutates rows.

DI mirrors the other services: every public function takes `storage` / `db`.
Errors are raised so the HTTP layer can map them — `ValueError` (bad input,
guarded delete) → 400, `LookupError` (missing template/beat) → 404.
"""

from __future__ import annotations

from typing import Any

from supabase import Client

from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter

_INPUT_TYPES = ("mood_slider", "chip_pick", "yes_no")


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


async def _require_template(store: StorageAdapter, name: str) -> dict[str, Any]:
    """Return the journey bundle for `name` or raise LookupError."""
    journey = await store.fetch_journey_by_name(name=name)
    if journey is None:
        raise LookupError(f"journey {name!r} not found")
    return journey


def _validate_input_type(input_type: str | None) -> None:
    if input_type is not None and input_type not in _INPUT_TYPES:
        raise ValueError(
            f"unknown input_type {input_type!r}; expected one of {', '.join(_INPUT_TYPES)}"
        )


# --------------------------------------------------------------------------- #
# templates


async def list_journeys(
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> list[dict[str, Any]]:
    """Every journey bundle (template + ordered beats + tags), default first."""
    store = _storage(storage, db)
    return await store.list_journeys()


async def create_journey(
    *,
    name: str,
    label_uk: str,
    label_en: str,
    is_default: bool = False,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> dict[str, Any]:
    """Create a journey template. Rejects a blank/duplicate name. When
    `is_default` is set, the previous default is cleared first so exactly one
    template stays default."""
    name = name.strip()
    if not name:
        raise ValueError("name is required")
    if not label_uk.strip() or not label_en.strip():
        raise ValueError("label_uk and label_en are required")
    store = _storage(storage, db)
    if await store.fetch_journey_by_name(name=name) is not None:
        raise ValueError(f"journey {name!r} already exists")
    if is_default:
        await store.unset_default_journeys()
    return await store.insert_journey(
        payload={
            "name": name,
            "label_uk": label_uk.strip(),
            "label_en": label_en.strip(),
            "is_default": is_default,
        }
    )


async def update_journey(
    *,
    name: str,
    label_uk: str | None = None,
    label_en: str | None = None,
    is_default: bool | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> dict[str, Any]:
    """Patch a template's labels and/or default flag. Setting `is_default=True`
    clears the previous default; `is_default=False` is rejected (a template
    cannot un-default itself — promote another one instead)."""
    store = _storage(storage, db)
    await _require_template(store, name)

    patch: dict[str, Any] = {}
    if label_uk is not None:
        if not label_uk.strip():
            raise ValueError("label_uk cannot be blank")
        patch["label_uk"] = label_uk.strip()
    if label_en is not None:
        if not label_en.strip():
            raise ValueError("label_en cannot be blank")
        patch["label_en"] = label_en.strip()
    if is_default is not None:
        if is_default is False:
            raise ValueError("cannot unset default; promote another journey instead")
        patch["is_default"] = True
    if not patch:
        raise ValueError("nothing to update")

    if patch.get("is_default"):
        await store.unset_default_journeys(except_name=name)
    rows = await store.update_journey_template(name=name, patch=patch)
    if not rows:
        raise LookupError(f"journey {name!r} not found")
    return rows[0]


async def delete_journey(
    *,
    name: str,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> None:
    """Delete a template (FK-cascades its beats + tags). Refuses to delete the
    default journey (reassign default first) or one still referenced by any
    session — both raise ValueError so the HTTP layer maps them to 400."""
    store = _storage(storage, db)
    journey = await _require_template(store, name)
    if journey["template"].get("is_default"):
        raise ValueError("cannot delete the default journey; promote another one first")
    refs = await store.count_sessions_for_journey(name=name)
    if refs > 0:
        raise ValueError(f"journey {name!r} is referenced by {refs} session(s)")
    await store.delete_journey_template(name=name)


# --------------------------------------------------------------------------- #
# beats


async def upsert_journey_beat(
    *,
    journey_name: str,
    beat_key: str,
    position: int | None = None,
    label_uk: str | None = None,
    label_en: str | None = None,
    icon: str | None = None,
    input_type: str | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> dict[str, Any]:
    """Insert-or-update a beat on a journey, keyed by (journey, beat_key).
    `input_type` must be one of mood_slider / chip_pick / yes_no when set."""
    beat_key = beat_key.strip()
    if not beat_key:
        raise ValueError("beat_key is required")
    _validate_input_type(input_type)
    store = _storage(storage, db)
    journey = await _require_template(store, journey_name)
    template_id = str(journey["template"]["id"])

    patch: dict[str, Any] = {}
    if position is not None:
        patch["position"] = position
    if label_uk is not None:
        patch["label_uk"] = label_uk
    if label_en is not None:
        patch["label_en"] = label_en
    if icon is not None:
        patch["icon"] = icon
    if input_type is not None:
        patch["input_type"] = input_type
    if not patch:
        raise ValueError("nothing to update")

    return await store.upsert_journey_beat(template_id=template_id, beat_key=beat_key, patch=patch)


async def delete_journey_beat(
    *,
    journey_name: str,
    beat_key: str,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> None:
    """Delete a beat from a journey (FK-cascades its tags). Raises LookupError
    when the journey or the beat does not exist."""
    store = _storage(storage, db)
    journey = await _require_template(store, journey_name)
    template_id = str(journey["template"]["id"])
    rows = await store.delete_journey_beat(template_id=template_id, beat_key=beat_key)
    if not rows:
        raise LookupError(f"beat {beat_key!r} not found in journey {journey_name!r}")


# --------------------------------------------------------------------------- #
# tags


def _beat_id_for_key(journey: dict[str, Any], beat_key: str) -> str:
    for beat in journey.get("beats", []):
        if beat.get("beat_key") == beat_key:
            return str(beat["id"])
    raise LookupError(f"beat {beat_key!r} not found in journey")


async def upsert_beat_tag(
    *,
    journey_name: str,
    beat_key: str,
    tag_key: str,
    position: int | None = None,
    label_uk: str | None = None,
    label_en: str | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> dict[str, Any]:
    """Insert-or-update a chip tag on a beat, keyed by (beat, tag_key)."""
    tag_key = tag_key.strip()
    if not tag_key:
        raise ValueError("tag_key is required")
    store = _storage(storage, db)
    journey = await _require_template(store, journey_name)
    beat_id = _beat_id_for_key(journey, beat_key)

    patch: dict[str, Any] = {}
    if position is not None:
        patch["position"] = position
    if label_uk is not None:
        patch["label_uk"] = label_uk
    if label_en is not None:
        patch["label_en"] = label_en
    if not patch:
        raise ValueError("nothing to update")

    return await store.upsert_beat_tag(beat_id=beat_id, tag_key=tag_key, patch=patch)


async def delete_beat_tag(
    *,
    journey_name: str,
    beat_key: str,
    tag_key: str,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> None:
    """Delete a chip tag from a beat. Raises LookupError when the journey, beat,
    or tag does not exist."""
    store = _storage(storage, db)
    journey = await _require_template(store, journey_name)
    beat_id = _beat_id_for_key(journey, beat_key)
    rows = await store.delete_beat_tag(beat_id=beat_id, tag_key=tag_key)
    if not rows:
        raise LookupError(f"tag {tag_key!r} not found on beat {beat_key!r}")
