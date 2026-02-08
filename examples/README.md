# OpenHQM Examples

This directory contains configuration examples and usage patterns for OpenHQM.

## 🎯 Quick Navigation

| File | Description | Use With |
|------|-------------|----------|
| [routing-config.yaml](routing-config.yaml) | Production-ready routing rules | Workers, Sidecar |
| [k8s-routing-configmap.yaml](k8s-routing-configmap.yaml) | Kubernetes ConfigMap deployment | K8s StatefulSet |
| [proxy_example.py](proxy_example.py) | Python client example | API Integration |
| [complete_workflow_example.py](complete_workflow_example.py) | End-to-end workflow demo | Testing, Learning |
| [validate_routing_config.py](validate_routing_config.py) | Config validation script | CI/CD, Pre-deployment |
| [configs/](configs/) | Configuration file examples | All modes |
| [kubernetes/](kubernetes/) | K8s deployment patterns | Production deployment |

## 🔗 Related Tools

**[OpenHQM Router Manager](../../openhqm-rm/)** - Visual web UI for creating and testing routing rules
- Import these examples directly into the Router Manager
- Test transformations in the JQ Playground
- Simulate routing with sample payloads
- Export validated ConfigMaps back to OpenHQM

## Files

### Routing Configuration

- **[routing-config.yaml](routing-config.yaml)** - Comprehensive routing configuration example
  - Multiple transform types (JQ, JSONPath, Template, Passthrough)
  - Field-based and pattern-based matching
  - Header and query parameter mappings
  - Priority-based route selection
  - Default route fallback
  - **✅ Validated by Router Manager E2E tests**

### Python Examples

- **[proxy_example.py](proxy_example.py)** - Client library example
  - Submit requests to OpenHQM
  - Poll for status and results
  - Handle async processing patterns
  - Error handling and retries

- **[complete_workflow_example.py](complete_workflow_example.py)** - Complete workflow demonstration
  - 7 end-to-end scenarios covering all features
  - User registration, order processing, notifications
  - Analytics tracking, legacy integration, payments
  - Default route handling
  - **▶️ Run this to see OpenHQM in action**

- **[validate_routing_config.py](validate_routing_config.py)** - Configuration validator
  - Validate YAML syntax and structure
  - Check JQ expressions, regex patterns
  - Verify required fields and types
  - Detect common configuration errors
  - **🔧 Use in CI/CD pipeline before deployment**

### Kubernetes Deployment

- **[k8s-routing-configmap.yaml](k8s-routing-configmap.yaml)** - Kubernetes deployment with routing
  - ConfigMap for routing configuration
  - StatefulSet deployment with partition support
  - Environment variable configuration
  - Volume mounts for config files
  - **✅ Deployable format for production**

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

### Validate Configuration

Before deploying, validate your routing configuration:

```bash
# Validate routing config
python3 examples/validate_routing_config.py examples/routing-config.yaml

# Validate Kubernetes ConfigMap
python3 examples/validate_routing_config.py examples/k8s-routing-configmap.yaml

# Expected output:
# 🔍 Validating: examples/routing-config.yaml
# 📋 Extracting routing config from ConfigMap
# ✅ Configuration is valid!
```

### Run Complete Workflow Demo

Test all routing scenarios with the complete workflow example:

```bash
# 1. Start OpenHQM with routing enabled
OPENHQM_ROUTING__ENABLED=true \
OPENHQM_ROUTING__CONFIG_PATH=examples/routing-config.yaml \
OPENHQM_QUEUE_TYPE=redis \
OPENHQM_REDIS_URL=redis://localhost:6379 \
python3 -m openhqm.api.listener &

# 2. Start workers
python3 -m openhqm.worker.worker &

# 3. Run the complete workflow demo
python3 examples/complete_workflow_example.py

# Expected output:
# 🚀 OpenHQM Complete Workflow Demo
# ✅ OpenHQM is running
# 
# 🎬 SCENARIO 1: User Registration
# 📤 Submitting: User Registration
# ✅ Submitted successfully
# 🔑 Correlation ID: ...
# ✅ Processing completed
# 
# ... (7 scenarios total)
# 
# 📊 WORKFLOW SUMMARY
# Total Requests: 10
# ✅ Completed: 10
# ❌ Failed: 0
```

### Test Routing Locally

Test individual routes:

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
- [OpenHQM Router Manager](../../openhqm-rm/) - Visual configuration tool

## 🛠️ Working with Router Manager

The [OpenHQM Router Manager](../../openhqm-rm/) provides a visual interface for managing these configurations:

### Import Examples into Router Manager

1. **Start Router Manager:**
   ```bash
   cd ../openhqm-rm
   npm install
   npm run dev
   ```

2. **Import Configuration:**
   - Open http://localhost:5173
   - Click "Import" button
   - Paste contents of `routing-config.yaml` or `k8s-routing-configmap.yaml`
   - Routes will be validated and loaded

3. **Test Transformations:**
   - Open "JQ Playground" tab
   - Select a route's transformation
   - Test with sample payloads (see below)
   - Verify expected outputs

4. **Simulate Routing:**
   - Open "Simulator" tab
   - Submit test messages
   - See which routes match
   - View transformation results

5. **Export ConfigMap:**
   - Click "Export" button
   - Choose YAML format
   - Download Kubernetes ConfigMap
   - Deploy to your cluster

### Sample Test Payloads

Use these payloads to test routing examples:

**User Registration:**
```json
{
  "payload": {
    "email": "john.doe@example.com",
    "name": "John Doe"
  },
  "metadata": {
    "type": "user.register",
    "source": "web-app"
  },
  "correlation_id": "test-user-001"
}
```

**Order Processing:**
```json
{
  "payload": {
    "order_id": "ORD-2024-001",
    "customer": { "id": "CUST-123" },
    "items": [
      { "sku": "LAPTOP-001", "qty": 1, "unit_price": 999.99 },
      { "sku": "MOUSE-002", "qty": 2, "unit_price": 25.50 }
    ],
    "currency": "USD"
  },
  "metadata": {
    "type": "order.create"
  },
  "correlation_id": "test-order-001"
}
```

**Expected Output (Order):**
```json
{
  "order_id": "ORD-2024-001",
  "customer_id": "CUST-123",
  "items": [
    { "product_id": "LAPTOP-001", "quantity": 1, "price": 999.99 },
    { "product_id": "MOUSE-002", "quantity": 2, "price": 25.50 }
  ],
  "total": 1051.49,
  "currency": "USD"
}
```

**Notification:**
```json
{
  "payload": {
    "user": { "email": "user@example.com" },
    "subject": "Order Confirmation",
    "message": "Your order has been confirmed"
  },
  "metadata": {
    "type": "notification.email",
    "template": "order-confirmation"
  },
  "correlation_id": "test-notif-001"
}
```

**Analytics:**
```json
{
  "payload": {
    "event": {
      "type": "page_view",
      "user_id": "user-123",
      "page": "/products"
    }
  },
  "metadata": {
    "type": "analytics.track"
  },
  "correlation_id": "test-analytics-001"
}
```

**Legacy Request:**
```json
{
  "payload": {
    "action": "get_user_cart",
    "user_id": "user-456"
  },
  "metadata": {
    "type": "legacy.request",
    "session_id": "sess-abc-123",
    "user_id": "user-456"
  },
  "correlation_id": "test-legacy-001"
}
```

## ✅ Validation

All examples in this directory are automatically validated by:

1. **Router Manager E2E Tests** - Ensures examples can be imported and used
2. **OpenHQM Unit Tests** - Validates routing logic and transformations
3. **Integration Tests** - Tests end-to-end message flow

To run validation:

```bash
# Validate with Router Manager
cd ../openhqm-rm
npm test e2e/openhqm-examples.spec.ts

# Validate with OpenHQM
cd ../openhqm
pytest tests/test_routing.py -v
```

## 🚀 Production Checklist

Before deploying these examples to production:

- [ ] **Test all transformations** in Router Manager JQ Playground
- [ ] **Simulate routing** with realistic payloads
- [ ] **Validate ConfigMap** format matches OpenHQM schema
- [ ] **Set appropriate priorities** for route ordering
- [ ] **Configure timeouts** based on backend SLAs
- [ ] **Add error handling** for failed transformations
- [ ] **Enable partitioning** if session affinity needed
- [ ] **Set up monitoring** and metrics collection
- [ ] **Document custom routes** for your team
- [ ] **Test failover** to default_endpoint

## 📚 Additional Resources

- **[SDD.md](../SDD.md)** - Software Design Document
- **[ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - System architecture
- **[DEPLOYMENT_PATTERNS.md](../docs/DEPLOYMENT_PATTERNS.md)** - Deployment strategies
- **[Router Manager SDD](../../openhqm-rm/SDD.md)** - Router Manager design
