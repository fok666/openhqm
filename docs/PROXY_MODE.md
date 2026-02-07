# OpenHQM Reverse Proxy Mode

## Overview

OpenHQM can operate as an **asynchronous reverse proxy**, allowing you to configure multiple backend endpoints that workers will call. This mode transforms OpenHQM into a scalable, queue-based HTTP proxy with support for:

- Multiple named endpoints with independent configurations
- Various authentication methods (Bearer, API Key, Basic, Custom)
- Transparent header forwarding
- Response caching and correlation tracking
- Retry logic and error handling

## Use Cases

1. **API Gateway**: Route requests to different microservices based on endpoint selection
2. **Rate Limiting**: Control request flow to backend services through queue management
3. **Load Distribution**: Distribute high-volume requests across worker pools
4. **Authentication Management**: Centrally manage authentication tokens for multiple services
5. **Request Buffering**: Handle traffic spikes by queuing requests
6. **Async Request Processing**: Submit requests and retrieve results later

## Architecture

```mermaid
flowchart LR
    Client[Client]
    API[OpenHQM API]
    ReqQueue[Request Queue]
    Workers[Workers]
    Backend[Backend Endpoints]
    RespQueue[Response Queue]
    Poll[Client polls for response]
    
    Client --> API
    API --> ReqQueue
    ReqQueue --> Workers
    Workers --> Backend
    Backend -.-> Results
    Results --> RespQueue
    RespQueue --> Poll
```

### Request Flow

1. **Client submits request** with:
   - Payload (JSON body to forward)
   - Headers (to be forwarded transparently)
   - Metadata (endpoint selection, priority, timeout)

2. **OpenHQM queues the request** with:
   - Generated correlation ID
   - Request metadata and headers
   - Timestamp and routing info

3. **Worker picks up request** and:
   - Selects configured endpoint
   - Merges authentication headers
   - Forwards request to backend
   - Captures response (body, status, headers)

4. **Response is stored** in cache with:
   - Original response body
   - HTTP status code
   - Response headers
   - Processing metadata

5. **Client retrieves response** using correlation ID

## Configuration

### Basic Setup

Enable proxy mode in your configuration:

```yaml
proxy:
  enabled: true
  default_endpoint: "my-api"
  max_response_size: 10485760  # 10MB
```

### Endpoint Configuration

Define one or more named endpoints:

```yaml
proxy:
  enabled: true
  default_endpoint: "primary-api"
  
  endpoints:
    primary-api:
      url: "https://api.example.com/v1/process"
      method: "POST"
      timeout: 300
      auth_type: "bearer"
      auth_token: "${API_TOKEN}"
      headers:
        X-Service: "openhqm"
    
    analytics-api:
      url: "https://analytics.example.com/events"
      method: "POST"
      timeout: 120
      auth_type: "api_key"
      auth_header_name: "X-API-Key"
      auth_token: "${ANALYTICS_KEY}"
```

### Environment Variables

Configure via environment variables:

```bash
# Enable proxy mode
OPENHQM_PROXY__ENABLED=true
OPENHQM_PROXY__DEFAULT_ENDPOINT=https://api.example.com/process

# Or use named endpoint
OPENHQM_PROXY__DEFAULT_ENDPOINT=my-api

# Configure endpoints as JSON
OPENHQM_PROXY__ENDPOINTS='{
  "my-api": {
    "url": "https://api.example.com/v1",
    "method": "POST",
    "timeout": 300,
    "auth_type": "bearer",
    "auth_token": "your-token-here"
  }
}'
```

## Authentication Methods

### Bearer Token

```yaml
endpoints:
  my-api:
    url: "https://api.example.com"
    auth_type: "bearer"
    auth_token: "${BEARER_TOKEN}"
```

Sends: `Authorization: Bearer ${BEARER_TOKEN}`

### API Key

```yaml
endpoints:
  my-api:
    url: "https://api.example.com"
    auth_type: "api_key"
    auth_header_name: "X-API-Key"
    auth_token: "${API_KEY}"
```

Sends: `X-API-Key: ${API_KEY}`

### Basic Authentication

```yaml
endpoints:
  my-api:
    url: "https://api.example.com"
    auth_type: "basic"
    auth_username: "${USERNAME}"
    auth_password: "${PASSWORD}"
```

Sends: `Authorization: Basic base64(username:password)`

### Custom Authentication

```yaml
endpoints:
  my-api:
    url: "https://api.example.com"
    auth_type: "custom"
    auth_header_name: "X-Custom-Auth"
    auth_token: "${CUSTOM_TOKEN}"
```

Sends: `X-Custom-Auth: ${CUSTOM_TOKEN}`

### No Authentication

```yaml
endpoints:
  public-api:
    url: "https://public-api.example.com"
    # No auth_type specified
```

## Header Forwarding

Configure which headers to forward from client to backend:

```yaml
proxy:
  forward_headers:
    - "Content-Type"
    - "Accept"
    - "User-Agent"
    - "Authorization"  # Client's auth (if not overridden)
    - "X-Request-ID"
    - "X-Correlation-ID"
  
  strip_headers:
    - "Host"
    - "Connection"
    - "Transfer-Encoding"
```

### Header Priority

1. **Static headers** from endpoint config (highest priority)
2. **Authentication headers** from endpoint config
3. **Forwarded headers** from client request
4. **Stripped headers** are removed

## API Usage

### Submit Request

```bash
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer client-token" \
  -d '{
    "payload": {
      "operation": "process",
      "data": "hello world"
    },
    "headers": {
      "X-Custom-Header": "value",
      "Authorization": "Bearer client-auth"
    },
    "metadata": {
      "endpoint": "my-api",
      "timeout": 300,
      "priority": 5
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

### Check Status

```bash
curl http://localhost:8000/api/v1/status/550e8400-e29b-41d4-a716-446655440000
```

Response:
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "submitted_at": "2026-02-07T10:30:00Z",
  "updated_at": "2026-02-07T10:30:05Z"
}
```

### Get Response

```bash
curl http://localhost:8000/api/v1/response/550e8400-e29b-41d4-a716-446655440000
```

Response:
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "status_code": 200,
  "result": {
    "output": "processed data from backend"
  },
  "headers": {
    "Content-Type": "application/json",
    "X-Response-ID": "abc123"
  },
  "processing_time_ms": 1250,
  "completed_at": "2026-02-07T10:30:10Z"
}
```

## Request Routing

### Using Default Endpoint

If no endpoint is specified, the default endpoint is used:

```json
{
  "payload": {"data": "hello"}
}
```

### Using Named Endpoint

Specify the endpoint in metadata:

```json
{
  "payload": {"data": "hello"},
  "metadata": {
    "endpoint": "analytics-api"
  }
}
```

### Method Override

Override the HTTP method per request:

```json
{
  "payload": {"data": "hello"},
  "metadata": {
    "endpoint": "my-api",
    "method": "PUT"
  }
}
```

## Response Handling

### Success Response

When the backend returns successfully, OpenHQM captures:
- Response body (JSON or text)
- HTTP status code
- Response headers
- Processing time

### Error Response

Backend errors (4xx, 5xx) are still captured transparently:

```json
{
  "correlation_id": "...",
  "status": "COMPLETED",
  "status_code": 400,
  "result": {
    "error": "Bad Request",
    "message": "Invalid payload"
  },
  "completed_at": "..."
}
```

### Request Failures

If the request to backend fails (timeout, connection error):

```json
{
  "correlation_id": "...",
  "status": "FAILED",
  "error": "Failed to proxy request: Connection timeout",
  "completed_at": "..."
}
```

## Timeouts and Retries

### Per-Endpoint Timeout

```yaml
endpoints:
  slow-api:
    url: "https://slow.example.com"
    timeout: 600  # 10 minutes
```

### Per-Request Timeout

```json
{
  "payload": {"data": "hello"},
  "metadata": {
    "timeout": 120
  }
}
```

### Retry Configuration

Global retry settings (worker level):

```yaml
worker:
  max_retries: 3
  retry_delay_base: 1.0
  retry_delay_max: 60.0
```

## Monitoring

### Metrics

Prometheus metrics are available at `/metrics`:

- `openhqm_queue_publish_total` - Requests submitted
- `openhqm_worker_processing_duration_seconds` - Processing time
- `openhqm_worker_errors_total` - Error counts by type
- `openhqm_queue_dlq_total` - Dead letter queue entries

### Logging

Structured logs include:
- `correlation_id` - Request tracking
- `endpoint` - Target endpoint name
- `status_code` - Backend response status
- `processing_time_ms` - Total processing time
- `error` - Error details if failed

## Security Considerations

1. **Token Management**: Store auth tokens in environment variables or secrets manager
2. **Header Filtering**: Only forward necessary headers to backends
3. **Response Size Limits**: Configure `max_response_size` to prevent memory issues
4. **Input Validation**: Validate payloads before forwarding
5. **Rate Limiting**: Use queue depth to control backend load
6. **TLS/SSL**: Always use HTTPS for backend endpoints
7. **Secrets**: Never log authentication tokens or sensitive headers

## Examples

### Multiple Microservices

```yaml
proxy:
  enabled: true
  endpoints:
    user-service:
      url: "https://users.example.com/api"
      auth_type: "bearer"
      auth_token: "${USER_SERVICE_TOKEN}"
    
    order-service:
      url: "https://orders.example.com/api"
      auth_type: "bearer"
      auth_token: "${ORDER_SERVICE_TOKEN}"
    
    payment-service:
      url: "https://payments.example.com/api"
      auth_type: "bearer"
      auth_token: "${PAYMENT_SERVICE_TOKEN}"
```

Client selects service:
```json
{
  "payload": {"action": "create_order"},
  "metadata": {"endpoint": "order-service"}
}
```

### Legacy System Integration

```yaml
proxy:
  enabled: true
  endpoints:
    legacy-soap:
      url: "https://legacy.example.com/soap/endpoint"
      method: "POST"
      timeout: 600
      auth_type: "basic"
      auth_username: "${LEGACY_USER}"
      auth_password: "${LEGACY_PASS}"
      headers:
        Content-Type: "text/xml"
        SOAPAction: "processRequest"
```

### External API with Rate Limiting

```yaml
proxy:
  enabled: true
  endpoints:
    rate-limited-api:
      url: "https://api.external.com/v1/process"
      timeout: 300
      auth_type: "api_key"
      auth_header_name: "X-API-Key"
      auth_token: "${EXTERNAL_API_KEY}"

worker:
  count: 2  # Limit concurrent requests
  batch_size: 1  # Process one at a time
```

## Troubleshooting

### Endpoint Not Found

```
ConfigurationError: Endpoint 'my-api' not found in configuration
```

**Solution**: Verify endpoint name in configuration matches metadata.

### Proxy Mode Disabled

```
ConfigurationError: Proxy mode is not enabled
```

**Solution**: Set `OPENHQM_PROXY__ENABLED=true`

### Connection Timeout

```
ProcessingError: Request timeout
```

**Solution**: Increase endpoint timeout or check backend availability.

### Authentication Failed

Backend returns 401/403.

**Solution**: Verify authentication credentials and type are correct.

### Headers Not Forwarded

**Solution**: Add header names to `forward_headers` list in proxy config.

## Best Practices

1. **Use Named Endpoints**: Define endpoints in config, not URLs in requests
2. **Environment Variables**: Store all secrets in environment variables
3. **Timeouts**: Set appropriate timeouts per endpoint based on expected response time
4. **Monitoring**: Track metrics to identify slow endpoints or failures
5. **Error Handling**: Implement proper error handling in clients for failed requests
6. **Correlation IDs**: Pass through client correlation IDs for end-to-end tracing
7. **Response Size**: Set appropriate `max_response_size` to prevent memory issues
8. **Worker Scaling**: Scale workers based on queue depth and processing needs
9. **Testing**: Test each endpoint configuration thoroughly before production
10. **Documentation**: Document which endpoint serves which purpose

## Performance Tuning

### High Throughput

```yaml
worker:
  count: 20  # More workers
  batch_size: 10  # Process multiple at once

cache:
  max_connections: 50  # Larger connection pool
```

### Low Latency

```yaml
worker:
  count: 5
  batch_size: 1  # Process immediately

proxy:
  endpoints:
    fast-api:
      timeout: 30  # Short timeout
```

### Long-Running Requests

```yaml
worker:
  timeout_seconds: 3600  # 1 hour

proxy:
  endpoints:
    slow-api:
      timeout: 3600
```

## Migration Guide

### From Custom Processor to Proxy Mode

**Before** (custom processor):
```python
class MyProcessor(MessageProcessor):
    async def process(self, payload):
        # Custom logic
        return result
```

**After** (proxy mode):
```yaml
proxy:
  enabled: true
  endpoints:
    my-backend:
      url: "https://backend.example.com/process"
      auth_type: "bearer"
      auth_token: "${TOKEN}"
```

No code changes needed - just configuration!
