#!/usr/bin/env bash
#
# install-hooks.sh - Install git hooks for this project
#
# Installs:
#   pre-push  → runs ruff lint, ruff format check, and unit tests
#
# Usage: ./scripts/install-hooks.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ ! -d "$HOOKS_DIR" ]; then
    echo "Error: .git/hooks directory not found. Run this from inside a git repository."
    exit 1
fi

# ---------------------------------------------------------------------------
# pre-push hook
# ---------------------------------------------------------------------------
PRE_PUSH_HOOK="$HOOKS_DIR/pre-push"

cat > "$PRE_PUSH_HOOK" << 'EOF'
#!/usr/bin/env bash
#
# pre-push hook — installed by scripts/install-hooks.sh
#
# Runs fast CI checks (ruff lint, ruff format, unit tests) before every push.
# Skips the hook when the SKIP_HOOKS environment variable is set.
#
# To bypass in emergencies: SKIP_HOOKS=1 git push

set -e

if [ -n "$SKIP_HOOKS" ]; then
    echo "pre-push: SKIP_HOOKS set, skipping checks."
    exit 0
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Activate virtual environment if present
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
    RUFF="$PROJECT_ROOT/.venv/bin/ruff"
    PYTEST="$PROJECT_ROOT/.venv/bin/pytest"
else
    RUFF="ruff"
    PYTEST="pytest"
fi

cd "$PROJECT_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}🔍 pre-push checks running...${NC}"
echo ""

FAILED=0

run_check() {
    local name="$1"; shift
    echo -e "${YELLOW}▶ $name${NC}"
    if "$@"; then
        echo -e "${GREEN}  ✓ passed${NC}"
        echo ""
    else
        echo -e "${RED}  ✗ failed${NC}"
        echo ""
        FAILED=$((FAILED + 1))
    fi
}

export PYTHONPATH="$PROJECT_ROOT/src"

run_check "Ruff lint"         $RUFF check src/ tests/
run_check "Ruff format"       $RUFF format --check src/ tests/
run_check "Unit tests"        $PYTEST tests/ -m "not integration" -q --tb=short --no-header

if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}✗ $FAILED pre-push check(s) failed. Push aborted.${NC}"
    echo -e "${YELLOW}  Fix the issues above, or bypass with: SKIP_HOOKS=1 git push${NC}"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ All pre-push checks passed.${NC}"
echo ""
exit 0
EOF

chmod +x "$PRE_PUSH_HOOK"
echo -e "${GREEN}✓ pre-push hook installed at $PRE_PUSH_HOOK${NC}"

# ---------------------------------------------------------------------------
# Also ensure pre-commit is installed if the tool is available
# ---------------------------------------------------------------------------
if command -v pre-commit &>/dev/null && [ -f "$PROJECT_ROOT/.pre-commit-config.yaml" ]; then
    pre-commit install --hook-type pre-commit -f > /dev/null 2>&1 && \
        echo -e "${GREEN}✓ pre-commit hook (re-)installed${NC}" || true
fi

echo ""
echo -e "${GREEN}All hooks installed successfully.${NC}"
echo -e "  To skip in emergencies: ${YELLOW}SKIP_HOOKS=1 git push${NC}"
