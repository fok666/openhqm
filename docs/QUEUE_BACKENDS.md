# Queue backends

OpenHQM ships six adapters plus a bring-your-own option. Select one with
`OPENHQM_QUEUE__TYPE`; install its dependencies with the matching pyproject
extra (or the Docker `QUEUE_BACKEND` build arg — same names).

| `type` | Extra | Delivery guarantee |
| --- | --- | --- |
| `redis` (default) | *(none — core)* | at-least-once (consumer group, ack on success) |
| `kafka` | `kafka` | at-least-once (manual commit after success) |
| `sqs` | `sqs` | at-least-once (delete after success, visibility timeout) |
| `azure_eventhubs` | `azure` | at-least-once with checkpoint store, else per-session |
| `gcp_pubsub` | `gcp` | at-least-once (ack after success) |
| `mqtt` | `mqtt` | broker QoS only — no app-level ack |
| `custom` | — | whatever your class does |

Two queue names are used everywhere, regardless of backend:

```bash
OPENHQM_QUEUE__REQUEST_QUEUE_NAME=openhqm-requests   # requests flow here
OPENHQM_QUEUE__DLQ_NAME=openhqm-dlq                  # exhausted retries land here
```

## The contract

Every adapter implements four methods (`src/openhqm/queue/base.py`):

```python
class Queue(ABC):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def publish(self, queue_name: str, message: dict) -> None: ...   # raises QueueError
    async def consume(self, queue_name: str, handler, batch_size: int = 10) -> None: ...
```

`consume` runs until cancelled and awaits `handler(message: dict)` per message.
Acknowledgment is internal to each adapter: ack after the handler returns, leave
the message for redelivery when it raises.

## Per-backend settings

Defaults shown; all optional unless noted.

### redis — Redis Streams

```bash
OPENHQM_QUEUE__REDIS_URL=redis://localhost:6379
```

### kafka — Apache Kafka

```bash
OPENHQM_QUEUE__KAFKA_BOOTSTRAP_SERVERS=localhost:9092   # comma-separated
OPENHQM_QUEUE__KAFKA_CONSUMER_GROUP=openhqm-workers
```

### sqs — AWS SQS

Credentials come from the standard AWS chain (env vars, IAM role, profile).
Queues are resolved by name; set the URL to skip the lookup for the request queue.

```bash
OPENHQM_QUEUE__SQS_REGION=us-east-1
OPENHQM_QUEUE__SQS_QUEUE_URL=            # optional
```

### azure_eventhubs — Azure Event Hubs

Event hubs named after `request_queue_name` and `dlq_name` must exist in the
namespace. Configure a Blob Storage checkpoint store or consumption restarts
from the beginning after a restart.

```bash
OPENHQM_QUEUE__AZURE_EVENTHUBS_CONNECTION_STRING=   # required (namespace-level)
OPENHQM_QUEUE__AZURE_EVENTHUBS_CONSUMER_GROUP=$Default
OPENHQM_QUEUE__AZURE_EVENTHUBS_CHECKPOINT_STORE=    # Blob Storage connection string
```

### gcp_pubsub — GCP Pub/Sub

Create a topic *and* a subscription with the same name as the queue name
(publish targets the topic, consume pulls the subscription).

```bash
OPENHQM_QUEUE__GCP_PROJECT_ID=            # required
OPENHQM_QUEUE__GCP_CREDENTIALS_PATH=      # empty = application default credentials
```

### mqtt — MQTT

```bash
OPENHQM_QUEUE__MQTT_BROKER_HOST=localhost
OPENHQM_QUEUE__MQTT_BROKER_PORT=1883
OPENHQM_QUEUE__MQTT_USERNAME=
OPENHQM_QUEUE__MQTT_PASSWORD=
OPENHQM_QUEUE__MQTT_QOS=1                 # 0, 1, or 2
OPENHQM_QUEUE__MQTT_CLIENT_ID=            # auto-generated if empty
```

## Bring your own backend

Implement the four methods, ship the module on the PYTHONPATH, point OpenHQM
at it. No OpenHQM code changes needed.

```python
# mycompany/queues.py
class MyQueue:
    def __init__(self, url: str):        # kwargs come from CUSTOM_CONFIG
        self.url = url

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def publish(self, queue_name, message) -> None: ...
    async def consume(self, queue_name, handler, batch_size=10) -> None:
        while True:
            for message in await self._fetch(queue_name, batch_size):
                await handler(message.body)   # ack only if this doesn't raise
                await self._ack(message)
```

```bash
OPENHQM_QUEUE__TYPE=custom
OPENHQM_QUEUE__CUSTOM_MODULE=mycompany.queues
OPENHQM_QUEUE__CUSTOM_CLASS=MyQueue
OPENHQM_QUEUE__CUSTOM_CONFIG='{"url": "myqueue://host:5672"}'
```

To make a backend built-in instead: add the adapter under `src/openhqm/queue/`,
one line to `_ADAPTERS` in `queue/base.py`, its settings to `QueueSettings` in
`config.py`, and a pyproject extra.
