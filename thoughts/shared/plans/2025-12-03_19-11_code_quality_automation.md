# Plan: Code Quality Automation Scripts

**Date:** 2025-12-03
**Goal:** Automate linting audits and common fixes

---

## Scripts to Create

### 1. `hack/lint_audit.py` - Full Codebase Lint Report

**Purpose:** Generate a summary report of all lint issues across the codebase

```python
# Inputs: Optional path filter (default: src/, tests/)
# Outputs: JSON report + console summary
# Features:
#   - Run pylint + flake8 on all Python files
#   - Aggregate by issue type and severity
#   - Track scores over time (append to logs/lint_history.json)
#   - Exit code 1 if below threshold
```

**Usage:**
```bash
python hack/lint_audit.py                    # Full audit
python hack/lint_audit.py src/preprocessing  # Single module
python hack/lint_audit.py --threshold 9.0    # Fail if score < 9.0
```

---

### 2. `hack/lint_fix.py` - Auto-fix Common Issues

**Purpose:** Automatically fix safe, mechanical lint issues

**Safe to auto-fix:**
- Trailing whitespace (W293, C0303)
- Missing encoding in `open()` (W1514)
- Import order (C0411) - use `isort`
- Unused imports (F401, W0611) - use `autoflake`
- Line too long (E501) - basic cases only

**NOT auto-fixed (require judgment):**
- Broad exception catching
- Too many arguments/locals
- Complex refactoring

```bash
python hack/lint_fix.py src/preprocessing/parser.py      # Fix single file
python hack/lint_fix.py --dry-run                        # Preview changes
python hack/lint_fix.py --all                            # Fix all src/ and tests/
```

---

### 3. `hack/lint_check.sh` - Pre-commit Hook

**Purpose:** Fast lint check for staged files only

```bash
#!/bin/bash
# Run on staged .py files only
# Exit 1 if flake8 errors (blocks commit)
# Warn on pylint score < 9.0 (doesn't block)
```

**Integration:**
```bash
# Add to .git/hooks/pre-commit or use pre-commit framework
cp hack/lint_check.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## Implementation Priority

| Script | Effort | Value | Priority |
|--------|--------|-------|----------|
| `lint_audit.py` | Medium | High | 1 |
| `lint_check.sh` | Low | High | 2 |
| `lint_fix.py` | High | Medium | 3 |

---

## Configuration Files to Add

### `pyproject.toml` additions
```toml
[tool.pylint.messages_control]
disable = [
    "too-few-public-methods",
    "too-many-arguments",
]

[tool.pylint.format]
max-line-length = 100

[tool.flake8]
max-line-length = 100
extend-ignore = ["E402"]  # Allow imports after sys.path modification
per-file-ignores = [
    "tests/*:W0718",  # Allow broad exceptions in tests
]
```

### `.flake8` (if pyproject.toml not supported)
```ini
[flake8]
max-line-length = 100
extend-ignore = E402
per-file-ignores =
    tests/*:W0718
```

---

## Success Criteria

- [ ] `lint_audit.py` runs in < 30 seconds for full codebase
- [ ] Pre-commit hook runs in < 5 seconds for typical commit
- [ ] All `src/` files maintain pylint score >= 9.0
- [ ] Zero flake8 errors on main branch
- [ ] Lint history tracked for trend analysis
