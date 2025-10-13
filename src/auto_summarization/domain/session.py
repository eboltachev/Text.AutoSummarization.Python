from __future__ import annotations

from .base import IDomain


class Session(IDomain):
    def __init__(
        self,
        session_id: str,
        title: str,
        category: str,
        text: str,
        summary: str,
        analysis: str,
        version: int,
        inserted_at: float,
        updated_at: float,
    ) -> None:
        self.session_id = session_id
        self.title = title
        self.category = category
        self.text = text
        self.summary = summary
        self.analysis = analysis
        self.version = version
        self.inserted_at = inserted_at
        self.updated_at = updated_at

    def __str__(self) -> str:
        return self.title or "Без названия"
