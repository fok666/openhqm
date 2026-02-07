.PHONY: help install install-dev clean test lint format docker-build docker-up docker-down run-api run-worker

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
	ruff check src/ tests/
	mypy src/

format: ## Format code
	ruff format src/ tests/

format-check: ## Check code formatting
	ruff format --check src/ tests/

security: ## Run security checks
	bandit -r src/
	safety check

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
