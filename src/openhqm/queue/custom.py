"""Custom/plugin queue handler support."""

import importlib
import inspect
from typing import Any

import structlog

from openhqm.exceptions import QueueError
from openhqm.queue.interface import MessageQueueInterface

logger = structlog.get_logger(__name__)


class CustomQueueHandler:
    """
    Support for bringing your own queue handler.

    This allows users to implement custom queue backends without
    modifying OpenHQM core code.

    Usage:
        1. Implement MessageQueueInterface in your custom module
        2. Configure OpenHQM to use your handler:

           queue:
             type: custom
             custom_module: my_company.queues.custom_handler
             custom_class: MyCustomQueue
             custom_config:
               connection_string: "..."
               option1: value1
    """

    @staticmethod
    def load_custom_queue(
        module_path: str,
        class_name: str,
        config: dict[str, Any],
    ) -> MessageQueueInterface:
        """
        Load a custom queue implementation dynamically.

        Args:
            module_path: Python module path (e.g., 'myapp.queues.handler')
            class_name: Class name within the module
            config: Configuration dict to pass to constructor

        Returns:
            Instance of custom queue implementation

        Raises:
            QueueError: If loading fails
        """
        try:
            # Import the module
            module = importlib.import_module(module_path)

            # Get the class
            queue_class = getattr(module, class_name)

            # Verify it implements the interface
            if not issubclass(queue_class, MessageQueueInterface):
                raise QueueError(
                    f"Custom queue class {class_name} must implement MessageQueueInterface"
                )

            # Inspect constructor to determine what parameters it accepts
            sig = inspect.signature(queue_class.__init__)
            params = list(sig.parameters.keys())[1:]  # Skip 'self'

            # Filter config to only include accepted parameters
            filtered_config = {key: value for key, value in config.items() if key in params}

            # Instantiate the queue
            queue_instance = queue_class(**filtered_config)

            logger.info(
                "Loaded custom queue handler",
                module=module_path,
                class_name=class_name,
            )

            return queue_instance

        except ImportError as e:
            raise QueueError(f"Failed to import custom queue module '{module_path}': {e}")
        except AttributeError as e:
            raise QueueError(f"Failed to find class '{class_name}' in module '{module_path}': {e}")
        except Exception as e:
            raise QueueError(f"Failed to load custom queue handler: {e}")

    @staticmethod
    def validate_custom_implementation(queue_instance: MessageQueueInterface) -> bool:
        """
        Validate that a custom implementation properly implements the interface.

        Args:
            queue_instance: Queue instance to validate

        Returns:
            True if valid

        Raises:
            QueueError: If validation fails
        """
        required_methods = [
            "connect",
            "disconnect",
            "publish",
            "consume",
            "acknowledge",
            "reject",
            "get_queue_depth",
        ]

        for method_name in required_methods:
            if not hasattr(queue_instance, method_name):
                raise QueueError(
                    f"Custom queue implementation missing required method: {method_name}"
                )

            method = getattr(queue_instance, method_name)
            if not callable(method):
                raise QueueError(f"Custom queue implementation: {method_name} is not callable")

        logger.info("Custom queue implementation validated successfully")
        return True


# Example custom queue implementation template
class CustomQueueTemplate(MessageQueueInterface):
    """
    Template for implementing a custom queue handler.

    Copy this template and implement all abstract methods.

    Example:
        class MyCustomQueue(MessageQueueInterface):
            def __init__(self, connection_string: str, option1: str):
                self.connection_string = connection_string
                self.option1 = option1
                self.client = None

            async def connect(self):
                # Implement connection logic
                self.client = await my_queue_library.connect(self.connection_string)

            # ... implement other methods
    """

    def __init__(self, **kwargs):
        """
        Initialize your custom queue.

        Accept any configuration parameters you need.
        """
        self.config = kwargs
        self.connected = False

    async def connect(self) -> None:
        """
        Establish connection to your queue backend.

        Example:
            self.client = await my_queue_library.connect(self.config['url'])
            self.connected = True
        """
        raise NotImplementedError("Implement connect() method")

    async def disconnect(self) -> None:
        """
        Close connection to your queue backend.

        Example:
            if self.client:
                await self.client.close()
            self.connected = False
        """
        raise NotImplementedError("Implement disconnect() method")

    async def publish(
        self,
        queue_name: str,
        message: dict[str, Any],
        priority: int = 0,
        attributes: dict[str, str] | None = None,
        delay_seconds: int = 0,
    ) -> str:
        """
        Publish a message to the queue.

        Example:
            message_id = await self.client.send(queue_name, message)
            return message_id
        """
        raise NotImplementedError("Implement publish() method")

    async def consume(
        self,
        queue_name: str,
        handler: Any,
        batch_size: int = 1,
        wait_time_seconds: int = 20,
    ) -> None:
        """
        Consume messages and process with handler.

        Example:
            while self.connected:
                messages = await self.client.receive(queue_name, batch_size)
                for msg in messages:
                    queue_msg = QueueMessage(
                        id=msg.id,
                        body=msg.body,
                        attributes=msg.attributes,
                        timestamp=msg.timestamp,
                        retry_count=0,
                    )
                    await handler(queue_msg)
        """
        raise NotImplementedError("Implement consume() method")

    async def acknowledge(self, message_id: str) -> bool:
        """
        Acknowledge successful message processing.

        Example:
            await self.client.ack(message_id)
            return True
        """
        raise NotImplementedError("Implement acknowledge() method")

    async def reject(
        self,
        message_id: str,
        requeue: bool = True,
        reason: str | None = None,
    ) -> bool:
        """
        Reject a message.

        Example:
            if requeue:
                await self.client.requeue(message_id)
            else:
                await self.client.move_to_dlq(message_id)
            return True
        """
        raise NotImplementedError("Implement reject() method")

    async def get_queue_depth(self, queue_name: str) -> int:
        """
        Get current queue depth.

        Example:
            depth = await self.client.get_message_count(queue_name)
            return depth
        """
        raise NotImplementedError("Implement get_queue_depth() method")
