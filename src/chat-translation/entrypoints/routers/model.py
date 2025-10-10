from entrypoints.schemas.model import ModelInfo, ModelsResponse
from fastapi import APIRouter, HTTPException
from services.data.unit_of_work import ModelUoW
from services.handlers.model import get_model_list

router = APIRouter()


@router.get("/", response_model=ModelsResponse, status_code=200)
async def get_models() -> ModelsResponse:
    try:
        models = [
            ModelInfo(
                model_id=m.get("model_id"),
                model=m.get("model"),
                description=m.get("description"),
                source_language_id=m.get("source_language_id"),
                target_language_id=m.get("target_language_id"),
                source_language_title=m.get("source_language_title"),
                target_language_title=m.get("target_language_title"),
            )
            for m in get_model_list(uow=ModelUoW())
        ]
        return ModelsResponse(models=models)
    except Exception as error:
        raise HTTPException(status_code=404, detail=error)
