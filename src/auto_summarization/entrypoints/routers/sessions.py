from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Security
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader

from auto_summarization.entrypoints.schemas.session import (
    CreateSessionRequest,
    DeleteSessionRequest,
    DeleteSessionResponse,
    SessionDetailResponse,
    SessionPageResponse,
    SessionSearchResponse,
    SessionSummary,
    UpdateTitleRequest,
    UpdateTranslationRequest,
)
from auto_summarization.services.config import authorization
from auto_summarization.services.session_service import SessionService


router = APIRouter()


user_id_security = APIKeyHeader(
    name="user_id",
    auto_error=False,
    description="User identifier that scopes stored analysis sessions.",
)


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


@router.get("/chat_session/fetch_page", response_model=SessionPageResponse)
async def fetch_page(
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Security(user_id_security),
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    size: int = Query(default=20, ge=1, le=100, description="Размер страницы"),
) -> SessionPageResponse:
    user_id = _extract_user_id(request, user_id_header)
    sessions, total = service.fetch_page(user_id, page=page, size=size)
    return SessionPageResponse(
        sessions=[SessionSummary(**item) for item in sessions],
        total=total,
        page=page,
        size=size,
    )


@router.post("/chat_session/create", response_model=SessionDetailResponse)
async def create_session(
    payload: CreateSessionRequest,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Security(user_id_security),
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


@router.post("/chat_session/update_translation", response_model=SessionDetailResponse)
async def update_translation(
    payload: UpdateTranslationRequest,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Security(user_id_security),
) -> SessionDetailResponse:
    user_id = _extract_user_id(request, user_id_header)
    session = service.update_translation(
        user_id,
        session_id=payload.session_id,
        text=payload.text,
        category=payload.category,
        choices=payload.choices,
        version=payload.version,
    )
    return SessionDetailResponse(**session)


@router.post("/chat_session/update_title", response_model=SessionDetailResponse)
async def update_title(
    payload: UpdateTitleRequest,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Security(user_id_security),
) -> SessionDetailResponse:
    user_id = _extract_user_id(request, user_id_header)
    session = service.rename_session(
        user_id,
        session_id=payload.session_id,
        title=payload.title,
        version=payload.version,
    )
    return SessionDetailResponse(**session)


@router.get("/chat_session/search", response_model=SessionSearchResponse)
async def search_sessions(
    request: Request,
    query: str = Query(..., alias="q", description="Поисковый запрос"),
    limit: int = Query(20, ge=1, le=100, description="Количество результатов"),
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Security(user_id_security),
) -> SessionSearchResponse:
    user_id = _extract_user_id(request, user_id_header)
    sessions = service.search_sessions(user_id, query=query, limit=limit)
    return SessionSearchResponse(sessions=[SessionSummary(**item) for item in sessions])


@router.get("/chat_session/download/{session_id}/{export_format}")
async def download_session(
    session_id: str,
    export_format: str,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Security(user_id_security),
) -> StreamingResponse:
    user_id = _extract_user_id(request, user_id_header)
    filename, content, media_type = service.download_session(
        user_id,
        session_id=session_id,
        export_format=export_format,
    )
    response = StreamingResponse(iter([content]), media_type=media_type)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@router.delete("/chat_session/delete", response_model=DeleteSessionResponse)
async def delete_session(
    payload: DeleteSessionRequest,
    request: Request,
    service: SessionService = Depends(get_service),
    user_id_header: str | None = Security(user_id_security),
) -> DeleteSessionResponse:
    user_id = _extract_user_id(request, user_id_header)
    service.delete_session(user_id, payload.session_id)
    return DeleteSessionResponse(status="deleted")
