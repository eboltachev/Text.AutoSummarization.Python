from __future__ import annotations

from typing import Optional

from .base import IDomain


class AnalysisTemplate(IDomain):
    def __init__(
        self,
        template_id: str,
        category_index: int,
        choice_index: int,
        category: str,
        choice_name: str,
        prompt: str,
        model_type: Optional[str] = None,
    ) -> None:
        self.template_id = template_id
        self.category_index = category_index
        self.choice_index = choice_index
        self.category = category
        self.choice_name = choice_name
        self.prompt = prompt
        self.model_type = model_type

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "category_index": self.category_index,
            "choice_index": self.choice_index,
            "category": self.category,
            "choice_name": self.choice_name,
            "prompt": self.prompt,
            "model_type": self.model_type,
        }
