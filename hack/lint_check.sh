#!/bin/bash
# Pre-commit hook for fast lint checking on staged Python files
#
# Installation:
#   cp hack/lint_check.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Or use with pre-commit framework in .pre-commit-config.yaml

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get staged Python files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)

if [ -z "$STAGED_FILES" ]; then
    echo -e "${GREEN}No Python files staged. Skipping lint check.${NC}"
    exit 0
fi

echo "Checking staged Python files..."
echo "$STAGED_FILES"
echo ""

# Track if we should block commit
BLOCK_COMMIT=0
WARN_COMMIT=0

# Run flake8 (blocking - errors prevent commit)
echo -e "${YELLOW}Running flake8...${NC}"
if ! python -m flake8 --max-line-length=100 $STAGED_FILES; then
    echo -e "${RED}Flake8 errors found. Please fix before committing.${NC}"
    BLOCK_COMMIT=1
else
    echo -e "${GREEN}Flake8: OK${NC}"
fi

echo ""

# Run pylint (warning only - doesn't block commit)
echo -e "${YELLOW}Running pylint...${NC}"
PYLINT_OUTPUT=$(python -m pylint --max-line-length=100 --output-format=text $STAGED_FILES 2>&1 || true)

# Extract score
SCORE=$(echo "$PYLINT_OUTPUT" | grep "rated at" | sed 's/.*rated at \([0-9.]*\).*/\1/' || echo "0")

if [ -n "$SCORE" ]; then
    # Compare score (bash doesn't do float comparison well, use python)
    SCORE_OK=$(python -c "print(1 if float('$SCORE') >= 9.0 else 0)" 2>/dev/null || echo "0")

    if [ "$SCORE_OK" = "1" ]; then
        echo -e "${GREEN}Pylint score: $SCORE/10 (OK)${NC}"
    else
        echo -e "${YELLOW}Pylint score: $SCORE/10 (below 9.0 threshold)${NC}"
        WARN_COMMIT=1
    fi
else
    echo -e "${YELLOW}Could not determine pylint score${NC}"
fi

echo ""

# Final verdict
if [ $BLOCK_COMMIT -eq 1 ]; then
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}COMMIT BLOCKED: Fix flake8 errors first${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi

if [ $WARN_COMMIT -eq 1 ]; then
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}WARNING: Pylint score below threshold${NC}"
    echo -e "${YELLOW}Consider improving code quality${NC}"
    echo -e "${YELLOW}========================================${NC}"
fi

echo -e "${GREEN}Lint check passed.${NC}"
exit 0
