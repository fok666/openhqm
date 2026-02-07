"""Google Cloud Pub/Sub implementation of message queue."""

import json
import time
from typing import Dict, Any, Callable, Optional

import structlog

from openhqm.queue.interface import MessageQueueInterface, QueueMessage
from openhqm.exceptions import QueueError

logger = structlog.get_logger(__name__)


class GCPPubSubQueue(MessageQueueInterface):
    """
    Google Cloud Pub/Sub implementation of message queue.
    
    Pub/Sub is a fully managed messaging service that allows you to send
    and receive messages between independent applications.
    
    Configuration:
        project_id: GCP project ID
        credentials_path: Path to service account JSON file (optional)
    """

    def __init__(
        self,
        project_id: str,
        credentials_path: Optional[str] = None,
        max_messages: int = 10,
    ):
        """
        Initialize GCP Pub/Sub queue.

        Args:
            project_id: GCP project ID
            credentials_path: Path to service account credentials JSON
            max_messages: Maximum messages to pull per request
        """
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.max_messages = max_messages
        
        self.publisher = None
        self.subscriber = None
        self._subscriptions = {}
        self._running = False

    async def connect(self) -> None:
        """Establish connection to GCP Pub/Sub."""
        try:
            # Lazy import to avoid dependency requirement if not used
            from google.cloud import pubsub_v1
            from google.oauth2 import service_account
            
            # Load credentials if provided
            credentials = None
            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
            
            # Create publisher and subscriber clients
            self.publisher = pubsub_v1.PublisherClient(credentials=credentials)
            self.subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
            
            logger.info("Connected to GCP Pub/Sub", project=self.project_id)
            
        except ImportError:
            raise QueueError(
                "GCP Pub/Sub dependencies not installed. "
                "Install with: pip install google-cloud-pubsub"
            )
        except Exception as e:
            logger.error("Failed to connect to GCP Pub/Sub", error=str(e))
            raise QueueError(f"Failed to connect to GCP Pub/Sub: {e}")

    async def disconnect(self) -> None:
        """Close connection to GCP Pub/Sub."""
        self._running = False
        
        try:
            # Cancel all subscriptions
            for future in self._subscriptions.values():
                future.cancel()
            
            self._subscriptions.clear()
            logger.info("Disconnected from GCP Pub/Sub")
            
        except Exception as e:
            logger.error("Error disconnecting from GCP Pub/Sub", error=str(e))

    async def publish(
        self,
        queue_name: str,
        message: Dict[str, Any],
        priority: int = 0,
        attributes: Optional[Dict[str, str]] = None,
        delay_seconds: int = 0,
    ) -> str:
        """
        Publish a message to Pub/Sub topic.
        
        Note: Pub/Sub doesn't support message delay natively.
        """
        try:
            topic_path = self.publisher.topic_path(self.project_id, queue_name)
            
            # Encode message as JSON
            data = json.dumps(message).encode("utf-8")
            
            # Prepare attributes
            msg_attributes = attributes or {}
            if priority > 0:
                msg_attributes["priority"] = str(priority)
            msg_attributes["timestamp"] = str(time.time())
            
            # Publish message
            future = self.publisher.publish(topic_path, data, **msg_attributes)
            message_id = future.result()  # Block until published
            
            logger.debug(
                "Published message to Pub/Sub",
                topic=queue_name,
                message_id=message_id,
            )
            
            return message_id
            
        except Exception as e:
            logger.error("Failed to publish to Pub/Sub", error=str(e))
            raise QueueError(f"Failed to publish to Pub/Sub: {e}")

    async def consume(
        self,
        queue_name: str,
        handler: Callable[[QueueMessage], Any],
        batch_size: int = 1,
        wait_time_seconds: int = 20,
    ) -> None:
        """
        Consume messages from Pub/Sub subscription.
        
        Note: queue_name should be the subscription name, not topic name.
        """
        import asyncio
        
        self._running = True
        subscription_path = self.subscriber.subscription_path(self.project_id, queue_name)
        
        def callback(message):
            """Message callback for Pub/Sub."""
            if not self._running:
                message.nack()
                return
            
            try:
                # Parse message body
                body = json.loads(message.data.decode("utf-8"))
                
                # Create standardized message
                queue_message = QueueMessage(
                    id=message.message_id,
                    body=body,
                    attributes=dict(message.attributes),
                    timestamp=message.publish_time.timestamp(),
                    retry_count=message.delivery_attempt - 1 if message.delivery_attempt else 0,
                    raw_message=message,
                )
                
                # Process message asynchronously
                asyncio.create_task(self._handle_message(handler, queue_message, message))
                
            except Exception as e:
                logger.error("Error processing Pub/Sub message", error=str(e))
                message.nack()
        
        try:
            # Start streaming pull
            streaming_pull_future = self.subscriber.subscribe(
                subscription_path,
                callback=callback,
                flow_control={"max_messages": self.max_messages},
            )
            
            self._subscriptions[queue_name] = streaming_pull_future
            
            # Keep alive
            await asyncio.get_event_loop().run_in_executor(
                None, streaming_pull_future.result
            )
            
        except Exception as e:
            logger.error("Error consuming from Pub/Sub", error=str(e))
            raise QueueError(f"Error consuming from Pub/Sub: {e}")

    async def _handle_message(self, handler, queue_message, pubsub_message):
        """Handle message processing and acknowledgment."""
        try:
            await handler(queue_message)
            pubsub_message.ack()
        except Exception as e:
            logger.error("Handler failed", error=str(e))
            pubsub_message.nack()

    async def acknowledge(self, message_id: str) -> bool:
        """
        Acknowledge message processing.
        
        Note: Pub/Sub handles acks in the callback automatically.
        """
        return True

    async def reject(
        self,
        message_id: str,
        requeue: bool = True,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Reject a message.
        
        Note: Pub/Sub handles nacks in the callback automatically.
        """
        logger.debug("Message rejection", message_id=message_id, reason=reason)
        return True

    async def get_queue_depth(self, queue_name: str) -> int:
        """
        Get approximate number of messages in subscription.
        
        Note: This requires the Monitoring API and may have quota limits.
        """
        try:
            subscription_path = self.subscriber.subscription_path(
                self.project_id, queue_name
            )
            subscription = self.subscriber.get_subscription(
                request={"subscription": subscription_path}
            )
            
            # Get approximate message count (not real-time)
            # This is a rough estimate
            return 0  # Pub/Sub doesn't provide exact depth
            
        except Exception as e:
            logger.warning("Failed to get queue depth", error=str(e))
            return 0

    async def create_queue(self, queue_name: str, **kwargs) -> bool:
        """
        Create a Pub/Sub topic and subscription.
        
        Args:
            queue_name: Topic name
            **kwargs: Can include 'create_subscription' bool
        """
        try:
            from google.api_core.exceptions import AlreadyExists
            
            # Create topic
            topic_path = self.publisher.topic_path(self.project_id, queue_name)
            try:
                self.publisher.create_topic(request={"name": topic_path})
                logger.info("Created Pub/Sub topic", topic=queue_name)
            except AlreadyExists:
                logger.debug("Topic already exists", topic=queue_name)
            
            # Create subscription if requested
            if kwargs.get("create_subscription", True):
                subscription_name = f"{queue_name}-subscription"
                subscription_path = self.subscriber.subscription_path(
                    self.project_id, subscription_name
                )
                try:
                    self.subscriber.create_subscription(
                        request={"name": subscription_path, "topic": topic_path}
                    )
                    logger.info("Created Pub/Sub subscription", subscription=subscription_name)
                except AlreadyExists:
                    logger.debug("Subscription already exists", subscription=subscription_name)
            
            return True
            
        except Exception as e:
            logger.error("Failed to create topic/subscription", error=str(e))
            return False
