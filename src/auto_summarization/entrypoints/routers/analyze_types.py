from __future__ import annotations

from fastapi import APIRouter

from auto_summarization.entrypoints.schemas.analyze_types import AnalyzeTypesResponse
from auto_summarization.services import analyze_types as analyze_type_service

router = APIRouter()


@router.get("/analyze_types", response_model=AnalyzeTypesResponse)
async def get_analyze_types() -> AnalyzeTypesResponse:
    categories = analyze_type_service.list_categories()
    choices = analyze_type_service.list_choice_names()
    return AnalyzeTypesResponse(
        categories=[category.name for category in categories],
        choices=choices,
    )
