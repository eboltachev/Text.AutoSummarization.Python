from pathlib import Path

from services.config import settings
from transformers import pipeline

model_dir = Path(settings.CHAT_TRANSLATION_SPEC_MODEL_PATH)


class SpecialTranslationModel:
    def __init__(self, model_name: Path):
        self.model = pipeline("translation", model=str(model_name))

    def translate(self, text: str) -> str:
        translated = self.model(text)[0]
        return translated.get("translation_text", "")


class SpecialTranslator:
    _models = {}

    @classmethod
    def get_model(cls, source_lang: str, target_lang: str) -> SpecialTranslationModel:
        key = f"{source_lang}-{target_lang}"
        if key not in cls._models:
            cls._models[key] = SpecialTranslationModel(model_dir / f"{source_lang}-{target_lang}")
        return cls._models[key]

    @classmethod
    def translate(cls, text: str, source_lang: str, target_lang: str) -> str:
        model = cls.get_model(source_lang, target_lang)
        return model.translate(text)
