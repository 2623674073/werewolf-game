# syntax=docker/dockerfile:1.7
FROM node:20-bookworm-slim AS web
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package.json
RUN npm ci
COPY frontend frontend
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS python-builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_URL=sqlite+aiosqlite:////app/data/werewolf.db \
    WEB_DIST_DIR=/app/frontend/dist
WORKDIR /app
RUN groupadd --system werewolf && useradd --system --gid werewolf --home /app werewolf
COPY --from=python-builder /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations migrations
COPY --from=web /workspace/frontend/dist frontend/dist
COPY docker-entrypoint.sh ./
RUN mkdir -p /app/data && chown -R werewolf:werewolf /app && chmod +x docker-entrypoint.sh
USER werewolf
EXPOSE 8000
VOLUME ["/app/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"]
ENTRYPOINT ["./docker-entrypoint.sh"]
