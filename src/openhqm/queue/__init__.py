"""Message queue abstraction layer."""

from openhqm.queue.interface import MessageQueueInterface
from openhqm.queue.factory import create_queue

__all__ = ["MessageQueueInterface", "create_queue"]
