# Contributing to OpenHQM

First off, thank you for considering contributing to OpenHQM! It's people like you that make OpenHQM such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to [tbd].

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps which reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include logs, screenshots, or animated GIFs if relevant**

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and explain which behavior you expected to see instead**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Follow the Python style guide (PEP 8)
* Include appropriate test coverage
* Update documentation as needed
* End all files with a newline

## Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/yourusername/openhqm.git
cd openhqm
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
make install-dev
```

4. **Start Redis for local development**

```bash
docker-compose up redis -d
```

5. **Run tests to verify setup**

```bash
make test
```

## Development Workflow

1. **Create a branch**

```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes**

Write your code following the project's coding standards.

3. **Write tests**

Add tests for your changes. We aim for >80% code coverage.

```bash
make test
```

4. **Format and lint your code**

```bash
make format
make lint
```

5. **Run security checks**

```bash
make security
```

6. **Commit your changes**

```bash
git add .
git commit -m "Add feature: description of your changes"
```

Use clear and meaningful commit messages. Follow conventional commits format:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for adding tests
- `refactor:` for code refactoring
- `chore:` for maintenance tasks

7. **Push to your fork**

```bash
git push origin feature/your-feature-name
```

8. **Create a Pull Request**

Go to the repository on GitHub and create a pull request from your branch.

## Coding Standards

### Python Style

* Follow PEP 8 style guide
* Use type hints for all function signatures
* Maximum line length: 100 characters
* Use async/await for all I/O operations
* Write docstrings for all public functions and classes (Google style)

### Example

```python
async def process_message(
    message: Dict[str, Any],
    timeout: int = 300
) -> Optional[Dict[str, Any]]:
    """
    Process a message with optional timeout.
    
    Args:
        message: Message payload to process
        timeout: Processing timeout in seconds
        
    Returns:
        Processing result or None if failed
        
    Raises:
        TimeoutError: If processing exceeds timeout
        ValidationError: If message is invalid
    """
    pass
```

### Testing

* Write unit tests for all new functions
* Write integration tests for component interactions
* Use descriptive test names: `test_<what>_<condition>_<expected_result>`
* Mock external dependencies in unit tests
* Use pytest fixtures for common test setup

### Example Test

```python
@pytest.mark.asyncio
async def test_process_message_valid_input_returns_result():
    """Test that valid message is processed successfully."""
    message = {"operation": "test", "data": "value"}
    processor = MessageProcessor()
    
    result = await processor.process(message)
    
    assert result is not None
    assert "output" in result
```

## Project Structure

```
openhqm/
├── src/openhqm/          # Main package
│   ├── api/              # HTTP API layer
│   ├── queue/            # Queue implementations
│   ├── worker/           # Worker logic
│   ├── cache/            # Caching layer
│   ├── config/           # Configuration
│   └── utils/            # Utilities
├── tests/                # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
├── docs/                 # Documentation
└── .github/              # GitHub workflows
```

## Adding New Queue Backends

To add support for a new message queue backend:

1. Create a new file in `src/openhqm/queue/` (e.g., `kafka_queue.py`)
2. Implement the `MessageQueueInterface`
3. Add factory logic in `queue/factory.py`
4. Add configuration in `config/settings.py`
5. Write unit and integration tests
6. Update documentation

## Running Locally

### Start API Server

```bash
make run-api
```

### Start Worker

```bash
make run-worker
```

### Start All Services with Docker

```bash
make docker-up
```

### View Logs

```bash
make docker-logs
```

## Testing

### Run All Tests

```bash
make test
```

### Run Specific Test Types

```bash
make test-unit           # Unit tests only
make test-integration    # Integration tests only
```

### Generate Coverage Report

```bash
make coverage
```

## Documentation

* Update README.md for user-facing changes
* Update SDD.md for architectural changes
* Add docstrings to all public APIs
* Update examples if API changes

## Release Process

1. Update version in `pyproject.toml` and `src/openhqm/__init__.py`
2. Update CHANGELOG.md
3. Create a git tag: `git tag -a v0.2.0 -m "Release v0.2.0"`
4. Push tag: `git push origin v0.2.0`
5. GitHub Actions will automatically build and release

## Getting Help

* Check the [documentation](docs/)
* Look at [existing issues](https://github.com/yourusername/openhqm/issues)
* Ask in [GitHub Discussions](https://github.com/yourusername/openhqm/discussions)

## Recognition

Contributors will be recognized in the README.md and release notes.

Thank you for contributing to OpenHQM! 🎉
