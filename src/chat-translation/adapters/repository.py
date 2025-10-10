from typing import Optional

from domain.model import Model
from domain.session import Session
from domain.user import User
from services.config import Session as DB

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


class ModelRepository(IRepository):
    def __init__(self, db: DB):
        self.db = db

    def add(self, data: Model) -> None:
        self.db.add(data)

    def get(self, object_id: str):
        return self.db.query(Model).filter_by(model_id=object_id).first()

    def list(self):
        return self.db.query(Model).all()

