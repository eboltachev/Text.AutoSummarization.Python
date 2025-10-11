from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from auto_summarization.entrypoints.schemas.session import (
    CreateSessionRequest,
    DeleteSessionResponse,
    SessionDetailResponse,
    SessionListResponse,
    UpdateSessionRequest,
)
from auto_summarization.entrypoints.schemas.session import SessionSummary
from auto_summarization.services.config import authorization
from auto_summarization.services.session_service import SessionService


router = APIRouter()


def get_service() -> SessionService:
    return SessionService()


def _extract_user_id(request: Request) -> str | None:
    header_names = {authorization, "Authorization", "user_id"}
    for header_name in header_names:
        value = request.headers.get(header_name)
        if value:
            return value
    return None


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(request: Request, service: SessionService = Depends(get_service)) -> SessionListResponse:
    user_id = _extract_user_id(request)
    sessions = service.list_sessions(user_id)
    return SessionListResponse(sessions=[SessionSummary(**item) for item in sessions])


@router.post("/sessions", response_model=SessionDetailResponse)
async def create_session(
    payload: CreateSessionRequest,
    request: Request,
    service: SessionService = Depends(get_service),
) -> SessionDetailResponse:
    user_id = _extract_user_id(request)
    session = service.create_session(
        user_id,
        title=payload.title,
        text=payload.text,
        category=payload.category,
        choices=payload.choices,
    )
    return SessionDetailResponse(**session)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    request: Request,
    service: SessionService = Depends(get_service),
) -> SessionDetailResponse:
    user_id = _extract_user_id(request)
    session = service.get_session(user_id, session_id)
    return SessionDetailResponse(**session)


@router.patch("/sessions/{session_id}", response_model=SessionDetailResponse)
async def update_session(
    session_id: str,
    payload: UpdateSessionRequest,
    request: Request,
    service: SessionService = Depends(get_service),
) -> SessionDetailResponse:
    user_id = _extract_user_id(request)
    session = service.update_session(
        user_id,
        session_id,
        title=payload.title,
        text=payload.text,
        category=payload.category,
        choices=payload.choices,
        version=payload.version,
    )
    return SessionDetailResponse(**session)


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(
    session_id: str,
    request: Request,
    service: SessionService = Depends(get_service),
) -> DeleteSessionResponse:
    user_id = _extract_user_id(request)
    service.delete_session(user_id, session_id)
    return DeleteSessionResponse(status="deleted")
