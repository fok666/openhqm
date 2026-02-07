# OpenHQM Proxy Mode - Summary

## What Changed

OpenHQM has been enhanced to function as an **asynchronous reverse proxy** while maintaining all its original queue-based async request processing capabilities.

## Key Features Added

### 1. Endpoint Configuration
- Configure multiple named backend endpoints
- Per-endpoint URL, method, timeout, and headers
- Default endpoint fallback

### 2. Authentication Support
- **Bearer Token**: `Authorization: Bearer <token>`
- **API Key**: Custom header with key (e.g., `X-API-Key`)
- **Basic Auth**: Username/password with Base64 encoding
- **Custom**: Any header name with token value

### 3. Header Management
- Transparent header forwarding from client to backend
- Configurable forward list (which headers to pass through)
- Configurable strip list (which headers to remove)
- Static headers per endpoint
- Auth header injection per endpoint

### 4. Request/Response Transparency
- Forward request payload as-is to backend
- Capture full response (body, status code, headers)
- Return backend response transparently to client
- Preserve HTTP status codes

## Architecture

```
Client Request with Headers
    ↓
OpenHQM API (stores correlation ID)
    ↓
Message Queue (with payload + headers)
    ↓
Worker (configured as proxy)
    ↓
HTTP Client → Backend Endpoint (with auth + headers)
    ↓
Backend Response (body + status + headers)
    ↓
Response Queue
    ↓
Cache (with full response)
    ↓
Client Retrieves Response
```

## Files Modified

### Core Application
1. **`src/openhqm/config/settings.py`**
   - Added `ProxySettings` class
   - Added `EndpointConfig` class
   - Support for endpoint configurations

2. **`src/openhqm/api/models.py`**
   - Added `headers` field to `SubmitRequest`
   - Added `endpoint` and `method` to `RequestMetadata`
   - Added `headers` and `status_code` to `ResultResponse`

3. **`src/openhqm/worker/processor.py`**
   - Complete rewrite as HTTP proxy client
   - Authentication header preparation
   - Header merging logic
   - HTTP request forwarding with aiohttp
   - Response capture and return

4. **`src/openhqm/worker/worker.py`**
   - Updated to handle new processor interface
   - Pass headers through message flow
   - Store response headers and status codes

5. **`src/openhqm/api/routes.py`**
   - Updated to accept and store headers
   - Return headers and status codes in responses

6. **`src/openhqm/exceptions.py`**
   - Added `ConfigurationError` exception

### Configuration Files
7. **`.env.example`**
   - Added proxy configuration examples
   - Endpoint configuration examples
   - Header forwarding configuration

8. **`config.example.yaml`** (new)
   - Comprehensive YAML configuration example
   - Multiple endpoint examples with different auth types

### Docker
9. **`docker-compose.proxy.yml`** (new)
   - Docker Compose setup for proxy mode
   - Example endpoints (JSONPlaceholder, httpbin)
   - Environment variable configuration

### Documentation
10. **`PROXY_MODE.md`** (new)
    - Complete proxy mode documentation
    - Configuration guide
    - Authentication examples
    - API usage examples
    - Troubleshooting guide

11. **`TESTING_PROXY.md`** (new)
    - Testing guide for proxy mode
    - Docker Compose quick start
    - Load testing instructions
    - Troubleshooting commands

12. **`README.md`**
    - Updated features list
    - Added proxy mode section
    - Link to proxy documentation

### Examples
13. **`examples/proxy_example.py`** (new)
    - Python client example
    - Multiple usage examples
    - Batch request example

### Tests
14. **`tests/unit/test_proxy_processor.py`** (new)
    - Unit tests for proxy processor
    - Auth header preparation tests
    - Header merging tests
    - Endpoint configuration tests

## Configuration Example

### Minimal Configuration
```yaml
proxy:
  enabled: true
  default_endpoint: "https://api.example.com/process"
```

### Full Configuration
```yaml
proxy:
  enabled: true
  default_endpoint: "my-api"
  max_response_size: 10485760
  
  forward_headers:
    - "Content-Type"
    - "Authorization"
  
  strip_headers:
    - "Host"
    - "Connection"
  
  endpoints:
    my-api:
      url: "https://api.example.com/v1"
      method: "POST"
      timeout: 300
      auth_type: "bearer"
      auth_token: "${API_TOKEN}"
      headers:
        X-Service: "openhqm"
```

## Usage Example

### Submit Request
```bash
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {"action": "process", "data": "hello"},
    "headers": {"Authorization": "Bearer client-token"},
    "metadata": {"endpoint": "my-api"}
  }'
```

### Get Response
```bash
curl http://localhost:8000/api/v1/response/{correlation_id}
```

Response includes:
- `result`: Backend response body
- `status_code`: Backend HTTP status
- `headers`: Backend response headers
- `processing_time_ms`: Total processing time

## Backward Compatibility

The changes are **fully backward compatible**:

1. **Proxy mode is optional** - Set `OPENHQM_PROXY__ENABLED=false` to use custom processors
2. **Existing API unchanged** - Headers and endpoint are optional fields
3. **Custom processors still work** - If proxy mode is disabled, custom processor logic runs

## Quick Start

### 1. Enable Proxy Mode
```bash
export OPENHQM_PROXY__ENABLED=true
export OPENHQM_PROXY__DEFAULT_ENDPOINT=https://api.example.com
```

### 2. Configure Endpoint (with auth)
```bash
export OPENHQM_PROXY__ENDPOINTS='{
  "my-api": {
    "url": "https://api.example.com/v1",
    "auth_type": "bearer",
    "auth_token": "your-token-here"
  }
}'
```

### 3. Start Services
```bash
docker-compose -f docker-compose.proxy.yml up -d
```

### 4. Test
```bash
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{"payload": {"test": "data"}}'
```

## Testing

Run proxy tests:
```bash
pytest tests/unit/test_proxy_processor.py -v
```

Run integration test:
```bash
# Start services
docker-compose -f docker-compose.proxy.yml up -d

# Run example
python examples/proxy_example.py

# Or test manually
bash TESTING_PROXY.md  # Follow the guide
```

## Benefits

1. **No Code Changes Needed** - Pure configuration
2. **Centralized Auth Management** - Tokens in one place
3. **Request Buffering** - Queue absorbs traffic spikes
4. **Async Processing** - Non-blocking request flow
5. **Correlation Tracking** - Full request traceability
6. **Retry Logic** - Automatic retry on failures
7. **Monitoring** - Metrics and logging included
8. **Scalability** - Scale workers independently

## Use Cases

1. **API Gateway** - Route to microservices
2. **Rate Limiting** - Control backend load via queue
3. **Request Aggregation** - Batch requests to backend
4. **Cache Layer** - Cache backend responses
5. **Auth Abstraction** - Hide backend auth from clients
6. **Load Distribution** - Spread requests across workers
7. **Async Processing** - Submit and retrieve later

## Next Steps

1. Read [PROXY_MODE.md](PROXY_MODE.md) for complete documentation
2. Review [config.example.yaml](config.example.yaml) for configuration examples
3. Try [examples/proxy_example.py](examples/proxy_example.py)
4. Follow [TESTING_PROXY.md](TESTING_PROXY.md) for testing guide
5. Configure your own endpoints and authentication
6. Scale workers based on load
7. Set up monitoring and alerting

## Support

For issues or questions:
1. Check [PROXY_MODE.md](PROXY_MODE.md) troubleshooting section
2. Review logs: `docker-compose logs -f`
3. Check metrics: `curl http://localhost:8000/metrics`
4. Refer to [ARCHITECTURE.md](ARCHITECTURE.md) for design details
