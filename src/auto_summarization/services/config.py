from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List
from uuid import uuid4

from pydantic import AliasChoices, Field, field_validator
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from auto_summarization.adapters.orm import metadata, start_mappers
from auto_summarization.adapters.repository import AnalysisTypeRepository
from auto_summarization.domain.analyze_type import AnalysisCategory, AnalysisChoice


class Settings(BaseSettings):
    AUTO_SUMMARIZATION_URL_PREFIX: str = Field(default="/v1", description="API URL prefix")
    AUTO_SUMMARIZATION_API_HOST: str = Field(default="0.0.0.0", description="FastAPI host")
    AUTO_SUMMARIZATION_API_PORT: int = Field(default=8000, description="FastAPI port")
    AUTO_SUMMARIZATION_DB_TYPE: str = Field(default="postgresql", description="Database driver")
    AUTO_SUMMARIZATION_DB_HOST: str = Field(default="db", description="Database host")
    AUTO_SUMMARIZATION_DB_PORT: int = Field(default=5432, description="Database port")
    AUTO_SUMMARIZATION_DB_NAME: str = Field(default="autosummarization", description="Database name")
    AUTO_SUMMARIZATION_DB_USER: str = Field(default="autosummarizer", description="Database user")
    AUTO_SUMMARIZATION_DB_PASSWORD: str = Field(default="autosummarizer", description="Database password")
    AUTO_SUMMARIZATION_SUPPORTED_FORMATS: str = Field(default="txt,doc,docx,pdf,odt", description="Allowed document formats")
    AUTO_SUMMARIZATION_ANALYZE_TYPES_FILE: str = Field(default="/app/analyze_types.json", description="Path to analyze types JSON")
    AUTO_SUMMARIZATION_HF_MODEL_PATH: str = Field(default="/app/hf_models", description="Mounted Hugging Face models directory")
    AUTO_SUMMARIZATION_OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="Universal OpenAI model for classification")
    AUTO_SUMMARIZATION_MAX_SESSIONS: int = Field(
        default=20,
        description="Maximum number of stored sessions per user",
        validation_alias=AliasChoices("AUTO_SUMMARIZATION_MAX_SESSIONS", "CHAT_TRANSLATION_MAX_SESSIONS"),
    )
    OPENAI_API_HOST: str = Field(default="https://api.openai.com/v1", description="Universal model API host")
    OPENAI_API_KEY: str = Field(default="", description="Universal model API key")
    DEBUG: int = Field(default=0, description="Debug flag")

    @field_validator("AUTO_SUMMARIZATION_SUPPORTED_FORMATS", mode="after")
    @classmethod
    def _parse_formats(cls, value: str) -> List[str]:
        return [item.strip().lower() for item in value.split(",") if item.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
authorization = "Authorization" if not settings.DEBUG else "user_id"

DB_URI = (
    f"{settings.AUTO_SUMMARIZATION_DB_TYPE}://{settings.AUTO_SUMMARIZATION_DB_USER}:{settings.AUTO_SUMMARIZATION_DB_PASSWORD}@"
    f"{settings.AUTO_SUMMARIZATION_DB_HOST}:{settings.AUTO_SUMMARIZATION_DB_PORT}/{settings.AUTO_SUMMARIZATION_DB_NAME}"
)

engine = create_engine(DB_URI)
metadata.create_all(engine)
start_mappers()
SessionFactory = sessionmaker(bind=engine)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_analyze_types() -> None:
    analyze_file = Path(settings.AUTO_SUMMARIZATION_ANALYZE_TYPES_FILE)
    if not analyze_file.exists():
        raise FileNotFoundError(f"Analyze types file not found: {analyze_file}")

    with analyze_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    types = data.get("types", [])
    with session_scope() as session:
        repository = AnalysisTypeRepository(session)
        repository.clear()
        for category_index, category_data in enumerate(types):
            category = AnalysisCategory(
                category_id=str(uuid4()),
                name=category_data["category"],
                position=category_index,
            )
            for choice_index, choice_data in enumerate(category_data.get("choices", [])):
                choice = AnalysisChoice(
                    choice_id=str(uuid4()),
                    category_id=category.category_id,
                    name=choice_data["name"],
                    prompt=choice_data["prompt"],
                    position=choice_index,
                    model_type=choice_data.get("model_type"),
                )
                category.choices.append(choice)
            repository.add(category)
        repository.commit()


load_analyze_types()
