from typing import List, Optional

from pydantic import BaseModel


class LoadDocumentResponse(BaseModel):
    text: str


class AnalyzeRequest(BaseModel):
    text: str
    category: int
    choices: List[int]


class AnalyzeResponse(BaseModel):
    entities: str
    sentiments: str
    classifications: str
    short_summary: str
    full_summary: str


class AnalyzeTypesResponse(BaseModel):
    categories: List[str]
    choices: List[str]


class AnalyzeErrorResponse(BaseModel):
    detail: str


class LoadDocumentRequest(BaseModel):
    document: Optional[str]
