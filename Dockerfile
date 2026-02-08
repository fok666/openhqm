# Multi-stage Docker build for OpenHQM
# Supports building lightweight images for specific queue backends

# Build argument to specify which queue backend(s) to include
ARG QUEUE_BACKEND=all

# Stage 1: Build stage
FROM python:3.12-slim AS builder

ARG QUEUE_BACKEND

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    autoconf \
    automake \
    libtool \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt .
COPY requirements-queue-*.txt ./

# Install core dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Install queue-specific dependencies based on build argument
RUN if [ "$QUEUE_BACKEND" = "all" ]; then \
      pip install --no-cache-dir --user -r requirements-queue-all.txt; \
    elif [ "$QUEUE_BACKEND" = "redis" ]; then \
      pip install --no-cache-dir --user -r requirements-queue-redis.txt; \
    elif [ "$QUEUE_BACKEND" = "kafka" ]; then \
      pip install --no-cache-dir --user -r requirements-queue-kafka.txt; \
    elif [ "$QUEUE_BACKEND" = "sqs" ]; then \
      pip install --no-cache-dir --user -r requirements-queue-sqs.txt; \
    elif [ "$QUEUE_BACKEND" = "azure" ]; then \
      pip install --no-cache-dir --user -r requirements-queue-azure.txt; \
    elif [ "$QUEUE_BACKEND" = "gcp" ]; then \
      pip install --no-cache-dir --user -r requirements-queue-gcp.txt; \
    elif [ "$QUEUE_BACKEND" = "mqtt" ]; then \
      pip install --no-cache-dir --user -r requirements-queue-mqtt.txt; \
    elif [ "$QUEUE_BACKEND" = "minimal" ]; then \
      echo "Minimal build - no queue dependencies"; \
    else \
      echo "Unknown QUEUE_BACKEND: $QUEUE_BACKEND" && exit 1; \
    fi

# Stage 2: Runtime stage
FROM python:3.12-slim

ARG QUEUE_BACKEND
LABEL org.opencontainers.image.title="OpenHQM" \
      org.opencontainers.image.description="HTTP Queue Message Handler - Queue Backend: ${QUEUE_BACKEND}" \
      org.opencontainers.image.vendor="OpenHQM" \
      org.opencontainers.image.source="https://github.com/yourusername/openhqm" \
      queue.backend="${QUEUE_BACKEND}"

WORKDIR /app

# Install runtime dependencies (curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 openhqm && \
    chown -R openhqm:openhqm /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/openhqm/.local

# Copy application code
COPY --chown=openhqm:openhqm src/ /app/src/

# Set PATH for user-installed packages
ENV PATH=/home/openhqm/.local/bin:$PATH
ENV PYTHONPATH=/app/src
ENV OPENHQM_QUEUE_BACKEND=${QUEUE_BACKEND}

# Switch to non-root user
USER openhqm

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "openhqm.api.listener"]
