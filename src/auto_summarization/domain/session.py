from __future__ import annotations

from typing import List, Optional

from .base import IDomain


class Session(IDomain):
    def __init__(
        self,
        session_id: str,
        version: int,
        title: str,
        text: str,
        short_summary: Optional[str],
        entities: Optional[str],
        sentiments: Optional[str],
        classifications: Optional[str],
        full_summary: Optional[str],
        inserted_at: float,
        updated_at: float,
    ) -> None:
        self.session_id = session_id
        self.version = version
        self.title = title
        self.text = text
        self.short_summary = short_summary
        self.entities = entities
        self.sentiments = sentiments
        self.classifications = classifications
        self.full_summary = full_summary
        self.inserted_at = inserted_at
        self.updated_at = updated_at

    def __str__(self) -> str:
        return self.title or self.text[:40]
