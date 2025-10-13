import json
import logging
from json import JSONDecodeError
from pathlib import Path
from typing import List, Tuple
from uuid import uuid4

from auto_summarization.adapters.orm import metadata, start_mappers
from auto_summarization.domain.analysis import AnalysisTemplate
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from pydantic_settings.sources import (
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        class LenientEnvSource(EnvSettingsSource):
            def decode_complex_value(self, field_name, field, value):  # type: ignore[override]
                try:
                    return super().decode_complex_value(field_name, field, value)
                except JSONDecodeError:
                    return value

        class LenientDotEnvSource(DotEnvSettingsSource):
            def decode_complex_value(self, field_name, field, value):  # type: ignore[override]
                try:
                    return super().decode_complex_value(field_name, field, value)
                except JSONDecodeError:
                    return value

        lenient_env = LenientEnvSource(
            settings_cls,
            case_sensitive=getattr(env_settings, "case_sensitive", None),
            env_prefix=getattr(env_settings, "env_prefix", None),
            env_nested_delimiter=getattr(env_settings, "env_nested_delimiter", None),
            env_nested_max_split=getattr(env_settings, "env_nested_max_split", None),
            env_ignore_empty=getattr(env_settings, "env_ignore_empty", None),
            env_parse_none_str=getattr(env_settings, "env_parse_none_str", None),
            env_parse_enums=getattr(env_settings, "env_parse_enums", None),
        )

        lenient_dotenv = LenientDotEnvSource(
            settings_cls,
            env_file=getattr(dotenv_settings, "env_file", None),
            env_file_encoding=getattr(dotenv_settings, "env_file_encoding", None),
            case_sensitive=getattr(dotenv_settings, "case_sensitive", None),
            env_prefix=getattr(dotenv_settings, "env_prefix", None),
            env_nested_delimiter=getattr(dotenv_settings, "env_nested_delimiter", None),
            env_nested_max_split=getattr(dotenv_settings, "env_nested_max_split", None),
            env_ignore_empty=getattr(dotenv_settings, "env_ignore_empty", None),
            env_parse_none_str=getattr(dotenv_settings, "env_parse_none_str", None),
            env_parse_enums=getattr(dotenv_settings, "env_parse_enums", None),
        )

        return (
            init_settings,
            lenient_env,
            lenient_dotenv,
            file_secret_settings,
        )

    @field_validator("AUTO_SUMMARIZATION_SUPPORTED_FORMATS", mode="before")
    @classmethod
    def parse_formats(cls, value: str | List[str] | Tuple[str, ...]) -> Tuple[str, ...]:
        if isinstance(value, str):
            formats = [item.strip().lower() for item in value.split(",") if item.strip()]
        elif isinstance(value, tuple):
            formats = [str(item).strip().lower() for item in value if str(item).strip()]
        else:
            formats = [str(item).strip().lower() for item in value if str(item).strip()]
        return tuple(sorted(set(formats), key=formats.index))

    AUTO_SUMMARIZATION_SUPPORTED_FORMATS: Tuple[str, ...] = Field(
        default=("txt", "doc", "docx", "pdf", "odt"), description="Allowed document formats"
    )
    AUTO_SUMMARIZATION_MAX_SESSIONS: int = Field(default=100, description="Max sessions per user")
    AUTO_SUMMARIZATION_URL_PREFIX: str = Field(default="/v1", description="API URL prefix")
    AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH: str = Field(
        default="/app/analyze_types.json", description="Path to analyze types configuration"
    )
    AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH: str = Field(
        default="/app/hf_models/xlm-roberta-large-xnli", description="Mounted HuggingFace model path"
    )
    AUTO_SUMMARIZATION_PRETRAINED_MODEL_NAME: str = Field(
        default="joeddav/xlm-roberta-large-xnli", description="Fallback HuggingFace model name"
    )
    AUTO_SUMMARIZATION_CONNECTION_TIMEOUT: int = Field(
        default=60, description="Timeout for knowledge base model requests"
    )
    AUTO_SUMMARIZATION_DB_TYPE: str = Field(default="postgresql", description="DB type")
    AUTO_SUMMARIZATION_DB_HOST: str = Field(default="db", description="DB host")
    AUTO_SUMMARIZATION_DB_PORT: int = Field(default=5432, description="DB port")
    AUTO_SUMMARIZATION_DB_NAME: str = Field(default="autosummarization", description="DB name")
    AUTO_SUMMARIZATION_DB_USER: str = Field(default="autosummary", description="DB user")
    AUTO_SUMMARIZATION_DB_PASSWORD: str | None = Field(
        default=None, description="DB password (optional for local development)"
    )
    OPENAI_API_HOST: str = Field(
        default="http://localhost:8000/v1", description="OpenAI compatible endpoint"
    )
    OPENAI_API_KEY: str | None = Field(default=None, description="API key for universal model")
    OPENAI_MODEL_NAME: str = Field(default="Qwen/Qwen3-4B-AWQ", description="Model name for universal analysis")
    DEBUG: int = Field(default=0, description="Debug mode flag")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
authorization = "Authorization" if not settings.DEBUG else "user_id"


def _build_db_uri(config: Settings) -> str:
    db_type = (config.AUTO_SUMMARIZATION_DB_TYPE or "").lower()
    if db_type.startswith("sqlite"):
        db_name = config.AUTO_SUMMARIZATION_DB_NAME
        if db_name.startswith("sqlite://"):
            return db_name
        return f"sqlite:///{db_name}"
    if config.AUTO_SUMMARIZATION_DB_PASSWORD is None:
        logger.warning(
            "Database password is not configured; using an in-memory SQLite database for temporary storage."
        )
        return "sqlite:///:memory:"
    return (
        f"{config.AUTO_SUMMARIZATION_DB_TYPE}://{config.AUTO_SUMMARIZATION_DB_USER}:{config.AUTO_SUMMARIZATION_DB_PASSWORD}@"
        f"{config.AUTO_SUMMARIZATION_DB_HOST}:{config.AUTO_SUMMARIZATION_DB_PORT}/{config.AUTO_SUMMARIZATION_DB_NAME}"
    )


FALLBACK_SQLITE_URI = "sqlite:///:memory:"


def _initialize_engine(primary_uri: str) -> tuple[str, Engine]:
    engine = create_engine(primary_uri)
    try:
        metadata.create_all(engine)
        return primary_uri, engine
    except OperationalError as exc:
        logger.warning(
            "Unable to initialize database at %s (%s); falling back to SQLite in-memory store.",
            primary_uri,
            exc,
        )
        engine.dispose()
        fallback_engine = create_engine(FALLBACK_SQLITE_URI)
        metadata.create_all(fallback_engine)
        return FALLBACK_SQLITE_URI, fallback_engine


DB_URI, engine = _initialize_engine(_build_db_uri(settings))
start_mappers()
session_factory = sessionmaker(bind=engine, expire_on_commit=False)


def register_analysis_templates(session: Session = session_factory()):
    path = Path(settings.AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH)
    if not path.exists():
        session.close()
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        session.query(AnalysisTemplate).delete()
        session.commit()
        for category_index, item in enumerate(payload.get("types", [])):
            category = item.get("category")
            if not category:
                continue
            for choice_index, choice in enumerate(item.get("choices", [])):
                name = choice.get("name")
                prompt = choice.get("prompt", "")
                model_type = choice.get("model_type")
                template = AnalysisTemplate(
                    template_id=str(uuid4()),
                    category_index=category_index,
                    choice_index=choice_index,
                    category=category,
                    choice_name=name,
                    prompt=prompt,
                    model_type=model_type,
                )
                session.add(template)
        session.commit()
    finally:
        session.close()


register_analysis_templates()
