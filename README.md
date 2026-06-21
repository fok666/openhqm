# OpenHQM — HTTP Queue Message Handler

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

OpenHQM decouples HTTP request handling from response delivery using a message
queue. Deploy it as a **Kubernetes sidecar** to add async queue processing to an
HTTP workload without changing the app.

It does exactly two things:

```text
http-to-queue   client ──HTTP──▶ [openhqm] ──enqueue──▶ queue        (returns 202 + id)
queue-to-http   queue ──consume──▶ [openhqm] ──HTTP──▶ your backend  (stores result)
```

Run them together and you get an async reverse proxy; run either alone for
just ingress or just egress. Both modes are the same image, selected by argument.

## How it works

1. A client `POST`s to the **http-to-queue** sidecar. It enqueues the request and
   returns `202` with a `correlation_id`.
2. The **queue-to-http** sidecar consumes the message, forwards the payload to the
   backend (typically the local app), and writes the result to a shared cache.
3. The client polls for the result by `correlation_id`.

Request state lives in the cache as `PENDING → PROCESSING → COMPLETED/FAILED`
(TTL'd). Both modes drain gracefully on `SIGTERM`.

## Quick start

```bash
pip install -r requirements.txt          # or requirements-queue-redis.txt for just Redis
cp .env.example .env                      # defaults target redis://localhost:6379

# Terminal 1 — ingress (HTTP → queue)
python -m openhqm http-to-queue

# Terminal 2 — egress (queue → HTTP), pointed at your backend
OPENHQM_PROXY__BACKEND_URL=http://localhost:8080 python -m openhqm queue-to-http
```

```bash
# Submit a request
curl -sX POST http://localhost:8000/api/v1/submit \
  -H 'Content-Type: application/json' \
  -d '{"payload": {"hello": "world"}}'
# → {"correlation_id": "…", "status": "PENDING", ...}

# Poll for the result
curl http://localhost:8000/api/v1/response/<correlation_id>
```

## API (http-to-queue mode)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/submit` | Enqueue a request, returns `202` + `correlation_id` |
| `GET`  | `/api/v1/status/{id}` | Current status |
| `GET`  | `/api/v1/response/{id}` | Result (`202` while still pending) |
| `GET`  | `/health` | Liveness |
| `GET`  | `/ready` | Readiness (queue + cache reachable) |
| `GET`  | `/metrics` | Prometheus metrics |

## Configuration

Environment variables, prefix `OPENHQM_`, `__` for nesting. Key ones:

```bash
OPENHQM_QUEUE__TYPE=redis                       # redis|kafka|sqs|azure_eventhubs|gcp_pubsub|mqtt|custom
OPENHQM_QUEUE__REDIS_URL=redis://localhost:6379
OPENHQM_CACHE__REDIS_URL=redis://localhost:6379
OPENHQM_PROXY__BACKEND_URL=http://localhost:8080   # queue-to-http target
```

See [`.env.example`](.env.example) for everything, and
[docs/QUEUE_BACKENDS.md](docs/QUEUE_BACKENDS.md) for per-backend setup.

## Queue backends

Redis Streams (default), Apache Kafka, AWS SQS, Azure Event Hubs, GCP Pub/Sub,
MQTT, or a custom handler. See [docs/QUEUE_BACKENDS.md](docs/QUEUE_BACKENDS.md).

## Deployment

Runs as a sidecar behind a Kubernetes Gateway. See
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and
[`examples/kubernetes/gateway.yaml`](examples/kubernetes/gateway.yaml).

## Development

```bash
pip install -r requirements-dev.txt
pytest                # unit tests run without Redis; integration tests auto-skip
ruff check . && ruff format --check .
```

## License

MIT — see [LICENSE](LICENSE).
