# Gemini Instructions for OpenHQM

## Project Context
You are working on OpenHQM, a production-grade asynchronous HTTP request processing system. The system decouples HTTP request handling from backend processing using message queues, enabling scalable and fault-tolerant operations.

## Architecture Understanding
- **HTTP Listener (FastAPI)**: Accepts requests, generates correlation IDs, queues messages
- **Message Queues**: Redis Streams, Kafka, or AWS SQS for request/response queuing
- **Workers**: Async Python workers that consume, process, and respond
- **Cache Layer**: Redis for request tracking and response storage

## Your Role
As an AI coding assistant, you should:
1. Write production-quality Python code following best practices
2. Implement async/await patterns consistently
3. Add comprehensive error handling and logging
4. Write testable, maintainable code
5. Consider scalability and performance
6. Document your code clearly

## Language and Framework Requirements

### Python Version
- Use Python 3.11 or higher
- Leverage modern Python features (type hints, async/await, pattern matching)

### Core Frameworks
- **FastAPI**: For HTTP API implementation
- **Pydantic**: For data validation and settings management
- **asyncio**: For asynchronous operations
- **Redis/Kafka clients**: For message queue operations

### Code Style
- Follow PEP 8 style guide
- Use `ruff` for code formatting and linting
- Maximum line length: 100 characters
- Use meaningful variable names
- Add type hints to all functions

## Implementation Guidelines

### 1. Async First
All I/O operations must be asynchronous:
```python
# ✅ Good - async I/O
async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# ❌ Bad - blocking I/O
def fetch_data(url: str) -> dict:
    return requests.get(url).json()
```

### 2. Type Safety
Use type hints extensively:
```python
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

# ✅ Good - fully typed
async def process_message(
    message: Dict[str, Any],
    queue: MessageQueueInterface,
    correlation_id: str
) -> Optional[Dict[str, Any]]:
    result = await queue.consume(message)
    return result

# ❌ Bad - no type hints
async def process_message(message, queue, correlation_id):
    result = await queue.consume(message)
    return result
```

### 3. Error Handling
Implement comprehensive error handling with specific exception types:
```python
from openhqm.exceptions import QueueError, ValidationError, ProcessingError

async def handle_request(request: dict):
    try:
        # Validate input
        validated = validate_request(request)
    except ValidationError as e:
        logger.error("Validation failed", error=str(e), request=request)
        raise HTTPException(status_code=400, detail=str(e))
    
    try:
        # Process request
        result = await process(validated)
        return result
    except QueueError as e:
        logger.error("Queue operation failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.exception("Unexpected error occurred")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 4. Structured Logging
Use structured logging with context:
```python
import structlog

logger = structlog.get_logger()

async def process_request(correlation_id: str, payload: dict):
    # Bind correlation ID to all logs in this context
    log = logger.bind(correlation_id=correlation_id)
    
    log.info("Starting request processing", payload_size=len(str(payload)))
    
    start_time = time.time()
    try:
        result = await process(payload)
        duration = (time.time() - start_time) * 1000
        log.info("Request processed successfully", duration_ms=duration)
        return result
    except Exception as e:
        log.error("Processing failed", error=str(e), error_type=type(e).__name__)
        raise
```

### 5. Configuration Management
Use pydantic-settings for type-safe configuration:
```python
from pydantic_settings import BaseSettings
from pydantic import Field

class QueueSettings(BaseSettings):
    type: str = Field(default="redis", description="Queue backend type")
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    max_connections: int = Field(default=10, description="Maximum connection pool size")
    
    class Config:
        env_prefix = "OPENHQM_QUEUE_"
        env_file = ".env"

class Settings(BaseSettings):
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Queue settings
    queue: QueueSettings = QueueSettings()
    
    # Worker settings
    worker_count: int = 5
    worker_timeout: int = 300
    
    class Config:
        env_prefix = "OPENHQM_"

settings = Settings()
```

## Component Implementation Patterns

### API Endpoints
Structure endpoints clearly with proper status codes and response models:
```python
from fastapi import APIRouter, HTTPException, Depends, status
from openhqm.api.models import SubmitRequest, SubmitResponse, StatusResponse

router = APIRouter(prefix="/api/v1", tags=["requests"])

@router.post(
    "/submit",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new request",
    description="Queue a request for asynchronous processing"
)
async def submit_request(
    request: SubmitRequest,
    queue: MessageQueueInterface = Depends(get_queue),
    cache: CacheInterface = Depends(get_cache)
) -> SubmitResponse:
    """
    Submit a request for processing.
    
    - Generates a unique correlation ID
    - Validates the payload
    - Queues the request
    - Returns the correlation ID for tracking
    """
    correlation_id = str(uuid.uuid4())
    
    message = {
        "correlation_id": correlation_id,
        "payload": request.payload,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": request.metadata.dict() if request.metadata else {}
    }
    
    # Store in cache
    await cache.set(
        f"req:{correlation_id}:meta",
        message,
        ttl=3600
    )
    
    # Publish to queue
    success = await queue.publish("requests", message)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to queue request"
        )
    
    return SubmitResponse(
        correlation_id=correlation_id,
        status="PENDING",
        submitted_at=datetime.utcnow()
    )
```

### Queue Abstraction
Implement a clean interface for queue operations:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional

class MessageQueueInterface(ABC):
    """Abstract interface for message queue implementations."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the queue backend."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the queue backend."""
        pass
    
    @abstractmethod
    async def publish(
        self,
        queue_name: str,
        message: Dict[str, Any],
        priority: int = 0
    ) -> bool:
        """
        Publish a message to the specified queue.
        
        Args:
            queue_name: Target queue name
            message: Message payload
            priority: Message priority (0-9, higher = more important)
            
        Returns:
            True if published successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def consume(
        self,
        queue_name: str,
        handler: Callable[[Dict[str, Any]], Any],
        batch_size: int = 1
    ) -> None:
        """
        Consume messages from queue and process with handler.
        
        Args:
            queue_name: Source queue name
            handler: Async function to process each message
            batch_size: Number of messages to process in batch
        """
        pass
    
    @abstractmethod
    async def acknowledge(self, message_id: str) -> bool:
        """Acknowledge successful message processing."""
        pass
    
    @abstractmethod
    async def reject(self, message_id: str, requeue: bool = True) -> bool:
        """Reject a message, optionally requeuing it."""
        pass
```

### Worker Implementation
Create robust workers with graceful shutdown:
```python
import signal
import asyncio
from typing import Optional

class Worker:
    """Message queue worker for processing requests."""
    
    def __init__(
        self,
        worker_id: str,
        queue: MessageQueueInterface,
        processor: MessageProcessor,
        batch_size: int = 10
    ):
        self.worker_id = worker_id
        self.queue = queue
        self.processor = processor
        self.batch_size = batch_size
        self.running = False
        self.current_message: Optional[str] = None
        
    async def start(self) -> None:
        """Start the worker loop."""
        self.running = True
        
        # Register shutdown handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        logger.info("Worker started", worker_id=self.worker_id)
        
        try:
            await self.queue.consume(
                "requests",
                self._handle_message,
                batch_size=self.batch_size
            )
        except Exception as e:
            logger.exception("Worker loop failed", worker_id=self.worker_id)
            raise
        finally:
            await self.shutdown()
    
    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Process a single message."""
        correlation_id = message.get("correlation_id")
        self.current_message = correlation_id
        
        log = logger.bind(
            worker_id=self.worker_id,
            correlation_id=correlation_id
        )
        
        log.info("Processing message")
        
        try:
            result = await self.processor.process(message["payload"])
            
            # Publish response
            await self.queue.publish("responses", {
                "correlation_id": correlation_id,
                "result": result,
                "status": "COMPLETED",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            await self.queue.acknowledge(correlation_id)
            log.info("Message processed successfully")
            
        except RetryableError as e:
            log.warning("Retryable error occurred", error=str(e))
            await self.queue.reject(correlation_id, requeue=True)
            
        except Exception as e:
            log.error("Fatal error occurred", error=str(e))
            await self._send_to_dlq(message)
            await self.queue.acknowledge(correlation_id)
        
        finally:
            self.current_message = None
    
    async def _send_to_dlq(self, message: Dict[str, Any]) -> None:
        """Send failed message to dead letter queue."""
        await self.queue.publish("dlq", {
            **message,
            "failed_at": datetime.utcnow().isoformat(),
            "worker_id": self.worker_id
        })
    
    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown signal received", worker_id=self.worker_id)
        self.running = False
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the worker."""
        logger.info("Shutting down worker", worker_id=self.worker_id)
        
        # Wait for current message to complete (with timeout)
        if self.current_message:
            logger.info("Waiting for current message to complete")
            for _ in range(30):  # 30 seconds max
                if not self.current_message:
                    break
                await asyncio.sleep(1)
        
        await self.queue.disconnect()
        logger.info("Worker shutdown complete", worker_id=self.worker_id)
```

## Testing Guidelines

### Unit Tests
Write comprehensive unit tests with mocks:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from openhqm.api.routes import submit_request
from openhqm.api.models import SubmitRequest

@pytest.mark.asyncio
async def test_submit_request_success():
    """Test successful request submission."""
    # Arrange
    mock_queue = AsyncMock(spec=MessageQueueInterface)
    mock_queue.publish.return_value = True
    
    mock_cache = AsyncMock(spec=CacheInterface)
    mock_cache.set.return_value = True
    
    request = SubmitRequest(
        payload={"operation": "test", "data": "value"}
    )
    
    # Act
    response = await submit_request(
        request=request,
        queue=mock_queue,
        cache=mock_cache
    )
    
    # Assert
    assert response.status == "PENDING"
    assert uuid.UUID(response.correlation_id)  # Valid UUID
    assert response.submitted_at is not None
    
    mock_queue.publish.assert_called_once()
    mock_cache.set.assert_called_once()

@pytest.mark.asyncio
async def test_submit_request_queue_failure():
    """Test request submission when queue is unavailable."""
    # Arrange
    mock_queue = AsyncMock(spec=MessageQueueInterface)
    mock_queue.publish.return_value = False
    
    mock_cache = AsyncMock(spec=CacheInterface)
    
    request = SubmitRequest(payload={"test": "data"})
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await submit_request(request, mock_queue, mock_cache)
    
    assert exc_info.value.status_code == 503
```

### Integration Tests
Test real component interactions:
```python
import pytest
import asyncio
from testcontainers.redis import RedisContainer

@pytest.mark.integration
async def test_redis_queue_end_to_end():
    """Test Redis queue publish and consume flow."""
    # Start Redis container
    with RedisContainer("redis:7-alpine") as redis:
        redis_url = redis.get_connection_url()
        
        # Create queue instance
        queue = RedisQueue(url=redis_url)
        await queue.connect()
        
        # Publish message
        test_message = {
            "correlation_id": "test-123",
            "payload": {"data": "test"}
        }
        
        published = await queue.publish("test-queue", test_message)
        assert published is True
        
        # Consume message
        received = []
        
        async def handler(msg):
            received.append(msg)
            await queue.acknowledge(msg["correlation_id"])
        
        # Start consumer in background
        consumer_task = asyncio.create_task(
            queue.consume("test-queue", handler)
        )
        
        # Wait for message processing
        await asyncio.sleep(1)
        
        # Verify
        assert len(received) == 1
        assert received[0]["correlation_id"] == "test-123"
        
        # Cleanup
        consumer_task.cancel()
        await queue.disconnect()
```

## Best Practices Checklist

When writing code, ensure:

- [ ] All functions have type hints
- [ ] Async/await used for I/O operations
- [ ] Error handling covers edge cases
- [ ] Logging includes correlation IDs
- [ ] Configuration uses pydantic-settings
- [ ] Code follows PEP 8 style
- [ ] Docstrings explain complex logic
- [ ] Tests cover success and failure paths
- [ ] Resources are properly closed (connections, files)
- [ ] Graceful shutdown is implemented for long-running processes

## Performance Optimization

### Connection Pooling
Always use connection pools for external resources:
```python
import redis.asyncio as aioredis

class RedisCache:
    def __init__(self, url: str, pool_size: int = 10):
        self.pool = aioredis.ConnectionPool.from_url(
            url,
            max_connections=pool_size,
            decode_responses=True
        )
        self.redis = aioredis.Redis(connection_pool=self.pool)
    
    async def close(self):
        await self.pool.disconnect()
```

### Batch Operations
Process multiple items efficiently:
```python
async def process_batch(messages: List[dict]):
    """Process multiple messages concurrently."""
    tasks = [process_single(msg) for msg in messages]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result, message in zip(results, messages):
        if isinstance(result, Exception):
            logger.error("Batch processing failed", 
                        correlation_id=message["correlation_id"],
                        error=str(result))
        else:
            logger.info("Batch item processed",
                       correlation_id=message["correlation_id"])
    
    return results
```

## Security Considerations

### Input Validation
Always validate and sanitize input:
```python
from pydantic import BaseModel, Field, validator

class SubmitRequest(BaseModel):
    payload: dict = Field(..., description="Request payload")
    priority: int = Field(default=0, ge=0, le=9, description="Priority 0-9")
    
    @validator('payload')
    def validate_payload(cls, v):
        if not v:
            raise ValueError("Payload cannot be empty")
        if len(str(v)) > 1_000_000:  # 1MB limit
            raise ValueError("Payload too large")
        return v
```

### Sensitive Data
Never log sensitive information:
```python
def sanitize_for_logging(data: dict) -> dict:
    """Remove sensitive fields from data before logging."""
    sensitive_fields = {'password', 'token', 'api_key', 'secret', 'ssn'}
    return {
        k: '***REDACTED***' if k.lower() in sensitive_fields else v
        for k, v in data.items()
    }

logger.info("Processing request", payload=sanitize_for_logging(request.payload))
```

## Common Patterns

### Retry with Exponential Backoff
```python
async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
):
    """Retry function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await func()
        except RetryableError as e:
            if attempt == max_retries - 1:
                raise
            
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(f"Retry attempt {attempt + 1}, waiting {delay}s", error=str(e))
            await asyncio.sleep(delay)
```

### Circuit Breaker
```python
class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func: Callable):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        try:
            result = await func()
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
    
    def on_success(self):
        self.failures = 0
        self.state = "CLOSED"
    
    def on_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
```

## Documentation Standards

### Function Docstrings
Use Google-style docstrings:
```python
async def publish_message(
    queue_name: str,
    message: Dict[str, Any],
    priority: int = 0,
    retry: bool = True
) -> bool:
    """
    Publish a message to the specified queue with optional priority.
    
    This function handles message serialization, validation, and publishing
    to the message queue. It supports automatic retries on transient failures.
    
    Args:
        queue_name: Name of the target queue (e.g., "requests", "responses")
        message: Message payload as a dictionary. Must be JSON-serializable.
        priority: Message priority from 0 (low) to 9 (high). Default is 0.
        retry: Whether to automatically retry on failure. Default is True.
    
    Returns:
        True if the message was successfully published, False otherwise.
    
    Raises:
        QueueError: If the queue connection is not available
        ValidationError: If the message cannot be serialized
        TimeoutError: If the publish operation times out
    
    Examples:
        >>> await publish_message("requests", {"id": 1, "data": "test"})
        True
        
        >>> await publish_message(
        ...     "urgent-requests",
        ...     {"id": 2, "data": "critical"},
        ...     priority=9
        ... )
        True
    """
    pass
```

## When to Ask for Clarification

Ask the user for clarification when:
1. Business logic requirements are ambiguous
2. Multiple implementation approaches are equally valid
3. Configuration values or external system details are needed
4. Security or compliance requirements are unclear

## Code Review Checklist

Before completing any code generation, verify:
- ✅ Type hints on all functions
- ✅ Async/await for I/O operations
- ✅ Comprehensive error handling
- ✅ Structured logging with context
- ✅ Unit tests included
- ✅ Docstrings for public APIs
- ✅ Configuration properly managed
- ✅ Security best practices followed
- ✅ Performance considerations addressed
- ✅ Code follows project structure

---

**Remember**: You're building a production system. Code quality, reliability, and maintainability are paramount. When in doubt, prefer explicit over implicit, simple over complex, and tested over untested.
