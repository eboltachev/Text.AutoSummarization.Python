from __future__ import annotations

from auto_summarization.domain.analyze_type import AnalysisCategory, AnalysisChoice
from auto_summarization.domain.session import AnalysisSession
from sqlalchemy import JSON, Column, Float, ForeignKey, Integer, MetaData, String, Table, Text
from sqlalchemy.orm import registry, relationship

metadata = MetaData()
mapper_registry = registry()

analysis_categories = Table(
    "analysis_categories",
    metadata,
    Column("category_id", String, primary_key=True, autoincrement=False),
    Column("name", String, nullable=False),
    Column("position", Integer, nullable=False),
)

analysis_choices = Table(
    "analysis_choices",
    metadata,
    Column("choice_id", String, primary_key=True, autoincrement=False),
    Column("category_id", String, ForeignKey("analysis_categories.category_id", ondelete="CASCADE"), nullable=False),
    Column("name", String, nullable=False),
    Column("prompt", Text, nullable=False),
    Column("model_type", String, nullable=True),
    Column("position", Integer, nullable=False),
)


analysis_sessions = Table(
    "analysis_sessions",
    metadata,
    Column("session_id", String, primary_key=True, autoincrement=False),
    Column("user_id", String, index=True, nullable=False),
    Column("title", String, nullable=False),
    Column("text", Text, nullable=False),
    Column("category_index", Integer, nullable=False),
    Column("choice_indexes", JSON, nullable=False),
    Column("results", JSON, nullable=False),
    Column("version", Integer, nullable=False),
    Column("inserted_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
)


def start_mappers() -> None:
    mapper_registry.map_imperatively(
        AnalysisCategory,
        analysis_categories,
        properties={
            "choices": relationship(
                AnalysisChoice,
                backref="category",
                order_by=analysis_choices.c.position,
                cascade="all, delete-orphan",
            )
        },
    )
    mapper_registry.map_imperatively(AnalysisChoice, analysis_choices)
    mapper_registry.map_imperatively(AnalysisSession, analysis_sessions)
