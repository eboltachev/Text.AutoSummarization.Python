from __future__ import annotations

from typing import List

from pydantic import BaseModel


class AnalyzeTypesResponse(BaseModel):
    categories: List[str]
    choices: List[str]
