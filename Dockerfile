# syntax=docker/dockerfile:1.6
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FIHI_ENV=production \
    FIHI_TRUST_PROXY=1 \
    FIHI_DATA_DIR=/data \
    PORT=8000

# security updates + unprivileged runtime user
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 appuser

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# application code only (databases and uploads live in the /data volume)
COPY app ./app
COPY server.py docker-entrypoint.py ./
COPY assets ./assets
COPY index.html info.html admin.html admin-add.html admin-login.html admin-reset.html ./
RUN rm -rf assets/uploads/* && mkdir -p /data && chown -R appuser:appuser /data

# NOTE: no VOLUME instruction on purpose (Railway rejects it). Attach a volume
# mounted at /data on the platform: that is what keeps the data across releases.

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/api/v1/ping' % os.environ.get('PORT','8000'), timeout=3).getcode()==200 else 1)"

EXPOSE 8000

# starts as root only to chown the mounted volume, then drops to appuser
CMD ["python", "docker-entrypoint.py"]
