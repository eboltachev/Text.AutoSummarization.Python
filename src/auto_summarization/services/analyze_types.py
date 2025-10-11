from __future__ import annotations

from typing import List

from auto_summarization.adapters.repository import AnalysisTypeRepository
from auto_summarization.domain.analyze_type import AnalysisCategory

from .config import session_scope


def list_categories() -> List[AnalysisCategory]:
    with session_scope() as session:
        repository = AnalysisTypeRepository(session)
        categories = list(repository.list())
        # Load choices before closing the session
        for category in categories:
            _ = list(category.ordered_choices())
        return categories


def list_choice_names() -> List[str]:
    categories = list_categories()
    if not categories:
        return []
    primary_choices = categories[0].ordered_choices()
    return [choice.name for choice in primary_choices]
