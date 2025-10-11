from auto_summarization.entrypoints.schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    DeleteSessionRequest,
    DeleteSessionResponse,
    FetchSessionResponse,
    SessionInfo,
    UpdateSessionSummarizationRequest,
    UpdateSessionSummarizationResponse,
    UpdateSessionTitleRequest,
    UpdateSessionTitleResponse,
)
from fastapi import APIRouter, Header, HTTPException
from auto_summarization.services.config import authorization
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW, UserUoW
from auto_summarization.services.handlers.session import (
    create_new_session,
    delete_exist_session,
    get_session_list,
    update_session_summarization,
    update_title_session,
)

router = APIRouter()


@router.get("/fetch_page", response_model=FetchSessionResponse, status_code=200)
async def fetch_page(auth: str = Header(default=None, alias=authorization)) -> FetchSessionResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    sessions = [SessionInfo(**session) for session in get_session_list(user_id=auth, uow=UserUoW())]
    return FetchSessionResponse(sessions=sessions)


@router.post("/create", response_model=CreateSessionResponse, status_code=200)
async def create(
    request: CreateSessionRequest,
    auth: str = Header(default=None, alias=authorization),
) -> CreateSessionResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    try:
        session = create_new_session(
            user_id=auth,
            text=request.text,
            category_index=request.category,
            choices=request.choices,
            temporary=request.temporary,
            user_uow=UserUoW(),
            analysis_uow=AnalysisTemplateUoW(),
        )
        return CreateSessionResponse(**session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/update_summarization", response_model=UpdateSessionSummarizationResponse, status_code=200)
async def update_summarization(
    request: UpdateSessionSummarizationRequest,
    auth: str = Header(default=None, alias=authorization),
) -> UpdateSessionSummarizationResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    session = update_session_summarization(
        user_id=auth,
        session_id=request.session_id,
        summary=request.summary,
        analysis=request.analysis,
        version=request.version,
        user_uow=UserUoW(),
    )
    return UpdateSessionSummarizationResponse(**session)


@router.post("/update_title", response_model=UpdateSessionTitleResponse, status_code=200)
async def update_title(
    request: UpdateSessionTitleRequest,
    auth: str = Header(default=None, alias=authorization),
) -> UpdateSessionTitleResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    session = update_title_session(
        user_id=auth,
        session_id=request.session_id,
        title=request.title,
        version=request.version,
        user_uow=UserUoW(),
    )
    return UpdateSessionTitleResponse(**session)


@router.delete("/delete", response_model=DeleteSessionResponse, status_code=200)
async def delete(
    request: DeleteSessionRequest,
    auth: str = Header(default=None, alias=authorization),
) -> DeleteSessionResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    status = delete_exist_session(session_id=request.session_id, user_id=auth, uow=UserUoW())
    return DeleteSessionResponse(status=status)
