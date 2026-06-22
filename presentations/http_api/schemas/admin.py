"""Pydantic request/response schemas for /admin/* HTTP routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# auth


class AuthRequest(BaseModel):
    init_data: str = Field(description="Raw Telegram.WebApp.initData query string")


class AuthResponse(BaseModel):
    token: str
    telegram_id: int


# --------------------------------------------------------------------------- #
# questions catalog


class QuestionOut(BaseModel):
    id: str
    text: str
    metric_key: str
    expected_type: str
    enum_values: list[str] | None = None


class QuestionsResponse(BaseModel):
    questions: list[QuestionOut]


# --------------------------------------------------------------------------- #
# overview


class TopicCountOut(BaseModel):
    topic: str
    count: int
    avg_sentiment: float


class OverviewResponse(BaseModel):
    sessions_count: int
    avg_sentiment: float | None
    top_positive_topics: list[TopicCountOut]
    top_negative_topics: list[TopicCountOut]


# --------------------------------------------------------------------------- #
# metrics


class MetricPointOut(BaseModel):
    bucket: str
    count: int
    avg: float | None
    min: float | None
    max: float | None


class CategoryCountOut(BaseModel):
    value: str
    count: int
    pct: float


class MetricsResponse(BaseModel):
    metric_key: str
    expected_type: str  # number | enum | boolean | text | unknown
    # one of `points` (numeric) or `distribution` (categorical) will be filled
    points: list[MetricPointOut] | None = None
    distribution: list[CategoryCountOut] | None = None
    total: int | None = None
    unknown: int | None = None
    enum_values: list[str] | None = None


# --------------------------------------------------------------------------- #
# topics


class TopicsResponse(BaseModel):
    topics: list[TopicCountOut]


# --------------------------------------------------------------------------- #
# semantic search


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=100)


class SemanticHitOut(BaseModel):
    session_id: str
    client_id: int | None
    score: float
    summary_text: str
    sentiment: str | None
    started_at: str | None


class SemanticSearchResponse(BaseModel):
    hits: list[SemanticHitOut]


# --------------------------------------------------------------------------- #
# client profile


class ClientProfileResponse(BaseModel):
    telegram_id: int
    name: str | None
    sessions_count: int
    last_session_at: str | None
    avg_sentiment: float | None
    recent_cards: list[dict[str, Any]]
    top_topics: list[TopicCountOut]


# --------------------------------------------------------------------------- #
# sessions drill-down


class SessionListItem(BaseModel):
    id: str
    client_id: int | None
    client_name: str | None
    started_at: str | None
    ended_at: str | None
    sentiment: str | None
    topics: list[str]
    source: str | None


class SessionsResponse(BaseModel):
    sessions: list[SessionListItem]


class SessionMessageOut(BaseModel):
    role: str
    content: str
    created_at: str | None


class SessionAnswerOut(BaseModel):
    question_text: str
    answer_text: str | None
    marked_value: str | None = None


class JourneyBeatOut(BaseModel):
    label_uk: str
    emoji: str
    score: int | None = None
    transcription_uk: str | None = None
    tags: list[str] = []


class SessionJourneyOut(BaseModel):
    mode: str
    meal_occasion: str | None = None
    beats: list[JourneyBeatOut]


class SessionDetailResponse(BaseModel):
    id: str
    client_id: int | None
    client_name: str | None
    started_at: str | None
    ended_at: str | None
    sentiment: str | None
    topics: list[str]
    source: str | None
    summary: str | None
    messages: list[SessionMessageOut]
    answers: list[SessionAnswerOut]
    card_summary: str | None
    # Present only for web (guest webapp) sessions — the beat ribbon with mood
    # emoji + UK transcription that the admin renders instead of a transcript.
    journey: SessionJourneyOut | None = None


# --------------------------------------------------------------------------- #
# client lists (topic / category / search / filter drill-down)


class ClientListItem(BaseModel):
    telegram_id: int
    name: str | None
    sessions_count: int
    last_session_at: str | None
    avg_sentiment: float | None


class ClientsResponse(BaseModel):
    clients: list[ClientListItem]


# --------------------------------------------------------------------------- #
# ask


class AskRequest(BaseModel):
    question: str
    history: list[dict[str, str]] | None = None


class AskResponse(BaseModel):
    answer_text: str
    tools_used: list[str]
    chart_text: str | None = None
    interpretation: str = ""
    clarification_needed: bool = False


# --------------------------------------------------------------------------- #
# settings


Theme = Literal["light", "dark", "system"]
Language = Literal["uk", "en"]


class AdminSettingsResponse(BaseModel):
    theme: Theme
    language: Language
    notifications_enabled: bool


class AdminSettingsUpdate(BaseModel):
    """Partial update — only the provided fields change; others are untouched."""

    theme: Theme | None = None
    language: Language | None = None
    notifications_enabled: bool | None = None


# --------------------------------------------------------------------------- #
# prizes (in-app gamification config)

PrizeTier = Literal["small", "medium", "large"]


class PrizeTierOut(BaseModel):
    tier: PrizeTier
    code: str
    label_uk: str
    label_en: str


class PrizesResponse(BaseModel):
    prizes: list[PrizeTierOut]


class PrizeTierUpdate(BaseModel):
    """Partial update of one tier — only provided fields change."""

    code: str | None = Field(default=None, max_length=120)
    label_uk: str | None = Field(default=None, max_length=120)
    label_en: str | None = Field(default=None, max_length=120)


# --------------------------------------------------------------------------- #
# journeys (admin CRUD — templates + beats + tags)

InputType = Literal["mood_slider", "chip_pick", "yes_no"]


class BeatTagOut(BaseModel):
    id: str
    tag_key: str
    position: int
    label_uk: str
    label_en: str


class JourneyBeatFullOut(BaseModel):
    id: str
    beat_key: str
    position: int
    label_uk: str
    label_en: str
    icon: str
    input_type: str
    tags: list[BeatTagOut] = []


class JourneyOut(BaseModel):
    name: str
    label_uk: str
    label_en: str
    is_default: bool
    beats: list[JourneyBeatFullOut] = []


class JourneysResponse(BaseModel):
    journeys: list[JourneyOut]


class JourneyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    label_uk: str = Field(min_length=1, max_length=120)
    label_en: str = Field(min_length=1, max_length=120)
    is_default: bool = False


class JourneyUpdate(BaseModel):
    """Partial update of one template — only provided fields change. `is_default`
    may only be set to True (promote); un-defaulting is rejected by the service."""

    label_uk: str | None = Field(default=None, max_length=120)
    label_en: str | None = Field(default=None, max_length=120)
    is_default: bool | None = None


class JourneyBeatUpsert(BaseModel):
    """Upsert one beat on a journey (keyed by beat_key in the path)."""

    position: int | None = Field(default=None, ge=0)
    label_uk: str | None = Field(default=None, max_length=120)
    label_en: str | None = Field(default=None, max_length=120)
    icon: str | None = Field(default=None, max_length=16)
    input_type: InputType | None = None


class BeatTagUpsert(BaseModel):
    """Upsert one chip tag on a beat (keyed by tag_key in the path)."""

    position: int | None = Field(default=None, ge=0)
    label_uk: str | None = Field(default=None, max_length=120)
    label_en: str | None = Field(default=None, max_length=120)


# --------------------------------------------------------------------------- #
# shared query helpers


Sentiment = Literal["positive", "neutral", "negative"]
GroupBy = Literal["day", "week", "none"]


def parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
