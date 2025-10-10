import os
from typing import Literal
import base64
import mimetypes

from entrypoints.schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    DeleteSessionRequest,
    DeleteSessionRespone,
    FetchSessionResponse,
    UpdateSessionTitleRequest,
    UpdateSessionTitleRespone,
    UpdateSessionTranslationRequest,
    UpdateSessionTranslationRespone,
    SearchRequest,
    SearchResponse,
    SearchMessagesInfo,
)
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from services.config import authorization
from services.data.unit_of_work import ModelUoW, UserUoW
from services.handlers.session import (
    create_new_session,
    delete_exist_session,
    download_session_file,
    get_session_list,
    update_exist_session,
    update_title_session,
    search_similarity_sessions,
)

router = APIRouter()


@router.get("/fetch_page", response_model=FetchSessionResponse, status_code=200)
async def fetch_page(auth: str = Header(default=None, alias=authorization)) -> FetchSessionResponse:
    try:
        user_id = auth
        chat_sessions = [
            CreateSessionResponse(**session) for session in get_session_list(user_id=user_id, uow=UserUoW())
        ]
        return FetchSessionResponse(chat_sessions=chat_sessions)
    except Exception as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/create", response_model=CreateSessionResponse, status_code=200)
async def create(
    request: CreateSessionRequest,
    auth: str = Header(default=None, alias=authorization),
) -> CreateSessionResponse:
    user_id = auth
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bad Request")
    try:
        chat_session = create_new_session(
            user_id=user_id,
            query=request.query,
            model_id=request.model_id,
            temporary=request.temporary,
            model_uow=ModelUoW(),
            user_uow=UserUoW()
        )
        return CreateSessionResponse(**chat_session)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/update_translation", response_model=UpdateSessionTranslationRespone, status_code=200)
async def update_translation(
    request: UpdateSessionTranslationRequest,
    auth: str = Header(default=None, alias=authorization),
) -> UpdateSessionTranslationRespone:
    user_id = auth
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bad Request")
    try:
        user_id = auth
        chat_session = update_exist_session(
            user_id=user_id,
            session_id=request.session_id,
            model_id=request.model_id,
            query=request.query,
            version=request.version,
            model_uow=ModelUoW(),
            user_uow=UserUoW(),
        )
        return UpdateSessionTranslationRespone(**chat_session)
    except Exception as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/update_title", response_model=UpdateSessionTitleRespone, status_code=200)
async def update_title(
    request: UpdateSessionTitleRequest,
    auth: str = Header(default=None, alias=authorization),
) -> UpdateSessionTitleRespone:
    user_id = auth
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bad Request")
    try:
        chat_session = update_title_session(
            user_id=user_id,
            session_id=request.session_id,
            title=request.title,
            version=request.version,
            user_uow=UserUoW(),
        )
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return UpdateSessionTitleRespone(**chat_session)
    except Exception as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/search", response_model=SearchResponse, status_code=200)
async def search_messages(
    request: SearchRequest,
    auth: str = Header(default=None, alias=authorization),
) -> SearchResponse:
    user_id = auth
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bad Request")
    try:
        sessions = search_similarity_sessions(user_id=user_id, query=request.query, uow=UserUoW())
        return SearchResponse(sessions=[SearchMessagesInfo(**session) for session in sessions])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get(
    "/download/{session_id}/{format}",
    responses={
        200: {
            "description": "Файл",
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "text/plain": {"schema": {"type": "string", "format": "binary"}},
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string"},
                            "content_type": {"type": "string"},
                            "data": {"type": "string", "description": "base64-encoded file"},
                        },
                        "required": ["filename", "content_type", "data"],
                    }
                },
            },
        }
    },
)
async def download_file(
    session_id: str,
    format: Literal["pdf"],
    auth: str = Header(default=None, alias=authorization),
    accept: str = Header(default="*/*", alias="Accept"),
):
    user_id = auth
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bad Request")

    try:
        path = download_session_file(
            session_id=session_id,
            format=format,
            user_id=user_id,
            uow=UserUoW(),
        )
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="File not found")
        filename = f"{session_id}.{format}"

        guessed_type, _ = mimetypes.guess_type(filename)
        media_type = guessed_type or ("application/pdf" if format.lower() == "pdf" else "application/octet-stream")

        # Если клиент просит JSON (как в сгенерированном TS-клиенте), отдаем base64-JSON вместо бинарного файла.
        if "application/json" in (accept or ""):
            with open(path, "rb") as fh:
                payload = base64.b64encode(fh.read()).decode("ascii")
            return JSONResponse(
                content={"filename": filename, "content_type": media_type, "data": payload},
                headers={"X-Served-For-User": user_id or "", "Access-Control-Expose-Headers": "*"},
            )

        return FileResponse(
            path=path,
            media_type=media_type,
            filename=filename,
            headers={"X-Served-For-User": user_id or "", "Access-Control-Expose-Headers": "*"},
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.delete("/delete", response_model=DeleteSessionRespone, status_code=200)
async def delete(
    request: DeleteSessionRequest,
    auth: str = Header(default=None, alias=authorization),
) -> DeleteSessionRespone:
    user_id = auth
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bad Request")
    try:
        status = delete_exist_session(session_id=request.session_id, user_id=user_id, uow=UserUoW())
        return DeleteSessionRespone(status=status)
    except Exception as error:
        raise HTTPException(status_code=404, detail=str(error))


