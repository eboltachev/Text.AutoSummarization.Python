from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auto_summarization.entrypoints.routers import analysis, analyze_types, document, sessions, users
from auto_summarization.services.config import settings


class API(FastAPI):
    def __init__(self) -> None:
        super().__init__(title="Auto Summarization API")

        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}


app = API()
prefix = settings.AUTO_SUMMARIZATION_URL_PREFIX
app.include_router(analyze_types.router, prefix=prefix, tags=["analyze-types"])
app.include_router(document.router, prefix=prefix, tags=["documents"])
app.include_router(analysis.router, prefix=prefix, tags=["analysis"])
app.include_router(users.router, prefix=prefix, tags=["users"])
app.include_router(sessions.router, prefix=prefix, tags=["sessions"])
