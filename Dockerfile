FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm AS python-deps
RUN python -m pip install --no-cache-dir uv==0.12.21
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PATH=/app/backend/.venv/bin:$PATH
WORKDIR /app/backend
COPY --from=python-deps /app/backend/.venv /app/backend/.venv
COPY backend/app /app/backend/app
COPY backend/scripts /app/backend/scripts
COPY backend/migrations /app/backend/migrations
COPY backend/alembic.ini /app/backend/alembic.ini
COPY demo /app/demo
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
RUN groupadd --gid 10001 sat-sa && useradd --uid 10001 --gid sat-sa --no-create-home sat-sa \
    && mkdir /data && chown sat-sa:sat-sa /data
USER sat-sa
EXPOSE 8000
CMD ["sh", "-c", "python -m app.startup && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log"]
