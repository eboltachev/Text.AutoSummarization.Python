from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from auto_summarization.entrypoints.schemas.document import LoadDocumentResponse
from auto_summarization.services.config import settings
from auto_summarization.services.document_service import DocumentService

router = APIRouter()


def get_document_service() -> DocumentService:
    return DocumentService(settings.AUTO_SUMMARIZATION_SUPPORTED_FORMATS)


@router.post("/load_document", response_model=LoadDocumentResponse)
async def load_document(
    document: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
) -> LoadDocumentResponse:
    text = await service.extract_text(document)
    return LoadDocumentResponse(text=text)
