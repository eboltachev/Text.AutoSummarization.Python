import os
from typing import List
from uuid import uuid4

from adapters.orm import metadata, start_mappers
from domain.enums import ModelType
from domain.model import Model
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session


class Settings(BaseSettings):
    @field_validator("CHAT_TRANSLATION_LANGUAGES", mode="after")
    @classmethod
    def parse_extensions(cls, v: str) -> List[str]:
        return [ext.strip().lower() for ext in v.split(",") if ext.strip()]

    CHAT_TRANSLATION_LANGUAGES: str = Field(default="en,ru", description="Allowed upload file formats")
    CHAT_TRANSLATION_DEFAULT_TARGET_LANGUAGE: str = Field(default="ru", description="Default target language")
    CHAT_TRANSLATION_UNIVERSAL_MODEL: str = Field(default="Qwen/Qwen3-4B-AWQ", description="Universal model")
    CHAT_TRANSLATION_SPEC_MODEL_PATH: str = Field(default="models", description="Special model path")
    CHAT_TRANSLATION_MAX_SESSIONS: int = Field(default=100, description="Max sessions")
    CHAT_TRANSLATION_URL_PREFIX: str = Field(default="/v1", description="API URL prefix")
    CHAT_TRANSLATION_DB_TYPE: str = Field(default="postgresql", description="DB type")
    CHAT_TRANSLATION_DB_HOST: str = Field(default="db", description="DB host")
    CHAT_TRANSLATION_DB_PORT: int = Field(default=5432, description="DB port")
    CHAT_TRANSLATION_DB_NAME: str = Field(default="cxchat", description="DB name")
    CHAT_TRANSLATION_DB_USER: str = Field(default="cxuser", description="DB user")
    CHAT_TRANSLATION_DB_PASSWORD: str = Field(description="DB password")
    OPENAI_API_HOST: str = Field(default="http://10.239.16.89:11435/v1", description="API URL")
    OPENAI_API_KEY: str = Field(description="API KEY")

    DEBUG: int = Field(default=0, description="Debug mode flag")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
authorization = "Authorization" if not settings.DEBUG else "user_id"
DB_URI = (
    f"{settings.CHAT_TRANSLATION_DB_TYPE}://{settings.CHAT_TRANSLATION_DB_USER}:{settings.CHAT_TRANSLATION_DB_PASSWORD}@"
    f"{settings.CHAT_TRANSLATION_DB_HOST}:{settings.CHAT_TRANSLATION_DB_PORT}/{settings.CHAT_TRANSLATION_DB_NAME}"
)
engine = create_engine(DB_URI)
metadata.create_all(engine)
start_mappers()
session_factory = sessionmaker(bind=create_engine(DB_URI))

LANGUAGE_NAMES = {
    "ru": "Русский",
    "en": "Английский",
    "ar": "Арабский",
    "kk": "Казахский",
    "uk": "Украинский",
    "tr": "Турецкий",
    "fa": "Персидский",
    "ku": "Курдский",
    "az": "Азербайджанский",
    "hy": "Армянский",
    "ky": "Киргизский",
    "tg": "Таджикский",
    "uz": "Узбекский",
}


def lang_title(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code.upper() if code == "auto" else code)


def register_translation_models(session: Session = session_factory()) -> None:
    models_dir = os.path.abspath(settings.CHAT_TRANSLATION_SPEC_MODEL_PATH)
    try:
        for folder in os.listdir(models_dir) + ["auto-ru"]:
            if "auto" not in folder and not os.path.isdir(os.path.join(models_dir, folder)):
                continue
            if "-" not in folder:
                continue
            source_lang, target_lang = folder.split("-", 1)
            if not (source_lang and target_lang):
                continue
            exists = (
                session.query(Model)
                .filter_by(model=ModelType.SPECIAL, source_language_id=source_lang, target_language_id=target_lang)
                .first()
            )
            if not exists:
                m = Model(
                    model_id=str(uuid4()),
                    model=ModelType.SPECIAL,
                    description=f"{lang_title(source_lang)} → {lang_title(target_lang)}",
                    source_language_id=source_lang,
                    target_language_id=target_lang,
                    source_language_title=LANGUAGE_NAMES.get(source_lang, "auto"),
                    target_language_title=LANGUAGE_NAMES.get(target_lang, "ru"),
                )
                session.add(m)
        langs = settings.CHAT_TRANSLATION_LANGUAGES
        target_lang = "ru"
        if isinstance(langs, str):
            langs = [l.strip() for l in langs.split(",") if l.strip()]
        for lang in langs + ["auto"]:
            exists = (
                session.query(Model)
                .filter_by(model=ModelType.UNIVERSAL, source_language_id=lang, target_language_id="ru")
                .first()
            )
            if not exists:
                m = Model(
                    model_id=str(uuid4()),
                    model=ModelType.UNIVERSAL,
                    description=f"{lang_title(lang)} → {lang_title(target_lang)}",
                    source_language_id=lang,
                    target_language_id="ru",
                    source_language_title=LANGUAGE_NAMES.get(lang, "auto"),
                    target_language_title=LANGUAGE_NAMES.get("ru", "ru"),
                )
                session.add(m)
        session.commit()
    finally:
        session.close()


register_translation_models()


