from __future__ import annotations

from typing import List, Optional

from .base import IDomain


class Model(IDomain):
    def __init__(
        self,
        model_id: str,
        model: str,
        description: str,
        source_language_id: str,
        target_language_id: str,
        source_language_title: str,
        target_language_title: str,
    ):
        self.model_id = model_id
        self.model = model
        self.description = description
        self.source_language_id = source_language_id
        self.target_language_id = target_language_id
        self.source_language_title = source_language_title
        self.target_language_title = target_language_title

