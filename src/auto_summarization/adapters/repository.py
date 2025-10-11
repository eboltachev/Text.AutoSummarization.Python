from auto_summarization.domain.analysis import AnalysisTemplate
from auto_summarization.domain.session import Session
from auto_summarization.domain.user import User
from auto_summarization.services.config import Session as DB

from .base import IRepository


class UserRepository(IRepository):
    def __init__(self, db: DB):
        self.db = db

    def add(self, data: User) -> None:
        self.db.add(data)

    def get(self, object_id: str):
        return self.db.query(User).filter_by(user_id=object_id).first()

    def delete(self, user_id: str) -> None:
        user = self.db.query(User).filter_by(user_id=user_id).first()
        if user:
            self.db.delete(user)

    def list(self):
        return self.db.query(User).all()


class SessionRepository(IRepository):
    def __init__(self, db: DB):
        self.db = db

    def add(self, data: Session) -> None:
        self.db.add(data)

    def get(self, object_id: str):
        return self.db.query(Session).filter_by(session_id=object_id).first()

    def list_for_user(self, user_id: str):
        return self.db.query(Session).filter_by(user_id=user_id).all()


class AnalysisTemplateRepository(IRepository):
    def __init__(self, db: DB):
        self.db = db

    def add(self, data: AnalysisTemplate) -> None:
        self.db.add(data)

    def get(self, object_id: str):
        return self.db.query(AnalysisTemplate).filter_by(template_id=object_id).first()

    def list(self):
        return self.db.query(AnalysisTemplate).all()

    def list_by_category(self, category_index: int):
        return (
            self.db.query(AnalysisTemplate)
            .filter_by(category_index=category_index)
            .order_by(AnalysisTemplate.choice_index)
            .all()
        )
