from __future__ import annotations

import time
from typing import Optional

from auto_summarization.domain.base import IDomain


class User(IDomain):
    def __init__(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        inserted_at: Optional[float] = None,
    ) -> None:
        self.user_id = user_id
        self.display_name = display_name or user_id
        self.inserted_at = inserted_at or time.time()

    def rename(self, display_name: str) -> None:
        cleaned = display_name.strip()
        if cleaned:
            self.display_name = cleaned
