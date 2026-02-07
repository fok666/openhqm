"""MQTT implementation of message queue."""

import json
import time
import asyncio
from typing import Dict, Any, Callable, Optional
from uuid import uuid4

import structlog

from openhqm.queue.interface import MessageQueueInterface, QueueMessage
from openhqm.exceptions import QueueError

logger = structlog.get_logger(__name__)


class MQTTQueue(MessageQueueInterface):
    """
    MQTT implementation of message queue.
    
    MQTT is a lightweight publish/subscribe messaging protocol
    commonly used in IoT applications.
    
    Configuration:
        broker_host: MQTT broker hostname
        broker_port: MQTT broker port (default: 1883)
        username: Optional username for authentication
        password: Optional password for authentication
        qos: Quality of Service level (0, 1, or 2)
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        qos: int = 1,
        client_id: Optional[str] = None,
        clean_session: bool = True,
        keepalive: int = 60,
    ):
        """
        Initialize MQTT queue.

        Args:
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            username: Authentication username
            password: Authentication password
            qos: Quality of Service (0, 1, or 2)
            client_id: Client identifier (auto-generated if None)
            clean_session: Whether to start with clean session
            keepalive: Keepalive interval in seconds
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.qos = qos
        self.client_id = client_id or f"openhqm-{uuid4().hex[:8]}"
        self.clean_session = clean_session
        self.keepalive = keepalive
        
        self.client = None
        self._message_handlers = {}
        self._running = False
        self._pending_messages = {}

    async def connect(self) -> None:
        """Establish connection to MQTT broker."""
        try:
            # Lazy import to avoid dependency requirement if not used
            import asyncio_mqtt
            
            self.client = asyncio_mqtt.Client(
                hostname=self.broker_host,
                port=self.broker_port,
                username=self.username,
                password=self.password,
                client_id=self.client_id,
                clean_session=self.clean_session,
                keepalive=self.keepalive,
            )
            
            await self.client.__aenter__()
            
            logger.info(
                "Connected to MQTT broker",
                broker=self.broker_host,
                port=self.broker_port,
                client_id=self.client_id,
            )
            
        except ImportError:
            raise QueueError(
                "MQTT dependencies not installed. "
                "Install with: pip install asyncio-mqtt"
            )
        except Exception as e:
            logger.error("Failed to connect to MQTT broker", error=str(e))
            raise QueueError(f"Failed to connect to MQTT broker: {e}")

    async def disconnect(self) -> None:
        """Close connection to MQTT broker."""
        self._running = False
        
        try:
            if self.client:
                await self.client.__aexit__(None, None, None)
            logger.info("Disconnected from MQTT broker")
        except Exception as e:
            logger.error("Error disconnecting from MQTT broker", error=str(e))

    async def publish(
        self,
        queue_name: str,
        message: Dict[str, Any],
        priority: int = 0,
        attributes: Optional[Dict[str, str]] = None,
        delay_seconds: int = 0,
    ) -> str:
        """
        Publish a message to MQTT topic.
        
        Note: MQTT doesn't support message priority or delay natively.
        Priority can be embedded in the message payload.
        """
        try:
            # Generate message ID
            message_id = str(uuid4())
            
            # Wrap message with metadata
            payload = {
                "id": message_id,
                "body": message,
                "attributes": attributes or {},
                "priority": priority,
                "timestamp": time.time(),
            }
            
            # Encode as JSON
            data = json.dumps(payload)
            
            # Publish to topic
            await self.client.publish(
                queue_name,
                payload=data,
                qos=self.qos,
                retain=False,
            )
            
            logger.debug(
                "Published message to MQTT",
                topic=queue_name,
                message_id=message_id,
                qos=self.qos,
            )
            
            return message_id
            
        except Exception as e:
            logger.error("Failed to publish to MQTT", error=str(e))
            raise QueueError(f"Failed to publish to MQTT: {e}")

    async def consume(
        self,
        queue_name: str,
        handler: Callable[[QueueMessage], Any],
        batch_size: int = 1,
        wait_time_seconds: int = 20,
    ) -> None:
        """
        Consume messages from MQTT topic.
        
        Note: MQTT doesn't support batching natively.
        Each message is processed individually.
        """
        self._running = True
        
        try:
            # Subscribe to topic
            await self.client.subscribe(queue_name, qos=self.qos)
            
            logger.info("Subscribed to MQTT topic", topic=queue_name, qos=self.qos)
            
            # Process messages
            async with self.client.filtered_messages(queue_name) as messages:
                async for mqtt_message in messages:
                    if not self._running:
                        break
                    
                    try:
                        # Parse message payload
                        payload = json.loads(mqtt_message.payload.decode("utf-8"))
                        
                        # Extract message components
                        message_id = payload.get("id", str(uuid4()))
                        body = payload.get("body", payload)  # Fallback to full payload
                        attributes = payload.get("attributes", {})
                        timestamp = payload.get("timestamp", time.time())
                        
                        # Create standardized message
                        message = QueueMessage(
                            id=message_id,
                            body=body,
                            attributes=attributes,
                            timestamp=timestamp,
                            retry_count=0,
                            raw_message=mqtt_message,
                        )
                        
                        # Store for acknowledgment
                        self._pending_messages[message_id] = mqtt_message
                        
                        # Process message
                        await handler(message)
                        
                        # Auto-acknowledge if handler succeeds (QoS 1/2)
                        if self.qos > 0:
                            await self.acknowledge(message_id)
                        
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON in MQTT message", topic=queue_name)
                    except Exception as e:
                        logger.error(
                            "Error processing MQTT message",
                            error=str(e),
                            topic=queue_name,
                        )
            
        except Exception as e:
            logger.error("Error consuming from MQTT", error=str(e))
            raise QueueError(f"Error consuming from MQTT: {e}")

    async def acknowledge(self, message_id: str) -> bool:
        """
        Acknowledge message processing.
        
        Note: MQTT QoS handles acknowledgment at protocol level.
        This method cleans up internal tracking.
        """
        if message_id in self._pending_messages:
            del self._pending_messages[message_id]
            logger.debug("Acknowledged MQTT message", message_id=message_id)
        return True

    async def reject(
        self,
        message_id: str,
        requeue: bool = True,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Reject a message.
        
        Note: MQTT doesn't support message rejection/requeuing natively.
        Implement DLQ at application level by publishing to a different topic.
        """
        logger.warning(
            "MQTT message rejection",
            message_id=message_id,
            requeue=requeue,
            reason=reason,
        )
        
        if message_id in self._pending_messages:
            del self._pending_messages[message_id]
        
        return True

    async def get_queue_depth(self, queue_name: str) -> int:
        """
        Get queue depth.
        
        Note: MQTT doesn't provide queue depth information.
        Returns number of pending messages in local tracking.
        """
        return len(self._pending_messages)

    async def health_check(self) -> bool:
        """Check MQTT broker connectivity."""
        try:
            if not self.client:
                return False
            
            # Try to publish a heartbeat message
            test_topic = f"$SYS/openhqm/health/{self.client_id}"
            await self.client.publish(test_topic, payload="ping", qos=0)
            return True
            
        except Exception:
            return False
