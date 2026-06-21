"""Guest journey service — anonymous web-app "вечер як стрічка" flow.

Wires the new public-guest-webapp UX through the storage adapter and the
existing analyze node:

  start anonymous web session
  → fetch default journey (template + ordered beats + tags)
  → save per-beat score / tags / skip flag
  → on a weak beat: ask the dig LLM node for guess cards, record reply
  → finalize: synthesize a free-form feedback string from the beat ribbon,
    pipe it into analyze_feedback, persist on the session row.

DI follows the other services: every public function takes `storage` /
`db` for testability. No business logic in storage; no Supabase calls here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import UUID

from supabase import Client

from core.agent.nodes.analyze import analyze_feedback
from core.agent.nodes.dig import dig_guesses_for_beat
from core.storage.adapters.supabase import SupabaseStorage
from core.storage.protocol import StorageAdapter

_WEB_SOURCES = ("web", "web_anon")


class BeatState(TypedDict):
    beat_id: str
    score: int | None
    tags: list[str]
    skipped: bool


class DigState(TypedDict):
    id: str
    beat_id: str
    guesses: list[dict[str, str]]
    accepted_guess_id: str | None
    free_text: str | None


class SessionState(TypedDict):
    session_id: str
    feedback_source: str
    started_at: str | None
    ended_at: str | None
    beats: list[BeatState]
    digs: list[DigState]


def _storage(storage: StorageAdapter | None, db: Client | None) -> StorageAdapter:
    return storage or SupabaseStorage(db)


async def _load_web_session(store: StorageAdapter, session_id: str | UUID) -> dict[str, Any]:
    rows = await store.fetch_sessions_by_ids(
        session_ids=[str(session_id)],
        columns=(
            "id, client_id, started_at, ended_at, feedback_source, language, "
            "journey_template_name, mode, meal_occasion"
        ),
    )
    if not rows:
        raise LookupError(f"session {session_id} not found")
    row = rows[0]
    if row.get("feedback_source") not in _WEB_SOURCES:
        raise LookupError(f"session {session_id} is not a web session")
    return row


async def _journey_for_session(store: StorageAdapter, row: dict[str, Any]) -> dict[str, Any]:
    """Resolve the journey bundle the session walked. Uses the session's
    `journey_template_name` when set, otherwise the default; falls back to the
    default if the named template no longer exists. Raises if nothing is
    configured."""
    name = row.get("journey_template_name")
    journey = (
        await store.fetch_journey_by_name(name=str(name))
        if name
        else await store.fetch_default_journey()
    )
    if journey is None:
        journey = await store.fetch_default_journey()
    if journey is None:
        raise LookupError("no journey configured")
    return journey


def _beat_state(row: dict[str, Any]) -> BeatState:
    tags = row.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return BeatState(
        beat_id=str(row.get("beat_id")),
        score=int(row["score"]) if row.get("score") is not None else None,
        tags=[str(t) for t in tags],
        skipped=bool(row.get("skipped", False)),
    )


def _dig_state(row: dict[str, Any]) -> DigState:
    guesses = row.get("guesses") or []
    if not isinstance(guesses, list):
        guesses = []
    return DigState(
        id=str(row["id"]),
        beat_id=str(row.get("beat_id")),
        guesses=[dict(g) for g in guesses if isinstance(g, dict)],
        accepted_guess_id=row.get("accepted_guess_id"),
        free_text=row.get("free_text"),
    )


# --------------------------------------------------------------------------- #
# journey + session lifecycle


async def get_default_journey(
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> dict[str, Any] | None:
    """Default journey bundle (template + ordered beats + tags), as the
    frontend's GET /guest/journey expects. None if no template is marked
    default in the DB."""
    store = _storage(storage, db)
    return await store.fetch_default_journey()


async def get_journey(
    name: str | None = None,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> dict[str, Any] | None:
    """Journey bundle for `name` (e.g. `'delivery'`), or the default journey
    when `name` is None. None if the requested template does not exist."""
    store = _storage(storage, db)
    if name is None:
        return await store.fetch_default_journey()
    return await store.fetch_journey_by_name(name=name)


async def start_anonymous_session(
    journey: str = "restaurant",
    mode: str = "non_targeted",
    meal_occasion: str | None = None,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> str:
    """Create a new anonymous web session and return its id. Captures the
    journey/mode/meal_occasion context on the row. `meal_occasion` is only
    meaningful for the restaurant journey — it is dropped for delivery."""
    store = _storage(storage, db)
    occasion = meal_occasion if journey == "restaurant" else None
    row = await store.insert_web_session(
        client_id=None,
        journey_template_name=journey,
        mode=mode,
        meal_occasion=occasion,
    )
    return str(row["id"])


async def restore_session(
    session_id: str | UUID,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> SessionState:
    """Snapshot of the session for UI restore: which beats are scored, which
    digs have been asked. Raises LookupError if the session does not exist
    or is not a web session."""
    store = _storage(storage, db)
    row = await _load_web_session(store, session_id)
    beats = await store.fetch_session_beats(session_id=session_id)
    digs = await store.fetch_session_digs(session_id=session_id)
    return SessionState(
        session_id=str(row["id"]),
        feedback_source=str(row.get("feedback_source") or ""),
        started_at=str(row["started_at"]) if row.get("started_at") else None,
        ended_at=str(row["ended_at"]) if row.get("ended_at") else None,
        beats=[_beat_state(b) for b in beats],
        digs=[_dig_state(d) for d in digs],
    )


# --------------------------------------------------------------------------- #
# per-beat input


async def save_beat(
    session_id: str | UUID,
    beat_id: str | UUID,
    *,
    score: int | None = None,
    tags: list[str] | None = None,
    skipped: bool | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> BeatState:
    """Upsert one beat for a session. At least one of score/tags/skipped
    must be provided; score must be 1..5 if set."""
    if score is None and tags is None and skipped is None:
        raise ValueError("at least one of score/tags/skipped must be set")
    if score is not None and not (1 <= score <= 5):
        raise ValueError(f"score must be 1..5, got {score}")

    store = _storage(storage, db)
    await _load_web_session(store, session_id)

    patch: dict[str, Any] = {}
    if score is not None:
        patch["score"] = score
    if tags is not None:
        patch["tags"] = list(tags)
    if skipped is not None:
        patch["skipped"] = bool(skipped)

    row = await store.upsert_session_beat(session_id=session_id, beat_id=beat_id, patch=patch)
    return _beat_state(row)


# --------------------------------------------------------------------------- #
# AI dig: surface 2–3 guess cards for a weak beat, record the guest's reaction


def _beat_label(journey: dict[str, Any], beat_id: str) -> tuple[str, list[str]]:
    """Return (uk label, tag_keys) for a beat in the journey bundle."""
    for beat in journey.get("beats", []):
        if str(beat.get("id")) == str(beat_id):
            label = str(beat.get("label_uk") or beat.get("beat_key") or "")
            tags = [str(t.get("tag_key") or "") for t in beat.get("tags") or []]
            return label, [t for t in tags if t]
    return "", []


async def dig_for_beat(
    session_id: str | UUID,
    beat_id: str | UUID,
    *,
    restaurant_context: str = "",
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> DigState:
    """Generate guess cards for a beat and persist a session_digs row.

    Reads the current score + tags the guest already picked on this beat to
    feed the LLM; falls back to score=3 if none recorded yet."""
    store = _storage(storage, db)
    row = await _load_web_session(store, session_id)

    journey = await _journey_for_session(store, row)
    label, _ = _beat_label(journey, str(beat_id))
    if not label:
        raise LookupError(f"beat {beat_id} not part of the default journey")

    beats = await store.fetch_session_beats(session_id=session_id)
    current = next((b for b in beats if str(b.get("beat_id")) == str(beat_id)), None)
    score = int(current["score"]) if current and current.get("score") is not None else 3
    tags_raw = current.get("tags") if current else None
    tags = [str(t) for t in tags_raw] if isinstance(tags_raw, list) else []

    guesses = await dig_guesses_for_beat(
        beat_label=label,
        score=score,
        tags=tags,
        restaurant_context=restaurant_context,
    )
    row = await store.insert_session_dig(session_id=session_id, beat_id=beat_id, guesses=guesses)
    return _dig_state(row)


async def record_dig_answer(
    session_id: str | UUID,
    dig_id: str | UUID,
    *,
    accepted_guess_id: str | None = None,
    free_text: str | None = None,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> DigState:
    """Record the guest's reaction to a dig. Exactly one of accepted_guess_id
    or free_text must be set."""
    if (accepted_guess_id is None) == (free_text is None):
        raise ValueError("exactly one of accepted_guess_id or free_text must be set")

    store = _storage(storage, db)
    await _load_web_session(store, session_id)

    dig = await store.fetch_session_dig(dig_id=dig_id)
    if dig is None or str(dig.get("session_id")) != str(session_id):
        raise LookupError(f"dig {dig_id} not found for this session")

    if accepted_guess_id is not None:
        guesses = dig.get("guesses") or []
        ids = {str(g.get("id")) for g in guesses if isinstance(g, dict)}
        if accepted_guess_id not in ids:
            raise ValueError(f"guess {accepted_guess_id!r} not in this dig")

    patch: dict[str, Any] = {
        "accepted_guess_id": accepted_guess_id,
        "free_text": free_text,
    }
    rows = await store.update_session_dig(dig_id=dig_id, patch=patch)
    if not rows:
        raise LookupError(f"dig {dig_id} not found")
    return _dig_state(rows[0])


# --------------------------------------------------------------------------- #
# finalize: synthesize a free-form feedback string and run it through analyze


def _synthesize_feedback_text(
    journey: dict[str, Any],
    beats: list[dict[str, Any]],
    digs: list[dict[str, Any]],
) -> str:
    """Render the beat ribbon + dig answers as a natural-language paragraph
    that the existing analyze node can consume."""
    beat_by_id = {str(b["id"]): b for b in journey.get("beats", [])}
    dig_lines_by_beat: dict[str, list[str]] = {}
    for dig in digs:
        beat_id = str(dig.get("beat_id"))
        guesses = dig.get("guesses") or []
        accepted = dig.get("accepted_guess_id")
        text = dig.get("free_text")
        if accepted is not None:
            picked = next(
                (
                    str(g.get("text_uk") or g.get("text_en") or "")
                    for g in guesses
                    if isinstance(g, dict) and str(g.get("id")) == str(accepted)
                ),
                "",
            )
            if picked:
                dig_lines_by_beat.setdefault(beat_id, []).append(picked)
        elif text:
            dig_lines_by_beat.setdefault(beat_id, []).append(str(text))

    sorted_beats = sorted(
        beats,
        key=lambda b: int(beat_by_id.get(str(b.get("beat_id")), {}).get("position") or 0),
    )
    parts: list[str] = []
    for beat in sorted_beats:
        meta = beat_by_id.get(str(beat.get("beat_id")))
        if meta is None:
            continue
        label = str(meta.get("label_uk") or meta.get("beat_key") or "")
        if beat.get("skipped"):
            parts.append(f"{label}: пропущено.")
            continue
        score = beat.get("score")
        score_text = f"{score}/5" if score is not None else "-"
        tag_keys = beat.get("tags") or []
        tag_labels: list[str] = []
        if isinstance(tag_keys, list):
            tag_meta = {
                str(t.get("tag_key")): str(t.get("label_uk") or "") for t in meta.get("tags") or []
            }
            tag_labels = [tag_meta[str(k)] for k in tag_keys if str(k) in tag_meta]
        segment = f"{label}: {score_text}"
        if tag_labels:
            segment += f" ({', '.join(tag_labels)})"
        digs_here = dig_lines_by_beat.get(str(beat.get("beat_id")))
        if digs_here:
            segment += f" — гість додав: {' / '.join(digs_here)}"
        parts.append(segment + ".")
    return " ".join(parts) if parts else "Гість не залишив оцінок по етапах вечора."


async def finalize_session(
    session_id: str | UUID,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> None:
    """Synthesize the session's beat ribbon into feedback text, run it through
    `analyze_feedback`, persist summary + ended_at on the session row. No-op
    if the session is already finalized (`ended_at` is not null)."""
    store = _storage(storage, db)
    row = await _load_web_session(store, session_id)
    if row.get("ended_at"):
        return

    journey = await _journey_for_session(store, row)
    beats = await store.fetch_session_beats(session_id=session_id)
    digs = await store.fetch_session_digs(session_id=session_id)

    text = _synthesize_feedback_text(journey, beats, digs)
    summary = await analyze_feedback(text)

    patch: dict[str, Any] = {
        "feedback_raw_text": text,
        "feedback_summary": summary.model_dump(),
        "ended_at": datetime.now(UTC).isoformat(),
        "language": "uk",
    }
    await store.update_session(session_id, patch)
