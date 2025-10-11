from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, root_validator, validator

from auto_summarization.entrypoints.schemas.analysis import AnalyzeResponse


class CreateChatSessionRequest(BaseModel):
    text: str
    category: int
    choices: List[int] = Field(default_factory=list)
    title: Optional[str] = None


class UpdateTranslationRequest(BaseModel):
    session_id: str
    text: Optional[str] = None
    category: Optional[int] = None
    choices: Optional[List[int]] = None
    version: Optional[int] = None

    @root_validator
    def _ensure_payload(cls, values: dict) -> dict:
        if not any(values.get(field) is not None for field in ("text", "category", "choices")):
            raise ValueError("Необходимо передать текст, категорию или варианты выбора для обновления")
        return values


class UpdateTitleRequest(BaseModel):
    session_id: str
    title: str
    version: Optional[int] = None

    @validator("title")
    def _validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Некорректный заголовок")
        return normalized


class SearchSessionsRequest(BaseModel):
    query: str = Field(default="", description="Строка для поиска среди заголовков и текстов сессий")


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


class SessionPageResponse(BaseModel):
    sessions: List[SessionSummary] = Field(default_factory=list)
    active_session: Optional[SessionDetailResponse] = None


class DeleteSessionResponse(BaseModel):
    status: str
