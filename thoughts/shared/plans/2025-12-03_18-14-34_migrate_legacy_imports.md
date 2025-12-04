---
date: 2025-12-03T18:14:34-06:00
researcher: bethCoderNewbie
git_commit: f599254
branch: main
repository: SEC finetune
topic: "Migrate Legacy Config Imports"
tags: [plan, config, migration, deprecation]
status: ready_for_review
last_updated: 2025-12-03
last_updated_by: bethCoderNewbie
related_research: thoughts/shared/research/2025-12-03_18-13-00_legacy_imports_audit.md
---

# Plan: Migrate Legacy Config Imports

## Desired End State

After this plan is complete:

* **Zero legacy imports** - All code uses `settings` object pattern
* **Deprecation warnings enforced** - pytest fails on `DeprecationWarning`
* **Clean codebase** - Consistent import pattern across all files

### Key Discoveries

* `src/preprocessing/parser.py:556` - Uses `PARSED_DATA_DIR` inside method
* `src/preprocessing/parser.py:665` - Uses `RAW_DATA_DIR`, `PARSED_DATA_DIR` in `__main__` block
* `src/preprocessing/segmenter.py:9` - Uses `MIN_SEGMENT_LENGTH`, `MAX_SEGMENT_LENGTH` at module level and as default args

## What We're NOT Doing

* Refactoring unrelated code
* Changing function signatures (preserve backward compatibility)
* Modifying test files (already using modern pattern)

## Implementation Approach

Simple find-and-replace migrations for 2 files, then add pytest warning enforcement.

---

## Phase 1: Migrate `src/preprocessing/segmenter.py`

**Overview:** Replace module-level legacy imports with `settings` object.

### Changes Required:

**File:** `src/preprocessing/segmenter.py`

**Change 1: Replace import statement (line 9)**

```python
# OLD (line 9):
from src.config import MIN_SEGMENT_LENGTH, MAX_SEGMENT_LENGTH

# NEW:
from src.config import settings
```

**Change 2: Update default arguments (lines 23-24)**

```python
# OLD (lines 21-27):
def __init__(
    self,
    min_length: int = MIN_SEGMENT_LENGTH,
    max_length: int = MAX_SEGMENT_LENGTH,
    semantic_model_name: str = "all-MiniLM-L6-v2",
    similarity_threshold: float = 0.5
):

# NEW:
def __init__(
    self,
    min_length: int | None = None,
    max_length: int | None = None,
    semantic_model_name: str = "all-MiniLM-L6-v2",
    similarity_threshold: float = 0.5
):
    """
    Initialize the segmenter

    Args:
        min_length: Minimum segment length (default from settings.preprocessing.min_segment_length)
        max_length: Maximum segment length (default from settings.preprocessing.max_segment_length)
        ...
    """
    self.min_length = min_length if min_length is not None else settings.preprocessing.min_segment_length
    self.max_length = max_length if max_length is not None else settings.preprocessing.max_segment_length
```

---

## Phase 2: Migrate `src/preprocessing/parser.py`

**Overview:** Replace legacy imports in two locations.

### Changes Required:

**File:** `src/preprocessing/parser.py`

**Change 1: Replace import inside method (line 556)**

```python
# OLD (line 556):
from src.config import PARSED_DATA_DIR

# NEW:
from src.config import settings
```

**Change 2: Update usage (line 561)**

```python
# OLD (line 561):
return PARSED_DATA_DIR / filename

# NEW:
return settings.paths.parsed_data_dir / filename
```

**Change 3: Replace import in `__main__` block (line 665)**

```python
# OLD (line 665):
from src.config import RAW_DATA_DIR, PARSED_DATA_DIR, ensure_directories

# NEW:
from src.config import settings, ensure_directories
```

**Change 4: Update usage in `__main__` (line 679)**

```python
# OLD (line 679):
print(f"\nLooking for HTML files in: {RAW_DATA_DIR}")

# NEW:
print(f"\nLooking for HTML files in: {settings.paths.raw_data_dir}")
```

---

## Phase 3: Add Deprecation Warning Enforcement

**Overview:** Configure pytest to fail on deprecation warnings.

### Changes Required:

**File:** `pyproject.toml`

**Add to `[tool.pytest.ini_options]`:**

```toml
filterwarnings = [
    "error::DeprecationWarning:src.config",  # Fail on our deprecation warnings
]
```

---

## Success Criteria

### Automated Verification:

```bash
# No legacy imports found (excluding config/ itself)
grep -r "from src.config import [A-Z_]" src/ --include="*.py" | grep -v "src/config/"
# Expected: No output

# Import works without warnings
python -W error::DeprecationWarning -c "from src.config import settings; print(settings.paths.data_dir)"
# Expected: Path printed, no error

# Tests pass
pytest tests/ -x --tb=short
```

### Manual Verification:

- [ ] `python src/preprocessing/parser.py` runs without deprecation warnings
- [ ] `RiskSegmenter()` instantiates correctly with defaults from settings

---

## File Summary

| File | Changes | Risk |
|------|---------|------|
| `src/preprocessing/segmenter.py` | 2 edits | Low |
| `src/preprocessing/parser.py` | 4 edits | Low |
| `pyproject.toml` | 1 addition | Low |
