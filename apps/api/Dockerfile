# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

# Extras to bake in, e.g. --build-arg EXTRAS="--extra temporal --extra litellm" or "--all-extras".
ARG EXTRAS="--all-extras"
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev ${EXTRAS} --no-install-project

COPY . .
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Same image runs the API (default) or the Temporal worker: `python -m app.temporal.worker`.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
