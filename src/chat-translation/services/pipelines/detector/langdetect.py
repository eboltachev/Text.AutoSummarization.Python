from ftlangdetect import detect


class LanguageDetector:
    @classmethod
    def detect(cls, text: str) -> str:
        detected_language = detect(text=text, low_memory=True)
        return detected_language.get("lang")
