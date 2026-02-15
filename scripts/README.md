# Scripts

This directory contains utility scripts for development and CI/CD.

## Available Scripts

### `run-ci-checks.sh`

Run all CI checks locally before pushing to catch issues early.

**Usage:**
```bash
./scripts/run-ci-checks.sh [--fix] [--fast]
```

**Options:**
- `--fix`: Automatically fix issues where possible (linting, formatting)
- `--fast`: Skip slow checks (integration tests, type checking)

**What it checks:**
- Ruff linting
- Ruff formatting
- Mypy type checking
- Bandit security scanning
- Unit tests with coverage
- Integration tests (unless --fast)
- Large files check
- Merge conflicts check

**Examples:**
```bash
# Run all checks
./scripts/run-ci-checks.sh

# Run with auto-fix
./scripts/run-ci-checks.sh --fix

# Quick check during development
./scripts/run-ci-checks.sh --fast

# Auto-fix and fast mode
./scripts/run-ci-checks.sh --fix --fast
```

### `setup-dev.sh`

Set up the local development environment.

**Usage:**
```bash
./scripts/setup-dev.sh
```

**What it does:**
1. Validates Python version (3.11+)
2. Installs production and development dependencies
3. Installs pre-commit hooks
4. Creates `.env` file with default configuration
5. Initializes secrets baseline
6. Checks Docker availability
7. Runs initial tests

**When to use:**
- First time setting up the project
- After cloning the repository
- When dependencies are updated
- To reset your development environment

### `build-multiarch.sh`

Build multi-architecture Docker images (AMD64, ARM64).

See [docs/MULTI_ARCH_BUILD.md](../docs/MULTI_ARCH_BUILD.md) for details.

## Quick Start

### New Developer Setup

```bash
# 1. Clone the repository
git clone https://github.com/fok666/openhqm.git
cd openhqm

# 2. Run setup script
./scripts/setup-dev.sh

# 3. Start development services
make docker-up

# 4. Run tests
make test
```

### Before Committing

```bash
# Run all CI checks with auto-fix
./scripts/run-ci-checks.sh --fix

# Or use Make target
make ci-checks-fix
```

### Pre-commit Hooks

Pre-commit hooks are automatically installed by `setup-dev.sh`. They run on every commit to catch issues early.

**Manual pre-commit commands:**
```bash
# Install hooks
make pre-commit-install

# Run hooks on all files
make pre-commit-run

# Update hooks to latest versions
make pre-commit-update
```

### Troubleshooting

**Permission denied when running scripts:**
```bash
chmod +x scripts/*.sh
```

**Pre-commit hooks not running:**
```bash
pre-commit install
```

**Tests failing locally:**
```bash
# Ensure Redis is running
make docker-up

# Check environment variables
cat .env

# Reinstall dependencies
make install-dev
```

## CI/CD Integration

These scripts mirror the GitHub Actions workflows in `.github/workflows/ci.yml`. Running them locally ensures your changes will pass CI.

**CI Workflow Steps:**
1. Lint and Format Check
2. Type Checking (mypy)
3. Security Scanning (bandit)
4. Unit Tests
5. Integration Tests (if Redis available)
6. Coverage Report

**Local equivalent:**
```bash
make ci-checks
```

## Additional Resources

- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [docs/QUICK_REFERENCE.md](../docs/QUICK_REFERENCE.md) - Command cheat sheet
- [docs/QUICKSTART.md](../docs/QUICKSTART.md) - 5-minute quickstart guide
- [Makefile](../Makefile) - All available make targets
