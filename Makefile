.PHONY: help install install-dev clean test test-unit test-integration lint lint-fix format format-check security
.PHONY: ci-checks ci-checks-fast ci-checks-fix install-hooks pre-commit-install pre-commit-run
.PHONY: docker-build docker-up docker-down docker-logs run-api run-worker dev stop coverage

export PYTHONPATH := $(shell pwd)/src

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install package (core = Redis backend)
	pip install .

install-dev: ## Install package editable with dev tools
	pip install -e ".[dev]"

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/

test: ## Run all tests (integration tests auto-skip without Redis)
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests only
	pytest tests/integration/ -v -m integration

lint: ## Run linters
	ruff check src/ tests/
	mypy src/

lint-fix: ## Run linters with auto-fix
	ruff check src/ tests/ --fix
	ruff format src/ tests/

format: ## Format code
	ruff format src/ tests/

format-check: ## Check code formatting
	ruff format --check src/ tests/

security: ## Run security checks
	bandit -r src/ -q

ci-checks: ## Run all CI checks locally (mimics GitHub Actions)
	@./scripts/run-ci-checks.sh

ci-checks-fast: ## Run CI checks without integration tests
	@./scripts/run-ci-checks.sh --fast

ci-checks-fix: ## Run CI checks with auto-fix
	@./scripts/run-ci-checks.sh --fix

install-hooks: ## Install git hooks (pre-push) and pre-commit hooks
	@./scripts/install-hooks.sh

pre-commit-install: ## Install pre-commit hooks
	pip install pre-commit
	pre-commit install

pre-commit-run: ## Run pre-commit hooks on all files
	pre-commit run --all-files

docker-build: ## Build Docker image (QUEUE_BACKEND=all|redis|kafka|sqs|azure|gcp|mqtt|minimal)
	docker build --build-arg QUEUE_BACKEND=$${QUEUE_BACKEND:-all} -t openhqm:latest .

docker-up: ## Start all services with Docker Compose
	docker-compose up -d

docker-down: ## Stop all services
	docker-compose down -v

docker-logs: ## View Docker Compose logs
	docker-compose logs -f

run-api: ## Run the http-to-queue listener locally
	python -m openhqm http-to-queue

run-worker: ## Run the queue-to-http worker locally (set BACKEND_URL)
	OPENHQM_PROXY__BACKEND_URL=$${BACKEND_URL:-http://localhost:8080} python -m openhqm queue-to-http

dev: ## Start Redis and the http-to-queue listener
	docker-compose up redis -d
	sleep 2
	make run-api

stop: ## Stop all running processes
	pkill -f "openhqm http-to-queue" || true
	pkill -f "openhqm queue-to-http" || true

coverage: ## Generate coverage report
	pytest tests/ --cov=openhqm --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"
