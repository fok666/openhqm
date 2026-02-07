"""Factory for creating message queue instances."""

import structlog

from openhqm.config import settings
from openhqm.exceptions import QueueError
from openhqm.queue.interface import MessageQueueFactory, MessageQueueInterface

logger = structlog.get_logger(__name__)


def register_all_queues():
    """Register all available queue implementations."""

    # Redis Streams
    try:
        from openhqm.queue.redis_queue import RedisQueue

        MessageQueueFactory.register("redis", RedisQueue)
        logger.debug("Registered Redis queue")
    except ImportError as e:
        logger.warning("Redis queue not available", error=str(e))

    # Apache Kafka
    try:
        from openhqm.queue.kafka_queue import KafkaQueue

        MessageQueueFactory.register("kafka", KafkaQueue)
        logger.debug("Registered Kafka queue")
    except ImportError as e:
        logger.warning("Kafka queue not available", error=str(e))

    # AWS SQS
    try:
        from openhqm.queue.sqs_queue import SQSQueue

        MessageQueueFactory.register("sqs", SQSQueue)
        logger.debug("Registered SQS queue")
    except ImportError as e:
        logger.warning("SQS queue not available", error=str(e))

    # Azure Event Hubs
    try:
        from openhqm.queue.azure_eventhubs import AzureEventHubsQueue

        MessageQueueFactory.register("azure_eventhubs", AzureEventHubsQueue)
        logger.debug("Registered Azure Event Hubs queue")
    except ImportError as e:
        logger.warning("Azure Event Hubs queue not available", error=str(e))

    # GCP Pub/Sub
    try:
        from openhqm.queue.gcp_pubsub import GCPPubSubQueue

        MessageQueueFactory.register("gcp_pubsub", GCPPubSubQueue)
        logger.debug("Registered GCP Pub/Sub queue")
    except ImportError as e:
        logger.warning("GCP Pub/Sub queue not available", error=str(e))

    # MQTT
    try:
        from openhqm.queue.mqtt import MQTTQueue

        MessageQueueFactory.register("mqtt", MQTTQueue)
        logger.debug("Registered MQTT queue")
    except ImportError as e:
        logger.warning("MQTT queue not available", error=str(e))


async def create_queue() -> MessageQueueInterface:
    """
    Create and connect message queue instance based on configuration.

    This is the main entry point for creating queues in OpenHQM.
    Supports: Redis, Kafka, SQS, Azure Event Hubs, GCP Pub/Sub, MQTT, and Custom handlers.

    Returns:
        Connected message queue instance

    Raises:
        QueueError: If queue type is not supported or connection fails
    """
    queue_type = settings.queue.type.lower()

    logger.info("Creating queue", type=queue_type)

    # Handle custom queue handler
    if queue_type == "custom":
        from openhqm.queue.custom import CustomQueueHandler

        if not settings.queue.custom_module or not settings.queue.custom_class:
            raise QueueError(
                "Custom queue handler requires 'custom_module' and 'custom_class' configuration"
            )

        queue = CustomQueueHandler.load_custom_queue(
            module_path=settings.queue.custom_module,
            class_name=settings.queue.custom_class,
            config=settings.queue.custom_config,
        )
        await queue.connect()
        return queue

    # Register all available queues
    register_all_queues()

    # Map queue type to configuration
    queue_configs = {
        "redis": {
            "url": settings.queue.redis_url,
            "max_connections": settings.cache.max_connections,
        },
        "kafka": {
            "bootstrap_servers": settings.queue.kafka_bootstrap_servers.split(","),
            "consumer_group": settings.queue.kafka_consumer_group,
            "topics": settings.queue.kafka_topics,
        },
        "sqs": {
            "region_name": settings.queue.sqs_region,
            "queue_url": settings.queue.sqs_queue_url,
        },
        "azure_eventhubs": {
            "connection_string": settings.queue.azure_eventhubs_connection_string,
            "eventhub_name": settings.queue.azure_eventhubs_name,
            "consumer_group": settings.queue.azure_eventhubs_consumer_group,
            "checkpoint_store_connection": settings.queue.azure_eventhubs_checkpoint_store or None,
        },
        "gcp_pubsub": {
            "project_id": settings.queue.gcp_project_id,
            "credentials_path": settings.queue.gcp_credentials_path or None,
            "max_messages": settings.queue.gcp_max_messages,
        },
        "mqtt": {
            "broker_host": settings.queue.mqtt_broker_host,
            "broker_port": settings.queue.mqtt_broker_port,
            "username": settings.queue.mqtt_username or None,
            "password": settings.queue.mqtt_password or None,
            "qos": settings.queue.mqtt_qos,
            "client_id": settings.queue.mqtt_client_id or None,
        },
    }

    config = queue_configs.get(queue_type)
    if not config:
        raise QueueError(f"No configuration found for queue type: {queue_type}")

    try:
        queue = MessageQueueFactory.create(queue_type, **config)
        await queue.connect()
        logger.info("Queue connected successfully", type=queue_type)
        return queue
    except Exception as e:
        logger.error("Failed to create queue", type=queue_type, error=str(e))
        raise QueueError(f"Failed to create {queue_type} queue: {e}") from e
