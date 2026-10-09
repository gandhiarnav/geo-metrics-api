# syntax=docker/dockerfile:1
# Multi-stage Docker build for geo-metrics-api using uv and Python 3.12

# Stage 1: Build virtual environment
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies using lockfile
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy application source and migrations
COPY app app/
COPY alembic alembic/
COPY alembic.ini docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Stage 2: Production runtime image
FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Create unprivileged user for security
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

WORKDIR /app

# Copy application and virtualenv from builder
COPY --from=builder --chown=appuser:appgroup /app /app

USER appuser

EXPOSE 8000

# Zero-dependency healthcheck probe using standard Python library
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8000\")}/health')" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
