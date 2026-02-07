"""Cache abstraction layer."""

from openhqm.cache.interface import CacheInterface
from openhqm.cache.factory import create_cache

__all__ = ["CacheInterface", "create_cache"]
