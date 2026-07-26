"""OpenHQM exceptions."""


class OpenHQMError(Exception):
    """Base exception for OpenHQM."""


class QueueError(OpenHQMError):
    """Queue operation failed."""


class RetryableError(OpenHQMError):
    """Processing failed but may succeed on retry."""


class FatalError(OpenHQMError):
    """Processing failed and must not be retried."""
