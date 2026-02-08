"""Common helper functions for OpenHQM."""

from typing import Any


def get_nested_value(data: dict[str, Any], path: str) -> Any:
    """Get nested value from dictionary using dot notation.
    
    Args:
        data: Dictionary to extract value from
        path: Dot-separated path (e.g., "metadata.user.id")
        
    Returns:
        Value at path, or None if not found
        
    Example:
        >>> data = {"metadata": {"user": {"id": 123}}}
        >>> get_nested_value(data, "metadata.user.id")
        123
    """
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value
