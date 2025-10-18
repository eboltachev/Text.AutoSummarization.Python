from typing import List, Optional

from pydantic import BaseModel

from auto_summarization.domain.enums import StatusType

class SessionContent(BaseModel):
    entities: str = ""
    sentiments: str = ""
    classifications: str = ""
    short_summary: str = ""
    full_summary: str = ""

class ShortSessionInfo(BaseModel):
    session_id: str
    version: int
    title: str
    inserted_at: float
    updated_at: float

class SessionInfo(BaseModel):
    session_id: str
    version: int
    title: str
    text: str
    content: SessionContent
    inserted_at: float
    updated_at: float

class FetchSessionResponse(BaseModel):
    sessions: List[ShortSessionInfo]


class CreateSessionRequest(BaseModel):
    title: str = ""
    text: str
    category: int
    choices: List[int]
    temporary: Optional[bool] = False


class CreateSessionResponse(BaseModel):
    session_id: str
    content: SessionContent
    error: Optional[str]


class UpdateSessionSummarizationRequest(BaseModel):
    session_id: str
    text: str
    category: int
    choices: List[int]
    version: int


class UpdateSessionSummarizationResponse(BaseModel):
    content: SessionContent
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
