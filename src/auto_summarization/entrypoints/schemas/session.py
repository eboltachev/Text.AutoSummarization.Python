from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from auto_summarization.entrypoints.schemas.analysis import AnalyzeResponse


class CreateSessionRequest(BaseModel):
    text: str
    category: int
    choices: List[int] = Field(default_factory=list)
    title: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    category: Optional[int] = None
    choices: Optional[List[int]] = None
    version: Optional[int] = None


class SessionSummary(BaseModel):
    session_id: str
    title: str
    category: int
    choices: List[int]
    version: int
    inserted_at: float
    updated_at: float


class SessionDetailResponse(SessionSummary):
    text: str
    analysis: AnalyzeResponse


class SessionListResponse(BaseModel):
    sessions: List[SessionSummary] = Field(default_factory=list)


class DeleteSessionResponse(BaseModel):
    status: str
