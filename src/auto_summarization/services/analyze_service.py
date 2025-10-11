from __future__ import annotations

from typing import Dict, List

from fastapi import HTTPException, status

from auto_summarization.domain.analysis import AnalysisResult
from auto_summarization.domain.analyze_type import AnalysisCategory, AnalysisChoice
from auto_summarization.services import analyze_types
from auto_summarization.services.utils.text_processing import (
    analyse_sentiment,
    build_full_summary,
    build_short_summary,
    classify_text,
    extract_entities,
)


class AnalyzeService:
    def _get_category(self, category_index: int) -> AnalysisCategory:
        categories = analyze_types.list_categories()
        ordered = sorted(categories, key=lambda item: item.position)
        if category_index < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректная категория")
        try:
            return ordered[category_index]
        except IndexError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректная категория") from exc

    def _get_choices(self, category: AnalysisCategory, indexes: List[int]) -> List[AnalysisChoice]:
        ordered_choices = category.ordered_choices()
        selected: List[AnalysisChoice] = []
        for idx in indexes:
            if idx < 0 or idx >= len(ordered_choices):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный выбор анализа")
            selected.append(ordered_choices[idx])
        return selected

    def analyse(self, text: str, category_index: int, choice_indexes: List[int]) -> AnalysisResult:
        if not text.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Текст не может быть пустым")

        category = self._get_category(category_index)
        choices = self._get_choices(category, choice_indexes)
        by_name: Dict[str, AnalysisChoice] = {choice.name: choice for choice in choices}

        result = AnalysisResult()

        entities_choice = by_name.get("Объекты")
        if entities_choice:
            result.entities = extract_entities(text)

        sentiments_choice = by_name.get("Тональность")
        if sentiments_choice:
            result.sentiments = analyse_sentiment(text)

        classification_choice = by_name.get("Классификация")
        if classification_choice:
            result.classifications = classify_text(
                text,
                category.name,
                classification_choice.model_type,
                classification_choice.prompt,
            )

        short_choice = by_name.get("Аннотация")
        if short_choice:
            result.short_summary = build_short_summary(text, short_choice.prompt)

        full_choice = by_name.get("Выводы")
        if full_choice:
            result.full_summary = build_full_summary(text, full_choice.prompt)

        return result
