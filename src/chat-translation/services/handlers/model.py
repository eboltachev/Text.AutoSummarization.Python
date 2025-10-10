from typing import List, Dict, Any
from services.data.unit_of_work import IUoW


def get_model_list(uow: IUoW) -> List[Dict[str, Any]]:
    with uow:
        models = [
            dict(
                model_id=m.model_id,
                model=m.model,
                description=m.description,
                source_language_id=m.source_language_id,
                target_language_id=m.target_language_id,
                source_language_title=m.source_language_title,
                target_language_title=m.target_language_title,
            ) for m in uow.models.list()
        ]
    return models
