from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from auto_summarization.entrypoints.schemas.analysis import AnalyzeRequest, AnalyzeResponse, AnalyzeTypesResponse, LoadDocumentResponse
from auto_summarization.services.config import authorization
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW
from auto_summarization.services.handlers.analysis import extract_text, get_analyze_types, perform_analysis

router = APIRouter()


@router.post("/load_document", response_model=LoadDocumentResponse, status_code=200)
async def load_document(
    document: UploadFile = File(...),
    auth: str = Header(default=None, alias=authorization),
) -> LoadDocumentResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    filename = document.filename or "document.txt"
    suffix = Path(filename).suffix or ".txt"
    try:
        content = await document.read()
        text = extract_text(content, suffix)
        return LoadDocumentResponse(text=text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/analyze_types", response_model=AnalyzeTypesResponse, status_code=200)
async def analyze_types() -> AnalyzeTypesResponse:
    categories, choices = get_analyze_types(AnalysisTemplateUoW())
    return AnalyzeTypesResponse(categories=categories, choices=choices)


@router.post("/analyze", response_model=AnalyzeResponse, status_code=200)
async def analyze(
    request: AnalyzeRequest,
    auth: str = Header(default=None, alias=authorization),
) -> AnalyzeResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    try:
        result = perform_analysis(
            text=request.text,
            category_index=request.category,
            choice_indices=request.choices,
            uow=AnalysisTemplateUoW(),
        )
        return AnalyzeResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
