from __future__ import annotations

import abc

from auto_summarization.adapters.repository import AnalysisTemplateRepository, SessionRepository, UserRepository
from auto_summarization.services.config import session_factory


class IUoW(abc.ABC):
    def __init__(self, session_factory=session_factory):
        self.session_factory = session_factory

    def __enter__(self) -> IUoW:
        return self

    def __exit__(self, *args):
        self.rollback()

    @abc.abstractmethod
    def commit(self):
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self):
        raise NotImplementedError


class UserUoW(IUoW):
    def __enter__(self) -> UserUoW:
        self.db = self.session_factory()
        self.users = UserRepository(self.db)
        self.sessions = SessionRepository(self.db)
        self.templates = AnalysisTemplateRepository(self.db)
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.db.close()

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()


class AnalysisTemplateUoW(IUoW):
    def __enter__(self) -> AnalysisTemplateUoW:
        self.db = self.session_factory()
        self.templates = AnalysisTemplateRepository(self.db)
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.db.close()

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()
