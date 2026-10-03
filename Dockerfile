# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# --- system deps (for Pillow/openpyxl, security updates) ---
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 appuser

WORKDIR /app

# --- python deps ---
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- app code ---
COPY app ./app
COPY server.py ./
COPY assets ./assets
COPY index.html admin.html admin-add.html admin-reset.html ./

# Ensure upload dir exists and is writable
RUN mkdir -p assets/uploads && chown -R appuser:appuser /app

USER appuser

# --- healthcheck ---
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ping', timeout=3).getcode()==200 else 1)"

EXPOSE 8000

# Use unprivileged port 8000; Fly/Render inject PORT env
CMD ["sh", "-c", "python server.py --host 0.0.0.0 --port ${PORT:-8000}"]
