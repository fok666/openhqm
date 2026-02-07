"""Cache abstraction layer."""

from openhqm.cache.factory import create_cache
from openhqm.cache.interface import CacheInterface

__all__ = ["CacheInterface", "create_cache"]
