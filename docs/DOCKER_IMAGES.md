# Docker Image Variants

## Overview

OpenHQM provides **8 optimized Docker image variants** to minimize image size and dependencies. Each variant includes only the dependencies needed for specific queue backends.

## Available Variants

### 1. Full Build (All Backends) - `openhqm:latest`

**Includes:** All queue backends (Redis, Kafka, SQS, Event Hubs, Pub/Sub, MQTT)

```bash
docker pull ghcr.io/yourusername/openhqm:latest
# or
docker pull ghcr.io/yourusername/openhqm:1.0.0
```

**Use when:**
- Multi-cloud deployments
- Need flexibility to switch backends
- Development/testing multiple backends
- Uncertain which queue backend to use

**Size:** ~500MB (estimated)

---

### 2. Redis Streams - `openhqm:latest-redis`

**Includes:** Redis Streams support only

```bash
docker pull ghcr.io/yourusername/openhqm:latest-redis
# or
docker build --build-arg QUEUE_BACKEND=redis -t openhqm:redis .
```

**Use when:**
- Development environments
- Low-latency requirements (< 5ms)
- Simple deployment needs
- Cost-conscious small deployments

**Size:** ~200MB (estimated)  
**Savings:** ~60% smaller than full build

---

### 3. Apache Kafka - `openhqm:latest-kafka`

**Includes:** Kafka support only

```bash
docker pull ghcr.io/yourusername/openhqm:latest-kafka
# or
docker build --build-arg QUEUE_BACKEND=kafka -t openhqm:kafka .
```

**Use when:**
- High-throughput workloads (millions msg/s)
- Event streaming architectures
- On-premise Kafka clusters
- Multi-consumer patterns

**Size:** ~250MB (estimated)  
**Savings:** ~50% smaller than full build

---

### 4. AWS SQS - `openhqm:latest-sqs`

**Includes:** AWS SQS support only

```bash
docker pull ghcr.io/yourusername/openhqm:latest-sqs
# or
docker build --build-arg QUEUE_BACKEND=sqs -t openhqm:sqs .
```

**Use when:**
- AWS ECS/EKS deployments
- Serverless architectures (AWS Lambda)
- AWS-native applications
- Simple managed queue needs

**Size:** ~230MB (estimated)  
**Savings:** ~54% smaller than full build

**Example Kubernetes deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openhqm
spec:
  template:
    spec:
      containers:
      - name: openhqm
        image: ghcr.io/yourusername/openhqm:latest-sqs
        env:
        - name: OPENHQM_QUEUE__TYPE
          value: sqs
        - name: OPENHQM_QUEUE__SQS_REGION
          value: us-east-1
```

---

### 5. Azure Event Hubs - `openhqm:latest-azure`

**Includes:** Azure Event Hubs support only

```bash
docker pull ghcr.io/yourusername/openhqm:latest-azure
# or
docker build --build-arg QUEUE_BACKEND=azure -t openhqm:azure .
```

**Use when:**
- Azure AKS deployments
- Azure-native applications
- Kafka protocol compatibility needed
- Event capture to Azure Blob Storage

**Size:** ~280MB (estimated)  
**Savings:** ~44% smaller than full build

---

### 6. GCP Pub/Sub - `openhqm:latest-gcp`

**Includes:** GCP Pub/Sub support only

```bash
docker pull ghcr.io/yourusername/openhqm:latest-gcp
# or
docker build --build-arg QUEUE_BACKEND=gcp -t openhqm:gcp .
```

**Use when:**
- GCP GKE deployments
- GCP-native applications
- Global distribution needs
- Push/pull subscription models

**Size:** ~270MB (estimated)  
**Savings:** ~46% smaller than full build

---

### 7. MQTT - `openhqm:latest-mqtt`

**Includes:** MQTT support only

```bash
docker pull ghcr.io/yourusername/openhqm:latest-mqtt
# or
docker build --build-arg QUEUE_BACKEND=mqtt -t openhqm:mqtt .
```

**Use when:**
- IoT device integration
- Edge computing scenarios
- Low bandwidth environments
- Resource-constrained deployments

**Size:** ~210MB (estimated)  
**Savings:** ~58% smaller than full build

---

### 8. Minimal - `openhqm:latest-minimal`

**Includes:** Core OpenHQM only, no queue dependencies

```bash
docker pull ghcr.io/yourusername/openhqm:latest-minimal
# or
docker build --build-arg QUEUE_BACKEND=minimal -t openhqm:minimal .
```

**Use when:**
- Custom queue handler implementations
- Bring your own queue backend
- Maximum security (minimal dependencies)
- Smallest possible image size

**Size:** ~180MB (estimated)  
**Savings:** ~64% smaller than full build

**Example with custom handler:**
```dockerfile
FROM ghcr.io/yourusername/openhqm:latest-minimal

# Install your custom queue dependencies
RUN pip install --no-cache-dir my-queue-library==1.0.0

# Copy your custom handler
COPY my_custom_queue.py /app/src/mycompany/
```

---

## Comparison Matrix

| Variant | Size | Latency | Throughput | Cloud | Use Case |
|---------|------|---------|------------|-------|----------|
| **Full** | ~500MB | Varies | Varies | All | Multi-cloud, development |
| **Redis** | ~200MB | < 5ms | 100k+ msg/s | Any | Low latency, simple |
| **Kafka** | ~250MB | 5-10ms | Millions/s | Any | High throughput, streaming |
| **SQS** | ~230MB | 20-50ms | Thousands/s | AWS | Serverless, managed |
| **Azure** | ~280MB | 10-30ms | Millions/s | Azure | Azure-native |
| **GCP** | ~270MB | 20-100ms | Millions/s | GCP | GCP-native |
| **MQTT** | ~210MB | < 10ms | Varies | Any | IoT, edge |
| **Minimal** | ~180MB | N/A | N/A | Any | Custom handlers |

---

## Building Locally

Build any variant locally:

```bash
# Build all variants
docker build --build-arg QUEUE_BACKEND=all -t openhqm:all .

# Build specific variant
docker build --build-arg QUEUE_BACKEND=redis -t openhqm:redis .
docker build --build-arg QUEUE_BACKEND=kafka -t openhqm:kafka .
docker build --build-arg QUEUE_BACKEND=sqs -t openhqm:sqs .
docker build --build-arg QUEUE_BACKEND=azure -t openhqm:azure .
docker build --build-arg QUEUE_BACKEND=gcp -t openhqm:gcp .
docker build --build-arg QUEUE_BACKEND=mqtt -t openhqm:mqtt .
docker build --build-arg QUEUE_BACKEND=minimal -t openhqm:minimal .
```

---

## Docker Compose Examples

### AWS Deployment with SQS

```yaml
version: '3.8'

services:
  openhqm:
    image: ghcr.io/yourusername/openhqm:latest-sqs
    environment:
      OPENHQM_QUEUE__TYPE: sqs
      OPENHQM_QUEUE__SQS_REGION: us-east-1
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
    ports:
      - "8000:8000"
```

### Development with Redis

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  openhqm:
    image: ghcr.io/yourusername/openhqm:latest-redis
    environment:
      OPENHQM_QUEUE__TYPE: redis
      OPENHQM_QUEUE__REDIS_URL: redis://redis:6379
    ports:
      - "8000:8000"
    depends_on:
      - redis
```

### IoT with MQTT

```yaml
version: '3.8'

services:
  mqtt:
    image: eclipse-mosquitto:latest
    ports:
      - "1883:1883"
  
  openhqm:
    image: ghcr.io/yourusername/openhqm:latest-mqtt
    environment:
      OPENHQM_QUEUE__TYPE: mqtt
      OPENHQM_QUEUE__MQTT_BROKER_HOST: mqtt
      OPENHQM_QUEUE__MQTT_BROKER_PORT: 1883
    ports:
      - "8000:8000"
    depends_on:
      - mqtt
```

---

## Kubernetes Examples

### AWS EKS with SQS Image

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openhqm
spec:
  replicas: 3
  selector:
    matchLabels:
      app: openhqm
  template:
    metadata:
      labels:
        app: openhqm
    spec:
      containers:
      - name: openhqm
        image: ghcr.io/yourusername/openhqm:1.0.0-sqs
        env:
        - name: OPENHQM_QUEUE__TYPE
          value: "sqs"
        - name: OPENHQM_QUEUE__SQS_REGION
          value: "us-east-1"
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### Azure AKS with Event Hubs Image

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openhqm
spec:
  replicas: 3
  selector:
    matchLabels:
      app: openhqm
  template:
    metadata:
      labels:
        app: openhqm
    spec:
      containers:
      - name: openhqm
        image: ghcr.io/yourusername/openhqm:1.0.0-azure
        env:
        - name: OPENHQM_QUEUE__TYPE
          value: "azure_eventhubs"
        - name: OPENHQM_QUEUE__AZURE_EVENTHUBS_CONNECTION_STRING
          valueFrom:
            secretKeyRef:
              name: eventhubs-secret
              key: connection-string
        ports:
        - containerPort: 8000
```

---

## Image Verification

Verify the queue backend included in an image:

```bash
# Check image label
docker inspect ghcr.io/yourusername/openhqm:latest-sqs | \
  jq -r '.[].Config.Labels."queue.backend"'
# Output: sqs

# Check installed packages
docker run --rm ghcr.io/yourusername/openhqm:latest-sqs pip list | grep boto
# Should show aioboto3 and boto3 for SQS image

# Check environment variable
docker run --rm ghcr.io/yourusername/openhqm:latest-sqs printenv | grep QUEUE_BACKEND
# Output: OPENHQM_QUEUE_BACKEND=sqs
```

---

## Multi-Architecture Support

All image variants support multiple architectures:

- **linux/amd64** (x86_64) - Intel/AMD processors
- **linux/arm64** (ARM64) - ARM processors, Apple Silicon

Docker automatically pulls the correct architecture for your platform.

---

## Security Considerations

All images:
- ✅ Run as non-root user (`openhqm:1000`)
- ✅ Multi-stage builds for minimal attack surface
- ✅ Only required dependencies installed
- ✅ No build tools in final image
- ✅ Regular security scans via Dependabot
- ✅ Minimal base image (python:3.11-slim)

**Security benefits of queue-specific images:**
- Smaller attack surface (fewer dependencies)
- Faster security patching (fewer packages to update)
- Reduced vulnerability exposure
- Compliance-friendly (only necessary components)

---

## CI/CD Integration

The CI pipeline automatically builds all 8 variants on every push:

```yaml
# .github/workflows/ci.yml
strategy:
  matrix:
    queue_backend:
      - name: all
      - name: redis
      - name: kafka
      - name: sqs
      - name: azure
      - name: gcp
      - name: mqtt
      - name: minimal
```

Each variant is:
- Built with appropriate dependencies
- Tagged with suffix (e.g., `-sqs`, `-kafka`)
- Cached independently for faster builds
- Size-analyzed and reported

---

## Best Practices

### 1. Use Queue-Specific Images in Production

❌ **Don't:**
```yaml
image: openhqm:latest  # Full build with all backends
```

✅ **Do:**
```yaml
image: openhqm:latest-sqs  # Only SQS dependencies
```

### 2. Match Cloud Provider

- **AWS** → Use `-sqs` image
- **Azure** → Use `-azure` image
- **GCP** → Use `-gcp` image
- **Multi-cloud** → Use full build

### 3. Development vs Production

- **Development:** Full build or Redis image
- **Staging:** Queue-specific image (match production)
- **Production:** Queue-specific image

### 4. Security Scanning

Scan images before deployment:

```bash
# Trivy scan
trivy image ghcr.io/yourusername/openhqm:latest-sqs

# Grype scan
grype ghcr.io/yourusername/openhqm:latest-sqs
```

### 5. Version Pinning

Always pin to specific versions in production:

```yaml
# ❌ Don't use latest in production
image: openhqm:latest-sqs

# ✅ Pin to specific version
image: openhqm:1.0.0-sqs
```

---

## FAQ

**Q: Can I install multiple queue backends in one image?**  
A: Not directly with the provided variants. Use the full build or create a custom Dockerfile.

**Q: How much space do I save with queue-specific images?**  
A: Typically 40-60% smaller than the full build, depending on the variant.

**Q: Can I use the minimal image with any queue?**  
A: Only with custom queue handlers. You'll need to install dependencies yourself.

**Q: Are all variants tested in CI?**  
A: Yes, all 8 variants are built and tested on every commit.

**Q: How do I know which dependencies are in each image?**  
A: Check the `requirements-queue-*.txt` files in the repository.

**Q: Can I build custom combinations?**  
A: Yes, modify the Dockerfile and install multiple requirements files.

---

## Support

For issues or questions about Docker images:
- 📖 [Documentation](../README.md)
- 🐛 [Issue Tracker](https://github.com/yourusername/openhqm/issues)
- 💬 [Discussions](https://github.com/yourusername/openhqm/discussions)
