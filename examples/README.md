# OpenHQM Examples

This directory contains configuration examples and usage patterns for OpenHQM.

## Files

### Routing Configuration

- **[routing-config.yaml](routing-config.yaml)** - Comprehensive routing configuration example
  - Multiple transform types (JQ, JSONPath, Template, Passthrough)
  - Field-based and pattern-based matching
  - Header and query parameter mappings
  - Priority-based route selection
  - Default route fallback

### Kubernetes Deployment

- **[k8s-routing-configmap.yaml](k8s-routing-configmap.yaml)** - Kubernetes deployment with routing
  - ConfigMap for routing configuration
  - StatefulSet deployment with partition support
  - Environment variable configuration
  - Volume mounts for config files

## Quick Start

### 1. Basic Routing

Create a simple routing configuration:

```yaml
version: "1.0"
routes:
  - name: api-v1
    match_field: "metadata.version"
    match_value: "v1"
    endpoint: "api-v1-service"
    transform_type: "passthrough"
```

Enable routing:

```bash
OPENHQM_ROUTING__ENABLED=true
OPENHQM_ROUTING__CONFIG_PATH=/path/to/routing.yaml
```

### 2. JQ Transformation

Transform complex payloads:

```yaml
routes:
  - name: order-transform
    match_field: "metadata.type"
    match_value: "order"
    endpoint: "order-service"
    transform_type: "jq"
    transform: |
      {
        "order_id": .payload.id,
        "items": [.payload.cart[] | {
          "sku": .product_id,
          "quantity": .qty
        }]
      }
```

### 3. Session-Based Partitioning

Enable session affinity:

```bash
OPENHQM_PARTITIONING__ENABLED=true
OPENHQM_PARTITIONING__PARTITION_COUNT=10
OPENHQM_PARTITIONING__PARTITION_KEY_FIELD=metadata.session_id
OPENHQM_PARTITIONING__STICKY_SESSION_TTL=3600
```

Submit messages with session ID:

```json
{
  "payload": {"action": "get_cart"},
  "metadata": {
    "type": "legacy.request",
    "session_id": "sess-123"
  }
}
```

### 4. Kubernetes Deployment

Deploy with ConfigMap:

```bash
kubectl apply -f k8s-routing-configmap.yaml
```

Scale workers:

```bash
kubectl scale statefulset openhqm-workers --replicas=10
```

## Use Cases

### Multi-Service Architecture

Route to different microservices:

```yaml
routes:
  - name: user-service
    match_field: "metadata.service"
    match_value: "users"
    endpoint: "user-service"
  
  - name: order-service
    match_field: "metadata.service"
    match_value: "orders"
    endpoint: "order-service"
  
  - name: payment-service
    match_field: "metadata.service"
    match_value: "payments"
    endpoint: "payment-service"
```

### Legacy Application Modernization

Add async capabilities to legacy apps:

```yaml
routes:
  - name: legacy-app
    match_field: "metadata.type"
    match_value: "legacy"
    endpoint: "legacy-service"
    transform_type: "template"
    transform: |
      {
        "session_id": "{{metadata.session_id}}",
        "user": "{{payload.user}}",
        "data": "{{payload.data}}"
      }
```

With partitioning:

```bash
OPENHQM_PARTITIONING__ENABLED=true
OPENHQM_PARTITIONING__PARTITION_KEY_FIELD=metadata.session_id
```

### API Versioning

Route based on API version:

```yaml
routes:
  - name: api-v2
    match_field: "metadata.api_version"
    match_value: "v2"
    endpoint: "api-v2-service"
    transform_type: "jq"
    transform: |
      {
        "version": 2,
        "payload": .payload
      }
  
  - name: api-v1
    match_field: "metadata.api_version"
    match_value: "v1"
    endpoint: "api-v1-service"
```

## Testing

Test routing locally:

```bash
# Start OpenHQM with routing config
OPENHQM_ROUTING__ENABLED=true \
OPENHQM_ROUTING__CONFIG_PATH=examples/routing-config.yaml \
python -m openhqm.api.listener

# Submit test message
curl -X POST http://localhost:8000/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {"user": "alice"},
    "metadata": {"type": "user.register"}
  }'
```

## Documentation

See:
- [ROUTING_PARTITIONING.md](../docs/ROUTING_PARTITIONING.md) - Complete routing and partitioning guide
- [PROXY_MODE.md](../docs/PROXY_MODE.md) - Proxy mode configuration
- [KUBERNETES_SIDECAR.md](../docs/KUBERNETES_SIDECAR.md) - Kubernetes sidecar pattern
