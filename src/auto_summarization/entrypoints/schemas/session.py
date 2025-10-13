from typing import List, Optional

from auto_summarization.domain.enums import StatusType
from pydantic import BaseModel


class SessionInfo(BaseModel):
    session_id: str
    version: int
    title: str
    text: str
    short_summary: Optional[str]
    entities: Optional[str]
    sentiments: Optional[str]
    classifications: Optional[str]
    full_summary: Optional[str]
    inserted_at: float
    updated_at: float
    error: Optional[str]

class FetchSessionResponse(BaseModel):
    sessions: List[SessionInfo]

class CreateSessionRequest(BaseModel):
    text: str
    category: int
    choices: List[int]
    temporary: Optional[bool] = False

class CreateSessionResult(BaseModel):
    entities: str
    sentiments: str
    classifications: str
    short_summary: str
    full_summary: str

class CreateSessionResponse(BaseModel):
    result: CreateSessionResult | None
    error: Optional[str]

class UpdateSessionSummarizationRequest(BaseModel):
    session_id: str
    text: str
    category: int
    choices: List[int]
    version: int

class UpdateSessionSummarizationResponse(SessionInfo):
    pass

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
