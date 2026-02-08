# GitHub Copilot Instructions for OpenHQM

## Project Overview
OpenHQM is an asynchronous HTTP request processing system built with Python and FastAPI. It uses message queues (Redis Streams, Kafka, or SQS) to decouple request submission from processing, enabling scalable, non-blocking request handling.

See [SDD](../SDD.md) for details.

**Proxy Mode**: OpenHQM can operate as an asynchronous reverse proxy, forwarding requests to configured backend endpoints with support for multiple authentication methods, transparent header forwarding, and full response capture. See [PROXY_MODE.md](../docs/PROXY_MODE.md) for details.

## Code Style and Conventions

### Python Standards
- Use Python 3.11+ features and type hints
- Follow PEP 8 style guide strictly
- Use `ruff` for linting and formatting
- Maximum line length: 100 characters
- Use async/await for all I/O operations
- Type hints are mandatory for all function signatures

### Naming Conventions
```python
# Classes: PascalCase
class MessageQueue:
    pass

# Functions and methods: snake_case
async def process_message(message: dict) -> Result:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 300

# Private methods: _leading_underscore
def _internal_helper():
    pass
```

### Import Organization
```python
# Standard library imports
import asyncio
import uuid
from typing import Dict, Any, Optional

# Third-party imports
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local application imports
from openhqm.config import settings
from openhqm.queue.interface import MessageQueueInterface
```

## Architecture Patterns

### Dependency Injection
Use FastAPI's dependency injection for all shared resources:
```python
from fastapi import Depends

async def get_queue() -> MessageQueueInterface:
    return queue_instance

@app.post("/api/v1/submit")
async def submit_request(
    request: RequestModel,
    queue: MessageQueueInterface = Depends(get_queue)
):
    pass
```

### Async/Await Pattern
All I/O operations must be async:
```python
# Correct
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Incorrect - don't use blocking calls
def fetch_data():
    return requests.get(url).json()
```

### Error Handling
Use custom exceptions and proper error propagation:
```python
from openhqm.exceptions import QueueError, ProcessingError

async def process_message(message: dict):
    try:
        result = await worker.process(message)
        return result
    except ValidationError as e:
        logger.error("Validation failed", correlation_id=message["correlation_id"])
        raise ProcessingError(f"Invalid message: {e}")
    except Exception as e:
        logger.exception("Unexpected error")
        raise QueueError(f"Processing failed: {e}")
```

## Key Components

### 1. API Layer (`src/openhqm/api/`)
- Use FastAPI routers for endpoint organization
- All endpoints return Pydantic models
- Use HTTP status codes correctly (202 for async, 404 for not found, etc.)
- Include correlation IDs in all responses
- Example:
```python
from fastapi import APIRouter, HTTPException, status
from openhqm.api.models import SubmitRequest, SubmitResponse

router = APIRouter(prefix="/api/v1", tags=["requests"])

@router.post("/submit", response_model=SubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_request(request: SubmitRequest, queue: MessageQueue = Depends(get_queue)):
    correlation_id = str(uuid.uuid4())
    await queue.publish("requests", {
        "correlation_id": correlation_id,
        "payload": request.payload,
        "timestamp": datetime.utcnow().isoformat()
    })
    return SubmitResponse(correlation_id=correlation_id, status="PENDING")
```

### 2. Queue Layer (`src/openhqm/queue/`)
- Implement `MessageQueueInterface` for all queue backends
- Use connection pools for efficiency
- Handle reconnection logic gracefully
- Example interface:
```python
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any

class MessageQueueInterface(ABC):
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to queue backend"""
        
    @abstractmethod
    async def publish(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Publish message to queue"""
        
    @abstractmethod
    async def consume(self, queue_name: str, handler: Callable) -> None:
        """Consume messages from queue"""
        
    @abstractmethod
    async def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message processing"""
```

### 3. Worker Layer (`src/openhqm/worker/`)
- Workers should be stateless
- Use graceful shutdown handlers
- Implement retry logic with exponential backoff
- Example:
```python
import asyncio
from openhqm.worker.processor import MessageProcessor

class Worker:
    def __init__(self, queue: MessageQueueInterface, processor: MessageProcessor):
        self.queue = queue
        self.processor = processor
        self.running = False
        
    async def start(self):
        self.running = True
        await self.queue.consume("requests", self.handle_message)
        
    async def handle_message(self, message: dict):
        correlation_id = message["correlation_id"]
        retry_count = message.get("metadata", {}).get("retry_count", 0)
        
        try:
            result = await self.processor.process(message["payload"])
            await self.queue.publish("responses", {
                "correlation_id": correlation_id,
                "result": result,
                "status": "COMPLETED"
            })
        except RetryableError as e:
            if retry_count < MAX_RETRIES:
                await self.retry_with_backoff(message, retry_count)
            else:
                await self.send_to_dlq(message)
```

### 4. Configuration (`src/openhqm/config/`)
- Use pydantic-settings for configuration management
- Support environment variables
- Validate configuration at startup
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Queue settings
    queue_type: str = "redis"
    redis_url: str = "redis://localhost:6379"
    
    # Worker settings
    worker_count: int = 5
    worker_timeout: int = 300
    
    class Config:
        env_prefix = "OPENHQM_"
        env_file = ".env"
        
settings = Settings()
```

## Testing Guidelines

### Unit Tests
- Use pytest with async support (`pytest-asyncio`)
- Mock external dependencies
- Test both success and failure paths
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_submit_request_success():
    mock_queue = AsyncMock(spec=MessageQueueInterface)
    mock_queue.publish.return_value = True
    
    response = await submit_request(
        request=SubmitRequest(payload={"test": "data"}),
        queue=mock_queue
    )
    
    assert response.status == "PENDING"
    assert uuid.UUID(response.correlation_id)
    mock_queue.publish.assert_called_once()
```

### Integration Tests
- Test real queue interactions
- Use testcontainers for dependencies
- Clean up resources after tests
```python
@pytest.mark.integration
async def test_redis_queue_publish_consume():
    queue = RedisQueue(url="redis://localhost:6379")
    await queue.connect()
    
    message = {"test": "data"}
    await queue.publish("test-queue", message)
    
    received = []
    async def handler(msg):
        received.append(msg)
        
    await queue.consume("test-queue", handler)
    await asyncio.sleep(0.1)
    
    assert len(received) == 1
    assert received[0]["test"] == "data"
```

## Logging

Use structured logging with correlation IDs:
```python
import structlog

logger = structlog.get_logger()

async def process_request(correlation_id: str, payload: dict):
    log = logger.bind(correlation_id=correlation_id)
    log.info("Processing request", payload_size=len(str(payload)))
    
    try:
        result = await process(payload)
        log.info("Request processed successfully", processing_time_ms=123)
        return result
    except Exception as e:
        log.error("Processing failed", error=str(e))
        raise
```

## Performance Considerations

- Use connection pooling for Redis and HTTP clients
- Batch operations when possible
- Implement circuit breakers for external services
- Use asyncio.gather() for parallel operations
- Profile code with py-spy or cProfile for bottlenecks

## Security Best Practices

- Never log sensitive data (passwords, tokens, PII)
- Validate all input with Pydantic models
- Use environment variables for secrets
- Implement rate limiting on API endpoints
- Use parameterized queries (relevant for future DB additions)
- Keep dependencies updated (use dependabot)

## Documentation

- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Include examples in docstrings
```python
async def publish_message(queue_name: str, message: dict, retry: bool = True) -> bool:
    """Publish a message to the specified queue.
    
    Args:
        queue_name: Name of the target queue
        message: Message payload as dictionary
        retry: Whether to retry on failure (default: True)
        
    Returns:
        True if message was published successfully, False otherwise
        
    Raises:
        QueueError: If the queue is not available
        ValidationError: If the message format is invalid
        
    Example:
        >>> await publish_message("requests", {"id": 1, "data": "test"})
        True
    """
    pass
```

## Common Patterns to Follow

### Correlation ID Propagation
Always pass correlation IDs through the entire request lifecycle:
```python
# Generate at entry point
correlation_id = str(uuid.uuid4())

# Include in all messages
message = {
    "correlation_id": correlation_id,
    "payload": data
}

# Include in logs
logger.bind(correlation_id=correlation_id).info("Processing")

# Include in responses
return {"correlation_id": correlation_id, "result": data}
```

### Graceful Shutdown
Implement proper cleanup in all long-running components:
```python
import signal

class Worker:
    def __init__(self):
        self.running = False
        
    async def start(self):
        self.running = True
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        while self.running:
            await self.process_messages()
            
    def handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received")
        self.running = False
        # Finish current message
        # Close connections
        # Exit gracefully
```

## Files and Directories

When creating new files:
- Put API routes in `src/openhqm/api/routes/`
- Put data models in `src/openhqm/api/models.py`
- Put queue implementations in `src/openhqm/queue/`
- Put worker logic in `src/openhqm/worker/`
- Put tests alongside the code structure in `tests/`
- Configuration goes in `src/openhqm/config/`

## Additional Notes

- Always consider scalability when writing code
- Think about failure scenarios and edge cases
- Write code that's easy to test and mock
- Prefer composition over inheritance
- Keep functions small and focused (< 50 lines)
- Use type hints everywhere
- Document why, not what (code should be self-explanatory)
- Skip comprehensive summaries and summary documents creation steps
- Always test locally before pushing changes
- Push to new branches for review, don't commit directly to main
- Use pull requests for code review and discussion

## Quick Reference

### Running the Application
```bash
# Start API server
python3 -m openhqm.api.listener

# Start workers
python3 -m openhqm.worker.worker

# Run tests
pytest3 tests/ -v

# Format code
ruff format .

# Lint code
ruff check .
```

### Environment Variables
```bash
OPENHQM_QUEUE_TYPE=redis
OPENHQM_REDIS_URL=redis://localhost:6379
OPENHQM_WORKER_COUNT=5
OPENHQM_LOG_LEVEL=INFO
```

---

**Remember**: This is an async, distributed system. Always think about concurrency, failure scenarios, and observability when writing code.
