# Queue Infrastructure Support

## Overview

OpenHQM supports **7 queue backends** out of the box, plus the ability to bring your own custom queue handler. All implementations follow a standardized `MessageQueueInterface` for consistent behavior across different backends.

## Supported Queue Backends

| Backend | Type | Use Case | Maturity | Dependencies |
|---------|------|----------|----------|--------------|
| **Redis Streams** | In-memory | Low latency, simple setup | ✅ Production | `redis` |
| **Apache Kafka** | Distributed | High throughput, event streaming | ✅ Production | `aiokafka` |
| **AWS SQS** | Cloud-managed | AWS ecosystem, serverless | ✅ Production | `aioboto3` |
| **Azure Event Hubs** | Cloud-managed | Azure ecosystem, Kafka-compatible | ✅ Production | `azure-eventhub` |
| **GCP Pub/Sub** | Cloud-managed | GCP ecosystem, global scale | ✅ Production | `google-cloud-pubsub` |
| **MQTT** | IoT protocol | Edge computing, IoT devices | ✅ Production | `asyncio-mqtt` |
| **Custom** | User-defined | Any queue system | ⚙️ Bring your own | None |

## Standardized Interface

All queue implementations follow the same interface:

```python
class MessageQueueInterface(ABC):
    async def connect() -> None
    async def disconnect() -> None
    async def publish(queue_name, message, priority, attributes, delay_seconds) -> str
    async def consume(queue_name, handler, batch_size, wait_time_seconds) -> None
    async def acknowledge(message_id) -> bool
    async def reject(message_id, requeue, reason) -> bool
    async def get_queue_depth(queue_name) -> int
    async def health_check() -> bool
    async def create_queue(queue_name, **kwargs) -> bool
    async def delete_queue(queue_name) -> bool
    async def purge_queue(queue_name) -> int
```

### Standardized Message Format

All queue backends use a unified message structure:

```python
@dataclass
class QueueMessage:
    id: str                          # Unique message identifier
    body: Dict[str, Any]            # Message payload
    attributes: Dict[str, str]      # Message metadata/headers
    timestamp: float                # Message timestamp
    retry_count: int                # Number of retry attempts
    raw_message: Optional[Any]      # Backend-specific raw message
```

---

## 1. Redis Streams

### Description
Redis Streams provides a lightweight, fast, in-memory queue with persistence options.

### When to Use
- **Low latency** requirements (< 5ms)
- **Simple setup** for development and testing
- **Cost-effective** for small to medium workloads
- **Single datacenter** deployments

### Configuration

```yaml
queue:
  type: redis
  redis_url: "redis://localhost:6379/0"
  request_queue_name: "openhqm-requests"
  response_queue_name: "openhqm-responses"
  dlq_name: "openhqm-dlq"
```

```bash
# Environment variables
OPENHQM_QUEUE__TYPE=redis
OPENHQM_QUEUE__REDIS_URL=redis://redis:6379/0
```

### Installation

```bash
pip install redis
```

### Features
✅ Message acknowledgment  
✅ Consumer groups  
✅ Dead letter queue  
✅ Message priorities (application level)  
✅ Queue depth monitoring  
❌ Native message delay  
❌ Multi-region replication (requires Redis Enterprise)

---

## 2. Apache Kafka

### Description
Distributed event streaming platform with high throughput and durability.

### When to Use
- **High throughput** (millions of messages/second)
- **Event sourcing** and stream processing
- **Multiple consumers** need same data
- **Long-term message retention**

### Configuration

```yaml
queue:
  type: kafka
  kafka_bootstrap_servers: "localhost:9092,localhost:9093"
  kafka_consumer_group: "openhqm-workers"
  kafka_topics:
    - "openhqm-requests"
    - "openhqm-responses"
```

```bash
# Environment variables
OPENHQM_QUEUE__TYPE=kafka
OPENHQM_QUEUE__KAFKA_BOOTSTRAP_SERVERS=kafka1:9092,kafka2:9092
OPENHQM_QUEUE__KAFKA_CONSUMER_GROUP=openhqm-workers
OPENHQM_QUEUE__KAFKA_TOPICS='["openhqm-requests"]'
```

### Installation

```bash
pip install aiokafka
```

### Features
✅ Horizontal scalability  
✅ Message ordering per partition  
✅ Long-term retention  
✅ Multiple consumers  
✅ Exactly-once semantics  
❌ Message priorities  
❌ Native message delay

---

## 3. AWS SQS

### Description
Fully managed message queuing service by AWS.

### When to Use
- **AWS ecosystem** integration
- **Serverless** architectures (Lambda)
- **Minimal operations** overhead
- **Variable workloads**

### Configuration

```yaml
queue:
  type: sqs
  sqs_region: us-east-1
  sqs_queue_url: "https://sqs.us-east-1.amazonaws.com/123456789/openhqm-requests"
```

```bash
# Environment variables
OPENHQM_QUEUE__TYPE=sqs
OPENHQM_QUEUE__SQS_REGION=us-east-1
OPENHQM_QUEUE__SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/openhqm-requests

# AWS credentials via standard AWS environment variables
AWS_ACCESS_KEY_ID=your_key_id
AWS_SECRET_ACCESS_KEY=your_secret_key
```

### Installation

```bash
pip install aioboto3 boto3
```

### Features
✅ Fully managed (no servers)  
✅ Dead letter queue support  
✅ Message delay (up to 15 minutes)  
✅ Visibility timeout  
✅ FIFO queues  
❌ Message ordering (standard SQS)  
⚠️ Higher latency (tens of milliseconds)

---

## 4. Azure Event Hubs

### Description
Fully managed event streaming service by Microsoft Azure, Kafka protocol compatible.

### When to Use
- **Azure ecosystem** integration
- **Kafka compatibility** needed
- **Event streaming** at scale
- **Real-time analytics**

### Configuration

```yaml
queue:
  type: azure_eventhubs
  azure_eventhubs_connection_string: "Endpoint=sb://..."
  azure_eventhubs_name: "openhqm"
  azure_eventhubs_consumer_group: "$Default"
  azure_eventhubs_checkpoint_store: "DefaultEndpointsProtocol=https;..."
```

```bash
# Environment variables
OPENHQM_QUEUE__TYPE=azure_eventhubs
OPENHQM_QUEUE__AZURE_EVENTHUBS_CONNECTION_STRING="Endpoint=sb://..."
OPENHQM_QUEUE__AZURE_EVENTHUBS_NAME=openhqm
OPENHQM_QUEUE__AZURE_EVENTHUBS_CONSUMER_GROUP=$Default
OPENHQM_QUEUE__AZURE_EVENTHUBS_CHECKPOINT_STORE="DefaultEndpointsProtocol=https;..."
```

### Installation

```bash
pip install azure-eventhub azure-eventhub-checkpointstoreblob-aio
```

### Features
✅ Kafka protocol compatible  
✅ Auto-inflate throughput  
✅ Capture to Azure Blob/Data Lake  
✅ Checkpointing (via Blob Storage)  
✅ Partitioned architecture  
❌ Message priorities  
❌ Native dead letter queue

---

## 5. GCP Pub/Sub

### Description
Fully managed messaging service by Google Cloud Platform.

### When to Use
- **GCP ecosystem** integration
- **Global distribution**
- **Push and pull delivery**
- **At-least-once delivery**

### Configuration

```yaml
queue:
  type: gcp_pubsub
  gcp_project_id: "my-gcp-project"
  gcp_credentials_path: "/path/to/service-account.json"
  gcp_max_messages: 10
```

```bash
# Environment variables
OPENHQM_QUEUE__TYPE=gcp_pubsub
OPENHQM_QUEUE__GCP_PROJECT_ID=my-gcp-project
OPENHQM_QUEUE__GCP_CREDENTIALS_PATH=/path/to/service-account.json
OPENHQM_QUEUE__GCP_MAX_MESSAGES=10

# Or use default credentials
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### Installation

```bash
pip install google-cloud-pubsub
```

### Features
✅ Global distribution  
✅ Push and pull subscriptions  
✅ Dead letter topics  
✅ Message filtering  
✅ Replay/seek capabilities  
✅ Exactly-once delivery (preview)  
❌ Message priorities  
❌ Native message ordering (except with ordering keys)

---

## 6. MQTT

### Description
Lightweight publish/subscribe messaging protocol for IoT and edge computing.

### When to Use
- **IoT devices** and sensors
- **Edge computing** scenarios
- **Low bandwidth** environments
- **Resource-constrained** devices

### Configuration

```yaml
queue:
  type: mqtt
  mqtt_broker_host: "mqtt.example.com"
  mqtt_broker_port: 1883
  mqtt_username: "openhqm"
  mqtt_password: "secret"
  mqtt_qos: 1  # 0, 1, or 2
  mqtt_client_id: "openhqm-worker-1"
```

```bash
# Environment variables
OPENHQM_QUEUE__TYPE=mqtt
OPENHQM_QUEUE__MQTT_BROKER_HOST=mqtt.example.com
OPENHQM_QUEUE__MQTT_BROKER_PORT=1883
OPENHQM_QUEUE__MQTT_USERNAME=openhqm
OPENHQM_QUEUE__MQTT_PASSWORD=secret
OPENHQM_QUEUE__MQTT_QOS=1
```

### Installation

```bash
pip install asyncio-mqtt
```

### Features
✅ Lightweight protocol  
✅ QoS levels (0, 1, 2)  
✅ Retained messages  
✅ Last Will and Testament  
✅ Low overhead  
❌ No built-in message persistence (broker-dependent)  
❌ Limited scalability compared to enterprise queues  
⚠️ No native acknowledgment (uses QoS)

---

## 7. Custom Queue Handler

### Description
Bring your own queue implementation by implementing the `MessageQueueInterface`.

### When to Use
- **Proprietary queue system**
- **Legacy queue integration**
- **Custom requirements**
- **Unsupported queue backend**

### Implementation

1. **Create your queue handler**:

```python
# mycompany/queues/custom_handler.py
from openhqm.queue.interface import MessageQueueInterface, QueueMessage

class MyCustomQueue(MessageQueueInterface):
    def __init__(self, connection_string: str, option1: str):
        self.connection_string = connection_string
        self.option1 = option1
        self.client = None
    
    async def connect(self) -> None:
        # Connect to your queue
        self.client = await my_queue_library.connect(self.connection_string)
    
    async def publish(self, queue_name, message, priority=0, attributes=None, delay_seconds=0):
        # Publish message
        message_id = await self.client.send(queue_name, message)
        return message_id
    
    # Implement other methods...
```

2. **Configure OpenHQM**:

```yaml
queue:
  type: custom
  custom_module: "mycompany.queues.custom_handler"
  custom_class: "MyCustomQueue"
  custom_config:
    connection_string: "myqueue://localhost:5672"
    option1: "value1"
    option2: "value2"
```

```bash
# Environment variables
OPENHQM_QUEUE__TYPE=custom
OPENHQM_QUEUE__CUSTOM_MODULE=mycompany.queues.custom_handler
OPENHQM_QUEUE__CUSTOM_CLASS=MyCustomQueue
OPENHQM_QUEUE__CUSTOM_CONFIG='{"connection_string": "...", "option1": "value1"}'
```

### Template

See [src/openhqm/queue/custom.py](src/openhqm/queue/custom.py) for a complete template.

---

## Queue Selection Guide

### Decision Matrix

| Requirement | Recommended Queue |
|-------------|-------------------|
| Lowest latency | Redis Streams |
| Highest throughput | Apache Kafka |
| AWS-native | AWS SQS |
| Azure-native | Azure Event Hubs |
| GCP-native | GCP Pub/Sub |
| IoT/Edge | MQTT |
| Cost-effective (small scale) | Redis Streams |
| Cost-effective (large scale) | Cloud-managed (SQS/Pub/Sub/Event Hubs) |
| Event sourcing | Apache Kafka |
| Serverless | AWS SQS or GCP Pub/Sub |
| Multi-cloud | Apache Kafka or MQTT |
| Custom/Legacy | Custom Handler |

### Performance Comparison

| Queue | Latency | Throughput | Durability | Scalability |
|-------|---------|------------|------------|-------------|
| Redis | < 5ms | High (100k+ msg/s) | Medium | Vertical |
| Kafka | 5-10ms | Very High (millions/s) | High | Horizontal |
| SQS | 20-50ms | Medium (thousands/s) | High | Automatic |
| Event Hubs | 10-30ms | Very High (millions/s) | High | Automatic |
| Pub/Sub | 20-100ms | High (millions/s) | High | Automatic |
| MQTT | < 10ms | Medium (depends on broker) | Low-Medium | Broker-dependent |

---

## Migration Between Queue Backends

OpenHQM's standardized interface makes it easy to migrate between queue backends:

### Step 1: Update Configuration

```yaml
# From Redis
queue:
  type: redis
  redis_url: "redis://localhost:6379"

# To Kafka
queue:
  type: kafka
  kafka_bootstrap_servers: "kafka:9092"
  kafka_consumer_group: "openhqm-workers"
```

### Step 2: Install New Dependencies

```bash
pip install aiokafka
```

### Step 3: Restart Services

```bash
# Restart API and workers
docker-compose restart
```

No code changes required! ✨

---

## Best Practices

### 1. Environment-Specific Queues
- **Development**: Redis Streams (easy setup)
- **Staging**: Same as production
- **Production**: Cloud-managed or Kafka (reliability)

### 2. Queue Naming Conventions
```
{environment}-{service}-{queue-type}
prod-openhqm-requests
staging-openhqm-responses
```

### 3. Monitoring
- Track queue depth metrics
- Set up alerts for queue growth
- Monitor processing latency
- Track dead letter queue size

### 4. Error Handling
- Use dead letter queues for failed messages
- Implement exponential backoff for retries
- Log correlation IDs for traceability

### 5. Security
- Use TLS/SSL for queue connections
- Rotate credentials regularly
- Use IAM roles (AWS/Azure/GCP) instead of static credentials
- Encrypt sensitive message payloads

---

## Dependencies

Add required dependencies to your `requirements.txt`:

```txt
# Core (always required)
redis>=4.5.0
structlog>=23.1.0

# Queue backends (install as needed)
aiokafka>=0.8.0              # Apache Kafka
aioboto3>=11.0.0             # AWS SQS
azure-eventhub>=5.11.0       # Azure Event Hubs
azure-eventhub-checkpointstoreblob-aio>=1.1.0  # Event Hubs checkpointing
google-cloud-pubsub>=2.18.0  # GCP Pub/Sub
asyncio-mqtt>=0.16.0         # MQTT
```

### Optional Dependencies

Create `requirements-optional.txt`:

```txt
# All queue backends
aiokafka>=0.8.0
aioboto3>=11.0.0
azure-eventhub>=5.11.0
azure-eventhub-checkpointstoreblob-aio>=1.1.0
google-cloud-pubsub>=2.18.0
asyncio-mqtt>=0.16.0
```

Install with:
```bash
pip install -r requirements.txt
pip install -r requirements-optional.txt  # Only if needed
```

---

## Troubleshooting

### Connection Issues

**Redis**:
```bash
# Test connection
redis-cli -h localhost -p 6379 ping
```

**Kafka**:
```bash
# Check broker connectivity
kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

**MQTT**:
```bash
# Test MQTT connection
mosquitto_sub -h localhost -p 1883 -t test
```

### Queue Depth Growing

1. Check worker health
2. Verify processing timeouts
3. Scale up worker count
4. Check for errors in logs

### Message Loss

1. Verify acknowledgment logic
2. Check dead letter queue
3. Review error logs
4. Ensure proper exception handling

---

## Examples

See the [examples/queue-backends/](examples/queue-backends/) directory for complete examples of each queue backend configuration.

---

## Contributing

To add a new queue backend:

1. Implement `MessageQueueInterface`
2. Add to `queue/factory.py` registration
3. Update documentation
4. Add tests
5. Submit PR

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.
