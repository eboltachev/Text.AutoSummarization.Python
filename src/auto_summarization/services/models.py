from __future__ import annotations

from functools import lru_cache
from typing import Iterable, List

from auto_summarization.services.config import settings
from openai import OpenAI
from transformers import pipeline


@lru_cache(maxsize=1)
def _get_openai_client() -> OpenAI:
    """Instantiate a reusable OpenAI client for universal analysis requests."""

    base_url = settings.OPENAI_API_HOST.rstrip("/")
    return OpenAI(api_key=settings.OPENAI_API_KEY, base_url=base_url)


def run_universal_completion(prompt: str, text: str) -> str:
    """Call the configured OpenAI compatible endpoint and return plain text."""

    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты эксперт по анализу текстов. Отвечай кратко, но информативно, "
                    "используя факты из текста."
                ),
            },
            {
                "role": "user",
                "content": f"{prompt}\n\nТекст:\n{text}",
            },
        ],
        max_tokens=300,
        temperature=0.2,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""


@lru_cache(maxsize=1)
def _get_zero_shot_pipeline():
    """Load the pre-trained HuggingFace model for zero-shot classification."""

    return pipeline(
        "zero-shot-classification",
        model=settings.AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH,
        tokenizer=settings.AUTO_SUMMARIZATION_PRETRAINED_MODEL_PATH,
        device=-1,
    )


def run_pretrained_classification(text: str, labels: Iterable[str]) -> str:
    classifier = _get_zero_shot_pipeline()
    result = classifier(text, candidate_labels=list(labels), multi_label=True)
    if not result["labels"]:
        return "Классификатор не смог определить метку."
    top_label: str = result["labels"][0]
    score: float = float(result["scores"][0])
    return f"{top_label} ({score:.1%})"


ECONOMY_LABELS: List[str] = [
    "макроэкономика",
    "финансовые рынки",
    "инфляция",
    "госрегулирование",
    "инвестиции",
]

SPORT_LABELS: List[str] = [
    "футбол",
    "баскетбол",
    "хоккей",
    "теннис",
    "единоборства",
    "легкая атлетика",
]

TRAVEL_LABELS: List[str] = [
    "деловое",
    "семейное",
    "приключенческое",
    "культурное",
    "пляжный отдых",
]


CATEGORY_LABEL_MAP = {
    "Экономика": ECONOMY_LABELS,
    "Спорт": SPORT_LABELS,
    "Путешествия": TRAVEL_LABELS,
}


def get_category_labels(category: str) -> Iterable[str]:
    return CATEGORY_LABEL_MAP.get(category, ("общая категория",))
