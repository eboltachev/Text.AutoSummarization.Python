from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    text: str
    category: int
    choices: List[int] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    entities: Dict[str, object]
    sentiments: Dict[str, object]
    classifications: Dict[str, object]
    short_summary: Optional[str]
    full_summary: Optional[str]
