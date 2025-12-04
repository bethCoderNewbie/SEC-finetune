---
date: 2025-12-03T18:13:00-06:00
researcher: bethCoderNewbie
git_commit: f599254
branch: main
repository: SEC finetune
topic: "Legacy Config Imports Audit & CI/CD Linting Analysis"
tags: [research, config, deprecation, linting, ci-cd, migration]
status: complete
last_updated: 2025-12-03
last_updated_by: bethCoderNewbie
related_research: thoughts/shared/research/2025-12-03_17-51-31_config_restructure.md
---

# Research: Legacy Config Imports Audit & CI/CD Linting Analysis

**Date**: 2025-12-03T18:13:00-06:00
**Researcher**: bethCoderNewbie
**Git Commit**: f599254
**Branch**: main
**Repository**: SEC finetune

## Research Questions

1. **Testing**: Are there existing tests that import legacy constants directly?
2. **CI/CD**: Does the project have linting rules that would catch deprecated imports?

## Summary

| Question | Answer |
|----------|--------|
| Tests importing legacy constants? | **No** - Tests use `settings` object only |
| Source files importing legacy constants? | **Yes** - 2 files use legacy imports |
| CI/CD with deprecation linting? | **No** - No GitHub Actions, no deprecation rules |
| Linting tools configured? | **Yes** - ruff, flake8, mypy, black in `pyproject.toml` |

## Detailed Findings

### 1. Test Files Analysis

**Result**: No legacy constant imports in tests.

**File**: `tests/conftest.py:24`
```python
from src.config import settings  # ✅ Modern pattern
```

All test files use the modern `settings` object pattern. No migration needed for tests.

### 2. Source Files Using Legacy Imports

**Found 2 files with legacy constant imports:**

| File | Line | Import | Status |
|------|------|--------|--------|
| `src/preprocessing/parser.py` | 556 | `from src.config import PARSED_DATA_DIR` | ⚠️ Needs migration |
| `src/preprocessing/parser.py` | 665 | `from src.config import RAW_DATA_DIR, PARSED_DATA_DIR, ensure_directories` | ⚠️ Needs migration |
| `src/preprocessing/segmenter.py` | 9 | `from src.config import MIN_SEGMENT_LENGTH, MAX_SEGMENT_LENGTH` | ⚠️ Needs migration |

### 3. Files Using Modern Pattern (No Changes Needed)

| File | Line | Import |
|------|------|--------|
| `src/analysis/inference.py` | 10 | `from src.config import settings` |
| `src/analysis/taxonomies/taxonomy_manager.py` | 32 | `from src.config import settings` |
| `src/features/sentiment.py` | 31 | `from src.config import settings` |
| `src/visualization/app.py` | 14 | `from src.config import settings` |
| `tests/conftest.py` | 24 | `from src.config import settings` |

### 4. CI/CD Analysis

**GitHub Actions**: Not configured (`.github/` directory does not exist)

**Linting Tools in `pyproject.toml`:**

| Tool | Version | Purpose | Deprecation Detection |
|------|---------|---------|----------------------|
| ruff | >=0.1.0 | Linting | ❌ No deprecation rules |
| flake8 | >=6.0.0 | Linting | ❌ No deprecation rules |
| mypy | >=1.0.0 | Type checking | ❌ No deprecation rules |
| black | >=23.0.0 | Formatting | N/A |
| pytest | >=7.0.0 | Testing | ⚠️ Can warn via `-W` flag |

**Ruff Configuration** (`pyproject.toml:239-258`):
```toml
[tool.ruff]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
```

**Missing**: No `D` (pydocstyle) or `RUF` rules that could catch deprecation patterns.

## Code References

### Files Requiring Migration

**`src/preprocessing/parser.py:556`**:
```python
from src.config import PARSED_DATA_DIR  # Deprecated
# Should be:
from src.config import settings
# Use: settings.paths.parsed_data_dir
```

**`src/preprocessing/parser.py:665`**:
```python
from src.config import RAW_DATA_DIR, PARSED_DATA_DIR, ensure_directories  # Deprecated
# Should be:
from src.config import settings, ensure_directories
# Use: settings.paths.raw_data_dir, settings.paths.parsed_data_dir
```

**`src/preprocessing/segmenter.py:9`**:
```python
from src.config import MIN_SEGMENT_LENGTH, MAX_SEGMENT_LENGTH  # Deprecated
# Should be:
from src.config import settings
# Use: settings.preprocessing.min_segment_length, settings.preprocessing.max_segment_length
```

## Recommendations

### Immediate Actions

1. **Migrate 2 files** to use `settings` object:
   - `src/preprocessing/parser.py` (2 import statements)
   - `src/preprocessing/segmenter.py` (1 import statement)

2. **Enable pytest deprecation warnings** in `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   filterwarnings = [
       "error::DeprecationWarning",  # Treat deprecation warnings as errors
   ]
   ```

### Future CI/CD Setup

When GitHub Actions is added, include:

```yaml
# .github/workflows/lint.yml
- name: Run pytest with deprecation warnings
  run: pytest -W error::DeprecationWarning tests/

- name: Check for deprecated imports
  run: |
    # Fail if legacy imports found (excluding config/ itself)
    ! grep -r "from src.config import [A-Z_]" src/ --include="*.py" | grep -v "src/config/"
```

### Ruff Enhancement (Optional)

Add custom rule to detect legacy imports:
```toml
[tool.ruff.lint.per-file-ignores]
# Could add banned-api rules in future ruff versions
```

## Migration Impact Assessment

| Metric | Value |
|--------|-------|
| Files to migrate | 2 |
| Import statements to change | 3 |
| Tests affected | 0 |
| Risk level | Low |
| Estimated effort | 10 minutes |

## Open Questions

None - all questions answered.
