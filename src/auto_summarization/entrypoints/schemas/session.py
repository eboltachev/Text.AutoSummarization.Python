from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from auto_summarization.entrypoints.schemas.analysis import AnalyzeResponse


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


class SessionPageResponse(BaseModel):
    sessions: List[SessionSummary] = Field(default_factory=list)
    total: int
    page: int
    size: int


class CreateSessionRequest(BaseModel):
    text: str
    category: int
    choices: List[int] = Field(default_factory=list)
    title: Optional[str] = None


class UpdateTranslationRequest(BaseModel):
    session_id: str
    text: Optional[str] = None
    category: Optional[int] = None
    choices: Optional[List[int]] = None
    version: int


class UpdateTitleRequest(BaseModel):
    session_id: str
    title: str
    version: int


class SessionSearchResponse(BaseModel):
    sessions: List[SessionSummary] = Field(default_factory=list)


class DeleteSessionRequest(BaseModel):
    session_id: str


class DeleteSessionResponse(BaseModel):
    status: str
