# Testing OpenHQM Proxy Mode

This guide shows how to test the proxy functionality.

## Quick Test with Docker Compose

### 1. Start the Services

```bash
docker-compose -f docker-compose.proxy.yml up -d
```

This starts OpenHQM in proxy mode with public APIs (JSONPlaceholder, httpbin) for testing.

### 2. Submit a Test Request

```bash
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "title": "Test Post",
      "body": "This is a test",
      "userId": 1
    },
    "metadata": {
      "endpoint": "jsonplaceholder"
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

### 3. Check Status

```bash
export CORRELATION_ID="550e8400-e29b-41d4-a716-446655440000"  # Use your actual ID

curl http://localhost:8000/api/v1/status/$CORRELATION_ID
```

### 4. Get Response

```bash
curl http://localhost:8000/api/v1/response/$CORRELATION_ID
```

Expected response:
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "status_code": 201,
  "result": {
    "id": 101,
    "title": "Test Post",
    "body": "This is a test",
    "userId": 1
  },
  "headers": {
    "content-type": "application/json; charset=utf-8"
  },
  "processing_time_ms": 245,
  "completed_at": "2026-02-07T10:30:01Z"
}
```

## Test with Different Endpoints

### Test httpbin endpoint

```bash
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "test": "data",
      "message": "Hello httpbin"
    },
    "headers": {
      "X-Custom-Header": "custom-value"
    },
    "metadata": {
      "endpoint": "httpbin"
    }
  }'
```

The response will include your payload echoed back from httpbin.org.

## Test Header Forwarding

```bash
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "data": "test"
    },
    "headers": {
      "Authorization": "Bearer test-token",
      "X-Request-ID": "req-123",
      "User-Agent": "OpenHQM-Test/1.0"
    },
    "metadata": {
      "endpoint": "httpbin"
    }
  }'
```

Check the response - httpbin will echo back the headers it received.

## Test with Authentication

### 1. Create .env file

```bash
cat > .env << EOF
OPENHQM_PROXY__ENABLED=true
OPENHQM_PROXY__ENDPOINTS={
  "protected-api": {
    "url": "https://your-api.com/endpoint",
    "auth_type": "bearer",
    "auth_token": "your-actual-token"
  }
}
EOF
```

### 2. Restart services

```bash
docker-compose -f docker-compose.proxy.yml down
docker-compose -f docker-compose.proxy.yml up -d
```

### 3. Test protected endpoint

```bash
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {"action": "test"},
    "metadata": {"endpoint": "protected-api"}
  }'
```

## Load Testing

### Install hey (HTTP load generator)

```bash
# macOS
brew install hey

# Linux
go install github.com/rakyll/hey@latest
```

### Run load test

```bash
# 100 requests with 10 concurrent workers
hey -n 100 -c 10 -m POST \
  -H "Content-Type: application/json" \
  -d '{"payload":{"test":"data"}}' \
  http://localhost:8000/api/v1/submit
```

### Monitor queue depth

```bash
# Watch Redis queue size
watch -n 1 'redis-cli llen openhqm-requests'
```

### Check metrics

```bash
curl http://localhost:8000/metrics
```

## Troubleshooting

### View logs

```bash
# API logs
docker-compose -f docker-compose.proxy.yml logs -f api

# Worker logs
docker-compose -f docker-compose.proxy.yml logs -f worker

# All logs
docker-compose -f docker-compose.proxy.yml logs -f
```

### Check Redis

```bash
# Connect to Redis
docker exec -it openhqm-redis-proxy redis-cli

# Check queue length
XLEN openhqm-requests

# View recent messages
XREAD COUNT 5 STREAMS openhqm-requests 0
```

### Health check

```bash
curl http://localhost:8000/health
```

### Metrics

```bash
# All metrics
curl http://localhost:8000/metrics

# Specific metric
curl http://localhost:8000/metrics | grep openhqm_worker_processing_duration
```

## Python Test Script

```python
import asyncio
import httpx

async def test_proxy():
    client = httpx.AsyncClient(timeout=30.0)
    
    # Submit request
    response = await client.post(
        "http://localhost:8000/api/v1/submit",
        json={
            "payload": {"title": "Test", "body": "Testing proxy mode"},
            "metadata": {"endpoint": "jsonplaceholder"}
        }
    )
    correlation_id = response.json()["correlation_id"]
    print(f"Submitted: {correlation_id}")
    
    # Poll for result
    for _ in range(30):
        await asyncio.sleep(1)
        response = await client.get(
            f"http://localhost:8000/api/v1/response/{correlation_id}"
        )
        result = response.json()
        
        if result["status"] in ["COMPLETED", "FAILED"]:
            print(f"Status: {result['status']}")
            print(f"Result: {result.get('result')}")
            break
    
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(test_proxy())
```

Run it:
```bash
python test_proxy.py
```

## Cleanup

```bash
docker-compose -f docker-compose.proxy.yml down -v
```

## Next Steps

1. Configure your own backend endpoints
2. Set up authentication tokens
3. Customize header forwarding rules
4. Scale workers based on load
5. Set up monitoring and alerting

See [PROXY_MODE.md](PROXY_MODE.md) for complete configuration guide.
