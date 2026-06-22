"""StorageAdapter Protocol — the boundary between business logic and persistence.

R2 design (M1): `core/services/*` and `core/tools/*` no longer call Supabase
directly. They depend on this Protocol and receive a concrete adapter
(`core/storage/adapters/supabase.SupabaseStorage` in production) via DI.

Granularity is *data-access*, not domain: methods fetch/mutate rows and return
plain `dict`/`list[dict]`. All aggregation (sentiment scoring, topic
histograms, metric summaries) stays in the services — storage holds no business
logic. A different backend (Postgres, Iiko, Bitrix) implements the same
Protocol by returning equivalently-shaped rows.

Rows are returned as loosely-typed `dict[str, Any]` (the shape mirrors
`core/storage/migrations/0001_init.sql`); the TypedDicts below document the
common shapes without forcing every adapter to construct them exactly.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol
from uuid import UUID

Role = Literal["user", "bot"]
FeedbackSource = Literal["text", "voice"]
WebFeedbackSource = Literal["web", "web_anon"]


class StorageAdapter(Protocol):
    # ─── clients ───
    async def get_client(self, telegram_id: int) -> dict[str, Any] | None: ...
    async def insert_client(self, *, telegram_id: int, name: str | None) -> dict[str, Any]: ...
    async def search_clients_by_name(self, *, pattern: str, limit: int) -> list[dict[str, Any]]:
        """Clients whose name matches the ilike `pattern` (caller wraps `%`)."""
        ...

    async def fetch_clients_by_ids(
        self, *, telegram_ids: list[int], columns: str
    ) -> list[dict[str, Any]]:
        """Clients for the given telegram_ids (batch name/metadata lookup)."""
        ...

    # ─── admin_users ───
    async def is_admin(self, telegram_id: int) -> bool: ...
    async def count_admins(self) -> int: ...
    async def insert_admin(
        self, *, telegram_id: int, name: str | None = None, invited_by: int | None = None
    ) -> None: ...

    # ─── admin_settings ───
    async def get_admin_settings(self, telegram_id: int) -> dict[str, Any] | None: ...
    async def upsert_admin_settings(
        self, *, telegram_id: int, patch: dict[str, Any]
    ) -> dict[str, Any]: ...

    # ─── questions ───
    async def list_questions(self, *, active_only: bool) -> list[dict[str, Any]]: ...
    async def find_questions_by_text(
        self, *, pattern: str, active_only: bool
    ) -> list[dict[str, Any]]: ...
    async def get_question_by_metric_key(self, metric_key: str) -> dict[str, Any] | None: ...
    async def insert_question(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def update_question(
        self, question_id: str | UUID, patch: dict[str, Any]
    ) -> list[dict[str, Any]]: ...
    async def deactivate_questions(
        self, *, restaurant_id: str | None = None
    ) -> list[dict[str, Any]]: ...

    # ─── sessions ───
    async def insert_session(self, *, client_id: int) -> dict[str, Any]: ...
    async def update_session(
        self, session_id: str | UUID, patch: dict[str, Any]
    ) -> list[dict[str, Any]]: ...
    async def insert_session_message(
        self, *, session_id: str | UUID, role: Role, content: str
    ) -> dict[str, Any]: ...
    async def fetch_session_messages(
        self, *, session_id: str | UUID, columns: str
    ) -> list[dict[str, Any]]:
        """Transcript rows for one session, ordered by created_at asc."""
        ...

    async def fetch_sessions_with_feedback(
        self, *, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        """Sessions in [date_from, date_to] whose feedback_summary is not null."""
        ...

    async def fetch_sessions_in_window(
        self, *, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        """Sessions in [date_from, date_to] (no feedback_summary filter)."""
        ...

    async def fetch_sessions_in_window_ordered(
        self, *, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        """Sessions in [date_from, date_to], ordered by started_at desc."""
        ...

    async def fetch_recent_sessions(self, *, columns: str, limit: int) -> list[dict[str, Any]]:
        """Latest sessions ordered by started_at desc, capped at `limit`."""
        ...

    async def fetch_sessions_by_ids(
        self, *, session_ids: list[str], columns: str
    ) -> list[dict[str, Any]]: ...
    async def fetch_sessions_for_client(
        self, *, client_id: int, columns: str, order_desc: bool = True
    ) -> list[dict[str, Any]]: ...
    async def earliest_session_started_at(self) -> str | None: ...

    # ─── session_answers ───
    async def insert_answer(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def fetch_answers_for_question(
        self,
        *,
        question_id: str,
        date_from: str,
        date_to: str,
        columns: str,
    ) -> list[dict[str, Any]]: ...
    async def fetch_answers_for_sessions(
        self,
        *,
        session_ids: list[str],
        question_ids: list[str],
        columns: str,
    ) -> list[dict[str, Any]]: ...

    # ─── client_cards ───
    async def insert_client_card(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def fetch_cards_by_sessions(
        self, *, session_ids: list[str], columns: str
    ) -> list[dict[str, Any]]: ...
    async def fetch_recent_cards(self, *, columns: str, limit: int) -> list[dict[str, Any]]: ...
    async def fetch_cards_for_client(
        self, *, client_id: int, columns: str, limit: int
    ) -> list[dict[str, Any]]: ...

    # ─── guest journey (web app) ───
    async def fetch_default_journey(self) -> dict[str, Any] | None:
        """Default journey bundle: `{template: {...}, beats: [{...beat..., tags: [...]}]}`
        ordered by `position`; `None` if no template is marked default."""
        ...

    async def fetch_journey_by_name(self, *, name: str) -> dict[str, Any] | None:
        """Journey bundle for a named template (e.g. `'delivery'`), same shape as
        `fetch_default_journey`; `None` if no template has that name."""
        ...

    async def list_journeys(self) -> list[dict[str, Any]]:
        """Every journey bundle (template + ordered beats + tags), ordered with
        the default first, then by name."""
        ...

    async def insert_journey(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert a journey_templates row and return it. Caller guarantees the
        single-default invariant (unsets the previous default first)."""
        ...

    async def update_journey_template(
        self, *, name: str, patch: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Patch a journey_templates row by name. Returns updated rows (empty
        when no template has that name)."""
        ...

    async def unset_default_journeys(self, *, except_name: str | None = None) -> None:
        """Clear `is_default` on every template (optionally keeping `except_name`)
        so a new default can be set without violating the single-default index."""
        ...

    async def delete_journey_template(self, *, name: str) -> list[dict[str, Any]]:
        """Delete a journey_templates row by name (FK-cascades beats + tags).
        Returns the deleted rows (empty when none matched)."""
        ...

    async def count_sessions_for_journey(self, *, name: str) -> int:
        """How many sessions reference this template by `journey_template_name`
        (delete guard)."""
        ...

    async def upsert_journey_beat(
        self, *, template_id: str | UUID, beat_key: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        """Insert-or-update a journey_beats row keyed by (template_id, beat_key).
        `patch` may include position/label_uk/label_en/icon/input_type."""
        ...

    async def delete_journey_beat(
        self, *, template_id: str | UUID, beat_key: str
    ) -> list[dict[str, Any]]:
        """Delete a journey_beats row by (template_id, beat_key); FK-cascades its
        tags. Returns the deleted rows."""
        ...

    async def upsert_beat_tag(
        self, *, beat_id: str | UUID, tag_key: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        """Insert-or-update a beat_tags row keyed by (beat_id, tag_key). `patch`
        may include position/label_uk/label_en."""
        ...

    async def delete_beat_tag(self, *, beat_id: str | UUID, tag_key: str) -> list[dict[str, Any]]:
        """Delete a beat_tags row by (beat_id, tag_key). Returns the deleted rows."""
        ...

    async def insert_web_session(
        self,
        *,
        client_id: int | None,
        journey_template_name: str | None = None,
        mode: str = "non_targeted",
        meal_occasion: str | None = None,
    ) -> dict[str, Any]:
        """Anonymous (`client_id=None`) or identified (`client_id=int`) web session.
        Sets `feedback_source` to `'web_anon'` or `'web'` respectively, and captures
        the journey/mode/meal_occasion context on the row."""
        ...

    async def upsert_session_beat(
        self, *, session_id: str | UUID, beat_id: str | UUID, patch: dict[str, Any]
    ) -> dict[str, Any]:
        """Insert-or-update a single beat for a session. `patch` may include
        `score`, `tags`, `skipped`."""
        ...

    async def fetch_session_beats(self, *, session_id: str | UUID) -> list[dict[str, Any]]: ...

    async def insert_session_dig(
        self,
        *,
        session_id: str | UUID,
        beat_id: str | UUID,
        guesses: list[dict[str, Any]],
    ) -> dict[str, Any]: ...

    async def fetch_session_dig(self, *, dig_id: str | UUID) -> dict[str, Any] | None: ...

    async def fetch_session_digs(self, *, session_id: str | UUID) -> list[dict[str, Any]]: ...

    async def update_session_dig(
        self, *, dig_id: str | UUID, patch: dict[str, Any]
    ) -> list[dict[str, Any]]: ...

    # ─── prize tiers (in-app prize config) ───
    async def fetch_prize_tiers(self) -> list[dict[str, Any]]:
        """All three prize-tier config rows (small/medium/large)."""
        ...

    async def fetch_prize_tier(self, *, tier: str) -> dict[str, Any] | None:
        """One prize-tier config row, or None if absent."""
        ...

    async def upsert_prize_tier(self, *, tier: str, patch: dict[str, Any]) -> dict[str, Any]:
        """Insert-or-update a prize-tier config row (code / label_uk / label_en)."""
        ...
