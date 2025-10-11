from __future__ import annotations

import logging
import sys
from time import time
from typing import Any, Dict, Iterable, List
from uuid import uuid4

from auto_summarization.domain.enums import StatusType
from auto_summarization.domain.session import Session
from auto_summarization.domain.user import User
from auto_summarization.services.config import settings
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW, IUoW
from auto_summarization.services.handlers.analysis import perform_analysis

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def _session_to_dict(session: Session) -> Dict[str, Any]:
    return {
        "session_id": session.session_id,
        "title": session.title,
        "category": session.category,
        "text": session.text,
        "summary": session.summary,
        "analysis": session.analysis,
        "version": session.version,
        "inserted_at": session.inserted_at,
        "updated_at": session.updated_at,
        "error": None,
    }


def get_session_list(user_id: str, uow: IUoW) -> List[Dict[str, Any]]:
    logger.info("start get_session_list")
    sessions: List[Dict[str, Any]] = []
    with uow:
        user = uow.users.get(object_id=user_id)
        if not user:
            return []
        for session in user.get_sessions()[: settings.AUTO_SUMMARIZATION_MAX_SESSIONS]:
            sessions.append(_session_to_dict(session))
    logger.info("finish get_session_list")
    return sessions


def create_new_session(
    user_id: str,
    text: str,
    category_index: int,
    choices: Iterable[int],
    temporary: bool | None,
    user_uow: IUoW,
    analysis_uow: AnalysisTemplateUoW,
) -> Dict[str, Any]:
    logger.info("start create_new_session")
    category, analysis_result = perform_analysis(
        text=text, category_index=category_index, choice_indices=choices, uow=analysis_uow
    )
    now = time()
    summary = analysis_result.get("short_summary", "")
    full_summary = analysis_result.get("full_summary", "")
    session = Session(
        session_id=str(uuid4()),
        title=f"{category}: {summary[:40]}" if summary else category,
        category=category,
        text=text,
        summary=summary,
        analysis=full_summary,
        version=0,
        inserted_at=now,
        updated_at=now,
    )
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        if user is None:
            is_temporary = True if temporary is None else bool(temporary)
            user = User(
                user_id=user_id,
                temporary=is_temporary,
                started_using_at=now,
                last_used_at=now,
                sessions=[],
            )
            user_uow.users.add(user)
        user.sessions.append(session)
        user.update_time(last_used_at=now)
        user_uow.commit()
    logger.info("finish create_new_session")
    response = _session_to_dict(session)
    response.update(analysis_result)
    return response


def update_session_summarization(
    user_id: str,
    session_id: str,
    summary: str,
    analysis: str,
    version: int,
    user_uow: IUoW,
) -> Dict[str, Any]:
    logger.info("start update_session_summarization")
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User not found")
        session = user.get_session(session_id)
        if session is None:
            raise ValueError("Session not found")
        if int(session.version) != int(version):
            raise ValueError("Version mismatch")
        now = time()
        session.summary = summary
        session.analysis = analysis
        session.version = version + 1
        session.updated_at = now
        user.update_time(last_used_at=now)
        user_uow.commit()
    logger.info("finish update_session_summarization")
    return _session_to_dict(session)


def update_title_session(
    user_id: str,
    session_id: str,
    title: str,
    version: int,
    user_uow: IUoW,
) -> Dict[str, Any]:
    logger.info("start update_title_session")
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User not found")
        session = user.get_session(session_id)
        if session is None:
            raise ValueError("Session not found")
        if int(session.version) != int(version):
            raise ValueError("Version mismatch")
        now = time()
        session.title = title
        session.version = version + 1
        session.updated_at = now
        user.update_time(last_used_at=now)
        user_uow.commit()
    logger.info("finish update_title_session")
    return _session_to_dict(session)


def delete_exist_session(session_id: str, user_id: str, uow: IUoW) -> StatusType:
    logger.info("start delete_exist_session")
    with uow:
        user = uow.users.get(object_id=user_id)
        if user is None:
            return StatusType.ERROR
        status = user.delete_session(session_id)
        if status:
            uow.commit()
            logger.info("session deleted")
            return StatusType.SUCCESS
    logger.info("finish delete_exist_session")
    return StatusType.ERROR
