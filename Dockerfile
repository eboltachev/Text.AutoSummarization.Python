FROM python:3.12

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./

RUN apt update && \
	apt install -y curl vim && \
	pip install --upgrade pip && \
	pip install uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY ./src/ ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

ENTRYPOINT uv run uvicorn chat-translation.entrypoints.api:app \
           --host ${CHAT_TRANSLATION_API_HOST} \
		   --port ${CHAT_TRANSLATION_API_PORT}
