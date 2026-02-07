# OpenHQM Quick Start Guide

Get OpenHQM running in under 5 minutes!

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose (for containerized setup)
- Redis (if running locally without Docker)

## Option 1: Quick Start with Docker (Recommended)

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/openhqm.git
cd openhqm
```

### 2. Start all services

```bash
docker-compose up -d
```

This starts:
- Redis (message queue and cache)
- API server on http://localhost:8000
- 3 worker instances

### 3. Verify services are running

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-02-07T10:30:00Z",
  "components": {
    "api": "healthy",
    "queue": "healthy",
    "cache": "healthy"
  }
}
```

### 4. Submit your first request

```bash
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "operation": "echo",
      "data": "Hello OpenHQM!"
    }
  }'
```

Response:
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "submitted_at": "2026-02-07T10:30:00Z"
}
```

### 5. Check request status

```bash
curl http://localhost:8000/api/v1/status/{correlation_id}
```

### 6. Get the result

```bash
curl http://localhost:8000/api/v1/response/{correlation_id}
```

Response:
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "result": {
    "output": "Hello OpenHQM!",
    "processed_at": "2026-02-07T10:30:01Z"
  },
  "processing_time_ms": 125,
  "completed_at": "2026-02-07T10:30:01Z"
}
```

### 7. View logs

```bash
docker-compose logs -f api
docker-compose logs -f worker
```

### 8. Stop services

```bash
docker-compose down
```

---

## Option 2: Local Development Setup

### 1. Clone and setup

```bash
git clone https://github.com/yourusername/openhqm.git
cd openhqm
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or install Redis locally
# macOS: brew install redis && redis-server
# Ubuntu: sudo apt install redis-server && redis-server
```

### 5. Configure environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work for local Redis)
```

### 6. Start API server

```bash
python -m openhqm.api.listener
```

In another terminal:

### 7. Start worker

```bash
python -m openhqm.worker.worker worker-1
```

### 8. Test the setup

```bash
# Submit request
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{"payload": {"operation": "echo", "data": "Test"}}'

# Get response (use correlation_id from above)
curl http://localhost:8000/api/v1/response/{correlation_id}
```

---

## Option 3: Using Makefile

### Quick commands

```bash
# Install dependencies
make install

# Start Redis with Docker
docker-compose up redis -d

# Run API
make run-api

# In another terminal, run worker
make run-worker

# Run tests
make test

# Format code
make format

# Lint code
make lint
```

---

## Available Operations

OpenHQM supports several built-in operations for testing:

### Echo
```json
{
  "payload": {
    "operation": "echo",
    "data": "Your text here"
  }
}
```

### Uppercase
```json
{
  "payload": {
    "operation": "uppercase",
    "data": "convert this to uppercase"
  }
}
```

### Reverse
```json
{
  "payload": {
    "operation": "reverse",
    "data": "reverse this string"
  }
}
```

### Custom Operation
Add your own business logic in `src/openhqm/worker/processor.py`

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |
| `/api/v1/submit` | POST | Submit request |
| `/api/v1/status/{id}` | GET | Check status |
| `/api/v1/response/{id}` | GET | Get result |

---

## Monitoring

### View Metrics

```bash
curl http://localhost:8000/metrics
```

### Key Metrics

- `openhqm_api_requests_total` - Total API requests
- `openhqm_queue_depth` - Messages in queue
- `openhqm_worker_active` - Active workers
- `openhqm_worker_processing_duration_seconds` - Processing time

---

## Troubleshooting

### Port already in use

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
OPENHQM_SERVER__PORT=9000 python -m openhqm.api.listener
```

### Redis connection failed

```bash
# Check Redis is running
redis-cli ping

# Should return: PONG
```

### Worker not processing messages

```bash
# Check Redis queue
redis-cli XINFO STREAM openhqm-requests

# Check worker logs
docker-compose logs worker
```

### Can't connect to API

```bash
# Check if API is running
curl http://localhost:8000/health

# Check Docker logs
docker-compose logs api
```

---

## Next Steps

1. **Read the documentation**: Check [SDD.md](SDD.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
2. **Explore the code**: Start with `src/openhqm/api/routes.py`
3. **Run tests**: `make test`
4. **Add custom logic**: Modify `src/openhqm/worker/processor.py`
5. **Deploy to production**: Use provided Kubernetes manifests (coming soon)

---

## Getting Help

- 📖 [Full Documentation](docs/)
- 🐛 [Report Issues](https://github.com/yourusername/openhqm/issues)
- 💬 [Discussions](https://github.com/yourusername/openhqm/discussions)
- 📧 Email: team@openhqm.dev

---

**Happy coding with OpenHQM! 🚀**
