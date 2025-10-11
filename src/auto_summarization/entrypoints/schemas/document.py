from __future__ import annotations

from pydantic import BaseModel


class LoadDocumentResponse(BaseModel):
    text: str
