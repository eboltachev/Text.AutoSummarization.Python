from __future__ import annotations

import logging
import sys
from time import time
from typing import Any, Dict, Iterable, List, Tuple
from uuid import uuid4

from langchain_openai import ChatOpenAI
from transformers import pipeline

from auto_summarization.domain.enums import StatusType
from auto_summarization.domain.session import Session
from auto_summarization.domain.user import User
from auto_summarization.services.config import settings
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW, IUoW

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def _extract_message_content(result: Any) -> str:
    """Normalize LLM responses to plain text."""

    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts).strip()
    return str(content).strip()


def _normalize_label(output: str, candidates: List[str]) -> str:
    """Pick the most suitable label from candidates based on LLM output."""

    if not candidates:
        return output.strip()
    normalized_output = output.strip().lower()
    for candidate in candidates:
        if candidate.lower() in normalized_output:
            return candidate
    return candidates[0]


def _load_templates(
    category_index: int,
    analysis_uow: AnalysisTemplateUoW,
) -> Tuple[Dict[int, Any], str]:
    with analysis_uow:
        templates = analysis_uow.templates.list_by_category(category_index)
    if not templates:
        raise ValueError("Invalid category index")
    template_map = {template.choice_index: template for template in templates}
    category = templates[0].category
    return template_map, category


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.OPENAI_API_HOST,
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL_NAME,
        temperature=0,
        timeout=settings.KNOWLEDGE_BASE_CONNECTION_TIMEOUT,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def _ensure_pipeline():
    try:
        return pipeline(
            "zero-shot-classification",
            model=settings.AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH,
        )
    except Exception:
        return pipeline(
            "zero-shot-classification",
            model=settings.AUTO_SUMMARIZATION_PRETRAINED_MODEL_NAME,
        )


def _generate_analysis(
    text: str,
    category_index: int,
    choices: Iterable[int],
    analysis_uow: AnalysisTemplateUoW,
    base_values: Dict[str, str] | None = None,
) -> Tuple[str, str, str, str, str, str]:
    template_map, category = _load_templates(category_index, analysis_uow)
    selected_indices = list(dict.fromkeys(list(choices)))
    short_summary = (base_values or {}).get("short_summary", "") or ""
    entities = (base_values or {}).get("entities", "") or ""
    sentiments = (base_values or {}).get("sentiments", "") or ""
    classifications = (base_values or {}).get("classifications", "") or ""
    full_summary = (base_values or {}).get("full_summary", "") or ""

    llm: ChatOpenAI | None = None
    clf_pipeline = None

    for index in selected_indices:
        template = template_map.get(index)
        if template is None:
            continue
        name = template.choice_name
        prompt = template.prompt or ""
        if name == "Классификация":
            candidates = [label.strip() for label in prompt.split(",") if label.strip()]
            if not candidates:
                continue
            model_type = (template.model_type or "UNIVERSAL").upper()
            if model_type == "PRETRAINED":
                if clf_pipeline is None:
                    clf_pipeline = _ensure_pipeline()
                result = clf_pipeline(text, candidate_labels=candidates, multi_label=False)
                if isinstance(result, dict):
                    labels = result.get("labels", [])
                    predicted = labels[0] if labels else candidates[0]
                elif isinstance(result, list) and result:
                    first_item = result[0]
                    if isinstance(first_item, dict):
                        predicted = first_item.get("label") or first_item.get("labels", [candidates[0]])[0]
                    else:
                        predicted = str(first_item)
                else:
                    labels = getattr(result, "labels", None)
                    if labels:
                        predicted = labels[0]
                    else:
                        predicted = candidates[0]
                normalized = _normalize_label(str(predicted), candidates)
                classifications = f"[Предобученная модель] {normalized}".strip()
            else:
                if llm is None:
                    llm = _build_llm()
                classification_prompt = (
                    "Выбери наиболее подходящую категорию из списка. "
                    f"Варианты: {', '.join(candidates)}.\n\n"
                    f"Текст:\n{text.strip()}\n\n"
                    "Ответь только одним вариантом из списка."
                )
                response = _extract_message_content(llm.invoke(classification_prompt))
                predicted = _normalize_label(response, candidates)
                classifications = f"[Универсальная модель] {predicted}".strip()
            continue

        if llm is None:
            llm = _build_llm()
        message_prompt = f"{prompt.strip()}\n\nТекст:\n{text.strip()}"
        response = _extract_message_content(llm.invoke(message_prompt))
        if name == "Аннотация":
            short_summary = response
        elif name == "Объекты":
            entities = response
        elif name == "Тональность":
            sentiments = response
        elif name == "Выводы":
            full_summary = response

    return short_summary, entities, sentiments, classifications, full_summary, category

def _session_to_dict(session: Session) -> Dict[str, Any]:
    return {
        "session_id": session.session_id,
        "title": session.title,
        "category": getattr(session, "category", ""),
        "text": session.text,
        "summary": getattr(session, "summary", session.short_summary),
        "analysis": getattr(session, "analysis", session.full_summary),
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
) -> Tuple[Dict[str, Any], str | None]:
    logger.info("start create_new_session")
    now = time()

    (
        short_summary,
        entities,
        sentiments,
        classifications,
        full_summary,
        category,
    ) = _generate_analysis(
        text=text,
        category_index=category_index,
        choices=list(choices),
        analysis_uow=analysis_uow,
    )

    session = Session(
        session_id=str(uuid4()),
        version=0,
        title=f"{short_summary[:40]}" or text[:40],
        text=text,
        short_summary=short_summary,
        entities=entities,
        sentiments=sentiments,
        classifications=classifications,
        full_summary=full_summary,
        inserted_at=now,
        updated_at=now,
    )
    session.category = category  # type: ignore[attr-defined]
    session.summary = short_summary  # type: ignore[attr-defined]
    session.analysis = full_summary  # type: ignore[attr-defined]
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
    response = {
        "entities": session.entities,
        "sentiments": session.sentiments,
        "classifications": session.classifications,
        "short_summary": session.short_summary,
        "full_summary": session.full_summary,
    }
    return response, None


def update_session_summarization(
    user_id: str,
    session_id: str,
    text: str,
    category_index: int,
    choices: Iterable[int],
    version: int,
    user_uow: IUoW,
    analysis_uow: AnalysisTemplateUoW,
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

        (
            short_summary,
            entities,
            sentiments,
            classifications,
            full_summary,
            category,
        ) = _generate_analysis(
            text=text,
            category_index=category_index,
            choices=list(choices),
            analysis_uow=analysis_uow,
            base_values={
                "short_summary": session.short_summary or "",
                "entities": session.entities or "",
                "sentiments": session.sentiments or "",
                "classifications": session.classifications or "",
                "full_summary": session.full_summary or "",
            },
        )

        session.short_summary = short_summary
        session.entities = entities
        session.sentiments = sentiments
        session.classifications = classifications
        session.full_summary = full_summary
        session.summary = short_summary  # type: ignore[attr-defined]
        session.analysis = full_summary  # type: ignore[attr-defined]
        session.category = category  # type: ignore[attr-defined]
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
