from domain.model import Model
from domain.session import Session
from domain.user import User
from sqlalchemy import Column, Float, ForeignKey, Integer, MetaData, String, Table, Boolean
from sqlalchemy.orm import registry, relationship

metadata = MetaData()
mapper_registry = registry()

models = Table(
    "models",
    metadata,
    Column("model_id", String, primary_key=True, autoincrement=False),
    Column("model", String, nullable=False),
    Column("description", String, nullable=False),
    Column("source_language_id", String, nullable=False),
    Column("target_language_id", String, nullable=False),
    Column("source_language_title", String, nullable=False),
    Column("target_language_title", String, nullable=False),
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
    Column("title", String, nullable=False),
    Column("model", String, nullable=False),
    Column("query", String, nullable=False),
    Column("translation", String, nullable=False),
    Column("source_language_id", String, nullable=False),
    Column("target_language_id", String, nullable=False),
    Column("source_language_title", String, nullable=False),
    Column("target_language_title", String, nullable=False),
    Column("version", Integer, nullable=False),
    Column("inserted_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
)


def start_mappers():
    mapper_registry.map_imperatively(Model, models)
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
