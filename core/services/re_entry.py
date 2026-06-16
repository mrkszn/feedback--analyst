"""Returning-client re-entry context for the guest bot's first touch.

The bot greets a brand-new user and a loyal repeat customer identically today.
This service answers, cheaply and at intake, "have we heard from this person
before, and about what?" so the greeting can acknowledge a returning client
("С возвращением 🙌 …") instead of the generic WELCOME.

Why memory matters only here: a one-and-done form has nothing to remember.
Inside a *recurring* feedback loop, recognising the returner (a) cuts friction
on round 2+ and (b) makes the bot feel like an ongoing relationship, not a
fresh form each time.

Design:
- `load_reentry_context` wraps the existing `analytics.client_profile` and never
  raises for an unknown client (returns a first-timer context).
- Returning is gated on `sessions_count >= 1` — a `clients` row alone is NOT
  enough (the row is created on the very first contact, before any session).
- `reentry_greeting` is a pure function (easy to unit-test) and returns `None`
  for a first-timer so the caller falls back to the static WELCOME.
- Detection comes from the DB (via `client_profile`), not FSM — the in-memory
  FSM store is wiped on pod restart, so it can't be trusted for "returning".

Anti-creepy: we reference "в прошлый раз" + at most ONE topic, never echo the
raw client-card text verbatim.
"""

from __future__ import annotations

from typing import TypedDict

from supabase import Client

from core.services.analytics import client_profile
from core.storage.protocol import StorageAdapter


class ReEntryContext(TypedDict):
    is_returning: bool
    sessions_count: int
    last_session_at: str | None
    top_topic: str | None


_FIRST_TIMER: ReEntryContext = {
    "is_returning": False,
    "sessions_count": 0,
    "last_session_at": None,
    "top_topic": None,
}


async def load_reentry_context(
    telegram_id: int,
    *,
    storage: StorageAdapter | None = None,
    db: Client | None = None,
) -> ReEntryContext:
    """Return a returning-client context, or a first-timer context.

    Never raises for an unknown/first-time client. `recent_cards_limit=1`
    keeps the read light (the heavy part is fetching the client's sessions).
    """
    try:
        profile = await client_profile(telegram_id, recent_cards_limit=1, storage=storage, db=db)
    except LookupError:
        return _FIRST_TIMER

    sessions_count = int(profile.get("sessions_count") or 0)
    if sessions_count < 1:
        # Client row exists but no feedback session yet → treat as first-timer.
        return _FIRST_TIMER

    top_topics = profile.get("top_topics") or []
    top_topic = top_topics[0]["topic"] if top_topics else None

    return {
        "is_returning": True,
        "sessions_count": sessions_count,
        "last_session_at": profile.get("last_session_at"),
        "top_topic": top_topic,
    }


def reentry_greeting(ctx: ReEntryContext) -> str | None:
    """Warm greeting for a returning client, or `None` for a first-timer.

    `None` signals the caller to use the generic WELCOME. Keeps it light:
    "в прошлый раз" + at most one topic, ≤2 emoji, no verbatim card echo.
    """
    if not ctx["is_returning"]:
        return None

    topic = (ctx.get("top_topic") or "").strip()
    if topic:
        return (
            f"С возвращением! 🙌 В прошлый раз речь была про «{topic}» — "
            "как в этот раз? Расскажи голосом или текстом, как удобнее."
        )
    return (
        "С возвращением! 🙌 Рад снова тебя слышать. Как прошёл этот заказ "
        "и доставка — голосом или текстом, как удобнее?"
    )
