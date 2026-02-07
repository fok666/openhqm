"""Azure Event Hubs implementation of message queue."""

import json
import time
from typing import Dict, Any, Callable, Optional

import structlog

from openhqm.queue.interface import MessageQueueInterface, QueueMessage
from openhqm.exceptions import QueueError

logger = structlog.get_logger(__name__)


class AzureEventHubsQueue(MessageQueueInterface):
    """
    Azure Event Hubs implementation of message queue.
    
    Azure Event Hubs is a fully managed, real-time data ingestion service
    compatible with Apache Kafka protocol.
    
    Configuration:
        connection_string: Event Hubs connection string
        consumer_group: Consumer group name (default: $Default)
        checkpoint_store: Azure Blob Storage connection for checkpointing
    """

    def __init__(
        self,
        connection_string: str,
        eventhub_name: str,
        consumer_group: str = "$Default",
        checkpoint_store_connection: Optional[str] = None,
        checkpoint_container: str = "checkpoints",
    ):
        """
        Initialize Azure Event Hubs queue.

        Args:
            connection_string: Event Hubs connection string
            eventhub_name: Event Hub name
            consumer_group: Consumer group name
            checkpoint_store_connection: Azure Blob Storage connection for checkpoints
            checkpoint_container: Blob container name for checkpoints
        """
        self.connection_string = connection_string
        self.eventhub_name = eventhub_name
        self.consumer_group = consumer_group
        self.checkpoint_store_connection = checkpoint_store_connection
        self.checkpoint_container = checkpoint_container
        
        self.producer_client = None
        self.consumer_client = None
        self.checkpoint_store = None
        self._running = False

    async def connect(self) -> None:
        """Establish connection to Azure Event Hubs."""
        try:
            # Lazy import to avoid dependency requirement if not used
            from azure.eventhub.aio import EventHubProducerClient, EventHubConsumerClient
            from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore
            
            # Create producer client
            self.producer_client = EventHubProducerClient.from_connection_string(
                conn_str=self.connection_string,
                eventhub_name=self.eventhub_name,
            )
            
            # Create checkpoint store if provided
            if self.checkpoint_store_connection:
                self.checkpoint_store = BlobCheckpointStore.from_connection_string(
                    conn_str=self.checkpoint_store_connection,
                    container_name=self.checkpoint_container,
                )
            
            # Create consumer client
            self.consumer_client = EventHubConsumerClient.from_connection_string(
                conn_str=self.connection_string,
                consumer_group=self.consumer_group,
                eventhub_name=self.eventhub_name,
                checkpoint_store=self.checkpoint_store,
            )
            
            logger.info(
                "Connected to Azure Event Hubs",
                eventhub=self.eventhub_name,
                consumer_group=self.consumer_group,
            )
        except ImportError:
            raise QueueError(
                "Azure Event Hubs dependencies not installed. "
                "Install with: pip install azure-eventhub azure-eventhub-checkpointstoreblob-aio"
            )
        except Exception as e:
            logger.error("Failed to connect to Azure Event Hubs", error=str(e))
            raise QueueError(f"Failed to connect to Azure Event Hubs: {e}")

    async def disconnect(self) -> None:
        """Close connection to Azure Event Hubs."""
        self._running = False
        
        try:
            if self.producer_client:
                await self.producer_client.close()
            if self.consumer_client:
                await self.consumer_client.close()
            logger.info("Disconnected from Azure Event Hubs")
        except Exception as e:
            logger.error("Error disconnecting from Azure Event Hubs", error=str(e))

    async def publish(
        self,
        queue_name: str,
        message: Dict[str, Any],
        priority: int = 0,
        attributes: Optional[Dict[str, str]] = None,
        delay_seconds: int = 0,
    ) -> str:
        """
        Publish a message to Event Hub.
        
        Note: Event Hubs doesn't support message priority or delay natively.
        These can be implemented at application level.
        """
        from azure.eventhub import EventData
        
        try:
            # Create event data
            event_data = EventData(json.dumps(message))
            
            # Add custom properties
            if attributes:
                for key, value in attributes.items():
                    event_data.properties[key] = value
            
            # Add priority as property
            if priority > 0:
                event_data.properties["priority"] = str(priority)
            
            # Send event
            async with self.producer_client:
                event_batch = await self.producer_client.create_batch()
                event_batch.add(event_data)
                await self.producer_client.send_batch(event_batch)
            
            # Event Hubs doesn't return message ID, use timestamp as identifier
            message_id = f"eventhub-{time.time()}"
            
            logger.debug(
                "Published message to Event Hub",
                eventhub=self.eventhub_name,
                message_id=message_id,
            )
            
            return message_id
            
        except Exception as e:
            logger.error("Failed to publish to Event Hub", error=str(e))
            raise QueueError(f"Failed to publish to Event Hub: {e}")

    async def consume(
        self,
        queue_name: str,
        handler: Callable[[QueueMessage], Any],
        batch_size: int = 1,
        wait_time_seconds: int = 20,
    ) -> None:
        """Consume messages from Event Hub."""
        self._running = True
        
        async def on_event(partition_context, event):
            """Event handler callback."""
            if not self._running:
                return
                
            try:
                # Parse message body
                body = json.loads(event.body_as_str())
                
                # Create standardized message
                message = QueueMessage(
                    id=f"{event.partition_key}-{event.sequence_number}",
                    body=body,
                    attributes=dict(event.properties) if event.properties else {},
                    timestamp=event.enqueued_time.timestamp() if event.enqueued_time else time.time(),
                    retry_count=0,
                    raw_message=event,
                )
                
                # Process message
                await handler(message)
                
                # Update checkpoint
                await partition_context.update_checkpoint(event)
                
            except Exception as e:
                logger.error(
                    "Error processing Event Hub message",
                    error=str(e),
                    partition=partition_context.partition_id,
                )
        
        try:
            async with self.consumer_client:
                await self.consumer_client.receive(
                    on_event=on_event,
                    starting_position="-1",  # Start from beginning
                )
        except Exception as e:
            logger.error("Error consuming from Event Hub", error=str(e))
            raise QueueError(f"Error consuming from Event Hub: {e}")

    async def acknowledge(self, message_id: str) -> bool:
        """
        Acknowledge message processing.
        
        Note: Event Hubs uses checkpointing instead of per-message acks.
        Acknowledgment is handled in the consume callback.
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
        
        Note: Event Hubs doesn't support message rejection natively.
        Implement DLQ at application level.
        """
        logger.warning(
            "Message rejection not supported natively in Event Hubs",
            message_id=message_id,
            reason=reason,
        )
        return True

    async def get_queue_depth(self, queue_name: str) -> int:
        """
        Get Event Hub partition information.
        
        Note: Event Hubs doesn't provide queue depth directly.
        Returns 0 as approximate depth.
        """
        return 0
