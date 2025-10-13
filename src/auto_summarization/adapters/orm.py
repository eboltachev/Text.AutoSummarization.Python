from auto_summarization.domain.analysis import AnalysisTemplate
from auto_summarization.domain.session import Session
from auto_summarization.domain.user import User
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, MetaData, String, Table, Text
from sqlalchemy.orm import registry, relationship

metadata = MetaData()
mapper_registry = registry()

analysis_templates = Table(
    "analysis_templates",
    metadata,
    Column("template_id", String, primary_key=True, autoincrement=False),
    Column("category_index", Integer, nullable=False),
    Column("choice_index", Integer, nullable=False),
    Column("category", String, nullable=False),
    Column("choice_name", String, nullable=False),
    Column("prompt", Text, nullable=False),
    Column("model_type", String, nullable=True),
)

users = Table(
    "users",
    metadata,
    Column("user_id", String, primary_key=True),
    Column("temporary", Boolean, nullable=False),
    Column("started_using_at", Float, nullable=False),
    Column("last_used_at", Float, nullable=True),
)

sessions = Table(
    "sessions",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("user_id", String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("title", String, nullable=False),
    Column("text", Text, nullable=False),
    Column("short_summary", Text, nullable=True),
    Column("entities", Text, nullable=True),
    Column("sentiments", Text, nullable=True),
    Column("classifications", Text, nullable=True),
    Column("full_summary", Text, nullable=True),
    Column("inserted_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
)


def start_mappers():
    mapper_registry.map_imperatively(AnalysisTemplate, analysis_templates)
    mapper_registry.map_imperatively(
        User,
        users,
        properties={
            "sessions": relationship(
                Session,
                backref="users",
                order_by=sessions.c.updated_at,
                cascade="all, delete-orphan",
                passive_deletes=True,
            )
        },
    )
    mapper_registry.map_imperatively(Session, sessions)
