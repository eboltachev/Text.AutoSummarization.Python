import abc
from typing import Iterable

from auto_summarization.domain.base import IDomain


class IRepository(abc.ABC):
    @abc.abstractmethod
    def add(self, data: IDomain) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def list(self) -> Iterable[IDomain]:
        raise NotImplementedError
