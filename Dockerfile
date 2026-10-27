# Stage 1: Build virtual environment with uv
FROM python:3.13-slim AS builder

WORKDIR /app

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Configure uv for containerized builds
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency definition files and package source
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install non-dev dependencies into /app/.venv
RUN uv sync --frozen --no-dev

# Stage 2: Final runtime container
FROM python:3.13-slim

# Create non-root user and group
RUN groupadd --system appgroup && useradd --system --gid appgroup --create-home appuser

WORKDIR /app

# Copy virtual environment from builder with non-root ownership
COPY --chown=appuser:appgroup --from=builder /app/.venv /app/.venv

# Add virtualenv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Streamlit environment variables
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Copy application files with non-root ownership
COPY --chown=appuser:appgroup src/ /app/src/
COPY --chown=appuser:appgroup app.py /app/app.py
COPY --chown=appuser:appgroup prompts/ /app/prompts/
COPY --chown=appuser:appgroup data/ /app/data/

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').getcode() == 200 else 1)"

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port", "8501"]
