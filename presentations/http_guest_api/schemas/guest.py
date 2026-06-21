"""Pydantic request/response schemas for /guest/* HTTP routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

InputType = Literal["mood_slider", "chip_pick", "yes_no"]
JourneyName = Literal["restaurant", "delivery"]
SessionMode = Literal["non_targeted", "targeted"]
MealOccasion = Literal["breakfast", "lunch", "dinner", "other"]


# --------------------------------------------------------------------------- #
# session auth


class StartSessionRequest(BaseModel):
    """Optional body for POST /guest/sessions. The QR code encodes which
    journey/mode the guest enters; `meal_occasion` is the restaurant's
    "when did you visit" answer (ignored for delivery). All optional so the
    bare anonymous start still works."""

    journey: JourneyName = "restaurant"
    mode: SessionMode = "non_targeted"
    meal_occasion: MealOccasion | None = None


class StartSessionResponse(BaseModel):
    session_id: str
    token: str


# --------------------------------------------------------------------------- #
# journey


class BeatTagOut(BaseModel):
    id: str
    tag_key: str
    label_uk: str
    label_en: str
    position: int


class BeatOut(BaseModel):
    id: str
    beat_key: str
    position: int
    label_uk: str
    label_en: str
    icon: str
    input_type: InputType
    tags: list[BeatTagOut] = []


class JourneyTemplateOut(BaseModel):
    id: str
    name: str
    label_uk: str
    label_en: str


class JourneyResponse(BaseModel):
    template: JourneyTemplateOut
    beats: list[BeatOut]


# --------------------------------------------------------------------------- #
# beats


class BeatPatch(BaseModel):
    score: int | None = Field(default=None, ge=1, le=5)
    tags: list[str] | None = None
    skipped: bool | None = None


class BeatStateOut(BaseModel):
    beat_id: str
    score: int | None = None
    tags: list[str] = []
    skipped: bool = False


# --------------------------------------------------------------------------- #
# session restore


class GuessOut(BaseModel):
    id: str
    text_uk: str
    text_en: str
    emoji: str


class DigStateOut(BaseModel):
    id: str
    beat_id: str
    guesses: list[GuessOut]
    accepted_guess_id: str | None = None
    free_text: str | None = None


class SessionStateOut(BaseModel):
    session_id: str
    feedback_source: str
    started_at: str | None = None
    ended_at: str | None = None
    beats: list[BeatStateOut]
    digs: list[DigStateOut]


# --------------------------------------------------------------------------- #
# dig (LLM follow-up)


class DigStartRequest(BaseModel):
    beat_id: str


class DigStartResponse(BaseModel):
    dig_id: str
    beat_id: str
    guesses: list[GuessOut]


class DigAnswerRequest(BaseModel):
    dig_id: str
    accepted_guess_id: str | None = None
    free_text: str | None = None


class DigAnswerResponse(BaseModel):
    dig_id: str
    accepted_guess_id: str | None = None
    free_text: str | None = None
    next_dig: DigStartResponse | None = None


# --------------------------------------------------------------------------- #
# finalize


class FinalizeResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
