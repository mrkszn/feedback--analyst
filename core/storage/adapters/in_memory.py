"""InMemoryStorage — a Protocol-complete StorageAdapter backed by dicts.

R2 ships this as a stub for the eventual test migration off `_FakeDB` (that
migration is out of scope here, so the existing tests do NOT use this yet). It
implements every StorageAdapter method against in-memory tables with enough
behavior to back simple flows; aggregation lives in the services, so this layer
only stores and filters rows.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from core.storage.protocol import Role


class InMemoryStorage:
    def __init__(self) -> None:
        self.clients: list[dict[str, Any]] = []
        self.admin_users: list[dict[str, Any]] = []
        self.admin_settings: list[dict[str, Any]] = []
        self.questions: list[dict[str, Any]] = []
        self.sessions: list[dict[str, Any]] = []
        self.session_messages: list[dict[str, Any]] = []
        self.session_answers: list[dict[str, Any]] = []
        self.client_cards: list[dict[str, Any]] = []
        self.journey_templates: list[dict[str, Any]] = []
        self.journey_beats: list[dict[str, Any]] = []
        self.beat_tags: list[dict[str, Any]] = []
        self.session_beats: list[dict[str, Any]] = []
        self.session_digs: list[dict[str, Any]] = []
        self.prize_tiers: list[dict[str, Any]] = []
        self._serial = itertools.count(1)

    def _next_serial(self) -> int:
        return next(self._serial)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    # ───────────────────────────────────────── clients ──
    async def get_client(self, telegram_id: int) -> dict[str, Any] | None:
        return next((c for c in self.clients if c["telegram_id"] == telegram_id), None)

    async def insert_client(self, *, telegram_id: int, name: str | None) -> dict[str, Any]:
        if any(c["telegram_id"] == telegram_id for c in self.clients):
            raise ValueError("duplicate key value (23505)")
        row = {"telegram_id": telegram_id, "name": name, "created_at": self._now()}
        self.clients.append(row)
        return row

    async def search_clients_by_name(self, *, pattern: str, limit: int) -> list[dict[str, Any]]:
        needle = pattern.strip("%").lower()
        out = [c for c in self.clients if needle in str(c.get("name") or "").lower()]
        return out[:limit]

    async def fetch_clients_by_ids(
        self, *, telegram_ids: list[int], columns: str
    ) -> list[dict[str, Any]]:
        ids = set(telegram_ids)
        return [c for c in self.clients if c.get("telegram_id") in ids]

    # ───────────────────────────────────────── admin_users ──
    async def is_admin(self, telegram_id: int) -> bool:
        return any(a["telegram_id"] == telegram_id for a in self.admin_users)

    async def count_admins(self) -> int:
        return len(self.admin_users)

    async def insert_admin(
        self, *, telegram_id: int, name: str | None = None, invited_by: int | None = None
    ) -> None:
        if any(a["telegram_id"] == telegram_id for a in self.admin_users):
            raise ValueError("duplicate key value (23505)")
        self.admin_users.append(
            {
                "telegram_id": telegram_id,
                "name": name,
                "invited_by": invited_by,
                "created_at": self._now(),
            }
        )

    # ───────────────────────────────────────── admin_settings ──
    async def get_admin_settings(self, telegram_id: int) -> dict[str, Any] | None:
        return next((s for s in self.admin_settings if s["telegram_id"] == telegram_id), None)

    async def upsert_admin_settings(
        self, *, telegram_id: int, patch: dict[str, Any]
    ) -> dict[str, Any]:
        existing = next((s for s in self.admin_settings if s["telegram_id"] == telegram_id), None)
        if existing is not None:
            existing.update(patch)
            existing["updated_at"] = self._now()
            return existing
        row = {
            "telegram_id": telegram_id,
            "created_at": self._now(),
            "updated_at": self._now(),
            **patch,
        }
        self.admin_settings.append(row)
        return row

    # ───────────────────────────────────────── questions ──
    async def list_questions(self, *, active_only: bool) -> list[dict[str, Any]]:
        rows = [q for q in self.questions if (q.get("is_active", True) or not active_only)]
        return sorted(rows, key=lambda q: q.get("created_at") or "", reverse=True)

    async def find_questions_by_text(
        self, *, pattern: str, active_only: bool
    ) -> list[dict[str, Any]]:
        needle = pattern.strip("%").lower()
        out: list[dict[str, Any]] = []
        for q in self.questions:
            if active_only and not q.get("is_active", True):
                continue
            text = str(q.get("text") or "").lower()
            key = str(q.get("metric_key") or "").lower()
            if needle in text or needle in key:
                out.append(q)
        return out

    async def get_question_by_metric_key(self, metric_key: str) -> dict[str, Any] | None:
        return next((q for q in self.questions if q.get("metric_key") == metric_key), None)

    async def insert_question(self, payload: dict[str, Any]) -> dict[str, Any]:
        if any(q.get("metric_key") == payload.get("metric_key") for q in self.questions):
            raise ValueError("duplicate key value (23505)")
        row = {
            "id": str(uuid4()),
            "is_active": True,
            "created_at": self._now(),
            "updated_at": self._now(),
            **payload,
        }
        self.questions.append(row)
        return row

    async def update_question(
        self, question_id: str | UUID, patch: dict[str, Any]
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for q in self.questions:
            if str(q.get("id")) == str(question_id):
                q.update(patch)
                q["updated_at"] = self._now()
                updated.append(q)
        return updated

    async def deactivate_questions(
        self, *, restaurant_id: str | None = None
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for q in self.questions:
            if q.get("is_active", True):
                q["is_active"] = False
                updated.append(q)
        return updated

    # ───────────────────────────────────────── sessions ──
    async def insert_session(self, *, client_id: int) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": str(uuid4()),
            "client_id": client_id,
            "started_at": self._now(),
            "ended_at": None,
            "feedback_summary": None,
        }
        self.sessions.append(row)
        return row

    async def update_session(
        self, session_id: str | UUID, patch: dict[str, Any]
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for s in self.sessions:
            if str(s.get("id")) == str(session_id):
                s.update(patch)
                updated.append(s)
        return updated

    async def insert_session_message(
        self, *, session_id: str | UUID, role: Role, content: str
    ) -> dict[str, Any]:
        row = {
            "id": self._next_serial(),
            "session_id": str(session_id),
            "role": role,
            "content": content,
            "created_at": self._now(),
        }
        self.session_messages.append(row)
        return row

    async def fetch_session_messages(
        self, *, session_id: str | UUID, columns: str
    ) -> list[dict[str, Any]]:
        rows = [m for m in self.session_messages if str(m.get("session_id")) == str(session_id)]
        return sorted(rows, key=lambda m: str(m.get("created_at") or ""))

    def _sessions_in_window(self, date_from: str, date_to: str) -> list[dict[str, Any]]:
        return [s for s in self.sessions if date_from <= str(s.get("started_at") or "") <= date_to]

    async def fetch_sessions_with_feedback(
        self, *, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        return [
            s for s in self._sessions_in_window(date_from, date_to) if s.get("feedback_summary")
        ]

    async def fetch_sessions_in_window(
        self, *, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        return self._sessions_in_window(date_from, date_to)

    async def fetch_sessions_in_window_ordered(
        self, *, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        rows = self._sessions_in_window(date_from, date_to)
        return sorted(rows, key=lambda s: s.get("started_at") or "", reverse=True)

    async def fetch_recent_sessions(self, *, columns: str, limit: int) -> list[dict[str, Any]]:
        rows = sorted(self.sessions, key=lambda s: s.get("started_at") or "", reverse=True)
        return rows[:limit]

    async def fetch_sessions_by_ids(
        self, *, session_ids: list[str], columns: str
    ) -> list[dict[str, Any]]:
        ids = set(session_ids)
        return [s for s in self.sessions if str(s.get("id")) in ids]

    async def fetch_sessions_for_client(
        self, *, client_id: int, columns: str, order_desc: bool = True
    ) -> list[dict[str, Any]]:
        rows = [s for s in self.sessions if s.get("client_id") == client_id]
        return sorted(rows, key=lambda s: s.get("started_at") or "", reverse=order_desc)

    async def earliest_session_started_at(self) -> str | None:
        starts = [str(s.get("started_at")) for s in self.sessions if s.get("started_at")]
        return min(starts) if starts else None

    # ───────────────────────────────────────── session_answers ──
    async def insert_answer(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"id": self._next_serial(), "created_at": self._now(), **payload}
        self.session_answers.append(row)
        return row

    async def fetch_answers_for_question(
        self, *, question_id: str, date_from: str, date_to: str, columns: str
    ) -> list[dict[str, Any]]:
        return [
            a
            for a in self.session_answers
            if str(a.get("question_id")) == str(question_id)
            and date_from <= str(a.get("created_at") or "") <= date_to
        ]

    async def fetch_answers_for_sessions(
        self, *, session_ids: list[str], question_ids: list[str], columns: str
    ) -> list[dict[str, Any]]:
        sids = set(session_ids)
        qids = set(question_ids)
        return [
            a
            for a in self.session_answers
            if str(a.get("session_id")) in sids and str(a.get("question_id")) in qids
        ]

    # ───────────────────────────────────────── client_cards ──
    async def insert_client_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        if any(c.get("session_id") == payload.get("session_id") for c in self.client_cards):
            raise ValueError("duplicate key value (23505)")
        row = {"id": str(uuid4()), "created_at": self._now(), **payload}
        self.client_cards.append(row)
        return row

    async def fetch_cards_by_sessions(
        self, *, session_ids: list[str], columns: str
    ) -> list[dict[str, Any]]:
        ids = set(session_ids)
        return [c for c in self.client_cards if str(c.get("session_id")) in ids]

    async def fetch_recent_cards(self, *, columns: str, limit: int) -> list[dict[str, Any]]:
        rows = sorted(self.client_cards, key=lambda c: c.get("created_at") or "", reverse=True)
        return rows[:limit]

    async def fetch_cards_for_client(
        self, *, client_id: int, columns: str, limit: int
    ) -> list[dict[str, Any]]:
        rows = [c for c in self.client_cards if c.get("client_id") == client_id]
        rows.sort(key=lambda c: c.get("created_at") or "", reverse=True)
        return rows[:limit]

    # ───────────────────────────────────────── guest journey (web app) ──
    def _journey_bundle(self, template: dict[str, Any]) -> dict[str, Any]:
        beats = sorted(
            (b for b in self.journey_beats if str(b.get("template_id")) == str(template["id"])),
            key=lambda b: int(b.get("position") or 0),
        )
        out_beats: list[dict[str, Any]] = []
        for beat in beats:
            tags = sorted(
                (t for t in self.beat_tags if str(t.get("beat_id")) == str(beat["id"])),
                key=lambda t: int(t.get("position") or 0),
            )
            out_beats.append({**beat, "tags": list(tags)})
        return {"template": dict(template), "beats": out_beats}

    async def fetch_default_journey(self) -> dict[str, Any] | None:
        template = next((t for t in self.journey_templates if t.get("is_default")), None)
        if template is None:
            return None
        return self._journey_bundle(template)

    async def fetch_journey_by_name(self, *, name: str) -> dict[str, Any] | None:
        template = next((t for t in self.journey_templates if t.get("name") == name), None)
        if template is None:
            return None
        return self._journey_bundle(template)

    async def list_journeys(self) -> list[dict[str, Any]]:
        templates = sorted(
            self.journey_templates,
            key=lambda t: (not t.get("is_default"), str(t.get("name") or "")),
        )
        return [self._journey_bundle(t) for t in templates]

    async def insert_journey(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": str(uuid4()),
            "is_default": False,
            "created_at": self._now(),
            **payload,
        }
        self.journey_templates.append(row)
        return dict(row)

    async def update_journey_template(
        self, *, name: str, patch: dict[str, Any]
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for tpl in self.journey_templates:
            if tpl.get("name") == name:
                tpl.update(patch)
                updated.append(dict(tpl))
        return updated

    async def unset_default_journeys(self, *, except_name: str | None = None) -> None:
        for tpl in self.journey_templates:
            if tpl.get("name") != except_name:
                tpl["is_default"] = False

    async def delete_journey_template(self, *, name: str) -> list[dict[str, Any]]:
        deleted = [dict(t) for t in self.journey_templates if t.get("name") == name]
        if not deleted:
            return []
        removed_ids = {str(t["id"]) for t in deleted}
        self.journey_templates = [t for t in self.journey_templates if t.get("name") != name]
        beat_ids = {
            str(b["id"]) for b in self.journey_beats if str(b.get("template_id")) in removed_ids
        }
        self.journey_beats = [
            b for b in self.journey_beats if str(b.get("template_id")) not in removed_ids
        ]
        self.beat_tags = [t for t in self.beat_tags if str(t.get("beat_id")) not in beat_ids]
        return deleted

    async def count_sessions_for_journey(self, *, name: str) -> int:
        return sum(1 for s in self.sessions if s.get("journey_template_name") == name)

    async def upsert_journey_beat(
        self, *, template_id: str | UUID, beat_key: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        existing = next(
            (
                b
                for b in self.journey_beats
                if str(b.get("template_id")) == str(template_id) and b.get("beat_key") == beat_key
            ),
            None,
        )
        if existing is not None:
            existing.update(patch)
            return dict(existing)
        row: dict[str, Any] = {
            "id": str(uuid4()),
            "template_id": str(template_id),
            "beat_key": beat_key,
            "position": 0,
            "label_uk": "",
            "label_en": "",
            "icon": "",
            "input_type": "mood_slider",
            "created_at": self._now(),
            **patch,
        }
        self.journey_beats.append(row)
        return dict(row)

    async def delete_journey_beat(
        self, *, template_id: str | UUID, beat_key: str
    ) -> list[dict[str, Any]]:
        deleted = [
            dict(b)
            for b in self.journey_beats
            if str(b.get("template_id")) == str(template_id) and b.get("beat_key") == beat_key
        ]
        if not deleted:
            return []
        removed_ids = {str(b["id"]) for b in deleted}
        self.journey_beats = [
            b
            for b in self.journey_beats
            if not (str(b.get("template_id")) == str(template_id) and b.get("beat_key") == beat_key)
        ]
        self.beat_tags = [t for t in self.beat_tags if str(t.get("beat_id")) not in removed_ids]
        return deleted

    async def upsert_beat_tag(
        self, *, beat_id: str | UUID, tag_key: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        existing = next(
            (
                t
                for t in self.beat_tags
                if str(t.get("beat_id")) == str(beat_id) and t.get("tag_key") == tag_key
            ),
            None,
        )
        if existing is not None:
            existing.update(patch)
            return dict(existing)
        row: dict[str, Any] = {
            "id": str(uuid4()),
            "beat_id": str(beat_id),
            "tag_key": tag_key,
            "position": 0,
            "label_uk": "",
            "label_en": "",
            **patch,
        }
        self.beat_tags.append(row)
        return dict(row)

    async def delete_beat_tag(self, *, beat_id: str | UUID, tag_key: str) -> list[dict[str, Any]]:
        deleted = [
            dict(t)
            for t in self.beat_tags
            if str(t.get("beat_id")) == str(beat_id) and t.get("tag_key") == tag_key
        ]
        if not deleted:
            return []
        self.beat_tags = [
            t
            for t in self.beat_tags
            if not (str(t.get("beat_id")) == str(beat_id) and t.get("tag_key") == tag_key)
        ]
        return deleted

    async def insert_web_session(
        self,
        *,
        client_id: int | None,
        journey_template_name: str | None = None,
        mode: str = "non_targeted",
        meal_occasion: str | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": str(uuid4()),
            "client_id": client_id,
            "feedback_source": "web" if client_id is not None else "web_anon",
            "mode": mode,
            "journey_template_name": journey_template_name,
            "meal_occasion": meal_occasion,
            "started_at": self._now(),
            "ended_at": None,
            "feedback_summary": None,
        }
        self.sessions.append(row)
        return row

    async def upsert_session_beat(
        self, *, session_id: str | UUID, beat_id: str | UUID, patch: dict[str, Any]
    ) -> dict[str, Any]:
        existing = next(
            (
                b
                for b in self.session_beats
                if str(b.get("session_id")) == str(session_id)
                and str(b.get("beat_id")) == str(beat_id)
            ),
            None,
        )
        if existing is not None:
            existing.update(patch)
            existing["updated_at"] = self._now()
            return existing
        row = {
            "session_id": str(session_id),
            "beat_id": str(beat_id),
            "score": None,
            "tags": [],
            "skipped": False,
            "updated_at": self._now(),
            **patch,
        }
        self.session_beats.append(row)
        return row

    async def fetch_session_beats(self, *, session_id: str | UUID) -> list[dict[str, Any]]:
        return [b for b in self.session_beats if str(b.get("session_id")) == str(session_id)]

    async def insert_session_dig(
        self,
        *,
        session_id: str | UUID,
        beat_id: str | UUID,
        guesses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "session_id": str(session_id),
            "beat_id": str(beat_id),
            "guesses": list(guesses),
            "accepted_guess_id": None,
            "free_text": None,
            "voice_object_key": None,
            "created_at": self._now(),
        }
        self.session_digs.append(row)
        return row

    async def fetch_session_dig(self, *, dig_id: str | UUID) -> dict[str, Any] | None:
        return next((d for d in self.session_digs if str(d.get("id")) == str(dig_id)), None)

    async def fetch_session_digs(self, *, session_id: str | UUID) -> list[dict[str, Any]]:
        rows = [d for d in self.session_digs if str(d.get("session_id")) == str(session_id)]
        return sorted(rows, key=lambda d: str(d.get("created_at") or ""))

    async def update_session_dig(
        self, *, dig_id: str | UUID, patch: dict[str, Any]
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for dig in self.session_digs:
            if str(dig.get("id")) == str(dig_id):
                dig.update(patch)
                updated.append(dig)
        return updated

    # ───────────────────────────────────────── prize tiers ──
    async def fetch_prize_tiers(self) -> list[dict[str, Any]]:
        return [dict(p) for p in self.prize_tiers]

    async def fetch_prize_tier(self, *, tier: str) -> dict[str, Any] | None:
        return next((dict(p) for p in self.prize_tiers if p.get("tier") == tier), None)

    async def upsert_prize_tier(self, *, tier: str, patch: dict[str, Any]) -> dict[str, Any]:
        existing = next((p for p in self.prize_tiers if p.get("tier") == tier), None)
        if existing is not None:
            existing.update(patch)
            existing["updated_at"] = self._now()
            return dict(existing)
        row = {
            "tier": tier,
            "code": "",
            "label_uk": "",
            "label_en": "",
            "updated_at": self._now(),
            **patch,
        }
        self.prize_tiers.append(row)
        return dict(row)
