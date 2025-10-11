from __future__ import annotations

from fastapi import APIRouter, Depends

from auto_summarization.entrypoints.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from auto_summarization.services.analyze_service import AnalyzeService

router = APIRouter()


def get_service() -> AnalyzeService:
    return AnalyzeService()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest, service: AnalyzeService = Depends(get_service)) -> AnalyzeResponse:
    result = service.analyse(payload.text, payload.category, payload.choices)
    return AnalyzeResponse(
        entities=result.entities or {},
        sentiments=result.sentiments or {},
        classifications=result.classifications or {},
        short_summary=result.short_summary,
        full_summary=result.full_summary,
    )
