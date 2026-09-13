FROM python:3.13-slim-bookworm@sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TIMBER_ENV=production \
    FLASK_DEBUG=0 \
    APP_PORT=2112 \
    DATA_DIR=/data \
    UPLOAD_DIR=/uploads
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-compile -r requirements.lock \
    && groupadd --gid 1000 timber \
    && useradd --uid 1000 --gid timber --no-create-home timber \
    && mkdir /data /uploads \
    && chown timber:timber /data /uploads
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY docker/ ./docker/
USER 1000:1000
EXPOSE 2112
VOLUME ["/data", "/uploads"]
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "/app/docker/healthcheck.py"]
CMD ["python", "/app/docker/start.py"]
