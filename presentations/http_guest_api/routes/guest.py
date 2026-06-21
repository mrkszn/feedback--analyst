"""Public guest-webapp HTTP routes — anonymous "вечер як стрічка" flow.

Thin layer over `core.services.guest_journey` and the new dig agent node:
no business logic here, only request/response shape conversion and HTTP
status mapping (ValueError → 400, LookupError → 404).

Auth: separate JWT (issued at POST /guest/sessions), independent of the
admin Mini App. The route handlers also enforce that the URL path's
session_id matches the token's session_id — otherwise a leaked token could
operate on a stranger's session.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from config import settings
from core.services.guest_journey import (
    dig_for_beat,
    finalize_session,
    get_journey,
    record_dig_answer,
    restore_session,
    save_beat,
    start_anonymous_session,
)
from presentations.http_guest_api.auth.jwt import issue_session_token
from presentations.http_guest_api.deps.auth import current_guest_session
from presentations.http_guest_api.schemas.guest import (
    BeatPatch,
    BeatStateOut,
    DigAnswerRequest,
    DigAnswerResponse,
    DigStartRequest,
    DigStartResponse,
    FinalizeResponse,
    JourneyResponse,
    SessionStateOut,
    StartSessionRequest,
    StartSessionResponse,
)

router = APIRouter(prefix="/guest", tags=["guest"])


def _require_path_matches_token(path_session_id: str, token_session_id: str) -> None:
    if path_session_id != token_session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="session mismatch")


# --------------------------------------------------------------------------- #
# session lifecycle


@router.post("/sessions", response_model=StartSessionResponse, status_code=201)
async def post_session(body: StartSessionRequest | None = None) -> StartSessionResponse:
    """Start a new anonymous web session. Returns its id + bearer token. The
    optional body carries the journey/mode/meal_occasion the QR code selected;
    a bare POST (no body) starts a default restaurant / non_targeted session."""
    req = body or StartSessionRequest()
    session_id = await start_anonymous_session(
        journey=req.journey,
        mode=req.mode,
        meal_occasion=req.meal_occasion,
    )
    token = issue_session_token(session_id, settings.guest_session_secret)
    return StartSessionResponse(session_id=session_id, token=token)


@router.post("/auth", status_code=501)
async def post_auth() -> dict[str, str]:
    """Exchange a magic-link one-time token for a session JWT. Not implemented
    in MVP — the frontend falls back to anonymous start."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="magic-link auth not yet implemented",
    )


@router.get("/journey", response_model=JourneyResponse)
async def get_journey_route(
    _: Annotated[str, Depends(current_guest_session)],
    name: str | None = None,
) -> JourneyResponse:
    """Journey bundle. Without `?name=` returns the default (restaurant);
    `?name=delivery` returns that named journey. A missing default is a server
    misconfiguration (500); a missing named journey is a 404."""
    journey = await get_journey(name)
    if journey is None:
        if name is None:
            raise HTTPException(status_code=500, detail="no default journey configured")
        raise HTTPException(status_code=404, detail=f"journey {name!r} not found")
    return JourneyResponse.model_validate(journey)


@router.get("/sessions/{session_id}", response_model=SessionStateOut)
async def get_session(
    session_id: str,
    token_session_id: Annotated[str, Depends(current_guest_session)],
) -> SessionStateOut:
    _require_path_matches_token(session_id, token_session_id)
    try:
        state = await restore_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionStateOut.model_validate(state)


# --------------------------------------------------------------------------- #
# beats


@router.patch("/sessions/{session_id}/beats/{beat_id}", response_model=BeatStateOut)
async def patch_beat(
    session_id: str,
    beat_id: str,
    body: BeatPatch,
    token_session_id: Annotated[str, Depends(current_guest_session)],
) -> BeatStateOut:
    _require_path_matches_token(session_id, token_session_id)
    try:
        state = await save_beat(
            session_id,
            beat_id,
            score=body.score,
            tags=body.tags,
            skipped=body.skipped,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BeatStateOut.model_validate(state)


# --------------------------------------------------------------------------- #
# dig (LLM follow-up on weak beats)


@router.post("/sessions/{session_id}/dig", response_model=DigStartResponse)
async def post_dig(
    session_id: str,
    body: DigStartRequest,
    token_session_id: Annotated[str, Depends(current_guest_session)],
) -> DigStartResponse:
    _require_path_matches_token(session_id, token_session_id)
    try:
        dig = await dig_for_beat(
            session_id,
            body.beat_id,
            restaurant_context=settings.restaurant_context,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DigStartResponse.model_validate(
        {
            "dig_id": dig["id"],
            "beat_id": dig["beat_id"],
            "guesses": dig["guesses"],
        }
    )


@router.post("/sessions/{session_id}/dig/answer", response_model=DigAnswerResponse)
async def post_dig_answer(
    session_id: str,
    body: DigAnswerRequest,
    token_session_id: Annotated[str, Depends(current_guest_session)],
) -> DigAnswerResponse:
    _require_path_matches_token(session_id, token_session_id)
    try:
        dig = await record_dig_answer(
            session_id,
            body.dig_id,
            accepted_guess_id=body.accepted_guess_id,
            free_text=body.free_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DigAnswerResponse(
        dig_id=dig["id"],
        accepted_guess_id=dig["accepted_guess_id"],
        free_text=dig["free_text"],
        next_dig=None,
    )


# --------------------------------------------------------------------------- #
# voice (deferred to v2)


@router.post("/sessions/{session_id}/voice", status_code=501)
async def post_voice(
    session_id: str,
    token_session_id: Annotated[str, Depends(current_guest_session)],
) -> dict[str, str]:
    _require_path_matches_token(session_id, token_session_id)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="voice upload not yet implemented",
    )


# --------------------------------------------------------------------------- #
# finalize


@router.post(
    "/sessions/{session_id}/finalize",
    response_model=FinalizeResponse,
    status_code=202,
)
async def post_finalize(
    session_id: str,
    token_session_id: Annotated[str, Depends(current_guest_session)],
) -> FinalizeResponse:
    _require_path_matches_token(session_id, token_session_id)
    try:
        await finalize_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FinalizeResponse(status="accepted")
