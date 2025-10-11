from __future__ import annotations

from auto_summarization.domain.analyze_type import AnalysisCategory, AnalysisChoice
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, Text
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
