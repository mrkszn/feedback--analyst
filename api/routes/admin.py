"""HTTP /admin/* routes — тонкая обёртка над services/analytics."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.auth.jwt import issue_token
from api.auth.telegram_webapp import validate_initdata
from api.deps.auth import current_admin
from api.schemas.admin import (
    AuthRequest,
    AuthResponse,
    CategoryCountOut,
    MetricPointOut,
    MetricsResponse,
    OverviewResponse,
    Sentiment,
    TopicCountOut,
    TopicsResponse,
)
from config import settings
from db.client import get_supabase
from services.admin_auth import is_admin
from services.analytics import (
    aggregate_metric,
    categorical_distribution,
    summary_overview,
    topic_histogram,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# --------------------------------------------------------------------------- #
# POST /admin/auth


@router.post("/auth", response_model=AuthResponse)
async def auth(body: AuthRequest) -> AuthResponse:
    try:
        user = validate_initdata(body.init_data, settings.telegram_admin_bot_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid init_data: {exc}",
        ) from exc

    if not await is_admin(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not an admin")

    token = issue_token(user.id, settings.mini_app_session_secret)
    return AuthResponse(token=token, telegram_id=user.id)


# --------------------------------------------------------------------------- #
# GET /admin/overview


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    date_from: Annotated[datetime, Query(description="ISO 8601 datetime")],
    date_to: Annotated[datetime, Query(description="ISO 8601 datetime")],
    _admin_id: Annotated[int, Depends(current_admin)],
) -> OverviewResponse:
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")
    o = await summary_overview(date_from, date_to)
    return OverviewResponse(
        sessions_count=o["sessions_count"],
        avg_sentiment=o["avg_sentiment"],
        top_positive_topics=[TopicCountOut(**t) for t in o["top_positive_topics"]],
        top_negative_topics=[TopicCountOut(**t) for t in o["top_negative_topics"]],
    )


# --------------------------------------------------------------------------- #
# GET /admin/metrics


async def _question_expected_type(metric_key: str) -> str | None:
    """Same shape as bot_admin.handlers.analytics_commands._question_expected_type.

    Duplicated (6 lines) rather than reaching into bot_admin from api/* — keeps
    the two entry points decoupled.
    """
    db = get_supabase()

    def _q() -> Any:
        return (
            db.table("questions")
            .select("expected_type")
            .eq("metric_key", metric_key)
            .limit(1)
            .execute()
        )

    resp = await asyncio.to_thread(_q)
    if not resp.data:
        return None
    et = resp.data[0].get("expected_type")
    return str(et) if et is not None else None


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(
    metric_key: Annotated[str, Query(min_length=1)],
    date_from: Annotated[datetime, Query()],
    date_to: Annotated[datetime, Query()],
    _admin_id: Annotated[int, Depends(current_admin)],
    group_by: Annotated[str, Query()] = "day",
) -> MetricsResponse:
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")
    if group_by not in ("day", "week", "none"):
        raise HTTPException(status_code=400, detail=f"unknown group_by {group_by!r}")

    expected = await _question_expected_type(metric_key)
    if expected is None:
        raise HTTPException(
            status_code=404, detail=f"question with metric_key {metric_key!r} not found"
        )

    if expected in ("enum", "boolean"):
        dist = await categorical_distribution(metric_key, date_from, date_to)
        return MetricsResponse(
            metric_key=metric_key,
            expected_type=expected,
            distribution=[CategoryCountOut(**c) for c in dist["categories"]],
            total=dist["total"],
            unknown=dist["unknown"],
            enum_values=dist["enum_values"],
        )

    if expected == "text":
        # Text questions can't be aggregated numerically; surface that clearly.
        return MetricsResponse(metric_key=metric_key, expected_type=expected, total=0)

    points = await aggregate_metric(
        metric_key,
        date_from,
        date_to,
        group_by=group_by,  # type: ignore[arg-type]
    )
    return MetricsResponse(
        metric_key=metric_key,
        expected_type=expected,
        points=[MetricPointOut(**p) for p in points],
    )


# --------------------------------------------------------------------------- #
# GET /admin/topics


@router.get("/topics", response_model=TopicsResponse)
async def topics(
    date_from: Annotated[datetime, Query()],
    date_to: Annotated[datetime, Query()],
    _admin_id: Annotated[int, Depends(current_admin)],
    sentiment: Annotated[Sentiment | None, Query()] = None,
) -> TopicsResponse:
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")
    rows = await topic_histogram(date_from, date_to, sentiment_filter=sentiment)
    return TopicsResponse(topics=[TopicCountOut(**t) for t in rows])
