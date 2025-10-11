from __future__ import annotations

from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile, status


class DocumentService:
    def __init__(self, supported_formats: Iterable[str]) -> None:
        self._supported_formats = {fmt.lower().lstrip(".") for fmt in supported_formats}

    async def extract_text(self, document: UploadFile) -> str:
        if not document.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл не найден")

        extension = Path(document.filename).suffix.lstrip(".").lower()
        if extension not in self._supported_formats:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Неподдерживаемый формат: {extension}",
            )

        content = await document.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пуст")

        # Простой текстовый импорт. Для бинарных форматов используем декодирование с игнорированием ошибок.
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="ignore")

        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if not cleaned:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Не удалось извлечь текст")
        return cleaned
