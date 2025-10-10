from __future__ import annotations

from typing import List, Optional

from .base import IDomain


class Session(IDomain):
    def __init__(
        self,
        session_id: str,
        title: str,
        model: str,
        query: str,
        translation: str,
        source_language_id: str,
        target_language_id: str,
        source_language_title: str,
        target_language_title: str,
        version: int,
        inserted_at: float,
        updated_at: float,
    ):
        self.session_id = session_id
        self.title = title
        self.model = model
        self.query = query
        self.translation = translation
        self.source_language_id = source_language_id
        self.target_language_id = target_language_id
        self.source_language_title = source_language_title
        self.target_language_title = target_language_title
        self.version = version
        self.inserted_at = inserted_at
        self.updated_at = updated_at

    def __str__(self):
        return self.title or "No Title"
