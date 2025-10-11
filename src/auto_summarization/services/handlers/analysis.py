from __future__ import annotations

import io
import os
import tempfile
from typing import Dict, Iterable, List, Tuple

from auto_summarization.services.config import settings
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW
from auto_summarization.services.models import (
    get_category_labels,
    run_pretrained_classification,
    run_universal_completion,
)

CHOICE_FIELD_MAP = {
    "аннотация": "short_summary",
    "объекты": "entities",
    "тональность": "sentiments",
    "классификация": "classifications",
    "выводы": "full_summary",
}

DEFAULT_MESSAGES = {
    "short_summary": "Аналитическая аннотация не запрошена пользователем.",
    "entities": "Извлечение объектов не запрошено пользователем.",
    "sentiments": "Анализ тональности не запрошен пользователем.",
    "classifications": "Классификация не запрошена пользователем.",
    "full_summary": "Полный вывод не запрошен пользователем.",
}


def extract_text(content: bytes, extension: str) -> str:
    ext = extension.lower().lstrip(".")
    if ext not in settings.AUTO_SUMMARIZATION_SUPPORTED_FORMATS:
        raise ValueError("Unsupported document format")

    if ext == "txt":
        return content.decode("utf-8", errors="ignore")

    if ext == "docx":
        try:
            from docx import Document  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing guard
            raise RuntimeError("Библиотека python-docx не установлена") from exc
        document = Document(io.BytesIO(content))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n".join(paragraphs)

    if ext == "pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing guard
            raise RuntimeError("Библиотека pypdf не установлена") from exc
        reader = PdfReader(io.BytesIO(content))
        fragments: List[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            fragments.append(text.strip())
        return "\n".join(fragment for fragment in fragments if fragment)

    if ext == "odt":
        try:
            from odf import teletype  # type: ignore
            from odf.opendocument import load  # type: ignore
            from odf.text import P  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing guard
            raise RuntimeError("Библиотека odfpy не установлена") from exc
        document = load(io.BytesIO(content))
        paragraphs = [
            teletype.extractText(node).strip()
            for node in document.getElementsByType(P)
            if teletype.extractText(node).strip()
        ]
        return "\n".join(paragraphs)

    if ext == "doc":
        try:
            import textract  # type: ignore
        except Exception:
            return (
                "Документ формата .doc успешно получен, однако автоматическое извлечение текста недоступно. "
                "Пожалуйста, сохраните файл в формате DOCX и повторите загрузку."
            )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        try:
            raw = textract.process(tmp_file_path)
            return raw.decode("utf-8", errors="ignore")
        finally:  # pragma: no cover - system cleanup
            try:
                os.remove(tmp_file_path)
            except OSError:
                pass

    raise ValueError("Unsupported document format")


def get_analyze_types(uow: AnalysisTemplateUoW) -> Tuple[List[str], List[str]]:
    with uow:
        templates = [template.to_dict() for template in uow.templates.list()]
    category_map: Dict[int, str] = {}
    choice_map: Dict[int, str] = {}
    for template in templates:
        category_map.setdefault(template["category_index"], template["category"])
        choice_map.setdefault(template["choice_index"], template["choice_name"])
    categories = [category_map[index] for index in sorted(category_map.keys())]
    choices = [choice_map[index] for index in sorted(choice_map.keys())]
    return categories, choices


def _build_model_header(model_type: str | None) -> str:
    if model_type == "UNIVERSAL":
        return f"[Универсальная модель] Источник: {settings.OPENAI_API_HOST}"
    if model_type == "PRETRAINED":
        return f"[Предобученная модель] Путь: {settings.AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH}"
    return "[Базовый анализ]"


def _format_text(text: str, max_length: int = 480) -> str:
    prepared = " ".join(text.split())
    if len(prepared) <= max_length:
        return prepared
    return prepared[: max_length - 3] + "..."


def _render_output(
    category: str,
    choice_name: str,
    prompt: str,
    text: str,
    model_type: str | None,
    generated: str | None = None,
    error: str | None = None,
) -> str:
    header = _build_model_header(model_type)
    formatted_text = _format_text(text)
    prompt_line = prompt.strip() if prompt.strip() else "Инструкция не указана."
    if generated:
        result_line = generated.strip()
    elif error:
        result_line = (
            f"Анализ завершился с ошибкой: {error}. Используйте резервный метод или повторите попытку позже."
        )
    else:
        result_line = (
            f"Сгенерированное объяснение: {choice_name} для категории '{category}' сформировано синтетическим обработчиком."
        )
    return (
        f"{header}\n"
        f"Категория: {category}\n"
        f"Тип анализа: {choice_name}\n"
        f"Инструкция: {prompt_line}\n"
        f"Анализируемый текст: {formatted_text}\n"
        f"Результат: {result_line}"
    )


def perform_analysis(
    text: str, category_index: int, choice_indices: Iterable[int], uow: AnalysisTemplateUoW
) -> Tuple[str, Dict[str, str]]:
    result = DEFAULT_MESSAGES.copy()
    with uow:
        templates = [template.to_dict() for template in uow.templates.list()]
    if not templates:
        raise ValueError("Типы анализа не настроены")
    category_map = {template["category_index"]: template["category"] for template in templates}
    if category_index not in category_map:
        raise ValueError("Некорректный индекс категории")
    available_choice_indexes = {
        template["choice_index"] for template in templates if template["category_index"] == category_index
    }
    invalid_choices = [idx for idx in choice_indices if idx not in available_choice_indexes]
    if invalid_choices:
        raise ValueError("Некорректный индекс выбора анализа")
    category = category_map[category_index]
    for template in templates:
        if template["category_index"] != category_index or template["choice_index"] not in choice_indices:
            continue
        field = CHOICE_FIELD_MAP.get(template["choice_name"].lower())
        if not field:
            continue
        model_type = template.get("model_type")
        generated_text: str | None = None
        error_message: str | None = None
        if model_type == "UNIVERSAL":
            try:
                generated_text = run_universal_completion(template["prompt"], text)
            except Exception as exc:  # pragma: no cover - network errors are environment specific
                error_message = f"{exc}"[:400]
        elif model_type == "PRETRAINED":
            try:
                labels = get_category_labels(category)
                generated_text = run_pretrained_classification(text, labels)
            except Exception as exc:  # pragma: no cover - model loading/inference failures
                error_message = f"{exc}"[:400]
        result[field] = _render_output(
            category,
            template["choice_name"],
            template["prompt"],
            text,
            model_type,
            generated=generated_text,
            error=error_message,
        )
    return category, result
