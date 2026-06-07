# Description: Multi-stage Docker image for the Stockie AI backend.
#              Stage 1 (builder) installs dependencies with uv.
#              Stage 2 (runtime) copies the venv and app code; no build tools.
#              The CMD runs the FastAPI server; Celery worker/beat services
#              override CMD in docker-compose.yml — they share this image.
#
# Last Modified By: bvela
# Created: 2026-06-07
# Last Modified:
#     2026-06-07 - File created; multi-stage build using uv.

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv
RUN pip install --no-cache-dir uv==0.7.12

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./

# Create venv and install runtime deps only (no dev extras)
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python -e "." --no-dev

# Copy application source
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the pre-built venv and application from the builder stage
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/app app/
COPY --from=builder /build/alembic alembic/
COPY --from=builder /build/alembic.ini ./
COPY --from=builder /build/pyproject.toml ./

# Activate the venv by prepending it to PATH
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Default: run the FastAPI server.
# Celery worker/beat override this CMD in docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
