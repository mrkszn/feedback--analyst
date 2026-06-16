"""HTTP /admin/* routes — тонкая обёртка над services/analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from config import settings
from core.services.admin_auth import is_admin
from core.services.analytics import (
    aggregate_metric,
    categorical_distribution,
    client_profile,
    semantic_search,
    summary_overview,
    topic_histogram,
)
from core.services.questions import get_question_expected_type, list_questions
from core.services.settings import get_admin_settings, update_admin_settings
from presentations.http_api.auth.jwt import issue_token
from presentations.http_api.auth.telegram_webapp import validate_initdata
from presentations.http_api.deps.auth import current_admin
from presentations.http_api.schemas.admin import (
    AdminSettingsResponse,
    AdminSettingsUpdate,
    AskRequest,
    AskResponse,
    AuthRequest,
    AuthResponse,
    CategoryCountOut,
    ClientProfileResponse,
    MetricPointOut,
    MetricsResponse,
    OverviewResponse,
    QuestionOut,
    QuestionsResponse,
    SemanticHitOut,
    SemanticSearchRequest,
    SemanticSearchResponse,
    Sentiment,
    TopicCountOut,
    TopicsResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# --------------------------------------------------------------------------- #
# GET /admin/questions


@router.get("/questions", response_model=QuestionsResponse)
async def questions(
    _admin_id: Annotated[int, Depends(current_admin)],
    active_only: Annotated[bool, Query()] = True,
) -> QuestionsResponse:
    rows = await list_questions(active_only=active_only)
    out: list[QuestionOut] = []
    for r in rows:
        raw_enum = r.get("enum_values")
        enum_list: list[str] | None
        if isinstance(raw_enum, list) and raw_enum:
            enum_list = [str(v) for v in raw_enum]
        else:
            enum_list = None
        out.append(
            QuestionOut(
                id=str(r["id"]),
                text=str(r["text"]),
                metric_key=str(r["metric_key"]),
                expected_type=str(r.get("expected_type") or "unknown"),
                enum_values=enum_list,
            )
        )
    return QuestionsResponse(questions=out)


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
    """Thin wrapper over the questions service so this route doesn't reach into
    storage directly (CLAUDE.md invariant 5)."""
    return await get_question_expected_type(metric_key)


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


# --------------------------------------------------------------------------- #
# POST /admin/semantic


@router.post("/semantic", response_model=SemanticSearchResponse)
async def semantic(
    body: SemanticSearchRequest,
    _admin_id: Annotated[int, Depends(current_admin)],
) -> SemanticSearchResponse:
    try:
        hits = await semantic_search(body.query, top_k=body.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SemanticSearchResponse(hits=[SemanticHitOut(**h) for h in hits])


# --------------------------------------------------------------------------- #
# GET /admin/clients/{telegram_id}


@router.get("/clients/{telegram_id}", response_model=ClientProfileResponse)
async def client(
    telegram_id: int,
    _admin_id: Annotated[int, Depends(current_admin)],
) -> ClientProfileResponse:
    try:
        p = await client_profile(telegram_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ClientProfileResponse(
        telegram_id=p["telegram_id"],
        name=p["name"],
        sessions_count=p["sessions_count"],
        last_session_at=p["last_session_at"],
        avg_sentiment=p["avg_sentiment"],
        recent_cards=p["recent_cards"],
        top_topics=[TopicCountOut(**t) for t in p["top_topics"]],
    )


# --------------------------------------------------------------------------- #
# POST /admin/ask


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    _admin_id: Annotated[int, Depends(current_admin)],
) -> AskResponse:
    # Local import — avoid pulling LangChain at api module-load time.
    from core.agent.analytics_agent.runner import answer_v2

    answer = await answer_v2(body.question, history=body.history)
    return AskResponse(
        answer_text=answer.answer_text,
        tools_used=answer.tools_used,
        chart_text=answer.chart_text,
        interpretation=answer.interpretation,
        clarification_needed=answer.clarification_needed,
    )


# --------------------------------------------------------------------------- #
# GET /admin/settings  +  PUT /admin/settings


@router.get("/settings", response_model=AdminSettingsResponse)
async def get_settings(
    admin_id: Annotated[int, Depends(current_admin)],
) -> AdminSettingsResponse:
    s = await get_admin_settings(admin_id)
    return AdminSettingsResponse(**s)


@router.put("/settings", response_model=AdminSettingsResponse)
async def put_settings(
    body: AdminSettingsUpdate,
    admin_id: Annotated[int, Depends(current_admin)],
) -> AdminSettingsResponse:
    try:
        s = await update_admin_settings(
            admin_id,
            theme=body.theme,
            language=body.language,
            notifications_enabled=body.notifications_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AdminSettingsResponse(**s)
