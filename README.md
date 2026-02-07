# OpenHQM - HTTP Queue Message Handler

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/yourusername/openhqm/workflows/CI/badge.svg)](https://github.com/yourusername/openhqm/actions)

**OpenHQM** is an asynchronous HTTP request processing system that decouples request handling from response delivery using message queues. Deploy it as a **Kubernetes sidecar** to add async queue capabilities to legacy HTTP workloads **without changing code**, or use it as a standalone microservice for async processing.

> **💡 New: Sidecar/Envoy Pattern** - Add async processing to ANY HTTP application with zero code changes! Deploy OpenHQM as a K8s sidecar to modernize legacy apps, decouple scaling, and protect backends from traffic spikes. See [SIDECAR_REVOLUTION.md](SIDECAR_REVOLUTION.md) for details.

## 🚀 Features

- **Asynchronous Request Processing**: Submit HTTP requests and retrieve responses without blocking
- **Reverse Proxy Mode**: Configure workers to forward requests to any HTTP endpoint(s)
- **Kubernetes Sidecar Pattern**: Deploy as sidecar to add async queue capabilities to legacy HTTP workloads
- **Flexible Authentication**: Support for Bearer, API Key, Basic, and custom authentication
- **Transparent Header Forwarding**: Pass headers from client to backend seamlessly
- **7 Queue Backends + Custom**: Redis Streams, Kafka, AWS SQS, Azure Event Hubs, GCP Pub/Sub, MQTT, plus bring-your-own handler
- **Scalable Worker Pool**: Horizontally scalable workers for processing requests
- **Correlation Tracking**: Built-in request/response correlation with UUIDs
- **High Availability**: Fault-tolerant design with retry logic and dead letter queues
- **RESTful API**: Clean, well-documented API endpoints
- **Monitoring & Metrics**: Prometheus metrics and structured logging
- **Production Ready**: Docker support, health checks, and CI/CD pipelines

## 📋 Table of Contents

- [Composable Patterns](#composable-patterns)
- [Architecture](#architecture)
- [Kubernetes Sidecar Pattern](#kubernetes-sidecar-pattern)
- [Reverse Proxy Mode](#reverse-proxy-mode)
- [Queue Backends](#queue-backends)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Usage](#api-usage)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

## 🧩 Composable Patterns

OpenHQM implements **two fundamental patterns** that can be used independently or together:

### 1️⃣ HTTP → Queue (Ingress)
Accept HTTP requests and queue them for processing.
- **Use when**: You need to accept HTTP requests and process them asynchronously with custom logic
- **Example**: Image processing, ETL pipelines, notification services

### 2️⃣ Queue → HTTP (Egress)
Consume messages from a queue and forward to HTTP endpoints.
- **Use when**: You need to consume from a queue (Kafka/Redis) and POST to REST APIs
- **Example**: Kafka-to-REST bridge, webhook relay, rate-limited API client

### 3️⃣ HTTP → Queue → HTTP (Combined)
Use both patterns together for full async reverse proxy capabilities.
- **Use when**: You need async proxy with load shedding, sidecar pattern, or API gateway with queueing
- **Example**: Kubernetes sidecar, legacy app modernization, traffic spike protection

**The power is in composition!** Use Pattern 1 alone, Pattern 2 alone, or combine them for maximum flexibility.

See **[COMPOSABLE_PATTERNS.md](COMPOSABLE_PATTERNS.md)** for detailed explanation, use cases, and configuration examples.

## 🏗️ Architecture

OpenHQM follows a queue-based asynchronous processing pattern:

```
Client → HTTP Listener → Request Queue → Workers → Response Queue → HTTP Listener → Client
```

### Components

1. **HTTP Listener** (FastAPI): Accepts requests, generates correlation IDs, manages responses
2. **Message Queues**: Decouples request submission from processing (Redis/Kafka/SQS)
3. **Worker Pool**: Processes messages asynchronously with configurable concurrency
4. **Response Handler**: Matches responses to requests and delivers results

For detailed architecture information, see [SDD.md](SDD.md).

## 🎯 Kubernetes Sidecar Pattern

OpenHQM can be deployed as a **Kubernetes sidecar container** to modernize legacy HTTP-only applications without code changes:

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      # OpenHQM sidecar - adds async queue capability
      - name: openhqm-sidecar
        image: openhqm:latest
        env:
        - name: OPENHQM_PROXY__ENABLED
          value: "true"
        - name: OPENHQM_PROXY__DEFAULT_ENDPOINT
          value: "http://localhost:8080"  # Legacy app in same pod
      
      # Legacy application - unchanged
      - name: legacy-app
        image: legacy-app:v1.0
        ports:
        - containerPort: 8080
```

**Benefits:**
- ✅ **Zero code changes** to legacy applications
- ✅ **Independent scaling** - scale workers separately from app pods
- ✅ **Load shedding** - queue absorbs traffic spikes
- ✅ **Gradual migration** - modernize incrementally
- ✅ **Cost optimization** - scale workers to zero during off-peak

**Use Cases:**
- Add async processing to synchronous REST APIs
- Protect legacy backends from traffic spikes  
- Decouple scaling of ingress, workers, and application
- Modernize monoliths without rewrites

See **[KUBERNETES_SIDECAR.md](KUBERNETES_SIDECAR.md)** for complete Kubernetes deployment patterns.

## 🔄 Reverse Proxy Mode

OpenHQM can function as an **asynchronous reverse proxy**, forwarding requests to configured backend endpoints with full transparency. This mode enables:

- **Multiple Backend Endpoints**: Route requests to different services/APIs
- **Authentication Management**: Centrally manage auth tokens for backends
- **Header Forwarding**: Transparently pass headers between client and backend
- **Response Caching**: Cache backend responses with correlation tracking
- **Load Distribution**: Queue and distribute requests across worker pools

### Quick Example

```yaml
proxy:
  enabled: true
  endpoints:
    my-api:
      url: "https://api.example.com/v1/process"
      auth_type: "bearer"
      auth_token: "${API_TOKEN}"
```

Submit a request:
```bash
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {"data": "hello"},
    "headers": {"X-Custom": "value"},
    "metadata": {"endpoint": "my-api"}
  }'
```

See **[PROXY_MODE.md](PROXY_MODE.md)** for comprehensive proxy configuration guide.

## ⚡ Quick Start

### Using Docker Compose

```bash
# Clone the repository
git clone https://github.com/yourusername/openhqm.git
cd openhqm

# Start all services (API, Workers, Redis)
docker-compose up -d

# Check service health
curl http://localhost:8000/health

# Submit a request
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{"payload": {"operation": "echo", "data": "Hello World"}}'

# Get the response (use correlation_id from previous response)
curl http://localhost:8000/api/v1/response/{correlation_id}
```

## 📦 Installation

### Prerequisites

- Python 3.11 or higher
- Redis 6.0+ (or Kafka/SQS)
- pip or poetry

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Set up configuration
cp config.example.yaml config.yaml
# Edit config.yaml with your settings

# Run the HTTP listener
python -m openhqm.api.listener

# In another terminal, run workers
python -m openhqm.worker.worker
```

## ⚙️ Configuration

OpenHQM uses YAML configuration files and environment variables.

### config.yaml

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4

queue:
  type: "redis"  # Options: redis, kafka, sqs
  connection:
    redis:
      url: "redis://localhost:6379"

worker:
  count: 5
  batch_size: 10
  timeout_seconds: 300
  max_retries: 3

cache:
  type: "redis"
  ttl_seconds: 3600
```

### Environment Variables

```bash
OPENHQM_QUEUE_TYPE=redis
OPENHQM_REDIS_URL=redis://localhost:6379
OPENHQM_LOG_LEVEL=INFO
OPENHQM_WORKER_COUNT=5
```

See [docs/configuration.md](docs/configuration.md) for all configuration options.

## 🔌 API Usage

### Submit a Request

```bash
POST /api/v1/submit
Content-Type: application/json

{
  "payload": {
    "operation": "process",
    "data": {"key": "value"}
  },
  "metadata": {
    "priority": "normal",
    "timeout": 300
  }
}
```

**Response:**
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "submitted_at": "2026-02-07T10:30:00Z"
}
```

### Check Status

```bash
GET /api/v1/status/{correlation_id}
```

**Response:**
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "submitted_at": "2026-02-07T10:30:00Z",
  "updated_at": "2026-02-07T10:30:05Z"
}
```

### Retrieve Response

```bash
GET /api/v1/response/{correlation_id}
```

**Response:**
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "result": {"output": "processed data"},
  "processing_time_ms": 1250,
  "completed_at": "2026-02-07T10:30:10Z"
}
```

## 🛠️ Development

### Project Structure

```
openhqm/
├── src/openhqm/           # Main package
│   ├── api/               # HTTP API layer
│   ├── queue/             # Queue implementations
│   ├── worker/            # Worker logic
│   ├── cache/             # Caching layer
│   └── config/            # Configuration
├── tests/                 # Test suite
├── docs/                  # Documentation
├── .github/workflows/     # CI/CD
└── docker/                # Docker configs
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy src/

# Run tests
pytest tests/ -v --cov=openhqm

# Security check
bandit -r src/
```

### Adding a New Queue Backend

1. Implement the `MessageQueueInterface` in `src/openhqm/queue/`
2. Register the implementation in `queue/__init__.py`
3. Add configuration schema in `config/settings.py`
4. Write integration tests

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=openhqm --cov-report=html

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run load tests
locust -f tests/load/locustfile.py
```

## 🚢 Deployment

### Docker

```bash
# Build image
docker build -t openhqm:latest .

# Run HTTP listener
docker run -p 8000:8000 openhqm:latest listener

# Run workers
docker run openhqm:latest worker
```

### Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/

# Check deployment
kubectl get pods -n openhqm

# View logs
kubectl logs -f deployment/openhqm-api -n openhqm
```

### Docker Compose

```bash
# Start all services
docker-compose up -d

# Scale workers
docker-compose up -d --scale worker=10

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📊 Monitoring

### Metrics

Prometheus metrics available at `/metrics`:

- `openhqm_requests_total`: Total requests received
- `openhqm_requests_duration_seconds`: Request processing time
- `openhqm_queue_depth`: Current queue depth
- `openhqm_worker_active`: Active workers

### Logging

Structured JSON logs with correlation IDs for tracing:

```json
{
  "timestamp": "2026-02-07T10:30:00Z",
  "level": "INFO",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Request processed successfully",
  "duration_ms": 1250
}
```

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Message queue support via Redis, Kafka, and AWS SQS
- Inspired by modern async processing patterns

## 📞 Support

- Documentation: [docs/](docs/)
- Issues: [GitHub Issues](https://github.com/yourusername/openhqm/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/openhqm/discussions)

---

**Made with 🤖 for the async processing community**
Bridges queues and https services

HTTP(s) Endpoint -> request -> queue -> message -> worker -> response -> HTTP(s) Endpoint

reciever queue
response queue

session handlig

worker pool
scaling

