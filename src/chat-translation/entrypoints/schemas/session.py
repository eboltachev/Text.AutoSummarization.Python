from typing import List, Optional

from domain.enums import StatusType
from pydantic import BaseModel


class CreateSessionResponse(BaseModel):
    session_id: str
    title: str
    model: str
    query: str
    translation: str
    source_language_id: str
    target_language_id: str
    source_language_title: str
    target_language_title: str
    version: int
    inserted_at: float
    updated_at: float
    error: str | None


class FetchSessionResponse(BaseModel):
    chat_sessions: List[CreateSessionResponse]


class CreateSessionRequest(BaseModel):
    query: str
    model_id: Optional[str] = ""
    temporary: Optional[bool] = False


class UpdateSessionTranslationRequest(BaseModel):
    session_id: str
    model_id: str
    query: str
    version: int


class UpdateSessionTranslationRespone(BaseModel):
    session_id: str
    title: str
    model: str
    query: str
    translation: str
    source_language_id: str
    target_language_id: str
    source_language_title: str
    target_language_title: str
    version: int
    inserted_at: float
    updated_at: float
    error: str | None


class UpdateSessionTitleRequest(BaseModel):
    session_id: str
    title: str
    version: int


class UpdateSessionTitleRespone(BaseModel):
    session_id: str
    title: str
    model: str
    query: str
    translation: str
    source_language_id: str
    target_language_id: str
    source_language_title: str
    target_language_title: str
    version: int
    inserted_at: float
    updated_at: float
    error: str | None


class DeleteSessionRequest(BaseModel):
    session_id: str


class DeleteSessionRespone(BaseModel):
    status: StatusType


class SearchMessagesInfo(BaseModel):
    title: str
    query: str
    translation: str
    inserted_at: float
    session_id: str
    score: float

class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    sessions: List[SearchMessagesInfo]