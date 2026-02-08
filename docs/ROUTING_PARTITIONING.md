# OpenHQM Routing and Partitioning

## Overview

OpenHQM now supports **advanced routing** and **partitioning** capabilities to enable:
- Dynamic payload transformations using JQ, JSONPath, or templates
- Flexible message routing to different endpoints
- Session affinity for legacy applications lacking horizontal scalability
- Sticky session management with partition assignment

## Routing

### Features

1. **Multiple Transform Types**
   - **JQ**: Powerful JSON transformation using jq expressions
   - **JSONPath**: Extract data using JSONPath queries
   - **Template**: Simple template-based substitution
   - **Passthrough**: No transformation (default)

2. **Flexible Matching**
   - Match by field value (exact match)
   - Match by regex pattern
   - Default routes for unmatched messages
   - Priority-based route selection

3. **Transformation Capabilities**
   - Transform payload structure
   - Map message fields to HTTP headers
   - Map message fields to query parameters
   - Override HTTP method per route
   - Override timeout and retry settings

### Configuration

#### Enable Routing

```bash
# Via environment variable
OPENHQM_ROUTING__ENABLED=true
OPENHQM_ROUTING__CONFIG_PATH=/etc/openhqm/routing.yaml

# Or inline config as JSON
OPENHQM_ROUTING__CONFIG_DICT='{"version":"1.0","routes":[...]}'
```

#### Routing Configuration File

Create a `routing.yaml` file:

```yaml
version: "1.0"
routes:
  - name: user-registration
    match_field: "metadata.type"
    match_value: "user.register"
    priority: 10
    endpoint: "user-service"
    transform_type: "jq"
    transform: |
      {
        "username": .payload.email | split("@")[0],
        "email": .payload.email,
        "full_name": .payload.name
      }
    header_mappings:
      X-Request-ID: "correlation_id"

default_endpoint: "default-service"
enable_fallback: true
```

### Transform Examples

#### JQ Transform

Transform complex nested structures:

```yaml
transform_type: "jq"
transform: |
  {
    "user_id": .payload.user.id,
    "items": [.payload.cart.items[] | {
      "sku": .product_id,
      "qty": .quantity,
      "price": .unit_price
    }],
    "total": (.payload.cart.items | map(.quantity * .unit_price) | add)
  }
```

#### JSONPath Transform

Extract specific fields:

```yaml
transform_type: "jsonpath"
transform: "$.payload.event.data"
```

#### Template Transform

Simple field substitution:

```yaml
transform_type: "template"
transform: |
  {
    "recipient": "{{payload.user.email}}",
    "subject": "{{payload.subject}}",
    "body": "{{payload.message}}"
  }
```

### Route Matching

Routes are evaluated in **priority order (highest first)**:

```yaml
routes:
  # High priority - exact match
  - name: critical-route
    match_field: "metadata.priority"
    match_value: "high"
    priority: 100
    endpoint: "critical-service"
  
  # Medium priority - pattern match
  - name: notification-routes
    match_field: "metadata.type"
    match_pattern: "^notification\\."
    priority: 50
    endpoint: "notification-service"
  
  # Default route
  - name: default
    is_default: true
    priority: 0
    endpoint: "default-service"
```

### Header and Query Parameter Mapping

Map message fields to HTTP headers and query params:

```yaml
routes:
  - name: api-route
    endpoint: "backend-service"
    header_mappings:
      X-User-ID: "payload.user.id"
      X-Session-ID: "metadata.session_id"
      X-Correlation-ID: "correlation_id"
    query_params:
      tenant_id: "metadata.tenant"
      version: "metadata.api_version"
```

## Partitioning

### Features

1. **Session Affinity**
   - Messages with same partition key always go to same worker
   - Enables state management for legacy applications
   - Supports sticky sessions with TTL

2. **Multiple Strategies**
   - **STICKY**: Consistent hashing for session affinity (recommended)
   - **HASH**: Hash-based distribution
   - **KEY**: Direct key-based assignment
   - **ROUND_ROBIN**: Simple round-robin

3. **Worker Coordination**
   - Automatic partition assignment across workers
   - Rebalancing on worker scale up/down
   - Session tracking and statistics

### Configuration

```bash
# Enable partitioning
OPENHQM_PARTITIONING__ENABLED=true
OPENHQM_PARTITIONING__PARTITION_COUNT=10
OPENHQM_PARTITIONING__STRATEGY=sticky

# Partition key field
OPENHQM_PARTITIONING__PARTITION_KEY_FIELD=metadata.session_id

# Session tracking
OPENHQM_PARTITIONING__STICKY_SESSION_TTL=3600
```

### Partition Key

Messages must include a partition key for routing:

```json
{
  "payload": {"data": "..."},
  "metadata": {
    "session_id": "user-123-session-456",
    "type": "user.request"
  }
}
```

### Worker Deployment

Workers need to know their index for partition assignment:

```bash
# Worker 0 of 5
python -m openhqm.worker.worker worker-0 0 5

# Worker 1 of 5
python -m openhqm.worker.worker worker-1 1 5
```

### Kubernetes StatefulSet

Use StatefulSet for automatic worker indexing:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: openhqm-workers
spec:
  replicas: 5
  serviceName: openhqm-workers
  template:
    spec:
      containers:
      - name: worker
        image: openhqm:latest
        command: ["python", "-m", "openhqm.worker.worker"]
        args:
        - "$(POD_NAME)"
        - "$(POD_INDEX)"
        - "5"
        env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: POD_INDEX
          value: "0"  # Set via init script or controller
        - name: OPENHQM_PARTITIONING__ENABLED
          value: "true"
        - name: OPENHQM_PARTITIONING__PARTITION_COUNT
          value: "10"
```

### Partition Assignment

With 10 partitions and 5 workers:
- Worker 0: Partitions [0, 5]
- Worker 1: Partitions [1, 6]
- Worker 2: Partitions [2, 7]
- Worker 3: Partitions [3, 8]
- Worker 4: Partitions [4, 9]

### Session Statistics

Get session stats (available via metrics or logs):

```python
stats = processor.get_partition_stats()
# {
#   "active_sessions": 42,
#   "assigned_partitions": 2,
#   "partition_ids": [0, 5],
#   "total_messages": 1250
# }
```

## Combined Usage

### Routing + Partitioning

Route messages based on type, then ensure session affinity:

```yaml
# routing.yaml
routes:
  - name: legacy-app
    match_field: "metadata.type"
    match_value: "legacy.request"
    endpoint: "legacy-service"
    transform_type: "passthrough"
    header_mappings:
      X-Session-ID: "metadata.session_id"
```

```bash
# Environment config
OPENHQM_ROUTING__ENABLED=true
OPENHQM_ROUTING__CONFIG_PATH=/etc/openhqm/routing.yaml
OPENHQM_PARTITIONING__ENABLED=true
OPENHQM_PARTITIONING__PARTITION_KEY_FIELD=metadata.session_id
```

Message format:

```json
{
  "correlation_id": "req-123",
  "payload": {
    "action": "get_cart",
    "user_id": "user-456"
  },
  "metadata": {
    "type": "legacy.request",
    "session_id": "sess-789"
  }
}
```

**Flow:**
1. Routing engine matches `legacy.request` type
2. Transforms to legacy format (passthrough in this case)
3. Maps `session_id` to `X-Session-ID` header
4. Partitioning ensures same worker handles all `sess-789` messages
5. Worker forwards to legacy-service with session affinity

## Use Cases

### 1. Multi-Tenant SaaS

```yaml
routes:
  - name: tenant-a
    match_field: "metadata.tenant_id"
    match_value: "tenant-a"
    endpoint: "tenant-a-service"
    transform_type: "jq"
    transform: |
      {
        "tenant": "tenant-a",
        "data": .payload
      }
```

### 2. Legacy Application Modernization

```yaml
routes:
  - name: legacy-stateful
    match_field: "metadata.type"
    match_value: "legacy"
    endpoint: "legacy-app"
    transform_type: "template"
    transform: |
      {
        "session_id": "{{metadata.session_id}}",
        "user_id": "{{payload.user}}",
        "action": "{{payload.action}}",
        "data": "{{payload.data}}"
      }
```

With partitioning:
```bash
OPENHQM_PARTITIONING__ENABLED=true
OPENHQM_PARTITIONING__PARTITION_KEY_FIELD=metadata.session_id
OPENHQM_PARTITIONING__STICKY_SESSION_TTL=1800
```

### 3. API Versioning

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
        "data": .payload
      }
  
  - name: api-v1
    match_field: "metadata.api_version"
    match_value: "v1"
    endpoint: "api-v1-service"
    transform_type: "passthrough"
```

## Dependencies

Install required packages:

```bash
pip install pyjq jsonpath-ng pyyaml
```

Or use specific queue images:
```bash
docker pull openhqm:latest  # Includes all dependencies
```

## Monitoring

Routing and partitioning metrics are logged:

```
{
  "event": "Message routed",
  "route_name": "user-registration",
  "endpoint": "user-service",
  "partition_id": 3,
  "worker_id": "worker-1"
}
```

## Configuration Reference

See:
- [routing-config.yaml](../examples/routing-config.yaml) - Full routing example
- [k8s-routing-configmap.yaml](../examples/k8s-routing-configmap.yaml) - Kubernetes deployment

## Troubleshooting

### Route Not Matching

Check match criteria:
```bash
# Enable debug logging
OPENHQM_MONITORING__LOG_LEVEL=DEBUG
```

### Transform Errors

Validate JQ expressions:
```bash
echo '{"payload":{"user":"test"}}' | jq '.payload.user'
```

### Partition Assignment

Check worker partition stats:
```python
stats = processor.get_partition_stats()
print(stats)
```

### Session Not Sticky

Verify partition key is present:
```json
{
  "metadata": {
    "session_id": "must-be-present-and-consistent"
  }
}
```
