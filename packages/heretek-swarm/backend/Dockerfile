# Heretek Swarm API — Docker build
#
# Multi-stage build:
#   1. Builder: install deps and compile the Python package
#   2. Production: slim runtime image with the installed package
#
# Build context: repo root (where pyproject.toml lives)
# Usage: docker build -f backend/Dockerfile -t heretek-swarm-api .

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.14-slim AS builder

WORKDIR /app

# Install uv from official image (faster + more reproducible than pip install uv)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install system deps for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./
COPY backend ./backend

# Install all project dependencies (managed in pyproject.toml)
RUN uv sync --frozen --no-dev --no-editable

# =============================================================================
# Stage 2: Production runtime
# =============================================================================
FROM python:3.14-slim AS production

# Install curl for HEALTHCHECK and create non-root user
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1001 appgroup && useradd -u 1001 -g appgroup -s /bin/bash -m appuser

WORKDIR /app

# Copy installed venv from builder (read-only for app files)
COPY --from=builder --chown=appuser:appgroup --chmod=555 /app/.venv /app/.venv

# Copy the installed package
COPY --from=builder --chown=appuser:appgroup --chmod=555 /app/backend /app/backend

# Copy migrations from build context root
COPY --chown=appuser:appgroup --chmod=555 migrations /app/migrations

# Copy scripts (includes run_migrations.py)
COPY --chown=appuser:appgroup --chmod=555 scripts /app/scripts

# Copy entrypoint
COPY --chown=appuser:appgroup --chmod=555 backend/entrypoint.sh /app/entrypoint.sh

# Create agent_workspace, heretek_data, and config directories owned by appuser
RUN chmod +x /app/entrypoint.sh && \
    mkdir -p /app/agent_workspace /app/heretek_data /config && \
    chown appuser:appgroup /app/agent_workspace /app/heretek_data /config

# Set up environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -sf http://localhost:8000/api/health || exit 1

# Entrypoint runs migrations, then exec's CMD
ENTRYPOINT ["/app/entrypoint.sh"]

# Default: run the API server via heretek-swarm serve
CMD ["heretek-swarm", "serve", "--host", "0.0.0.0", "--port", "8000"]
