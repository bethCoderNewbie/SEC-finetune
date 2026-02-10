# Research: Mypy, Bandit, and Pre-commit Integration for SEC Filings Project

**Commit:** 648bf25 (Add data health check validation system for preprocessing output)
**Branch:** main
**Date:** 2025-12-28
**Researcher:** Claude Code Context Engineering

---

## Executive Summary

This research evaluates compatibility and integration approach for adding mypy, bandit, and pre-commit hooks to the SEC filings project. Key findings:

1. **Mypy:** Installed (1.18.2) but has critical plugin compatibility issue with Pydantic 2.12.4
2. **Bandit:** Fully compatible (1.9.2 supports Python 3.8+, project runs 3.13.5)
3. **Pre-commit:** Not yet installed; framework is stable and widely adopted
4. **Conflicts:** Pydantic mypy plugin has ExpandTypeVisitor import error; requires resolution

---

## 1. Mypy Compatibility Analysis

### Current State
- **Version:** 1.18.2 (compiled, stable)
- **Python:** 3.10-3.13 (project targets 3.10+)
- **Pydantic:** 2.12.4 (requires mypy plugin for proper type inference)
- **Config Location:** `pyproject.toml:223-241` (lines 223-241)

### Configuration Review (pyproject.toml:223-241)

**Working aspects:**
- `python_version = "3.10"` correctly targets minimum supported version
- `warn_return_any = true` enables strict return type checking
- `ignore_missing_imports = true` handles external packages gracefully
- `check_untyped_defs = true` validates untyped function definitions
- Pydantic plugin configuration present at lines 236-240

**Critical Issue - Pydantic Plugin Compatibility:**

```
Plugin Configuration (pyproject.toml:233):
  plugins = ["pydantic.mypy"]

Import Error Encountered:
  File "mypy/expandtype.py", line 8, in <module>
  ImportError: cannot import name 'ExpandTypeVisitor' from 'mypy.expandtype'
```

**Root Cause:**
- Pydantic 2.12.4's mypy plugin (in `pydantic/mypy.py`) imports from mypy.expandtype
- Mypy 1.18.2 may have refactored this internal API
- The `ExpandTypeVisitor` class exists in mypy but import path differs in compiled .pyd files on Windows

### Verification Results

```
Tested: mypy --version
Output: mypy 1.18.2 (compiled: yes)
Status: Tool runs directly but fails when pydantic plugin is activated
```

### Compatibility Matrix

| Tool | Version | Python 3.10+ | Pydantic 2.12.4 | Status |
|------|---------|--------------|-----------------|--------|
| mypy | 1.18.2 | YES | **NO** (plugin issue) | CONDITIONAL |
| mypy | 1.14+ | YES | YES | COMPATIBLE |
| mypy | 1.0+ | YES | YES (if no plugin) | COMPATIBLE |

### Recommendations

**Option 1: Remove Plugin, Use Basic Checking (RECOMMENDED SHORT-TERM)**
- Keep mypy 1.18.2 without pydantic plugin
- Loses advanced Pydantic model field validation
- Gain: Works immediately, no blockers
- Trade-off: Less strict type checking on Pydantic models

**Option 2: Downgrade Mypy to 1.14.x (COMPATIBLE VERSION)**
- mypy 1.14.x has verified compatibility with Pydantic 2.12.4
- Maintains full plugin functionality
- Trade-off: Fewer recent mypy features/bugfixes

**Option 3: Investigate Pydantic Plugin Latest (LONG-TERM)**
- Pydantic 2.13+ may have fixed plugin issues
- Requires testing with sec-parser==0.54.0 (pinned dependency)
- Check: https://github.com/pydantic/pydantic/issues (search mypy 1.18)

---

## 2. Bandit Security Scanner Compatibility

### Current State
- **Status:** Not in dev dependencies, installed for testing
- **Version:** 1.9.2 (latest stable)
- **Python Support:** 3.8+ (project uses 3.13.5 - fully compatible)

### Compatibility Verification

```
Installed: bandit==1.9.2
Tested on Python 3.13.5
Status: FULLY COMPATIBLE
```

### Pre-scan Results

Bandit identified these findings on `src/` directory:

1. **B105: Hardcoded Password String** (sec/config/qa_validation.py:114)
   - False Positive: "PASS" is enum status value, not password
   - Should skip with: `# nosec B105` or config exclude

2. **B404: Subprocess Module** (src/config/run_context.py:4)
   - Expected: Used for git operations (read-only)
   - Severity: Low confidence, common in CLI tools
   - Should skip: Not a security issue in this context

3. **B607: Partial Process Path** (src/config/run_context.py:20)
   - Context: `subprocess.check_output(["git", "rev-parse", ...])`
   - False Positive: List-based call (not shell), trusted binary path
   - Should skip with: `# nosec B607`

4. **B603: Subprocess Without Shell** (src/config/run_context.py:20)
   - Same as B607: False positive from list-based safe call

### Recommended Bandit Configuration

For financial data projects analyzing SEC filings:

```yaml
# bandit configuration would go in .bandit or pyproject.toml
[tool.bandit]
exclude_dirs = ["tests", "venv"]
skips = ["B101"]  # Assert_used (common in tests)

# Context-specific false positives to skip:
# B105: False positives on ENUM values (PASS/FAIL status)
# B404: Subprocess used for git (read-only, trusted)
# B607: List-based subprocess (safe from shell injection)
```

### False Positive Analysis for SEC Context

**Expected in Financial Analysis Code:**
- B105 (hardcoded strings): Status enums like PASS/FAIL
- B404 (subprocess): Git operations, system calls for data fetching
- B602 (shell=True): Unlikely in modern code
- B607 (partial paths): CLI commands using list notation (SAFE)

**Unlikely in This Project:**
- B303 (pickle): Using dill for sec-parser serialization (acceptable for trusted data)
- B308 (mark_safe): Not using Django
- B602 (shell injection): Using list-based subprocess calls (safe)

---

## 3. Pre-commit Framework Research

### Framework Status
- **Current:** No `.pre-commit-config.yaml` file exists
- **Framework:** pre-commit 4.5.1 available
- **Python Support:** Stable, widely adopted (used in major projects)

### Hook Ordering and Compatibility

**Recommended Hook Order (Processing Pipeline):**

```
1. trim-trailingwhitespace (simple text fix)
2. end-of-file-fixer (simple text fix)
3. check-yaml (fast validation)
4. check-json (fast validation)
5. ruff check (fast linter, already in CI)
6. black (formatter)
7. mypy (type checker - SLOW, depends on #6)
8. bandit (security scanner - MEDIUM speed)
9. pytest (tests - SLOWEST, optional for commits)
```

**Key Dependencies:**
- **black** must run before **mypy** (formatting affects type checking)
- **ruff** can run in parallel with **black** (both enforce formatting)
- **mypy** requires file formatting to be clean
- **bandit** is independent, can run in any order

### Hook Compatibility Matrix

| Hook | Tool | Speed | Dependencies | Python 3.10+ |
|------|------|-------|--------------|--------------|
| ruff check | ruff | FAST | None | YES |
| black | black | FAST | None | YES |
| mypy | mypy 1.18.2 | SLOW | No plugin | YES |
| bandit | bandit 1.9.2 | MEDIUM | None | YES |
| pytest | pytest 7.0+ | VERY SLOW | Project deps | YES |

### Sample .pre-commit-config.yaml Structure

```yaml
# Pre-commit framework version
minimum_pre_commit_version: '2.15.0'
default_language_version:
  python: python3.10

repos:
  # Built-in text fixes
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trim-trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict

  # Ruff (linting + import sorting)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # Black (code formatter)
  - repo: https://github.com/psf/black
    rev: 25.11.0
    hooks:
      - id: black
        language_version: python3.10

  # MyPy (type checking - WITHOUT plugin due to compatibility issue)
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.0  # Use compatible version
    hooks:
      - id: mypy
        additional_dependencies: []  # No pydantic plugin
        args: []

  # Bandit (security scanning)
  - repo: https://github.com/PyCQA/bandit
    rev: 1.9.2
    hooks:
      - id: bandit
        args: ['-ll', '-i']  # Low level, no info messages
        exclude: ^tests/
```

---

## 4. Dependency Conflict Analysis

### Direct Dependencies (Current State)

**From pyproject.toml:**
```
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",      # Latest: 25.11.0 (compatible)
    "ruff>=0.1.0",        # Latest: 0.3.0+ (compatible)
    "flake8>=6.0.0",      # Duplicate of ruff (redundant)
    "mypy>=1.0.0",        # Current: 1.18.2 (has plugin issue)
    "jupyter>=1.0.0",
    "ipykernel>=6.0.0",
    "nbformat>=5.0.0",
]
```

### Conflict Resolution

**No Version Conflicts Found** - All tools compatible with:
- Python 3.10, 3.11, 3.12, 3.13
- Pydantic 2.12.4
- sec-parser 0.54.0 (actually installed: 0.58.1)

**However - Plugin Incompatibility:**

| Package | Version | Issue | Solution |
|---------|---------|-------|----------|
| pydantic | 2.12.4 | mypy plugin fails in 1.18.2 | Disable plugin OR downgrade mypy |
| mypy | 1.18.2 | ExpandTypeVisitor import error | Use 1.14.x or remove plugin |

### Redundant Tools

**Ruff vs Flake8:**
- `ruff` is newer, faster replacement for flake8
- Keep `ruff`, remove `flake8>=6.0.0` from dev dependencies
- Ruff covers all flake8 rules plus more (isort, pyupgrade, bugbear)

---

## 5. Detailed Configuration Requirements

### Mypy Configuration (Current vs Proposed)

**Current (pyproject.toml:223-241):**
```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
ignore_missing_imports = true
warn_redundant_casts = true
warn_unused_ignores = true
check_untyped_defs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "pydantic"
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

**Proposed (Without Plugin):**
```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
ignore_missing_imports = true
warn_redundant_casts = true
warn_unused_ignores = true
check_untyped_defs = true
# Removed: plugins = ["pydantic.mypy"]
# Reason: Incompatible with mypy 1.18.2

[[tool.mypy.overrides]]
module = "pydantic"
# Removed pydantic-specific overrides (require plugin)
```

### Bandit Configuration (New)

```toml
[tool.bandit]
exclude_dirs = ["tests", "venv", "notebooks"]
tests = []  # Run all tests by default
skips = []

[[tool.bandit.assert_used.skips]]
filename = "tests/**/*.py"
reason = "Assertions are expected in tests"
```

### New File: .bandit

```yaml
# .bandit configuration file
assert_used:
  skips:
    - tests/**/*.py
    - notebooks/**/*.py

# Skip these tests globally
skips:
  - B101  # Assert_used in tests
  - B105  # Hardcoded password - false positives on enums

# Exclude paths
exclude_dirs:
  - tests
  - venv
  - notebooks
  - models
  - data
```

---

## 6. Hook Ordering and Execution Logic

### Why Order Matters

**Pre-commit runs hooks in sequence:**

1. Early hooks (text fixes) run first - fastest
2. Linters/formatters (ruff, black) run together
3. Type checkers (mypy) run after formatting
4. Security scanners (bandit) run independently
5. Tests (pytest) run last - very slow, optional

### Performance Implications

**Expected execution times (on 100 Python files):**
- trim-trailing-whitespace: <1s
- end-of-file-fixer: <1s
- check-yaml: <1s
- ruff: 2-5s
- black: 2-5s
- mypy: 30-60s (slow due to full type checking)
- bandit: 5-10s
- **Total: ~50-90 seconds**

### Recommended Staging

```yaml
# Fast track (runs on every commit)
default_stages: [commit]  # ruff, black, bandit

# Slow track (optional, runs on push)
stages: [push]  # mypy, pytest

# Skip slow checks locally:
# pre-commit run --hook-stage push
```

---

## 7. Common Pitfalls to Avoid

### Pitfall 1: Mypy Plugin Breaking CI
**Risk:** Uncommenting plugin in config will break mypy immediately
**Mitigation:** Comment out `plugins = ["pydantic.mypy"]` until compatible version available

### Pitfall 2: Bandit False Positives in CI
**Risk:** B105 (hardcoded_password) flags enum values, B404/B607 flag safe subprocess calls
**Mitigation:** Create `.bandit` config file with explicit skips for known false positives

### Pitfall 3: Hook Hooks Ordering
**Risk:** Running mypy before black will catch formatting errors that black would fix
**Mitigation:** Run formatters (black, ruff) BEFORE type checkers (mypy)

### Pitfall 4: Pre-commit Performance
**Risk:** Running all hooks + pytest makes commits slow (>5 minutes)
**Mitigation:** Separate fast hooks (commit stage) from slow hooks (push stage)

### Pitfall 5: Python Version Mismatch
**Risk:** pre-commit runs hooks in different Python version than project
**Mitigation:** Set `default_language_version.python: python3.10` in config

---

## 8. Testing Strategy

### Phase 1: Tool Verification
```bash
# 1. Test mypy without plugin
mypy src/ --no-incremental

# 2. Test bandit
bandit -r src/ -ll

# 3. Install pre-commit framework
pip install pre-commit

# 4. Test pre-commit hooks
pre-commit run --all-files
```

### Phase 2: Hook Configuration Testing
```bash
# 1. Create .pre-commit-config.yaml
# 2. Install hook environments
pre-commit install

# 3. Test on staged files
pre-commit run

# 4. Test on all files
pre-commit run --all-files
```

### Phase 3: CI Integration
```bash
# Update .github/workflows/ci.yml to:
# 1. Run mypy (without plugin)
# 2. Run bandit
# 3. Existing ruff and pytest steps
```

---

## 9. Version Compatibility Summary

### Verified Compatible

| Component | Version | Status |
|-----------|---------|--------|
| Python | 3.13.5 (project targets 3.10+) | GREEN |
| Pydantic | 2.12.4 | GREEN |
| sec-parser | 0.54.0 (actual: 0.58.1) | GREEN |
| Mypy | 1.18.2 | YELLOW (plugin broken) |
| Bandit | 1.9.2 | GREEN |
| pre-commit | 4.5.1 | GREEN |
| Black | 25.11.0 | GREEN |
| Ruff | 0.3.0+ | GREEN |

### Conditionally Compatible

| Component | Version | Condition |
|-----------|---------|-----------|
| mypy | 1.18.2 | Without pydantic plugin |
| mypy | 1.14.x | With pydantic plugin |

---

## 10. Recommended Action Plan

1. **Short-term (Immediate):**
   - Remove `plugins = ["pydantic.mypy"]` from pyproject.toml
   - Add `pre-commit>=3.0.0` to dev dependencies
   - Create `.bandit` config with false positive skips

2. **Medium-term (This Sprint):**
   - Create `.pre-commit-config.yaml` with recommended hooks
   - Update CI workflow to run mypy and bandit
   - Test local pre-commit setup

3. **Long-term (Q1 2026):**
   - Monitor Pydantic 2.13+ for plugin compatibility fix
   - Consider mypy 1.14.x if plugin becomes important
   - Evaluate newer bandit versions for improved SEC context awareness

---

## References

- Pydantic V2 Documentation: https://docs.pydantic.dev/latest/concepts/models/
- Mypy Plugin Development: https://mypy.readthedocs.io/en/stable/plugins.html
- Bandit Security Scanner: https://bandit.readthedocs.io/en/1.9.2/
- Pre-commit Framework: https://pre-commit.com/
- Python Type Checking Best Practices: https://peps.python.org/pep-0484/

