FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

ARG WORKER_DIR=agent_analysis
ENV WORKER_DIR=${WORKER_DIR}

COPY sdk ./sdk
COPY workers ./workers

RUN test -f "/app/workers/${WORKER_DIR}/pyproject.toml"
RUN uv sync --frozen --no-dev --project "/app/workers/${WORKER_DIR}"

COPY workers/start-worker.sh /start-worker.sh
RUN chmod +x /start-worker.sh

CMD ["bash", "/start-worker.sh"]
