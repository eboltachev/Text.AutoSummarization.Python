from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import HTTPException, status

from auto_summarization.adapters.repository import SessionRepository
from auto_summarization.domain.analysis import AnalysisResult
from auto_summarization.domain.session import AnalysisSession
from auto_summarization.services.analyze_service import AnalyzeService
from auto_summarization.services.config import session_scope, settings


class SessionService:
    def __init__(self, analyze_service: Optional[AnalyzeService] = None) -> None:
        self._analyze_service = analyze_service or AnalyzeService()
        self._max_sessions = settings.AUTO_SUMMARIZATION_MAX_SESSIONS

    def list_sessions(self, user_id: Optional[str]) -> List[Dict[str, Any]]:
        owner = self._require_user(user_id)
        with session_scope() as db:
            repository = SessionRepository(db)
            sessions = repository.list_for_user(owner)
            return [self._serialize_summary(session) for session in sessions]

    def create_session(
        self,
        user_id: Optional[str],
        *,
        title: Optional[str],
        text: str,
        category: int,
        choices: List[int],
    ) -> Dict[str, Any]:
        owner = self._require_user(user_id)
        analysis = self._analyze_service.analyse(text, category, choices)
        results = self._prepare_results(analysis)
        resolved_title = self._resolve_title(title, results, text)

        with session_scope() as db:
            repository = SessionRepository(db)
            if self._max_sessions > 0:
                repository.trim_to_limit(owner, self._max_sessions - 1)

            session = AnalysisSession(
                session_id=str(uuid4()),
                user_id=owner,
                title=resolved_title,
                text=text,
                category_index=category,
                choice_indexes=choices,
                results=results,
            )
            repository.add(session)
            db.flush()
            payload = self._serialize_detail(session)
        return payload

    def get_session(self, user_id: Optional[str], session_id: str) -> Dict[str, Any]:
        owner = self._require_user(user_id)
        with session_scope() as db:
            repository = SessionRepository(db)
            session = repository.get_for_user(session_id, owner)
            if session is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")
            return self._serialize_detail(session)

    def update_session(
        self,
        user_id: Optional[str],
        session_id: str,
        *,
        title: Optional[str] = None,
        text: Optional[str] = None,
        category: Optional[int] = None,
        choices: Optional[List[int]] = None,
        version: Optional[int] = None,
    ) -> Dict[str, Any]:
        owner = self._require_user(user_id)
        with session_scope() as db:
            repository = SessionRepository(db)
            session = repository.get_for_user(session_id, owner)
            if session is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")

            if version is not None and version != session.version:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Версия сессии устарела")

            changed = False

            if title is not None:
                normalized_title = title.strip()
                if not normalized_title:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный заголовок")
                if normalized_title != session.title:
                    session.rename(normalized_title)
                    changed = True

            reanalyse = any(item is not None for item in (text, category, choices))
            if reanalyse:
                new_text = text if text is not None else session.text
                new_category = category if category is not None else session.category_index
                new_choices = choices if choices is not None else session.choice_indexes

                analysis = self._analyze_service.analyse(new_text, new_category, new_choices)
                results = self._prepare_results(analysis)
                session.update_payload(
                    text=new_text,
                    category_index=new_category,
                    choice_indexes=new_choices,
                    results=results,
                )
                if title is None:
                    auto_title = self._resolve_title(None, results, new_text)
                    if auto_title != session.title:
                        session.rename(auto_title)
                changed = True

            if not changed:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет изменений для обновления")

            session.version += 1
            session.updated_at = time.time()
            db.flush()
            return self._serialize_detail(session)

    def delete_session(self, user_id: Optional[str], session_id: str) -> None:
        owner = self._require_user(user_id)
        with session_scope() as db:
            repository = SessionRepository(db)
            session = repository.get_for_user(session_id, owner)
            if session is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")
            repository.delete(session)

    def _require_user(self, user_id: Optional[str]) -> str:
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не указан идентификатор пользователя")
        return user_id

    def _prepare_results(self, result: AnalysisResult) -> Dict[str, Any]:
        payload = asdict(result)
        payload.setdefault("entities", {})
        payload.setdefault("sentiments", {})
        payload.setdefault("classifications", {})
        payload.setdefault("short_summary", None)
        payload.setdefault("full_summary", None)
        # Ensure JSON serialisable structure
        return json.loads(json.dumps(payload, ensure_ascii=False))

    def _resolve_title(self, title: Optional[str], results: Dict[str, Any], text: str) -> str:
        if title and title.strip():
            return title.strip()

        summary = results.get("short_summary") if isinstance(results, dict) else None
        if isinstance(summary, str) and summary.strip():
            candidate = summary.strip()
        else:
            candidate = text.strip()

        if len(candidate) > 80:
            candidate = candidate[:77].rstrip() + "..."

        return candidate or "Новая сессия"

    def _serialize_summary(self, session: AnalysisSession) -> Dict[str, Any]:
        return {
            "session_id": session.session_id,
            "title": session.title,
            "category": session.category_index,
            "choices": session.choice_indexes,
            "version": session.version,
            "inserted_at": session.inserted_at,
            "updated_at": session.updated_at,
        }

    def _serialize_detail(self, session: AnalysisSession) -> Dict[str, Any]:
        summary = self._serialize_summary(session)
        summary.update(
            {
                "text": session.text,
                "analysis": session.results,
            }
        )
        return summary
