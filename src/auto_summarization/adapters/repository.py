from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from auto_summarization.domain.analyze_type import AnalysisCategory, AnalysisChoice
from auto_summarization.domain.session import AnalysisSession
from auto_summarization.domain.user import User

from .base import IRepository


class AnalysisTypeRepository(IRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, data: AnalysisCategory) -> None:  # type: ignore[override]
        self._db.add(data)

    def list(self) -> Iterable[AnalysisCategory]:  # type: ignore[override]
        return (
            self._db.query(AnalysisCategory)
            .order_by(AnalysisCategory.position)
            .all()
        )

    def clear(self) -> None:
        self._db.query(AnalysisChoice).delete()
        self._db.query(AnalysisCategory).delete()

    def commit(self) -> None:
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def list_choices(self) -> List[AnalysisChoice]:
        return (
            self._db.query(AnalysisChoice)
            .order_by(AnalysisChoice.position)
            .all()
        )


class SessionRepository(IRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, data: AnalysisSession) -> None:  # type: ignore[override]
        self._db.add(data)

    def list(self) -> Iterable[AnalysisSession]:  # type: ignore[override]
        return (
            self._db.query(AnalysisSession)
            .order_by(AnalysisSession.updated_at.desc())
            .all()
        )

    def list_for_user(self, user_id: str) -> List[AnalysisSession]:
        return (
            self._db.query(AnalysisSession)
            .filter(AnalysisSession.user_id == user_id)
            .order_by(AnalysisSession.updated_at.desc())
            .all()
        )

    def fetch_page_for_user(
        self,
        user_id: str,
        *,
        page: int,
        size: int,
    ) -> Tuple[List[AnalysisSession], int]:
        query = (
            self._db.query(AnalysisSession)
            .filter(AnalysisSession.user_id == user_id)
            .order_by(AnalysisSession.updated_at.desc())
        )
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def get_for_user(self, session_id: str, user_id: str) -> Optional[AnalysisSession]:
        return (
            self._db.query(AnalysisSession)
            .filter(
                AnalysisSession.session_id == session_id,
                AnalysisSession.user_id == user_id,
            )
            .one_or_none()
        )

    def delete(self, instance: AnalysisSession) -> None:
        self._db.delete(instance)

    def count_for_user(self, user_id: str) -> int:
        return (
            self._db.query(AnalysisSession)
            .filter(AnalysisSession.user_id == user_id)
            .count()
        )

    def trim_to_limit(self, user_id: str, max_keep: int) -> None:
        if max_keep < 0:
            return
        total = self.count_for_user(user_id)
        if total <= max_keep:
            return
        excess = total - max_keep
        oldest = (
            self._db.query(AnalysisSession)
            .filter(AnalysisSession.user_id == user_id)
            .order_by(AnalysisSession.updated_at.asc())
            .limit(excess)
            .all()
        )
        for session in oldest:
            self._db.delete(session)

    def search_for_user(
        self,
        user_id: str,
        *,
        query: str,
        limit: int,
    ) -> List[AnalysisSession]:
        pattern = f"%{query}%"
        return (
            self._db.query(AnalysisSession)
            .filter(AnalysisSession.user_id == user_id)
            .filter(
                or_(
                    AnalysisSession.title.ilike(pattern),
                    AnalysisSession.text.ilike(pattern),
                    cast(AnalysisSession.results, String).ilike(pattern),
                )
            )
            .order_by(AnalysisSession.updated_at.desc())
            .limit(limit)
            .all()
        )


class UserRepository(IRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, data: User) -> None:  # type: ignore[override]
        self._db.merge(data)

    def list(self) -> Iterable[User]:  # type: ignore[override]
        return self._db.query(User).order_by(User.inserted_at.asc()).all()

    def get(self, user_id: str) -> Optional[User]:
        return self._db.query(User).filter(User.user_id == user_id).one_or_none()

    def delete(self, user: User) -> None:
        self._db.delete(user)
