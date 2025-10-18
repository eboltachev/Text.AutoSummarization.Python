from typing import List, Optional

from pydantic import BaseModel


class LoadDocumentResponse(BaseModel):
    text: str


class AnalyzeTypesResponse(BaseModel):
    categories: List[str]
    choices: List[str]


class AnalyzeErrorResponse(BaseModel):
    detail: str
