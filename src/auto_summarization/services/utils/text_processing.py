from __future__ import annotations

import json
import logging
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from openai import OpenAI
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

from auto_summarization.services.config import settings


logger = logging.getLogger(__name__)


def _unique(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def extract_entities(text: str) -> Dict[str, List[str]]:
    persons = re.findall(r"\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\b", text)
    organisations = re.findall(r"(?:ООО|ПАО|АО|ЗАО|ОАО|ИП)\s*\"?[A-Za-zА-Яа-я0-9\-\s]+\"?", text)
    locations = re.findall(r"(?:(?:в|из|на)\s+)([А-ЯЁ][а-яё]+)", text)
    phones = re.findall(r"\+?\d[\d\s\-()]{7,}\d", text)
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", text)
    urls = re.findall(r"https?://[^\s]+", text)
    social_accounts = [
        handle
        for handle in re.findall(r"(?<![\w.@])@[A-Za-z0-9_]{3,}", text)
        if handle.split("@")[-1] not in {email.split("@")[-1] for email in emails}
    ]
    vehicles = re.findall(r"\b[А-ЯA-Z]{1,2}\d{3}[А-ЯA-Z]{2}\d{2,3}\b", text)
    documents = re.findall(r"\b\d{4}\s?\d{6}\b", text)

    return {
        "persons": _unique(persons),
        "organizations": _unique(organisations),
        "locations": _unique(locations),
        "phones": _unique(phones),
        "emails": _unique(emails),
        "vehicles": _unique(vehicles),
        "urls": _unique(urls),
        "social_accounts": _unique(social_accounts),
        "identity_documents": _unique(documents),
    }


POSITIVE_KEYWORDS = [
    "успех",
    "рост",
    "прибыль",
    "поддерж",
    "развит",
    "новый",
    "стабиль",
    "сильный",
    "побед",
]

NEGATIVE_KEYWORDS = [
    "убыт",
    "кризис",
    "паден",
    "снижен",
    "негатив",
    "проблем",
    "ошиб",
    "конфликт",
]

TOXIC_KEYWORDS = [
    "дурак",
    "идиот",
    "туп",
    "ругатель",
    "черт",
    "ненавижу",
]


def analyse_sentiment(text: str) -> Dict[str, object]:
    lowered = text.lower()
    positivity = sum(lowered.count(keyword) for keyword in POSITIVE_KEYWORDS)
    negativity = sum(lowered.count(keyword) for keyword in NEGATIVE_KEYWORDS)
    toxicity_hits = [keyword for keyword in TOXIC_KEYWORDS if keyword in lowered]

    polarity: str
    if positivity > negativity:
        polarity = "positive"
    elif negativity > positivity:
        polarity = "negative"
    else:
        polarity = "neutral"

    confidence = min(1.0, max(positivity, negativity) / 5 + 0.2)

    return {
        "polarity": polarity,
        "positivity_score": positivity,
        "negativity_score": negativity,
        "toxicity": {"has_toxic": bool(toxicity_hits), "keywords": toxicity_hits},
        "confidence": round(confidence, 2),
    }


CATEGORY_KEYWORDS = {
    "Экономика": [
        "банк",
        "инвест",
        "контракт",
        "финанс",
        "рынок",
        "выруч",
        "капитал",
        "эконом",
    ],
    "Спорт": [
        "матч",
        "команд",
        "турнир",
        "гол",
        "спорт",
        "игр",
        "тренер",
        "спортсмен",
    ],
    "Путешествия": [
        "поезд",
        "тур",
        "отель",
        "город",
        "путешеств",
        "маршрут",
        "виза",
        "авиабил",
    ],
}

CATEGORY_LABELS = {
    "Экономика": [
        "инвестиции",
        "макроэкономика",
        "рынок капитала",
        "торговля",
        "финансовые услуги",
    ],
    "Спорт": [
        "футбол",
        "баскетбол",
        "хоккей",
        "олимпийские виды",
        "киберспорт",
    ],
    "Путешествия": [
        "обзор маршрута",
        "отзыв",
        "советы",
        "репортаж",
        "культура",
    ],
}

DEFAULT_LABELS = ["Экономика", "Спорт", "Путешествия"]


def _heuristic_classification(text: str, category_name: str) -> Dict[str, object]:
    lowered = text.lower()
    keywords = CATEGORY_KEYWORDS.get(category_name, [])
    matches = [kw for kw in keywords if kw in lowered]
    counter = Counter(matches)
    matched_keywords = sorted(counter.keys())

    if not matched_keywords:
        matched_keywords = ["общая тематика"]

    confidence = min(0.95, 0.4 + 0.1 * len(matches))
    return {
        "strategy": "heuristic",
        "predicted_label": category_name if matches else matched_keywords[0],
        "matched_keywords": matched_keywords,
        "confidence": round(confidence, 2),
    }


@lru_cache(maxsize=1)
def _openai_client() -> Optional[OpenAI]:
    if not settings.OPENAI_API_KEY:
        return None
    return OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_API_HOST)


@lru_cache(maxsize=1)
def _hf_pipeline():
    model_path = Path(settings.AUTO_SUMMARIZATION_HF_MODEL_PATH)
    if not model_path.exists():
        raise FileNotFoundError(f"Hugging Face model path not found: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    return pipeline("zero-shot-classification", model=model, tokenizer=tokenizer)


def _classify_with_openai(text: str, category_name: str, prompt: str) -> Dict[str, object]:
    labels = CATEGORY_LABELS.get(category_name) or DEFAULT_LABELS
    client = _openai_client()
    if client is None:
        raise RuntimeError("OpenAI credentials are not configured")

    system_prompt = (
        "Ты помощник по аналитике текста. Выбери наиболее подходящую метку из списка и верни JSON с полями "
        "label и confidence (0..1). Если уверенности нет, выбери метку 'общая тематика'."
    )
    user_prompt = (
        f"Метки: {', '.join(labels)}.\n"
        f"Контекст категории: {category_name}.\n"
        f"Инструкция: {prompt}.\n"
        f"Текст: {text}"
    )

    response = client.chat.completions.create(
        model=settings.AUTO_SUMMARIZATION_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    content = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Unexpected OpenAI response: {content}") from exc

    label = data.get("label") or category_name
    confidence = float(data.get("confidence", 0.0))

    return {
        "strategy": "openai",
        "predicted_label": label,
        "confidence": round(confidence, 2),
        "labels": labels,
        "raw": data,
    }


def _classify_with_hf(text: str, category_name: str) -> Dict[str, object]:
    labels = CATEGORY_LABELS.get(category_name) or DEFAULT_LABELS
    classifier = _hf_pipeline()
    result = classifier(text, candidate_labels=labels, hypothesis_template="Этот текст о {}", multi_label=True)
    label_scores = dict(zip(result["labels"], result["scores"]))
    top_label = result["labels"][0] if result["labels"] else category_name
    return {
        "strategy": "huggingface",
        "predicted_label": top_label,
        "confidence": round(float(label_scores.get(top_label, 0.0)), 2),
        "scores": {label: round(float(score), 4) for label, score in label_scores.items()},
        "labels": labels,
    }


def classify_text(text: str, category_name: str, model_type: Optional[str], prompt: str) -> Dict[str, object]:
    base_payload = {
        "category": category_name,
        "model_type": model_type,
        "prompt": prompt,
    }

    heuristics = _heuristic_classification(text, category_name)

    try:
        if model_type == "universal":
            details = _classify_with_openai(text, category_name, prompt)
        elif model_type == "pretrained":
            details = _classify_with_hf(text, category_name)
        else:
            details = heuristics
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falling back to heuristic classification: %s", exc)
        details = heuristics
        details["warning"] = str(exc)
    else:
        if details.get("strategy") != "heuristic":
            details.setdefault("matched_keywords", heuristics.get("matched_keywords", []))

    base_payload.update(details)
    return base_payload


def _split_sentences(text: str) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def build_short_summary(text: str, prompt: str) -> str:
    sentences = _split_sentences(text)
    summary = " ".join(sentences[:2]) if sentences else text.strip()
    return summary or prompt


def build_full_summary(text: str, prompt: str) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return prompt
    core = sentences[:4]
    conclusion = f"Вывод: {prompt.lower()}" if prompt else "Вывод: ключевые идеи выделены."
    return " ".join(core + [conclusion])
