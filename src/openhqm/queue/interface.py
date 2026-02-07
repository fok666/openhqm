"""Message queue interface definition.

Standardized interface supporting multiple queue backends:
- AWS SQS
- Apache Kafka
- Azure Event Hubs
- GCP Pub/Sub
- Redis Streams
- MQTT
- Custom implementations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass


@dataclass
class QueueMessage:
    """Standardized queue message structure."""

    id: str
    body: Dict[str, Any]
    attributes: Dict[str, str]
    timestamp: float
    retry_count: int = 0
    
    # Backend-specific metadata (optional)
    raw_message: Optional[Any] = None


class MessageQueueInterface(ABC):
    """
    Abstract interface for message queue implementations.
    
    This interface provides a standardized API for different queue backends.
    All implementations must support:
    - Connection management
    - Publishing messages
    - Consuming messages with acknowledgment
    - Queue depth monitoring
    - Dead letter queue handling
    """

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the queue backend.
        
        Raises:
            QueueError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the queue backend gracefully."""
        pass

    @abstractmethod
    async def publish(
        self,
        queue_name: str,
        message: Dict[str, Any],
        priority: int = 0,
        attributes: Optional[Dict[str, str]] = None,
        delay_seconds: int = 0,
    ) -> str:
        """
        Publish a message to the specified queue.

        Args:
            queue_name: Target queue/topic name
            message: Message payload as dictionary
            priority: Message priority (0-9, higher = more important)
            attributes: Optional message attributes/headers
            delay_seconds: Delay before message becomes available (0 = immediate)

        Returns:
            Message ID assigned by the queue backend

        Raises:
            QueueError: If publish fails
        """
        pass

    @abstractmethod
    async def consume(
        self,
        queue_name: str,
        handler: Callable[[QueueMessage], Any],
        batch_size: int = 1,
        wait_time_seconds: int = 20,
    ) -> None:
        """
        Consume messages from queue and process with handler.
        
        This is a long-running operation that continuously polls for messages.
        The handler should be an async function that processes the message.

        Args:
            queue_name: Source queue/topic name
            handler: Async function to process each message
            batch_size: Number of messages to fetch per batch
            wait_time_seconds: Long polling wait time (if supported)

        Raises:
            QueueError: If consume operation fails
        """
        pass

    @abstractmethod
    async def acknowledge(self, message_id: str) -> bool:
        """
        Acknowledge successful message processing.
        
        This removes the message from the queue permanently.

        Args:
            message_id: Message identifier

        Returns:
            True if acknowledged successfully

        Raises:
            QueueError: If acknowledgment fails
        """
        pass

    @abstractmethod
    async def reject(
        self, 
        message_id: str, 
        requeue: bool = True,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Reject a message, optionally requeuing it.
        
        If requeue=False, the message is typically moved to a dead letter queue.

        Args:
            message_id: Message identifier
            requeue: Whether to requeue the message for retry
            reason: Optional reason for rejection (for logging/debugging)

        Returns:
            True if rejected successfully

        Raises:
            QueueError: If rejection fails
        """
        pass

    @abstractmethod
    async def get_queue_depth(self, queue_name: str) -> int:
        """
        Get the approximate current depth of a queue.
        
        Note: This may be approximate for distributed queues.

        Args:
            queue_name: Queue/topic name

        Returns:
            Approximate number of messages in queue

        Raises:
            QueueError: If depth check fails
        """
        pass

    async def health_check(self) -> bool:
        """
        Check if queue backend is healthy and responsive.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            await self.connect()
            return True
        except Exception:
            return False

    async def create_queue(self, queue_name: str, **kwargs) -> bool:
        """
        Create a new queue/topic if it doesn't exist.
        
        Optional method - not all backends require explicit creation.
        
        Args:
            queue_name: Queue/topic name to create
            **kwargs: Backend-specific configuration
            
        Returns:
            True if created successfully
        """
        # Default implementation does nothing (queue auto-created)
        return True

    async def delete_queue(self, queue_name: str) -> bool:
        """
        Delete a queue/topic.
        
        Optional method - use with caution in production.
        
        Args:
            queue_name: Queue/topic name to delete
            
        Returns:
            True if deleted successfully
        """
        # Default implementation does nothing
        return True

    async def purge_queue(self, queue_name: str) -> int:
        """
        Remove all messages from a queue.
        
        Args:
            queue_name: Queue name to purge
            
        Returns:
            Number of messages purged
        """
        # Default implementation does nothing
        return 0


class MessageQueueFactory:
    """Factory for creating queue instances based on configuration."""

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, queue_type: str, queue_class: type) -> None:
        """
        Register a queue implementation.
        
        Args:
            queue_type: Queue type identifier (e.g., "redis", "kafka")
            queue_class: Queue class implementing MessageQueueInterface
        """
        cls._registry[queue_type.lower()] = queue_class

    @classmethod
    def create(cls, queue_type: str, **kwargs) -> MessageQueueInterface:
        """
        Create a queue instance.
        
        Args:
            queue_type: Queue type identifier
            **kwargs: Queue-specific configuration
            
        Returns:
            Queue instance
            
        Raises:
            ValueError: If queue type is not registered
        """
        queue_class = cls._registry.get(queue_type.lower())
        if not queue_class:
            available = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unknown queue type: {queue_type}. "
                f"Available types: {available}"
            )
        return queue_class(**kwargs)

    @classmethod
    def list_types(cls) -> List[str]:
        """
        Get list of registered queue types.
        
        Returns:
            List of queue type identifiers
        """
        return list(cls._registry.keys())
