from __future__ import annotations

from typing import List, Optional

from .base import IDomain


class AnalysisChoice(IDomain):
    def __init__(
        self,
        choice_id: str,
        category_id: str,
        name: str,
        prompt: str,
        position: int,
        model_type: Optional[str] = None,
    ) -> None:
        self.choice_id = choice_id
        self.category_id = category_id
        self.name = name
        self.prompt = prompt
        self.position = position
        self.model_type = model_type


class AnalysisCategory(IDomain):
    def __init__(
        self,
        category_id: str,
        name: str,
        position: int,
        choices: Optional[List[AnalysisChoice]] = None,
    ) -> None:
        self.category_id = category_id
        self.name = name
        self.position = position
        self.choices: List[AnalysisChoice] = choices or []

    def ordered_choices(self) -> List[AnalysisChoice]:
        return sorted(self.choices, key=lambda choice: choice.position)
