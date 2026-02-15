.PHONY: help install install-dev clean test lint format docker-build docker-up docker-down run-api run-worker
.PHONY: ci-checks ci-checks-fix lint-fix pre-commit-install pre-commit-run

# Environment setup
PYTHON := python3
PIP := $(PYTHON) -m pip
PYTEST := pytest
RUFF := ruff
MYPY := mypy
export PYTHONPATH := $(shell pwd)/src

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install -e .

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/

test: ## Run all tests
	pytest tests/ -v --cov=openhqm --cov-report=term-missing

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests only
	pytest tests/integration/ -v -m integration

lint: ## Run linters
	$(RUFF) check src/ tests/
	$(MYPY) src/

lint-fix: ## Run linters with auto-fix
	$(RUFF) check src/ tests/ --fix
	$(RUFF) format src/ tests/

format: ## Format code
	$(RUFF) format src/ tests/

format-check: ## Check code formatting
	$(RUFF) format --check src/ tests/

security: ## Run security checks
	bandit -r src/ -q
	@echo "Security scan complete"

# CI/CD targets
ci-checks: ## Run all CI checks locally (mimics GitHub Actions)
	@echo "==> Running CI checks..."
	@chmod +x scripts/run-ci-checks.sh
	@./scripts/run-ci-checks.sh

ci-checks-fix: ## Run CI checks with auto-fix
	@echo "==> Running CI checks with auto-fix..."
	@chmod +x scripts/run-ci-checks.sh
	@./scripts/run-ci-checks.sh --fix

ci-checks-fast: ## Run fast CI checks (skip integration tests and mypy)
	@echo "==> Running fast CI checks..."
	@chmod +x scripts/run-ci-checks.sh
	@./scripts/run-ci-checks.sh --fast

# Pre-commit hooks
pre-commit-install: ## Install pre-commit hooks
	$(PIP) install pre-commit
	pre-commit install
	@echo "Pre-commit hooks installed successfully"

pre-commit-run: ## Run pre-commit hooks on all files
	pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks to latest versions
	pre-commit autoupdate

docker-build: ## Build Docker image
	docker build -t openhqm:latest .

docker-up: ## Start all services with Docker Compose
	docker-compose up -d

docker-down: ## Stop all services
	docker-compose down -v

docker-logs: ## View Docker Compose logs
	docker-compose logs -f

run-api: ## Run API server locally
	python -m openhqm.api.listener

run-worker: ## Run worker locally
	python -m openhqm.worker.worker

run-all: ## Run API and worker in background
	python -m openhqm.api.listener &
	sleep 2
	python -m openhqm.worker.worker worker-1 &

dev: ## Start development environment
	docker-compose up redis -d
	sleep 2
	make run-api

stop: ## Stop all running processes
	pkill -f "openhqm.api.listener" || true
	pkill -f "openhqm.worker.worker" || true

coverage: ## Generate coverage report
	pytest tests/ --cov=openhqm --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

docs: ## Generate documentation (if using mkdocs)
	mkdocs serve

requirements: ## Update requirements files
	pip-compile requirements.in -o requirements.txt
	pip-compile requirements-dev.in -o requirements-dev.txt
