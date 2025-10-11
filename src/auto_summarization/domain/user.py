from __future__ import annotations

import logging
import sys
from typing import List

from .base import IDomain
from .session import Session

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


class User(IDomain):
    def __init__(self, user_id: str, temporary: bool, started_using_at: float, last_used_at: float, sessions: List[Session]):
        self.user_id = user_id
        self.temporary = temporary
        self.started_using_at = started_using_at
        self.last_used_at = last_used_at
        self.sessions = sessions

    def __eq__(self, other):
        if not isinstance(other, User):
            return False
        return self.user_id == other.user_id

    def __hash__(self):
        return hash(self.user_id)

    def get_session(self, session_id: str) -> Session | None:
        try:
            indicies = [session.session_id for session in self.sessions]
            index = indicies.index(session_id)
            return self.sessions[index]
        except Exception as error:
            logger.error(f"{error=}")
            return None

    def delete_session(self, session_id: str) -> bool:
        try:
            indicies = [session.session_id for session in self.sessions]
            index = indicies.index(session_id)
            return bool(self.sessions.pop(index))
        except Exception as error:
            logger.error(f"{error=}")
            return False

    def get_sessions(self) -> List[Session]:
        sessions = sorted(self.sessions, key=lambda session: session.updated_at, reverse=True)
        return sessions

    def update_time(self, last_used_at: float):
        self.last_used_at = last_used_at
