# Kubernetes Examples

Complete Kubernetes deployment examples for OpenHQM's composable patterns.

## Overview

OpenHQM provides two fundamental patterns that can be used independently:

1. **HTTP → Queue**: Accept HTTP requests and queue them for async processing
2. **Queue → HTTP**: Consume from queue and forward to HTTP endpoints

## Examples

### 1. HTTP → Queue Pattern

**File:** [`http-to-queue.yaml`](http-to-queue.yaml)

**Use Case:**
- Accept HTTP requests from clients
- Queue messages for asynchronous processing
- Workers run custom business logic (not HTTP forwarding)
- Examples: ETL pipelines, image processing, notifications, batch jobs

**Architecture:**
```
Client → Load Balancer → API Pods → Redis Queue → Worker Pods (custom logic)
```

**Key Features:**
- 3 API replicas with HPA
- 5 worker replicas with HPA (3-20 pods)
- Redis StatefulSet with persistent storage
- Network policies for security
- ServiceMonitor for Prometheus

**Deploy:**
```bash
kubectl apply -f http-to-queue.yaml

# Check status
kubectl get pods -n openhqm-http-to-queue

# Get API endpoint
kubectl get svc openhqm-api -n openhqm-http-to-queue

# Test
curl -X POST http://<EXTERNAL-IP>/api/v1/submit \
  -H "Content-Type: application/json" \
  -d '{"payload": {"operation": "process", "data": "test"}}'
```

**Scaling:**
```bash
# Scale API
kubectl scale deployment openhqm-api -n openhqm-http-to-queue --replicas=5

# Scale workers
kubectl scale deployment openhqm-workers -n openhqm-http-to-queue --replicas=10

# View HPA status
kubectl get hpa -n openhqm-http-to-queue
```

---

### 2. Queue → HTTP Pattern

**File:** [`queue-to-http.yaml`](queue-to-http.yaml)

**Use Case:**
- Consume messages from queue (fed by external systems)
- Forward messages to backend HTTP endpoints
- Handle authentication, retries, and rate limiting
- Examples: Kafka-to-REST bridge, webhook relay, API gateway

**Architecture:**
```
External System → Redis Queue → Worker Pods → Backend HTTP APIs
```

**Key Features:**
- 10 worker replicas with HPA (5-50 pods)
- Support for multiple backend endpoints
- Bearer token and API key authentication
- Configurable retry logic with exponential backoff
- PodDisruptionBudget for high availability

**Deploy:**
```bash
# 1. Update secrets with your API credentials
kubectl create secret generic backend-api-credentials \
  -n openhqm-queue-to-http \
  --from-literal=api-token='your-bearer-token' \
  --from-literal=api-key='your-api-key'

# 2. Update ConfigMap with your backend URLs
# Edit queue-to-http.yaml and update OPENHQM_PROXY__ENDPOINTS

# 3. Deploy
kubectl apply -f queue-to-http.yaml

# Check status
kubectl get pods -n openhqm-queue-to-http

# View logs
kubectl logs -f deployment/openhqm-workers -n openhqm-queue-to-http
```

**Configuration:**
The ConfigMap includes endpoint configuration in JSON format:
```json
{
  "backend-api": {
    "url": "https://api.example.com/v1/process",
    "method": "POST",
    "timeout": 300,
    "auth_type": "bearer",
    "auth_token": "${BACKEND_API_TOKEN}"
  }
}
```

**Scaling:**
```bash
# Manual scaling
kubectl scale deployment openhqm-workers -n openhqm-queue-to-http --replicas=20

# HPA automatically scales based on CPU/memory
kubectl get hpa -n openhqm-queue-to-http

# View HPA events
kubectl describe hpa openhqm-workers-hpa -n openhqm-queue-to-http
```

---

## Common Operations

### Monitoring

Both examples include Prometheus integration:

```bash
# Check metrics endpoint (HTTP→Queue pattern)
kubectl port-forward -n openhqm-http-to-queue svc/openhqm-api 8000:80
curl http://localhost:8000/metrics

# View worker logs
kubectl logs -f -l component=worker -n openhqm-http-to-queue
kubectl logs -f -l component=worker -n openhqm-queue-to-http
```

### Debugging

```bash
# Get pod details
kubectl describe pod <pod-name> -n <namespace>

# Exec into pod
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# Check Redis connection
kubectl exec -it <pod-name> -n <namespace> -- redis-cli -h redis ping

# View events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

### Resource Management

```bash
# View resource usage
kubectl top pods -n openhqm-http-to-queue
kubectl top pods -n openhqm-queue-to-http

# Update resource limits
kubectl set resources deployment openhqm-workers \
  -n openhqm-http-to-queue \
  --limits=cpu=2,memory=2Gi \
  --requests=cpu=500m,memory=512Mi
```

### Cleanup

```bash
# Delete HTTP→Queue deployment
kubectl delete namespace openhqm-http-to-queue

# Delete Queue→HTTP deployment
kubectl delete namespace openhqm-queue-to-http

# Or delete individual components
kubectl delete -f http-to-queue.yaml
kubectl delete -f queue-to-http.yaml
```

---

## Advanced Configurations

### Using Kafka Instead of Redis

Replace Redis StatefulSet with Kafka:

```yaml
# Add to ConfigMap
OPENHQM_QUEUE__TYPE: "kafka"
OPENHQM_QUEUE__KAFKA__BOOTSTRAP_SERVERS: "kafka:9092"
OPENHQM_QUEUE__KAFKA__CONSUMER_GROUP: "openhqm-workers"
OPENHQM_QUEUE__KAFKA__TOPICS: "requests"

# Use openhqm:latest-kafka image
image: openhqm:latest-kafka
```

### Multi-Region Deployment

Deploy workers in multiple regions, all consuming from same central queue:

```yaml
# Region US workers
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openhqm-workers-us
spec:
  replicas: 10
  template:
    spec:
      nodeSelector:
        topology.kubernetes.io/region: us-east-1
        
# Region EU workers
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openhqm-workers-eu
spec:
  replicas: 10
  template:
    spec:
      nodeSelector:
        topology.kubernetes.io/region: eu-west-1
```

### Custom Processing Logic

For HTTP→Queue pattern, mount custom processor:

```yaml
spec:
  containers:
  - name: worker
    image: openhqm:latest-redis
    volumeMounts:
    - name: custom-processor
      mountPath: /app/src/openhqm/worker/processor.py
      subPath: processor.py
  volumes:
  - name: custom-processor
    configMap:
      name: custom-processor-code
```

---

## Production Considerations

### High Availability

1. **Redis Cluster:**
   - Use Redis Sentinel or Redis Cluster instead of single StatefulSet
   - Or use managed Redis (AWS ElastiCache, Azure Cache, GCP Memorystore)

2. **Multiple Availability Zones:**
```yaml
spec:
  template:
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: openhqm
              topologyKey: topology.kubernetes.io/zone
```

3. **PodDisruptionBudgets:**
   - Already included in Queue→HTTP example
   - Ensures minimum replicas during updates

### Security

1. **Network Policies:**
   - Both examples include NetworkPolicy manifests
   - Restrict traffic to only required ports

2. **RBAC:**
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: openhqm-worker
  namespace: openhqm-http-to-queue
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: openhqm-worker
  namespace: openhqm-http-to-queue
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list"]
```

3. **Pod Security Standards:**
```yaml
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: worker
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: ["ALL"]
```

### Observability

1. **Logging:**
```yaml
# Fluent Bit sidecar for log forwarding
- name: fluent-bit
  image: fluent/fluent-bit:latest
  volumeMounts:
  - name: varlog
    mountPath: /var/log
```

2. **Tracing:**
```yaml
# Jaeger agent sidecar
- name: jaeger-agent
  image: jaegertracing/jaeger-agent:latest
  env:
  - name: REPORTER_GRPC_HOST_PORT
    value: jaeger-collector:14250
```

3. **Metrics:**
   - ServiceMonitor included in HTTP→Queue example
   - Export to Prometheus, visualize in Grafana

---

## Performance Tuning

### Worker Optimization

```yaml
# Increase worker concurrency
env:
- name: OPENHQM_WORKER__COUNT
  value: "20"  # Workers per pod
- name: OPENHQM_WORKER__BATCH_SIZE
  value: "10"  # Messages per batch

# Optimize resource allocation
resources:
  requests:
    cpu: 1000m
    memory: 1Gi
  limits:
    cpu: 4000m
    memory: 4Gi
```

### HPA Tuning

```yaml
# More aggressive scaling
behavior:
  scaleUp:
    stabilizationWindowSeconds: 30
    policies:
    - type: Percent
      value: 100
      periodSeconds: 30
  scaleDown:
    stabilizationWindowSeconds: 600
```

### Redis Optimization

```yaml
# Redis with optimized settings
command:
- redis-server
- --maxmemory 2gb
- --maxmemory-policy allkeys-lru
- --appendonly yes
- --tcp-backlog 511
```

---

## Support

- **Documentation**: [docs/](../../docs/)
- **Kubernetes Guide**: [docs/KUBERNETES_SIDECAR.md](../../docs/KUBERNETES_SIDECAR.md)
- **Deployment Patterns**: [docs/DEPLOYMENT_PATTERNS.md](../../docs/DEPLOYMENT_PATTERNS.md)
- **Issues**: [GitHub Issues](https://github.com/yourusername/openhqm/issues)
