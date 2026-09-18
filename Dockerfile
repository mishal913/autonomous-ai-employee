# ============================================================
# Autonomous AI Employee — FastAPI backend
# Stage 5B
# ============================================================

FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip wheel \
       --wheel-dir /wheels \
       -r requirements.lock.txt


FROM python:3.11-slim AS runtime

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.lock.txt .

RUN python -m pip install \
      --no-index \
      --find-links=/wheels \
      -r requirements.lock.txt \
    && rm -rf /wheels

COPY app ./app

RUN mkdir -p \
    /app/logs \
    /app/knowledge/uploads \
    /app/.cache/huggingface

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
