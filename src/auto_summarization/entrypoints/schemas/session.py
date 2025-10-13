from typing import List, Optional

from auto_summarization.domain.enums import StatusType
from pydantic import BaseModel


class SessionSearchResult(BaseModel):
    title: str
    query: str
    entities: Optional[str]
    sentiments: Optional[str]
    classifications: Optional[str]
    short_summary: Optional[str]
    full_summary: Optional[str]
    inserted_at: float
    session_id: str
    score: float


class SearchSessionsResponse(BaseModel):
    results: List[SessionSearchResult]


class SessionContent(BaseModel):
    entities: Optional[str]
    sentiments: Optional[str]
    classifications: Optional[str]
    short_summary: Optional[str]
    full_summary: Optional[str]

class SessionInfo(BaseModel):
    session_id: str
    version: int
    title: str
    text: str
    content: SessionContent
    inserted_at: float
    updated_at: float

class FetchSessionResponse(BaseModel):
    sessions: List[SessionInfo]


class CreateSessionRequest(BaseModel):
    text: str
    category: int
    choices: List[int]
    temporary: Optional[bool] = False

class CreateSessionResponse(BaseModel):
    content: SessionContent | None
    error: Optional[str]

class UpdateSessionSummarizationRequest(BaseModel):
    session_id: str
    text: str
    category: int
    choices: List[int]
    version: int

class UpdateSessionSummarizationResponse(BaseModel):
    content: SessionContent | None
    error: Optional[str]

class UpdateSessionTitleRequest(BaseModel):
    session_id: str
    title: str
    version: int

class UpdateSessionTitleResponse(SessionInfo):
    pass

class DeleteSessionRequest(BaseModel):
    session_id: str

class DeleteSessionResponse(BaseModel):
    status: StatusType
