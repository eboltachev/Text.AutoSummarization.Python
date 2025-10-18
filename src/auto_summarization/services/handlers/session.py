from __future__ import annotations

import logging
import math
import os
import sys
import tempfile
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Tuple
from uuid import uuid4

import httpx
from transformers import AutoTokenizer, pipeline

from auto_summarization.domain.enums import StatusType
from auto_summarization.domain.session import Session
from auto_summarization.domain.user import User
from auto_summarization.services.config import settings
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW, IUoW

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
else:  # pragma: no cover - runtime fallback when optional dependency is missing
    ChatOpenAI = Any


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    return " ".join(value.lower().split())


def _match_score(text_blob: str, query: str) -> float:
    normalized_blob = _normalize_text(text_blob)
    normalized_query = _normalize_text(query)
    if not normalized_blob or not normalized_query:
        return 0.0
    matcher_score = SequenceMatcher(None, normalized_blob, normalized_query).ratio()
    blob_tokens = set(normalized_blob.split())
    query_tokens = set(normalized_query.split())
    if not query_tokens:
        return 0.0
    overlap_score = len(blob_tokens & query_tokens) / len(query_tokens)
    return float(max(matcher_score, overlap_score))


@lru_cache(maxsize=1)
def _get_context_window(model_name: str) -> int:
    """Fetch the context window for the configured model."""

    fallback_window = 4096
    base_url = settings.OPENAI_API_HOST.rstrip("/")
    model_path = f"{base_url}/models/{model_name}"
    try:
        with httpx.Client(timeout=settings.AUTO_SUMMARIZATION_CONNECTION_TIMEOUT) as client:
            response = client.get(model_path)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # pragma: no cover - network error path
        logger.warning("Failed to fetch model metadata for context window: %s", exc)
        return fallback_window

    def _extract_from_item(item: Dict[str, Any]) -> int | None:
        for key in ("context_window", "context_length", "max_input_tokens", "max_context", "max_tokens"):
            value = item.get(key)
            if isinstance(value, int) and value > 0:
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return None

    if isinstance(payload, dict):
        direct_value = _extract_from_item(payload)
        if direct_value:
            return direct_value
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("id") == model_name:
                    extracted = _extract_from_item(item)
                    if extracted:
                        return extracted
    return fallback_window


def _estimate_token_length(text: str, context_window: int) -> int:
    if not text:
        return 0
    # Approximate 4 characters per token as a conservative heuristic
    estimated = max(1, math.ceil(len(text) / 4))
    # Guard against overflow for exceptionally long strings
    return min(estimated, len(text)) if context_window else estimated


def _apply_map_reduce(text: str, context_window: int) -> str:
    try:
        from langchain.chains.summarize import load_summarize_chain  # type: ignore
        from langchain.docstore.document import Document  # type: ignore
        from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
    except ModuleNotFoundError:
        logger.warning("LangChain is not installed; skipping map-reduce summarization and returning the original text.")
        return text

    chunk_size = max(200, context_window * 4)
    chunk_overlap = max(50, int(chunk_size * 0.1))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    documents = [Document(page_content=chunk) for chunk in splitter.split_text(text)]
    if len(documents) <= 1:
        return text
    llm = _build_llm()
    chain = load_summarize_chain(llm, chain_type="map_reduce")
    summary = chain.run(documents)
    return summary.strip() or text


def _sanitize_prompt_text(text: str) -> str:
    """Ensure the text passed to the LLM fits inside the model context window."""

    if not text:
        return ""

    context_window = _get_context_window(settings.OPENAI_MODEL_NAME)
    if context_window <= 0:
        return text

    safe_window = max(512, int(context_window * 0.8))
    estimated_tokens = _estimate_token_length(text, context_window)
    if estimated_tokens <= safe_window:
        return text

    logger.info("Condensing prompt text due to context window overflow")
    condensed = _apply_map_reduce(text, context_window)
    condensed = condensed or text

    # If condensation is still too large, truncate to the safe character budget
    if _estimate_token_length(condensed, context_window) > safe_window:
        char_budget = safe_window * 4
        condensed = condensed[:char_budget].strip()

    return condensed or text[: safe_window * 4]


def _extract_message_content(result: Any) -> str:
    """Normalize LLM responses to plain text and condense oversized payloads."""

    if result is None:
        return ""
    if isinstance(result, str):
        text = result.strip()
    else:
        content = getattr(result, "content", result)
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            text = "".join(parts).strip()
        else:
            text = str(content).strip()

    if not text:
        return ""

    context_window = _get_context_window(settings.OPENAI_MODEL_NAME)
    if _estimate_token_length(text, context_window) > context_window:
        logger.info("Applying map-reduce summarization due to context window overflow")
        return _apply_map_reduce(text, context_window)

    return text


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
) -> Tuple[Dict[int, Dict[str, Any]], str]:
    with analysis_uow:
        templates = analysis_uow.templates.list_by_category(category_index)
        if not templates:
            raise ValueError("Invalid category index")
        template_map: Dict[int, Dict[str, Any]] = {}
        for template in templates:
            template_map[template.choice_index] = {
                "choice_name": template.choice_name,
                "prompt": template.prompt or "",
                "model_type": (template.model_type or "").upper(),
            }
        category = templates[0].category
    return template_map, category


def _build_llm() -> "ChatOpenAI":
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured. Set the environment variable to use the LLM client.")
    try:
        from langchain_openai import ChatOpenAI as _ChatOpenAI  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "langchain-openai is required to build the LLM client. Install the 'langchain-openai' package."
        ) from exc

    return _ChatOpenAI(
        base_url=settings.OPENAI_API_HOST,
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL_NAME,
        temperature=0,
        timeout=settings.AUTO_SUMMARIZATION_CONNECTION_TIMEOUT,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def _ensure_pipeline():
    tokenizer_kwargs = {"use_fast": False}
    try:
        tokenizer = AutoTokenizer.from_pretrained(settings.AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH, **tokenizer_kwargs)
        return pipeline(
            "zero-shot-classification",
            model=settings.AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH,
            tokenizer=tokenizer,
        )
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(settings.AUTO_SUMMARIZATION_PRETRAINED_MODEL_NAME, **tokenizer_kwargs)
        return pipeline(
            "zero-shot-classification",
            model=settings.AUTO_SUMMARIZATION_PRETRAINED_MODEL_NAME,
            tokenizer=tokenizer,
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

    prompt_text = _sanitize_prompt_text(text)

    llm: ChatOpenAI | None = None
    clf_pipeline = None

    for index in selected_indices:
        template = template_map.get(index)
        if template is None:
            continue
        name = template.get("choice_name", "")
        prompt = template.get("prompt", "")
        if name == "Классификация":
            candidates = [label.strip() for label in prompt.split(",") if label.strip()]
            if not candidates:
                continue
            model_type = template.get("model_type") or "UNIVERSAL"
            if model_type == "PRETRAINED":
                if clf_pipeline is None:
                    clf_pipeline = _ensure_pipeline()
                result = clf_pipeline(prompt_text, candidate_labels=candidates, multi_label=False)
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
                classifications = f"{normalized}".strip()
            else:
                if llm is None:
                    llm = _build_llm()
                classification_prompt = (
                    "Выбери наиболее подходящую категорию из списка. "
                    f"Варианты: {', '.join(candidates)}.\n\n"
                    f"Текст:\n{prompt_text.strip()}\n\n"
                    "Ответь только одним вариантом из списка."
                )
                response = _extract_message_content(llm.invoke(classification_prompt))
                predicted = _normalize_label(response, candidates)
                classifications = f"{predicted}".strip()
            continue

        if llm is None:
            llm = _build_llm()
        message_prompt = f"{prompt.strip()}\n\nТекст:\n{prompt_text.strip()}"
        response = _extract_message_content(llm.invoke(message_prompt))
        if name == "Аннотация":
            short_summary = f"{response}"
        elif name == "Объекты":
            entities = f"{response}"
        elif name == "Тональность":
            sentiments = f"{response}"
        elif name == "Выводы":
            full_summary = f"{response}"

    return short_summary, entities, sentiments, classifications, full_summary, category


def _session_to_dict(session: Session, short: bool = False) -> Dict[str, Any]:
    payload = {
        "session_id": session.session_id,
        "version": session.version,
        "title": session.title,
        "text": session.text,
        "content": {
            "short_summary": session.short_summary,
            "entities": session.entities,
            "sentiments": session.sentiments,
            "classifications": session.classifications,
            "full_summary": session.full_summary,
        },
        "inserted_at": session.inserted_at,
        "updated_at": session.updated_at,
    }
    if short:
        payload.pop("text", None)
        payload.pop("content", None)
    return payload


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
    title: str,
    text: str,
    category_index: int,
    choices: Iterable[int],
    temporary: bool,
    user_uow: IUoW,
    analysis_uow: AnalysisTemplateUoW,
) -> Tuple[str, Dict[str, Any], str | None]:
    logger.info("start create_new_session")
    _validate_text_length(text)
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

    session_id = str(uuid4())
    session = Session(
        session_id=session_id,
        version=0,
        title=title.strip() or f"{short_summary[:40]}" or text[:40],
        text=text,
        short_summary=short_summary,
        entities=entities,
        sentiments=sentiments,
        classifications=classifications,
        full_summary=full_summary,
        inserted_at=now,
        updated_at=now,
    )
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        if user is None:
            user = User(
                user_id=user_id,
                temporary=temporary,
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
    return session_id, response, None


def update_session_summarization(
    user_id: str,
    session_id: str,
    text: str,
    category_index: int,
    choices: Iterable[int],
    version: int,
    user_uow: IUoW,
    analysis_uow: AnalysisTemplateUoW,
) -> Tuple[Dict[str, Any], str | None]:
    logger.info("start update_session_summarization")
    _validate_text_length(text)
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
        session.version = version + 1
        session.updated_at = now
        user.update_time(last_used_at=now)
        user_uow.commit()
    logger.info("finish update_session_summarization")
    response = {
        "short_summary": session.short_summary,
        "entities": session.entities,
        "sentiments": session.sentiments,
        "classifications": session.classifications,
        "full_summary": session.full_summary,
    }
    return response, None


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


def _build_session_pdf(payload: Dict[str, Any]) -> Path:
    from fpdf import FPDF

    title = (payload.get("title") or "Экспорт сессии").strip()
    query = payload.get("text")
    content: Dict[str, Any] = payload.get("content") or {}
    summary = "\n".join(
        [
            f'Краткое резюме: {content.get("short_summary", "")}',
            f'Извлеченные сущности: {content.get("entities", "")}',
            f'Тональность: {content.get("sentiments", "")}',
            f'Классификация: {content.get("classifications", "")}',
            f'Полный отчет: {content.get("full_summary", "")}',
        ]
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as fp:
        pdf = FPDF()
        pdf.add_page()
        font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", "", 12)
        pdf.cell(0, 10, f"Session: {title}", ln=1)
        pdf.ln(5)
        pdf.set_font("DejaVu", "", 11)
        pdf.multi_cell(0, 8, f"Query:\n{query}")
        pdf.ln(2)
        pdf.multi_cell(0, 8, f"Summary:\n{summary}")
        pdf.output(fp.name)
        return Path(fp.name)


def download_session_file(session_id: str, format: str, user_id: str, uow: IUoW) -> Path:
    normalized_format = (format or "").strip().lower()
    if normalized_format != "pdf":
        raise ValueError("Unsupported format")

    with uow:
        user = uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User not found")
        session = user.get_session(session_id)
        if session is None:
            raise ValueError("Session not found")
        payload = _session_to_dict(session)

    return _build_session_pdf(payload)


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
            parts = [
                session.title or "",
                session.entities or "",
                session.sentiments or "",
                session.classifications or "",
                session.short_summary or "",
                session.full_summary or "",
            ]
            session_query = getattr(session, "query", None)
            if session_query:
                parts.append(session_query or "")
            text_value = getattr(session, "text", "")
            if text_value:
                parts.append(text_value)
            summarization_value = getattr(session, "summarization", None)
            if summarization_value:
                parts.append(summarization_value)
            text_blob = " | ".join(part for part in parts if part)
            score = _match_score(text_blob, query)
            if score <= 0:
                continue
            results.append((_session_to_dict(session, short=True), score))
    results.sort(key=lambda item: item[1], reverse=True)
    results = results[:settings.AUTO_SUMMARIZATION_MAX_SESSIONS]
    results = [result[0] for result in results]
    logger.info(f"finish search_similarity_sessions, found={len(results)}")
    return results

def get_session_info(session_id: str, user_id: str, user_uow: IUoW) -> Dict[str, Any]:
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User not found")
        session = user.get_session(session_id)
        if session is None:
            raise ValueError("Session not found")
        return _session_to_dict(session)

def _validate_text_length(text: str) -> None:
    max_len = int(settings.AUTO_SUMMARIZATION_MAX_TEXT_LENGTH)
    if text is None or text == "":
        raise ValueError("Текст не задан")
    if len(text) > max_len:
        raise ValueError(f"Длина одного документа превышает лимит {max_len} символов")