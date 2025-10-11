from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response

from auto_summarization.entrypoints.schemas.session import (
    CreateChatSessionRequest,
    DeleteSessionResponse,
    SearchSessionsRequest,
    SessionDetailResponse,
    SessionListResponse,
    SessionPageResponse,
    SessionSummary,
    UpdateTitleRequest,
    UpdateTranslationRequest,
)
from auto_summarization.services.config import authorization
from auto_summarization.services.session_service import SessionService


router = APIRouter(prefix="/chat_session", tags=["chat_session"])


def get_service() -> SessionService:
    return SessionService()


def _extract_user_id(request: Request, explicit_user_id: str | None = None) -> str | None:
    if explicit_user_id:
        return explicit_user_id

    header_names = {authorization, "Authorization", "user_id"}
    for header_name in header_names:
        value = request.headers.get(header_name)
        if value:
            return value
    return None


@router.get("/fetch_page", response_model=SessionPageResponse)
async def fetch_page(
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Header(
        default=None,
        alias="user_id",
        description="User identifier used to scope stored analysis sessions.",
    ),
    session_id: str | None = Query(
        default=None,
        description="Идентификатор сессии, которая должна быть активной на странице.",
    ),
) -> SessionPageResponse:
    user_id = _extract_user_id(request, user_id_header)
    sessions = [SessionSummary(**item) for item in service.list_sessions(user_id)]
    active_session = None

    resolved_session_id = session_id or (sessions[0].session_id if sessions else None)
    if resolved_session_id:
        session_detail = service.get_session(user_id, resolved_session_id)
        active_session = SessionDetailResponse(**session_detail)

    return SessionPageResponse(sessions=sessions, active_session=active_session)


@router.post("/create", response_model=SessionDetailResponse)
async def create_session(
    payload: CreateChatSessionRequest,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Header(
        default=None,
        alias="user_id",
        description="User identifier used to scope stored analysis sessions.",
    ),
) -> SessionDetailResponse:
    user_id = _extract_user_id(request, user_id_header)
    session = service.create_session(
        user_id,
        title=payload.title,
        text=payload.text,
        category=payload.category,
        choices=payload.choices,
    )
    return SessionDetailResponse(**session)


@router.post("/update_translation", response_model=SessionDetailResponse)
async def update_translation(
    payload: UpdateTranslationRequest,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Header(
        default=None,
        alias="user_id",
        description="User identifier used to scope stored analysis sessions.",
    ),
) -> SessionDetailResponse:
    user_id = _extract_user_id(request, user_id_header)
    session = service.update_session(
        user_id,
        payload.session_id,
        text=payload.text,
        category=payload.category,
        choices=payload.choices,
        version=payload.version,
    )
    return SessionDetailResponse(**session)


@router.post("/update_title", response_model=SessionDetailResponse)
async def update_title(
    payload: UpdateTitleRequest,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Header(
        default=None,
        alias="user_id",
        description="User identifier used to scope stored analysis sessions.",
    ),
) -> SessionDetailResponse:
    user_id = _extract_user_id(request, user_id_header)
    session = service.update_session(
        user_id,
        payload.session_id,
        title=payload.title,
        version=payload.version,
    )
    return SessionDetailResponse(**session)


@router.post("/search", response_model=SessionListResponse)
async def search_sessions(
    payload: SearchSessionsRequest,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Header(
        default=None,
        alias="user_id",
        description="User identifier used to scope stored analysis sessions.",
    ),
) -> SessionListResponse:
    user_id = _extract_user_id(request, user_id_header)
    sessions = service.search_sessions(user_id, payload.query)
    return SessionListResponse(sessions=[SessionSummary(**item) for item in sessions])


@router.get("/download/{session_id}/{file_format}")
async def download_session(
    session_id: str,
    file_format: str,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Header(
        default=None,
        alias="user_id",
        description="User identifier used to scope stored analysis sessions.",
    ),
):
    user_id = _extract_user_id(request, user_id_header)
    detail = service.get_session(user_id, session_id)

    filename = f"chat_session_{session_id}.{file_format}"
    disposition = {"Content-Disposition": f"attachment; filename=\"{filename}\""}

    if file_format.lower() == "json":
        payload = json.dumps(detail, ensure_ascii=False, indent=2)
        return Response(
            content=payload,
            media_type="application/json",
            headers=disposition,
        )
    if file_format.lower() == "txt":
        payload = detail.get("text", "")
        return Response(
            content=payload,
            media_type="text/plain; charset=utf-8",
            headers=disposition,
        )

    raise HTTPException(
        status_code=400,
        detail="Поддерживаются только форматы json и txt",
    )


@router.delete("/delete", response_model=DeleteSessionResponse)
async def delete_session(
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Header(
        default=None,
        alias="user_id",
        description="User identifier used to scope stored analysis sessions.",
    ),
    session_id: str = Query(
        ...,
        description="Идентификатор сессии, которую необходимо удалить.",
    ),
) -> DeleteSessionResponse:
    user_id = _extract_user_id(request, user_id_header)
    service.delete_session(user_id, session_id)
    return DeleteSessionResponse(status="deleted")
