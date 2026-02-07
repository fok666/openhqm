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
git commit -m "feat: add new feature description"
```

**Important:** Use [Conventional Commits](https://www.conventionalcommits.org/) format for all commit messages. This is required for automatic semantic versioning and changelog generation.

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type** (required):
- `feat:` - New features (triggers MINOR version bump)
- `fix:` - Bug fixes (triggers PATCH version bump)
- `docs:` - Documentation changes only
- `style:` - Code style changes (formatting, no logic change)
- `refactor:` - Code refactoring (no feature or bug fix)
- `perf:` - Performance improvements
- `test:` - Adding or updating tests
- `build:` - Build system or dependency changes
- `ci:` - CI/CD configuration changes
- `chore:` - Other changes that don't modify src or test files

**Scope** (optional): Component affected (e.g., api, queue, worker, cache)

**Breaking Changes**: Add `BREAKING CHANGE:` in footer or `!` after type (triggers MAJOR version bump)

### Examples

```bash
# Feature (minor version bump: 1.2.0 → 1.3.0)
git commit -m "feat(api): add endpoint for batch request submission"

# Bug fix (patch version bump: 1.2.0 → 1.2.1)
git commit -m "fix(worker): resolve timeout handling in proxy mode"

# Breaking change (major version bump: 1.2.0 → 2.0.0)
git commit -m "feat(queue)!: change message format for better compatibility

BREAKING CHANGE: Queue message format now requires 'version' field"

# Documentation (no version bump)
git commit -m "docs: update proxy mode configuration examples"

# Multiple paragraphs
git commit -m "fix(cache): prevent memory leak in connection pool

Redis connections were not being properly released under high load.
This change ensures all connections are returned to the pool.

Closes #123"
```

### Commit Best Practices

- Keep the subject line under 72 characters
- Use imperative mood ("add" not "added" or "adds")
- Don't end the subject line with a period
- Separate subject from body with a blank line
- Wrap the body at 72 characters
- Use the body to explain what and why, not how
- Reference issues and pull requests in the footer

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

Releases are automated using [Python Semantic Release](https://python-semantic-release.readthedocs.io/).

### Automatic Releases

When commits are pushed to the `main` branch:
1. Semantic Release analyzes commit messages
2. Determines the next version based on commit types:
   - `feat:` → MINOR version bump (1.2.0 → 1.3.0)
   - `fix:` / `perf:` → PATCH version bump (1.2.0 → 1.2.1)
   - `BREAKING CHANGE:` or `!` → MAJOR version bump (1.2.0 → 2.0.0)
3. Updates version in `pyproject.toml` and `__init__.py`
4. Generates CHANGELOG.md from commit messages
5. Creates a Git tag (e.g., `v1.3.0`)
6. Creates a GitHub Release with release notes
7. Triggers Docker image build and push to registry

### Manual Release Preparation

If you need to prepare a release manually:

```bash
# Install semantic-release
pip install python-semantic-release

# Preview what the next version will be
semantic-release version --print

# Create a release (updates files and creates tag)
semantic-release version

# Push the release
git push --follow-tags origin main
```

### Pre-releases

To create pre-release versions (e.g., release candidates):

1. Use the `develop` branch
2. Commits will create pre-release versions: `1.3.0-rc.1`, `1.3.0-rc.2`, etc.
3. Merge to `main` to create the stable release

### Version Branches

- `main` - Stable releases (e.g., `1.2.0`, `1.3.0`)
- `develop` - Pre-releases (e.g., `1.3.0-rc.1`)

### Docker Images

Released versions automatically build and push Docker images:
- Full version tag: `ghcr.io/owner/repo:1.2.3`
- Minor version tag: `ghcr.io/owner/repo:1.2`
- Major version tag: `ghcr.io/owner/repo:1`
- Latest tag: `ghcr.io/owner/repo:latest`
- Queue-specific variants: `-redis`, `-kafka`, `-sqs`, etc.
- Architecture-specific: `-amd64`, `-arm64`

All images are multi-architecture (amd64 and arm64).

### Changelog

The CHANGELOG.md is automatically generated from commit messages. Structure your commits properly to ensure accurate changelogs!

## Getting Help

* Check the [documentation](docs/)
* Look at [existing issues](https://github.com/yourusername/openhqm/issues)
* Ask in [GitHub Discussions](https://github.com/yourusername/openhqm/discussions)

## Recognition

Contributors will be recognized in the README.md and release notes.

Thank you for contributing to OpenHQM! 🎉
