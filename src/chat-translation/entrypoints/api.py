from entrypoints.routers import session, user, model
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services import config


class API(FastAPI):
    def __init__(self) -> None:
        super().__init__()

        self.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
        )

        @self.get("/health")
        async def health():
            return {"status": "ok"}


app = API()
prefix = config.settings.CHAT_TRANSLATION_URL_PREFIX
app.include_router(user.router, prefix=f"{prefix}/user", tags=["users"])
app.include_router(model.router, prefix=f"{prefix}/models", tags=["models"])
app.include_router(session.router, prefix=f"{prefix}/chat_session", tags=["sessions"])

