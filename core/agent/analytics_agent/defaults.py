"""Constants and keyword mappings for the analytics agent.

Pure data, no logic. Read by prompts (as hints baked into the system text)
and by interpret/execute (defaults + period resolution).
"""

from __future__ import annotations

DEFAULT_PERIOD_DAYS: int = 7
MONTH_PERIOD_DAYS: int = 30

NEGATIVE_SENTIMENTS: tuple[str, ...] = ("negative",)
SATISFACTORY_SENTIMENTS: tuple[str, ...] = ("positive", "neutral")

# Russian keyword stems → sentiment. Used only as a hint inside the interpret
# prompt; the actual interpretation is the LLM's job.
SENTIMENT_KEYWORDS: dict[str, str] = {
    "недовольн": "negative",
    "жалоб": "negative",
    "негатив": "negative",
    "довольн": "positive",
    "позитив": "positive",
    "хвал": "positive",
}

RECENT_DEFAULT_LIMIT: int = 5
SEMANTIC_DEFAULT_TOP_K: int = 10

TOOL_NAMES: tuple[str, ...] = (
    "full_report",
    "aggregate_metric",
    "categorical_distribution",
    "topic_histogram",
    "semantic_search",
    "client_profile",
    "recent_sessions",
)
