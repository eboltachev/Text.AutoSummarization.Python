from openai import OpenAI
from services.config import LANGUAGE_NAMES as languages
from services.config import settings


class UniversalTranslator:
    _client = None

    @classmethod
    def get_client(cls) -> OpenAI:
        if cls._client is None:
            cls._client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_HOST,
            )
        return cls._client

    @classmethod
    def translate(cls, text: str, source_lang: str, target_lang: str) -> str:
        client = cls.get_client()
        chat_response = client.chat.completions.create(
            model=settings.CHAT_TRANSLATION_UNIVERSAL_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": f"You should translate from {languages.get(source_lang)} to {languages.get(target_lang)}",
                },
                {"role": "user", "content": text},
            ],
            temperature=0,
            timeout=None,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        translated: str = chat_response.choices[0].message.content
        return translated
