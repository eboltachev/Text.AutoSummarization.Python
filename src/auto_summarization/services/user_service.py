from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from auto_summarization.adapters.repository import SessionRepository, UserRepository
from auto_summarization.domain.user import User
from auto_summarization.services.config import session_scope


class UserService:
    def list_users(self) -> List[Dict[str, Any]]:
        with session_scope() as db:
            repository = UserRepository(db)
            users = repository.list()
            return [self._serialize(user) for user in users]

    def create_user(self, user_id: str, display_name: Optional[str] = None) -> Dict[str, Any]:
        normalized = self._normalize_identifier(user_id)
        with session_scope() as db:
            repository = UserRepository(db)
            existing = repository.get(normalized)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Пользователь уже существует",
                )
            user = User(user_id=normalized, display_name=display_name)
            repository.add(user)
            db.flush()
            return self._serialize(user)

    def delete_user(self, user_id: str) -> None:
        normalized = self._normalize_identifier(user_id)
        with session_scope() as db:
            user_repository = UserRepository(db)
            user = user_repository.get(normalized)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Пользователь не найден",
                )
            session_repository = SessionRepository(db)
            sessions = session_repository.list_for_user(normalized)
            for session in sessions:
                session_repository.delete(session)
            user_repository.delete(user)

    def _normalize_identifier(self, user_id: Optional[str]) -> str:
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не указан идентификатор пользователя",
            )
        normalized = user_id.strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный идентификатор пользователя",
            )
        return normalized

    def _serialize(self, user: User) -> Dict[str, Any]:
        return {
            "user_id": user.user_id,
            "display_name": user.display_name,
            "inserted_at": user.inserted_at,
        }
