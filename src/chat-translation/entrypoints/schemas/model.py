from pydantic import BaseModel
from typing import List


class ModelInfo(BaseModel):
    model_id: str
    model: str
    description: str
    source_language_id: str
    target_language_id: str
    source_language_title: str
    target_language_title: str

class ModelsResponse(BaseModel):
    models: List[ModelInfo]
