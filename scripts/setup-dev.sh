#!/usr/bin/env bash
#
# setup-dev.sh - Set up local development environment
#
# This script installs all dependencies and configures the development
# environment for OpenHQM.
#
# Usage: ./scripts/setup-dev.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OpenHQM Development Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. Check Python version
echo -e "${YELLOW}1. Checking Python version${NC}"
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
REQUIRED_VERSION="3.11"

if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"; then
    echo -e "${GREEN}✓ Python ${PYTHON_VERSION} is installed${NC}"
else
    echo -e "${RED}✗ Python 3.11+ is required, but ${PYTHON_VERSION} is installed${NC}"
    exit 1
fi
echo ""

# 2. Install Python dependencies
echo -e "${YELLOW}2. Installing Python dependencies${NC}"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-dev.txt
echo -e "${GREEN}✓ Python dependencies installed${NC}"
echo ""

# 3. Install pre-commit hooks
echo -e "${YELLOW}3. Installing pre-commit hooks${NC}"
python3 -m pip install pre-commit
pre-commit install
echo -e "${GREEN}✓ Pre-commit hooks installed${NC}"
echo ""

# 4. Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}4. Creating .env file${NC}"
    cat > .env <<EOF
# OpenHQM Configuration
OPENHQM_QUEUE__TYPE=redis
OPENHQM_QUEUE__REDIS_URL=redis://localhost:6379
OPENHQM_CACHE__TYPE=redis
OPENHQM_CACHE__REDIS_URL=redis://localhost:6379
OPENHQM_MONITORING__LOG_LEVEL=INFO
OPENHQM_MONITORING__LOG_FORMAT=json
EOF
    echo -e "${GREEN}✓ .env file created${NC}"
else
    echo -e "${YELLOW}4. .env file already exists (skipping)${NC}"
fi
echo ""

# 5. Initialize secrets baseline
echo -e "${YELLOW}5. Initializing secrets baseline${NC}"
if [ ! -f .secrets.baseline ]; then
    detect-secrets scan > .secrets.baseline || echo -e "${YELLOW}Note: detect-secrets not installed, skipping${NC}"
fi
echo ""

# 6. Check Docker (optional)
echo -e "${YELLOW}6. Checking Docker${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker is installed${NC}"
    echo -e "${BLUE}  Tip: Run 'make docker-up' to start Redis${NC}"
else
    echo -e "${YELLOW}⚠ Docker not found (optional but recommended)${NC}"
    echo -e "${BLUE}  Install Docker to run Redis locally${NC}"
fi
echo ""

# 7. Run initial tests
echo -e "${YELLOW}7. Running initial tests${NC}"
export PYTHONPATH="${PROJECT_ROOT}/src"
if pytest tests/unit/ -v --tb=short; then
    echo -e "${GREEN}✓ Initial tests passed${NC}"
else
    echo -e "${YELLOW}⚠ Some tests failed (this may be expected)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Development environment setup complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Start Redis: ${BLUE}make docker-up${NC}"
echo -e "  2. Run API: ${BLUE}make run-api${NC}"
echo -e "  3. Run tests: ${BLUE}make test${NC}"
echo -e "  4. Before committing: ${BLUE}make ci-checks${NC}"
echo ""
echo -e "Available commands:"
echo -e "  ${BLUE}make help${NC}             - Show all available commands"
echo -e "  ${BLUE}make ci-checks${NC}        - Run all CI checks locally"
echo -e "  ${BLUE}make ci-checks-fix${NC}    - Run CI checks with auto-fix"
echo -e "  ${BLUE}make pre-commit-run${NC}   - Run pre-commit hooks manually"
echo ""
