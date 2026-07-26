# Multi-stage build. QUEUE_BACKEND selects the pyproject extra to install:
# all (default) | redis | kafka | sqs | azure | gcp | mqtt | minimal
ARG QUEUE_BACKEND=all

FROM python:3.13-slim AS builder
ARG QUEUE_BACKEND

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN pip install --no-cache-dir --user ".[${QUEUE_BACKEND}]"

FROM python:3.13-slim

ARG QUEUE_BACKEND
LABEL org.opencontainers.image.title="OpenHQM" \
      org.opencontainers.image.description="HTTP/queue bridge sidecar - Queue Backend: ${QUEUE_BACKEND}" \
      org.opencontainers.image.source="https://github.com/yourusername/openhqm" \
      queue.backend="${QUEUE_BACKEND}"

# curl for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 openhqm

COPY --from=builder --chown=openhqm:openhqm /root/.local /home/openhqm/.local
ENV PATH=/home/openhqm/.local/bin:$PATH

USER openhqm

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Override with: python -m openhqm queue-to-http
CMD ["python", "-m", "openhqm", "http-to-queue"]
