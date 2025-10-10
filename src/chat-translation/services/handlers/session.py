import logging
import sys
import tempfile
from pathlib import Path
from time import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from domain.enums import StatusType
from domain.session import Session
from domain.user import User
from fpdf import FPDF
from services.config import lang_title, settings
from services.data.unit_of_work import IUoW
from services.pipelines.processor import DetectorProcessor, TranslatorProcessor

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def get_session_list(user_id: str, uow: IUoW) -> List[Dict[str, Any]]:
    logger.info(f"start get_session_list")
    try:
        with uow:
            user = uow.users.get(object_id=user_id)
            sessions = [
                {
                    "session_id": session.session_id,
                    "title": session.title,
                    "model": session.model,
                    "query": session.query,
                    "translation": session.translation,
                    "source_language_id": session.source_language_id,
                    "target_language_id": session.target_language_id,
                    "source_language_title": session.source_language_title,
                    "target_language_title": session.target_language_title,
                    "version": session.version,
                    "inserted_at": session.inserted_at,
                    "updated_at": session.updated_at,
                    "error": None,
                }
                for session in user.get_sessions()
            ]
            sessions, tail = (
                sessions[: settings.CHAT_TRANSLATION_MAX_SESSIONS],
                sessions[settings.CHAT_TRANSLATION_MAX_SESSIONS :],
            )
            for session in tail:  # to-do parallel process
                session_id: str | None = session.get("session_id")
                delete_exist_session(session_id=session_id, user_id=user_id, uow=uow)
        logger.info(f"{sessions=}")
    except Exception as error:
        logger.error(f"{error=}")
        sessions = []
    finally:
        logger.info(f"finish get_session_list")
        return sessions


def create_new_session(
    user_id: str,
    query: str,
    model_id: str | None,
    temporary: bool | None,
    model_uow: IUoW,
    user_uow: IUoW,
) -> Dict[str, Any] | None:
    logger.info(f"start create_new_session")
    logger.info(f"{user_id=}")
    pipeline = [DetectorProcessor(), TranslatorProcessor()]
    with model_uow:
        if not bool(model_id):
            mode = "AUTO"
            source_language_id = "auto"
            target_language_id = settings.CHAT_TRANSLATION_DEFAULT_TARGET_LANGUAGE
        else:
            model = model_uow.models.get(object_id=model_id)
            if model is None:
                raise ValueError(f"Model {model} does not exist")
            else:
                mode = model.model
                source_language_id = model.source_language_id
                target_language_id = model.target_language_id
        special_models = [
            model.source_language_id for model in model_uow.models.list() if model.model == "SPECIAL"
        ]
    data = {
        "query": query,
        "mode": mode,
        "source_language_id": source_language_id,
        "target_language_id": target_language_id,
        "special_models": special_models,
        "error": None,
    }
    for step in pipeline:
        data = step.process(data)
    star_time = time()
    translation: str = data.get("translation", "")
    error: str | None = data.get("error")
    session = Session(
        session_id=str(uuid4()),
        title=f"{query[:10]} → {translation[:10]}",
        model=data.get("mode", mode),
        query=query,
        translation=translation,
        source_language_id=source_language_id,
        target_language_id=target_language_id,
        source_language_title=lang_title(data.get("source_language_id", source_language_id)),
        target_language_title=lang_title(data.get("target_language_id", target_language_id)),
        version=0,
        inserted_at=star_time,
        updated_at=time(),
    )
    result_session = {
        "session_id": session.session_id,
        "title": session.title,
        "model": session.model,
        "query": session.query,
        "translation": session.translation,
        "source_language_id": session.source_language_id,
        "target_language_id": session.target_language_id,
        "source_language_title": session.source_language_title,
        "target_language_title": session.target_language_title,
        "version": session.version,
        "inserted_at": session.inserted_at,
        "updated_at": session.updated_at,
        "error": error,
    }
    if error is None:
        with user_uow:
            user = user_uow.users.get(object_id=user_id)
            if user is None:
                now = time()
                user = User(
                    user_id=user_id,
                    temporary=temporary,
                    started_using_at=now,
                    last_used_at=now,
                    sessions=[],
                )
                user_uow.users.add(user)
            user.sessions.append(session)
            user_uow.commit()

    logger.info(f"{result_session=}")
    logger.info(f"finish create_new_session")
    return result_session

def update_exist_session(
    user_id: str,
    session_id: str,
    model_id: str,
    query: str,
    version: int,
    model_uow: IUoW,
    user_uow: IUoW,
) -> Dict[str, Any] | None:
    logger.info(f"start update_exist_session")
    logger.info(f"{session_id=}")
    logger.info(f"{user_id=}")
    pipeline = [DetectorProcessor(), TranslatorProcessor()]
    with model_uow:
        model = model_uow.models.get(object_id=model_id)
        mode = model.model
        source_language_id = model.source_language_id
        target_language_id = model.target_language_id
    data = {
        "query": query,
        "mode": mode,
        "source_language_id": source_language_id,
        "target_language_id": target_language_id,
        "error": None,
    }
    for step in pipeline:
        data = step.process(data)
    translation: str = data.get("translation", "")
    error: str | None = data.get("error")
    result_session = {
        "session_id": session_id,
        "model": mode,
        "query": query,
        "translation": translation,
        "source_language_id": source_language_id,
        "target_language_id": target_language_id,
        "source_language_title": lang_title(data.get("source_language_id", source_language_id)),
        "target_language_title": lang_title(data.get("target_language_id", target_language_id)),
        "version": version,
        "inserted_at": time(),
        "updated_at": time(),
        "error": error,
    }
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        logger.info(f"{user=}")
        now = time()
        if user is not None:
            logger.info(f"{user=}")
            session = user.get_session(session_id)
            logger.info(f"{session=}")
            logger.info(f"{session.version=}")
            session.model = mode
            session.query = query
            session.translation = translation
            session.source_language_id = source_language_id
            session.target_language_id = target_language_id
            session.source_language_title = lang_title(data.get("source_language_id", source_language_id))
            session.target_language_title = lang_title(data.get("target_language_id", target_language_id))
            if int(version) != int(session.version):
                raise ValueError(f"Version {version} is not correct")
            session.version = version + 1
            session.updated_at = now
            user.update_time(last_used_at=now)
            result_session = {
                "session_id": session.session_id,
                "title": session.title,
                "model": session.model,
                "query": session.query,
                "translation": session.translation,
                "source_language_id": session.source_language_id,
                "target_language_id": session.target_language_id,
                "source_language_title": session.source_language_title,
                "target_language_title": session.target_language_title,
                "version": session.version,
                "inserted_at": session.inserted_at,
                "updated_at": session.updated_at,
                "error": error,
            }
            if error is None:
                user_uow.commit()
    logger.info(f"{result_session=}")
    logger.info(f"finish update_exist_session")
    result_session["error"] = error
    return result_session


def update_title_session(
    user_id: str,
    session_id: str,
    title: str,
    version: int,
    user_uow: IUoW,
) -> Dict[str, Any] | None:
    logger.info(f"start update_title_session")
    logger.info(f"{session_id=}")
    logger.info(f"{user_id=}")
    result_session = None
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        logger.info(f"{user=}")
        now = time()
        if user is not None:
            logger.info(f"{user=}")
            session = user.get_session(session_id)
            logger.info(f"{session=}")
            logger.info(f"{session.version=}")
            session.title = title
            if int(version) != int(session.version):
                raise ValueError(f"Version {version} is not correct")
            session.version = version + 1
            session.updated_at = now
            user.update_time(last_used_at=now)
            result_session = {
                "session_id": session.session_id,
                "title": session.title,
                "model": session.model,
                "query": session.query,
                "translation": session.translation,
                "source_language_id": session.source_language_id,
                "target_language_id": session.target_language_id,
                "source_language_title": session.source_language_title,
                "target_language_title": session.target_language_title,
                "version": session.version,
                "inserted_at": session.inserted_at,
                "updated_at": session.updated_at,
                "error": None,
            }
            user_uow.commit()
    logger.info(f"{result_session=}")
    logger.info(f"finish update_exist_session")
    return result_session


def download_session_file(session_id: str, format: str, user_id: str, uow: IUoW) -> Path:
    with uow:
        user = uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User not found")
        session = user.get_session(session_id)
        if session is None:
            raise ValueError("Session not found")
        title = session.title
        model = session.model
        query = session.query
        translation = session.translation
        source_language_title = session.source_language_title
        target_language_title = session.target_language_title

    if format == "pdf":
        import os

        from fpdf import FPDF

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as fp:
            pdf = FPDF()
            pdf.add_page()
            font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
            pdf.add_font("DejaVu", "", font_path, uni=True)
            pdf.set_font("DejaVu", "", 12)
            pdf.cell(0, 10, f"Session: {title}", ln=1)
            pdf.cell(0, 10, f"Model: {model}", ln=1)
            pdf.cell(0, 10, f"From: {source_language_title} → To: {target_language_title}", ln=1)
            pdf.ln(5)
            pdf.set_font("DejaVu", "", 11)
            pdf.multi_cell(0, 8, f"Query:\n{query}")
            pdf.ln(2)
            pdf.multi_cell(0, 8, f"Translation:\n{translation}")
            pdf.output(fp.name)
            return Path(fp.name)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as fp:
            with open(fp.name, "w", encoding="utf-8") as f:
                f.write(f"{query} : {translation}")
            return Path(fp.name)


def search_similarity_sessions(user_id: str, query: str, uow: IUoW) -> List[Dict[str, Any]]:
    logger.info("start search_similarity_sessions")
    if not query or not query.strip():
        raise ValueError("Request is empty")
    results: List[Dict[str, Any]] = []
    with uow:
        user = uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User does not have any sessions")
        for session in user.get_sessions():
            text_blob = " | ".join([session.title or "", session.query or "", session.translation or ""])
            score = _match_score(text_blob, query)
            if score <= 0:
                continue
            results.append(
                {
                    "title": session.title or "",
                    "query": session.query or "",
                    "translation": session.translation or "",
                    "inserted_at": float(session.inserted_at),
                    "session_id": session.session_id,
                    "score": float(score),
                }
            )
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:20]
    logger.info(f"finish search_similarity_sessions, found={len(results)}")
    return results


def delete_exist_session(session_id: str, user_id: str, uow: IUoW) -> StatusType:
    logger.info(f"start delete_exist_session")
    logger.info(f"{session_id=}")
    logger.info(f"{user_id=}")
    status = None
    with uow:
        user = uow.users.get(object_id=user_id)
        logger.info(f"{user=}")
        if user is not None:
            logger.info(f"{user=}")
            status = user.delete_session(session_id)
            logger.info(f"{status}")
            uow.commit()
    logger.info(f"finish delete_exist_session")
    return StatusType.SUCCESS if status else StatusType.ERROR


def _match_score(text: str, query: str) -> float:
    if not text or not query:
        return 0.0
    q = query.lower().strip()
    t = text.lower()
    if q in t:
        return 1.0
    qs = {tok for tok in q.split() if tok}
    ts = set(t.split())
    inter = len(qs & ts)
    return inter / max(len(qs), 1)






