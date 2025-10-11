from __future__ import annotations

from typing import Iterable, List

from sqlalchemy.orm import Session

from auto_summarization.domain.analyze_type import AnalysisCategory, AnalysisChoice

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
