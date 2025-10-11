from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple
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

    def fetch_page(
        self,
        user_id: Optional[str],
        *,
        page: int,
        size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        owner = self._require_user(user_id)
        if page < 1 or size < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректные параметры пагинации")
        with session_scope() as db:
            repository = SessionRepository(db)
            items, total = repository.fetch_page_for_user(owner, page=page, size=size)
            return [self._serialize_summary(session) for session in items], total

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

    def update_translation(
        self,
        user_id: Optional[str],
        *,
        session_id: str,
        text: Optional[str],
        category: Optional[int],
        choices: Optional[List[int]],
        version: int,
    ) -> Dict[str, Any]:
        return self.update_session(
            user_id,
            session_id,
            text=text,
            category=category,
            choices=choices,
            version=version,
        )

    def rename_session(
        self,
        user_id: Optional[str],
        *,
        session_id: str,
        title: str,
        version: int,
    ) -> Dict[str, Any]:
        return self.update_session(user_id, session_id, title=title, version=version)

    def search_sessions(
        self,
        user_id: Optional[str],
        *,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        owner = self._require_user(user_id)
        normalized_query = query.strip()
        if not normalized_query:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный поисковый запрос")
        effective_limit = max(1, min(limit, 100))
        with session_scope() as db:
            repository = SessionRepository(db)
            results = repository.search_for_user(owner, query=normalized_query, limit=effective_limit)
            return [self._serialize_summary(item) for item in results]

    def download_session(
        self,
        user_id: Optional[str],
        *,
        session_id: str,
        export_format: str,
    ) -> Tuple[str, bytes, str]:
        detail = self.get_session(user_id, session_id)
        export = export_format.lower()
        if export == "json":
            content = json.dumps(detail, ensure_ascii=False, indent=2).encode("utf-8")
            filename = f"session_{session_id}.json"
            media_type = "application/json"
        elif export == "txt":
            payload = [f"Заголовок: {detail['title']}", "", detail["text"], "", "---", ""]
            payload.append(json.dumps(detail["analysis"], ensure_ascii=False, indent=2))
            content = "\n".join(payload).encode("utf-8")
            filename = f"session_{session_id}.txt"
            media_type = "text/plain; charset=utf-8"
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неподдерживаемый формат выгрузки")
        return filename, content, media_type

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
