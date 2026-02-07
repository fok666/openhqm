"""Message queue abstraction layer."""

from openhqm.queue.factory import create_queue
from openhqm.queue.interface import MessageQueueInterface

__all__ = ["MessageQueueInterface", "create_queue"]
