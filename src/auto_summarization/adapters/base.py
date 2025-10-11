import abc
from typing import Optional

from auto_summarization.domain.base import IDomain


class IRepository(abc.ABC):
    @abc.abstractmethod
    def add(self, data: IDomain, foreign_key: Optional[str] = None) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, object_id: str) -> IDomain:
        raise NotImplementedError
