from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auto_summarization.entrypoints.routers import analysis, session, user
from auto_summarization.services import config


class API(FastAPI):
    def __init__(self) -> None:
        super().__init__(title="FastAPI", description="Auto Summarization API")

        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.get("/health")
        async def health():
            return {"status": "ok"}


app = API()
prefix = config.settings.AUTO_SUMMARIZATION_URL_PREFIX
app.include_router(user.router, prefix=f"{prefix}/user", tags=["users"])
app.include_router(session.router, prefix=f"{prefix}/chat_session", tags=["sessions"])
app.include_router(analysis.router, prefix=f"{prefix}/analysis", tags=["analysis"])
