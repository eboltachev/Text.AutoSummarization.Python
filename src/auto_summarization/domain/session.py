from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from auto_summarization.domain.base import IDomain


class AnalysisSession(IDomain):
    def __init__(
        self,
        session_id: str,
        user_id: str,
        title: str,
        text: str,
        category_index: int,
        choice_indexes: List[int],
        results: Dict[str, Any],
        version: int = 1,
        inserted_at: Optional[float] = None,
        updated_at: Optional[float] = None,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.title = title
        self.text = text
        self.category_index = category_index
        self.choice_indexes = choice_indexes
        self.results = results
        self.version = version
        now = time.time()
        self.inserted_at = inserted_at or now
        self.updated_at = updated_at or now

    def update_payload(
        self,
        *,
        text: str,
        category_index: int,
        choice_indexes: List[int],
        results: Dict[str, Any],
    ) -> None:
        self.text = text
        self.category_index = category_index
        self.choice_indexes = choice_indexes
        self.results = results

    def rename(self, title: str) -> None:
        self.title = title

