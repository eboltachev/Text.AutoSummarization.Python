import logging
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict

from domain.enums import ModelType
from services.config import LANGUAGE_NAMES as languages
from services.pipelines.detector.langdetect import LanguageDetector
from services.pipelines.translation.special import SpecialTranslator
from services.pipelines.translation.universal import UniversalTranslator

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


class IProcessor(ABC):
    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplemented


class TranslatorProcessor(IProcessor):
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"start translation")
        query: str = data["query"]
        mode: ModelType = data.get("mode", "UNIVERSAL").upper()
        source_language_id: str = data.get("source_language_id", "auto").lower()
        target_language_id: str = data.get("target_language_id", "ru").lower()
        special_models: list = data.get("special_models", [])
        try:
            if mode == "AUTO":
                mode = "SPECIAL" if source_language_id in special_models else "UNIVERSAL"
                data['mode'] = mode
            if data.get("error"):
                data["translation"] = ""
            else:
                if mode == "UNIVERSAL":
                    data["translation"] = UniversalTranslator.translate(query, source_language_id, target_language_id)
                elif mode == "SPECIAL":
                    data["translation"] = SpecialTranslator.translate(query, source_language_id, target_language_id)
                else:
                    raise ValueError(f"Unknown mode: {mode}")
        except Exception as error:
            data["translation"] = ""
            data["error"] = error
            logger.error(f"{error=}")
        finally:
            logger.info(f"finish translation")
            return data


class DetectorProcessor(IProcessor):
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"start language detection")
        query: str = data["query"]
        source_language_id: str = data.get("source_language_id", "auto").lower()
        try:
            if source_language_id == "auto":
                source_language_id = LanguageDetector.detect(query)
            if source_language_id not in languages:
                data["error"] = "bad language"
            data["source_language_id"] = source_language_id
        except Exception as error:
            data["error"] = error
            logger.error(f"{error=}")
        finally:
            logger.info(f"finish language detection")
            return data
