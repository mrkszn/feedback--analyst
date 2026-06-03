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
# shared query helpers


Sentiment = Literal["positive", "neutral", "negative"]
GroupBy = Literal["day", "week", "none"]


def parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
