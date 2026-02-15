#!/usr/bin/env bash
#
# run-ci-checks.sh - Run all CI checks locally before pushing
#
# This script mirrors the GitHub Actions CI workflow to catch issues early.
# Run this before committing to avoid pipeline failures.
#
# Usage: ./scripts/run-ci-checks.sh [--fix] [--fast]
#   --fix   Automatically fix issues where possible
#   --fast  Skip slow checks (integration tests, type checking)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
FIX_MODE=false
FAST_MODE=false
for arg in "$@"; do
    case $arg in
        --fix) FIX_MODE=true ;;
        --fast) FAST_MODE=true ;;
        --help)
            echo "Usage: $0 [--fix] [--fast]"
            echo "  --fix   Automatically fix issues where possible"
            echo "  --fast  Skip slow checks (integration tests, type checking)"
            exit 0
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Running CI checks locally${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Track failures
CHECKS_FAILED=0

# Function to run a check
run_check() {
    local name="$1"
    local command="$2"
    
    echo -e "${YELLOW}▶ $name${NC}"
    
    if eval "$command"; then
        echo -e "${GREEN}✓ $name passed${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ $name failed${NC}"
        echo ""
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
        return 1
    fi
}

# 1. Check dependencies
echo -e "${BLUE}1. Checking dependencies${NC}"
if ! python3 -c "import ruff" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    python3 -m pip install -q -r requirements.txt -r requirements-dev.txt
fi
echo ""

# 2. Ruff linting
if [ "$FIX_MODE" = true ]; then
    run_check "Ruff lint (with fixes)" "ruff check src/ tests/ --fix"
else
    run_check "Ruff lint" "ruff check src/ tests/"
fi

# 3. Ruff formatting
if [ "$FIX_MODE" = true ]; then
    run_check "Ruff format" "ruff format src/ tests/"
else
    run_check "Ruff format check" "ruff format --check src/ tests/"
fi

# 4. Type checking (skip in fast mode)
if [ "$FAST_MODE" = false ]; then
    run_check "Mypy type checking" "mypy src/"
fi

# 5. Security checks
run_check "Bandit security scan" "bandit -r src/ -q" || true  # Don't fail on security warnings

# 6. Unit tests
echo -e "${BLUE}6. Running tests${NC}"
export PYTHONPATH="${PROJECT_ROOT}/src"
export OPENHQM_QUEUE__REDIS_URL="redis://localhost:6379"
export OPENHQM_CACHE__REDIS_URL="redis://localhost:6379"

if [ "$FAST_MODE" = true ]; then
    run_check "Unit tests (fast)" "pytest tests/ -v -m 'not integration' --tb=short"
else
    run_check "All tests with coverage" "pytest tests/ -v --cov=src/openhqm --cov-report=term-missing --cov-report=html --tb=short"
fi

# 7. Check for large files
run_check "Check for large files" "find . -type f -size +1M -not -path '*/\.*' -not -path '*/htmlcov/*' -not -path '*/node_modules/*' | grep -q . && echo 'Large files found' && exit 1 || exit 0"

# 8. Check for merge conflicts
run_check "Check for merge conflicts" "! grep -r '<<<<<<< HEAD' src/ tests/ || (echo 'Merge conflicts found' && exit 1)"

# Summary
echo -e "${BLUE}========================================${NC}"
if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo -e "${GREEN}Ready to commit and push.${NC}"
    exit 0
else
    echo -e "${RED}✗ $CHECKS_FAILED check(s) failed${NC}"
    echo -e "${YELLOW}Fix the issues above before pushing.${NC}"
    if [ "$FIX_MODE" = false ]; then
        echo -e "${YELLOW}Tip: Run with --fix to auto-fix some issues${NC}"
    fi
    exit 1
fi
