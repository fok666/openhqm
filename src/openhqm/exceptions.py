"""Custom exceptions for OpenHQM."""


class OpenHQMError(Exception):
    """Base exception for OpenHQM."""

    pass


class QueueError(OpenHQMError):
    """Exception raised for queue operation errors."""

    pass


class ValidationError(OpenHQMError):
    """Exception raised for validation errors."""

    pass


class ProcessingError(OpenHQMError):
    """Exception raised for processing errors."""

    pass


class ConfigurationError(OpenHQMError):
    """Exception raised for configuration errors."""

    pass


class RetryableError(ProcessingError):
    """Exception that indicates the operation can be retried."""

    pass


class FatalError(ProcessingError):
    """Exception that indicates the operation should not be retried."""

    pass


class TimeoutError(OpenHQMError):
    """Exception raised when an operation times out."""

    pass


class CircuitBreakerOpenError(OpenHQMError):
    """Exception raised when circuit breaker is open."""

    pass
