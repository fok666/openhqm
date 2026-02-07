# OpenHQM Composable Patterns

## Overview

OpenHQM implements **two fundamental, composable patterns** that can be used independently or together:

1. **HTTP → Queue** (Ingress Pattern): Accept HTTP requests and queue them
2. **Queue → HTTP** (Egress Pattern): Consume from queue and forward to HTTP endpoints

These patterns are **orthogonal** - you can use either one alone, or combine them for powerful async proxy capabilities.

---

## Pattern 1: HTTP → Queue (Ingress)

### Purpose
Accept HTTP requests from clients and queue them for asynchronous processing.

### Architecture
```
┌─────────┐
│ Client  │
└────┬────┘
     │ HTTP POST
     ▼
┌─────────────────┐
│  HTTP Listener  │
│  (Port 8000)    │
│  • Accept req   │
│  • Generate ID  │
│  • Queue msg    │
└────┬────────────┘
     │
     ▼
┌─────────────────┐
│  Request Queue  │
│  (Redis/Kafka)  │
└─────────────────┘
```

### When to Use Alone
- **Custom processing logic**: Workers run your custom Python code, not HTTP forwarding
- **Event-driven systems**: Queue messages trigger arbitrary business logic
- **Batch processing**: Collect requests and process in batches
- **Fan-out patterns**: Multiple worker types consume same queue
- **Integration hub**: Queue feeds multiple downstream systems

### Configuration
```yaml
# HTTP → Queue only
proxy:
  enabled: false  # No HTTP forwarding

worker:
  count: 5
  # Workers run custom processor.py logic
```

### Example Use Cases
1. **Image Processing Pipeline**
   - Accept image upload via HTTP
   - Queue for processing (resize, compress, OCR)
   - Workers run custom image processing code
   - Results stored in S3 or database

2. **ETL System**
   - HTTP API accepts data transformation requests
   - Queue job for processing
   - Workers execute custom ETL logic
   - Results written to data warehouse

3. **Notification Service**
   - HTTP endpoint accepts notification requests
   - Queue for delivery
   - Workers send emails/SMS/push notifications
   - Custom retry logic per channel

### Worker Implementation
```python
# src/openhqm/worker/processor.py
class MessageProcessor:
    async def process(self, payload: dict) -> dict:
        # Your custom business logic here
        result = await my_custom_function(payload)
        return result
```

---

## Pattern 2: Queue → HTTP (Egress)

### Purpose
Consume messages from a queue and forward them as HTTP requests to backend endpoints.

### Architecture
```
┌─────────────────┐
│  Request Queue  │
│  (Redis/Kafka)  │
│  • Fed by       │
│    external     │
│    systems      │
└────┬────────────┘
     │
     ▼
┌─────────────────┐
│     Workers     │
│  • Consume msg  │
│  • Add auth     │
│  • HTTP POST    │
└────┬────────────┘
     │ HTTP
     ▼
┌─────────────────┐
│ Backend Service │
│ (Port 8080)     │
└─────────────────┘
```

### When to Use Alone
- **Queue consumer for external systems**: Other services publish to your queue, workers forward to HTTP endpoints
- **Message bus integration**: Consume from Kafka topics and POST to REST APIs
- **Webhook relay**: Queue webhook events, forward to configured endpoints
- **Rate-limited API client**: Queue requests, workers enforce rate limits when calling external APIs
- **Retry/circuit breaker**: Queue messages, workers handle HTTP failures with sophisticated retry logic

### Configuration
```yaml
# Queue → HTTP only
proxy:
  enabled: true
  endpoints:
    my-backend:
      url: "https://api.example.com/process"
      auth_type: "bearer"
      auth_token: "${API_TOKEN}"

# No HTTP listener needed - queue fed by external systems
# Just run workers
```

### Example Use Cases
1. **Kafka to REST Bridge**
   - Kafka producer publishes events
   - OpenHQM workers consume from Kafka
   - Forward events to REST API
   - Handle authentication and retries

2. **Async Webhook Dispatcher**
   - Event system publishes to Redis queue
   - Workers consume and POST to customer webhooks
   - Built-in retry with exponential backoff
   - Dead letter queue for failed deliveries

3. **Rate-Limited API Client**
   - Internal services publish to queue
   - Workers consume at controlled rate
   - Forward to rate-limited external API
   - Prevent API throttling

### Worker Implementation
```python
# No custom processor needed - proxy mode handles HTTP forwarding
# Just configure endpoints in settings.yaml
```

---

## Pattern 3: HTTP → Queue → HTTP (Full Proxy)

### Purpose
Accept HTTP requests, queue them, and forward to backend endpoints asynchronously.

### Architecture
```
┌─────────┐
│ Client  │
└────┬────┘
     │ HTTP POST
     ▼
┌─────────────────┐
│  HTTP Listener  │
│  (Port 8000)    │
│  • Accept req   │
│  • Generate ID  │
│  • Queue msg    │
└────┬────────────┘
     │
     ▼
┌─────────────────┐
│  Request Queue  │
│  (Redis/Kafka)  │
└────┬────────────┘
     │
     ▼
┌─────────────────┐
│     Workers     │
│  • Consume msg  │
│  • Add auth     │
│  • HTTP POST    │
└────┬────────────┘
     │ HTTP
     ▼
┌─────────────────┐
│ Backend Service │
│ (Port 8080)     │
└─────────────────┘
```

### When to Use Combined
- **Async reverse proxy**: Client submits request, worker forwards to backend asynchronously
- **Load shedding**: Queue absorbs traffic spikes, protects backend
- **Kubernetes sidecar**: Add async processing to legacy apps
- **API gateway with queueing**: Decouple frontend from backend processing
- **Multi-tenant proxy**: Different queues per tenant, independent scaling

### Configuration
```yaml
# HTTP → Queue → HTTP (full proxy mode)
proxy:
  enabled: true
  default_endpoint: "my-backend"
  
  endpoints:
    my-backend:
      url: "https://api.example.com/process"
      method: "POST"
      timeout: 300
      auth_type: "bearer"
      auth_token: "${API_TOKEN}"

worker:
  count: 10
```

### Example Use Cases
1. **Legacy App Modernization (Sidecar)**
   - OpenHQM sidecar accepts HTTP requests
   - Queues requests
   - Workers forward to legacy app in same pod
   - Zero code changes to legacy app

2. **Scalable API Gateway**
   - Clients POST to OpenHQM API
   - Requests queued
   - Workers forward to multiple microservices
   - Independent scaling of ingress/workers/backends

3. **Traffic Spike Protection**
   - E-commerce site during Black Friday
   - OpenHQM absorbs traffic bursts
   - Queue depth grows temporarily
   - Workers process at sustainable rate
   - Backend never overwhelmed

---

## Pattern Comparison

| Aspect | HTTP → Queue | Queue → HTTP | Both Combined |
|--------|--------------|--------------|---------------|
| **HTTP Listener** | ✅ Yes | ❌ No | ✅ Yes |
| **Workers** | ✅ Custom code | ✅ HTTP proxy | ✅ HTTP proxy |
| **Proxy Mode** | ❌ Disabled | ✅ Enabled | ✅ Enabled |
| **Queue Source** | HTTP API | External | HTTP API |
| **Processing** | Custom logic | HTTP forward | HTTP forward |
| **Typical Use** | Event processing | Queue consumer | Async proxy |
| **Code Required** | Python processor | Config only | Config only |

---

## Deployment Scenarios

### Scenario 1: Custom Message Processing

**Pattern**: HTTP → Queue only

**Setup**:
- Deploy HTTP listener to accept requests
- Queue messages to Redis
- Deploy workers with custom processor code
- No proxy configuration needed

**Command**:
```bash
# Start API
python -m openhqm.api.listener

# Start workers (custom processing)
python -m openhqm.worker.worker
```

**Config**:
```yaml
proxy:
  enabled: false  # Custom processing, not HTTP forwarding
```

---

### Scenario 2: Kafka to REST Bridge

**Pattern**: Queue → HTTP only

**Setup**:
- External systems publish to Kafka
- Deploy workers only (no HTTP listener)
- Workers consume from Kafka, forward to REST API
- Configure endpoint with authentication

**Command**:
```bash
# Only start workers (no HTTP listener needed)
python -m openhqm.worker.worker
```

**Config**:
```yaml
queue:
  type: "kafka"
  kafka:
    bootstrap_servers: ["kafka:9092"]
    consumer_group: "openhqm-workers"

proxy:
  enabled: true
  endpoints:
    external-api:
      url: "https://api.example.com/events"
      auth_type: "api_key"
      auth_header_name: "X-API-Key"
      auth_token: "${API_KEY}"
```

---

### Scenario 3: Kubernetes Sidecar

**Pattern**: HTTP → Queue → HTTP

**Setup**:
- OpenHQM sidecar container in same pod as legacy app
- HTTP listener on port 8000
- Legacy app on port 8080
- Workers in separate deployment scale independently

**Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: legacy-app-with-sidecar
spec:
  replicas: 3
  template:
    spec:
      containers:
      # OpenHQM sidecar (HTTP → Queue)
      - name: openhqm-sidecar
        image: openhqm:latest
        command: ["python", "-m", "openhqm.api.listener"]
        ports:
        - containerPort: 8000
        env:
        - name: OPENHQM_PROXY__ENABLED
          value: "true"
        - name: OPENHQM_PROXY__DEFAULT_ENDPOINT
          value: "http://localhost:8080"
      
      # Legacy app (unchanged)
      - name: legacy-app
        image: legacy-app:v1.0
        ports:
        - containerPort: 8080

---
# Separate worker deployment (Queue → HTTP)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openhqm-workers
spec:
  replicas: 10  # Scale independently
  template:
    spec:
      containers:
      - name: worker
        image: openhqm:latest
        command: ["python", "-m", "openhqm.worker.worker"]
        env:
        - name: OPENHQM_PROXY__ENABLED
          value: "true"
        - name: OPENHQM_PROXY__DEFAULT_ENDPOINT
          value: "http://legacy-app-service:8080"
```

---

## Mixing Patterns in Multi-Service Architecture

You can deploy OpenHQM multiple times with different patterns:

```
┌──────────────────────────────────────────────────────────────┐
│                    Service Mesh                              │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Service A: HTTP → Queue (custom processing)      │     │
│  │  • Accept user uploads                             │     │
│  │  • Queue for processing                            │     │
│  │  • Workers run image processing                    │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Service B: Queue → HTTP (Kafka consumer)         │     │
│  │  • Consume from Kafka topic                        │     │
│  │  • Forward to external API                         │     │
│  │  • Handle authentication                           │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Service C: HTTP → Queue → HTTP (sidecar)         │     │
│  │  • Sidecar for legacy app                          │     │
│  │  • Accept HTTP, queue, forward                     │     │
│  │  • Zero code changes to app                        │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Configuration Examples

### HTTP → Queue (Custom Processing)

```yaml
# config.yaml
server:
  host: "0.0.0.0"
  port: 8000

queue:
  type: "redis"
  redis:
    url: "redis://redis:6379"

worker:
  count: 5
  timeout_seconds: 300

# Proxy disabled - custom processing
proxy:
  enabled: false

# Implement custom processor:
# src/openhqm/worker/processor.py
```

### Queue → HTTP (Kafka Consumer)

```yaml
# config.yaml
queue:
  type: "kafka"
  kafka:
    bootstrap_servers: ["kafka:9092"]
    consumer_group: "openhqm-workers"
    topics: ["events"]

worker:
  count: 10

# Proxy enabled - forward to HTTP endpoint
proxy:
  enabled: true
  endpoints:
    external-api:
      url: "https://api.example.com/webhook"
      method: "POST"
      auth_type: "bearer"
      auth_token: "${API_TOKEN}"
```

### HTTP → Queue → HTTP (Full Proxy)

```yaml
# config.yaml
server:
  host: "0.0.0.0"
  port: 8000

queue:
  type: "redis"
  redis:
    url: "redis://redis:6379"

worker:
  count: 10

# Full proxy mode
proxy:
  enabled: true
  default_endpoint: "backend-api"
  
  endpoints:
    backend-api:
      url: "http://backend-service:8080/api/process"
      method: "POST"
      timeout: 300
      auth_type: "bearer"
      auth_token: "${BACKEND_TOKEN}"
  
  forward_headers:
    - "Content-Type"
    - "Authorization"
    - "X-Request-ID"
```

---

## Decision Tree: Which Pattern to Use?

```
Do you need to accept HTTP requests from clients?
│
├─ YES ─────────────────────────────────────────┐
│   Do workers forward to HTTP endpoints?       │
│   │                                            │
│   ├─ YES → HTTP → Queue → HTTP (Full Proxy)  │
│   │         • Async reverse proxy              │
│   │         • Sidecar pattern                  │
│   │         • Load shedding                    │
│   │                                            │
│   └─ NO ──→ HTTP → Queue (Custom Processing) │
│             • Event-driven processing          │
│             • Custom business logic            │
│             • ETL, notifications, etc.         │
│                                                │
└─ NO ──────────────────────────────────────────┘
    Queue fed by external systems?
    │
    └─ YES → Queue → HTTP (Kafka/Event Consumer)
             • Kafka to REST bridge
             • Webhook relay
             • Rate-limited API client
```

---

## Best Practices

### For HTTP → Queue Pattern
1. **Implement idempotent processors**: Messages may be redelivered
2. **Use correlation IDs**: Track requests through the system
3. **Set appropriate timeouts**: Based on processing complexity
4. **Monitor queue depth**: Scale workers based on backlog
5. **Handle errors gracefully**: Use dead letter queues

### For Queue → HTTP Pattern
1. **Configure authentication**: Store tokens securely in environment variables
2. **Set endpoint timeouts**: Match backend SLAs
3. **Use retry logic**: Workers handle temporary failures automatically
4. **Monitor external API health**: Circuit breakers prevent cascading failures
5. **Validate responses**: Check status codes and response schemas

### For Combined Pattern (Full Proxy)
1. **Design for scalability**: Scale ingress, workers, and backends independently
2. **Use queue depth metrics**: Auto-scale workers based on queue size
3. **Configure HPA**: Kubernetes Horizontal Pod Autoscaler
4. **Test failure scenarios**: Queue full, backend down, network issues
5. **Monitor end-to-end latency**: Track time from submit to response

---

## Migration Strategies

### From Custom Processing to Proxy Mode

**Before** (HTTP → Queue with custom processing):
```python
class MessageProcessor:
    async def process(self, payload: dict) -> dict:
        # Custom logic that calls HTTP endpoint
        response = await http_client.post(url, json=payload)
        return response.json()
```

**After** (HTTP → Queue → HTTP with proxy mode):
```yaml
proxy:
  enabled: true
  endpoints:
    my-backend:
      url: "https://api.example.com/process"
      auth_type: "bearer"
      auth_token: "${TOKEN}"
```

**No Python code changes needed** - just configuration!

### From Standalone Queue Consumer to OpenHQM

**Before** (Custom Kafka consumer):
```python
# custom_consumer.py
consumer = KafkaConsumer('my-topic')
for message in consumer:
    response = requests.post(backend_url, json=message.value)
```

**After** (OpenHQM Queue → HTTP):
```yaml
queue:
  type: "kafka"
  kafka:
    bootstrap_servers: ["kafka:9092"]
    topics: ["my-topic"]

proxy:
  enabled: true
  endpoints:
    backend:
      url: "https://backend.example.com/api"
```

**Benefits**:
- Automatic retry logic
- Built-in monitoring
- Health checks
- Correlation tracking
- Dead letter queue
- Prometheus metrics

---

## Summary

OpenHQM's **two composable patterns** provide maximum flexibility:

| Pattern | Use When | Key Benefit |
|---------|----------|-------------|
| **HTTP → Queue** | Accept HTTP requests, custom processing | Event-driven architecture |
| **Queue → HTTP** | Consume from queue, forward to HTTP | Queue-to-REST bridge |
| **Both Combined** | Async HTTP proxy | Load shedding, sidecar pattern |

Choose the pattern(s) that fit your architecture. Mix and match across services. Scale each component independently.

**The power is in the composition!** 🚀
