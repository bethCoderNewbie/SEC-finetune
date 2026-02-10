---
date: 2025-12-27T13:35:13-06:00
git_commit: 648bf25
branch: main
repository: SEC finetune
researcher: bethCoderNewbie
status: ACTIVE
type: research
tags: [validation, organization, refactoring, best-practices]
---

# Validation Scripts Reorganization Research

## Executive Summary

The current validation scripts are scattered across `scripts/utils/` and `scripts/utils/validation/` with mixed responsibilities, inconsistent naming, and significant code duplication. This research proposes a reorganized structure that separates concerns by validation domain (data quality, feature quality, extraction quality, code quality) with consistent naming conventions and shared utilities to improve maintainability, scalability, and reproducibility.

## Current State Analysis

### Directory Structure

```
scripts/utils/
├── validation/
│   ├── validate_preprocessing_output.py         # Data health check (single file)
│   ├── validate_preprocessing_output_batch.py   # Data health check (batch)
│   ├── validate_pydantic_v2.py                  # Code quality validation
│   └── README.md
├── generate_validation_report.py                 # NLP metrics report (single file)
├── generate_validation_report_batch.py           # NLP metrics report (batch)
├── generate_extractor_qa_report.py               # Extractor QA (single file, from tests)
└── generate_extractor_qa_report_batch.py         # Extractor QA (batch)

src/validation/
└── schema_validator.py                           # Schema & identity validation logic
```

### Identified Scripts and Their Responsibilities

#### 1. Data Quality Validation
**Location:** `scripts/utils/validation/`

- **`validate_preprocessing_output.py`** (160 lines)
  - **Purpose:** Validate single preprocessing run directory against MLOps quality standards
  - **Checks:** Completeness (CIK, company name), cleanliness (HTML artifacts), substance (segment length), consistency (duplicates, keywords)
  - **Technology:** Uses `HealthCheckValidator` from `src.config.qa_validation`
  - **Exit codes:** 0 = pass, 1 = fail
  - **Features:** Verbose output, JSON report, fail-on-warn flag

- **`validate_preprocessing_output_batch.py`** (668 lines)
  - **Purpose:** Batch validate all JSON files in preprocessing run with parallel processing
  - **Features:** Parallel processing, checkpoint/resume, progress tracking
  - **Architecture:** ProcessPoolExecutor with worker initialization, checkpoint management
  - **Duplication:** Reimplements checkpoint logic, parallel processing pattern

#### 2. Feature Quality Validation (NLP Metrics)
**Location:** `scripts/utils/`

- **`generate_validation_report.py`** (307 lines)
  - **Purpose:** Generate human-readable NLP validation report for sentiment & readability metrics
  - **Metrics:** LM hit rate, zero-vector rate, polarity ratios, uncertainty-negative correlation, Gunning Fog, metric correlations
  - **Data:** Single test file (AAPL 10-K 2021)
  - **Output:** Markdown report with interpretation guides

- **`generate_validation_report_batch.py`** (906 lines)
  - **Purpose:** Batch NLP validation with parallel processing and QA thresholds
  - **Features:** Parallel processing, checkpoint/resume, validates against `configs/qa_validation/features.yaml`
  - **Output:** JSON or Markdown report with per-file and aggregate results
  - **Duplication:** Reimplements checkpoint logic, parallel processing, worker initialization

#### 3. Extraction Quality Validation
**Location:** `scripts/utils/`

- **`generate_extractor_qa_report.py`** (258 lines)
  - **Purpose:** Generate QA report for SEC Section Extractor by running test suite
  - **Method:** Runs `tests/preprocessing/test_extractor.py`, parses pytest output
  - **Metrics:** Section start precision, key item recall, page header filtering, subsection classification, char count range, keyword density
  - **Output:** Markdown report with Go/No-Go decisions

- **`generate_extractor_qa_report_batch.py`** (826 lines)
  - **Purpose:** Batch extractor QA with parallel processing
  - **Validation:** Direct file validation (doesn't run tests), checks identifier, title, content, page headers, subsections, keyword density
  - **Features:** Parallel processing, checkpoint/resume
  - **Duplication:** Reimplements checkpoint logic, parallel processing, QA metric definitions

#### 4. Code Quality Validation
**Location:** `scripts/utils/validation/`

- **`validate_pydantic_v2.py`** (246 lines)
  - **Purpose:** Enforce Pydantic v2 patterns, detect deprecated v1 code
  - **Scope:** Python code files (not data files)
  - **Checks:** 14 deprecated patterns (BaseSettings import, @validator, .dict(), etc.)
  - **Usage:** Pre-commit hooks, CI/CD integration

#### 5. Schema Validation (Core Logic)
**Location:** `src/validation/`

- **`schema_validator.py`** (124 lines)
  - **Purpose:** Schema integrity and identity field validation
  - **Checks:** CIK (required), company name (required), SIC code (recommended)
  - **Architecture:** Reusable class with single-file and batch methods
  - **Note:** Core logic lives in `src/`, but no corresponding CLI script in `scripts/`

### Problems Identified

#### 1. **Mixed Responsibilities**
- `scripts/utils/validation/` contains both **data validation** (preprocessing output) and **code quality validation** (Pydantic)
- Report generation scripts are **outside** the validation folder
- Similar concerns are not co-located (e.g., NLP feature validation scripts in different location than data quality)

#### 2. **Naming Inconsistencies**
- Inconsistent prefixes: `validate_*` vs `generate_*`
- Not clear which scripts validate **data** vs **code** vs **extraction quality**
- Batch vs single-file distinction not systematic (sometimes suffix `_batch`, sometimes separate files)

#### 3. **Code Duplication**
- **Checkpoint management** logic duplicated across 3 batch scripts:
  - Lines 78-124 in `validate_preprocessing_output_batch.py`
  - Lines 394-424 in `generate_validation_report_batch.py`
  - Lines 272-302 in `generate_extractor_qa_report_batch.py`
- **Parallel processing pattern** duplicated (ProcessPoolExecutor setup, worker initialization)
- **Report generation helpers** duplicated (metadata gathering, git info, summary printing)

#### 4. **Location Confusion**
- Core validation logic in `src/validation/` but CLI scripts in `scripts/utils/`
- Report generation vs validation scripts not clearly separated
- `schema_validator.py` in `src/validation/` has no corresponding CLI script

#### 5. **Scalability Issues**
- No shared utilities for common patterns (checkpointing, parallel processing)
- Each new validation type requires duplicating infrastructure code
- Difficult to maintain consistent behavior across validation scripts

## Proposed Reorganization

### Design Principles

1. **Separation of Concerns:** Group by validation domain (data, features, extraction, code)
2. **Consistent Naming:** Use `check_*` for validators, `report_*` for report generators
3. **DRY (Don't Repeat Yourself):** Extract common utilities into shared modules
4. **Clear Location:** Scripts in `scripts/validation/`, core logic in `src/validation/`
5. **Scalability:** Easy to add new validation types without duplication

### Proposed Directory Structure

```
scripts/validation/
├── _shared/                                    # Shared utilities
│   ├── __init__.py
│   ├── checkpoint.py                           # Checkpoint management (save/load/cleanup)
│   ├── parallel.py                             # Parallel processing helpers (worker patterns)
│   ├── metadata.py                             # Metadata gathering (git, environment)
│   └── reporting.py                            # Report formatting utilities
│
├── data_quality/                               # Data health & schema validation
│   ├── __init__.py
│   ├── check_preprocessing_output.py           # Single-file data health check
│   ├── check_preprocessing_output_batch.py     # Batch data health check
│   ├── check_schema.py                         # Schema & identity validation (uses src/validation/schema_validator.py)
│   └── README.md                               # Data quality validation guide
│
├── feature_quality/                            # NLP feature validation
│   ├── __init__.py
│   ├── report_nlp_metrics.py                   # Single-file NLP metrics report
│   ├── report_nlp_metrics_batch.py             # Batch NLP metrics report
│   └── README.md                               # Feature quality validation guide
│
├── extraction_quality/                         # Extractor QA
│   ├── __init__.py
│   ├── report_extractor_qa.py                  # Single-file extractor QA (from tests)
│   ├── report_extractor_qa_batch.py            # Batch extractor QA
│   └── README.md                               # Extraction quality validation guide
│
├── code_quality/                               # Code standards validation
│   ├── __init__.py
│   ├── check_pydantic_v2.py                    # Pydantic v2 enforcement
│   └── README.md                               # Code quality validation guide
│
└── README.md                                   # Master validation guide

src/validation/
├── __init__.py
├── schema_validator.py                         # Schema & identity validation (existing)
├── health_check_validator.py                   # Data health check logic (extract from scripts)
└── extractor_qa_validator.py                   # Extractor QA logic (extract from scripts)
```

### Script Naming Conventions

| Prefix | Purpose | Exit Behavior | Examples |
|--------|---------|---------------|----------|
| `check_*` | **Validation scripts** that pass/fail based on thresholds | Exit 0 (pass) or 1 (fail) | `check_preprocessing_output.py`, `check_pydantic_v2.py` |
| `report_*` | **Report generation** scripts that always succeed | Exit 0 (always, unless error) | `report_nlp_metrics.py`, `report_extractor_qa.py` |
| `*_batch` | **Batch processing** version with parallel execution | Suffix for batch variants | `check_preprocessing_output_batch.py` |

### Migration Plan

#### Phase 1: Extract Shared Utilities

**`scripts/validation/_shared/checkpoint.py`**
```python
"""Checkpoint management for batch processing with crash recovery."""

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import json
from datetime import datetime


class CheckpointManager:
    """Manages checkpoint state for long-running batch operations."""

    def __init__(self, checkpoint_path: Path):
        self.checkpoint_path = checkpoint_path

    def save(
        self,
        processed_files: List[str],
        results: List[Dict],
        metrics: Dict[str, Any]
    ) -> None:
        """Save checkpoint for crash recovery."""
        checkpoint_data = {
            "processed_files": processed_files,
            "results": results,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }

        with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, default=str)

    def load(self) -> Tuple[Set[str], List[Dict], Dict[str, Any]]:
        """Load checkpoint data for resume."""
        if not self.checkpoint_path.exists():
            return set(), [], {}

        with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return (
                set(data.get('processed_files', [])),
                data.get('results', []),
                data.get('metrics', {})
            )

    def cleanup(self) -> None:
        """Remove checkpoint file after successful completion."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
```

**`scripts/validation/_shared/parallel.py`**
```python
"""Parallel processing utilities for batch validation."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import os


def process_files_parallel(
    files: List[Path],
    worker_func: Callable,
    max_workers: Optional[int] = None,
    worker_init: Optional[Callable] = None,
    verbose: bool = False,
    checkpoint_callback: Optional[Callable[[int, Any], None]] = None,
    checkpoint_interval: int = 10
) -> List[Dict[str, Any]]:
    """
    Process files in parallel with optional checkpointing.

    Args:
        files: List of file paths to process
        worker_func: Function to process each file (receives file_path as arg)
        max_workers: Number of parallel workers (default: CPU count)
        worker_init: Optional initialization function for workers
        verbose: Print per-file progress
        checkpoint_callback: Optional callback for periodic checkpointing
        checkpoint_interval: Save checkpoint every N files

    Returns:
        List of results from worker_func
    """
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, len(files))

    results = []

    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=worker_init,
        max_tasks_per_child=50  # Prevent memory leaks
    ) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(worker_func, f): f
            for f in files
        }

        # Process results as completed
        for idx, future in enumerate(as_completed(future_to_file), 1):
            result = future.result()
            results.append(result)

            if verbose:
                print(f"[{idx}/{len(files)}] Processed: {result.get('file', 'unknown')}")

            # Checkpoint periodically
            if checkpoint_callback and idx % checkpoint_interval == 0:
                checkpoint_callback(idx, results)

    return results
```

**`scripts/validation/_shared/metadata.py`**
```python
"""Metadata gathering for validation reports."""

import datetime
import os
import platform
import subprocess
from pathlib import Path
from typing import Dict


def get_git_info() -> Dict[str, str]:
    """Retrieve git metadata safely."""
    def _run_git(args):
        try:
            return subprocess.check_output(
                ["git"] + args,
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    return {
        "commit": _run_git(["rev-parse", "--short", "HEAD"]),
        "commit_full": _run_git(["rev-parse", "HEAD"]),
        "branch": _run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "user": _run_git(["config", "user.name"]) or os.environ.get("USERNAME", "unknown")
    }


def get_run_metadata() -> Dict[str, str]:
    """Gather comprehensive run environment metadata."""
    git = get_git_info()
    return {
        "timestamp": datetime.datetime.now().astimezone().isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git["commit"],
        "git_commit_full": git["commit_full"],
        "git_branch": git["branch"],
        "researcher": git["user"],
        "working_dir": str(Path.cwd()),
    }
```

#### Phase 2: Move Core Validation Logic to `src/validation/`

Extract reusable validation logic from scripts into `src/validation/`:
- `health_check_validator.py` - Already exists as `src.config.qa_validation.HealthCheckValidator` (may refactor location)
- `extractor_qa_validator.py` - Extract QA metric definitions and validation logic from batch script

#### Phase 3: Reorganize Scripts by Domain

**Move and rename files:**
```bash
# Data Quality
scripts/utils/validation/validate_preprocessing_output.py
  → scripts/validation/data_quality/check_preprocessing_output.py

scripts/utils/validation/validate_preprocessing_output_batch.py
  → scripts/validation/data_quality/check_preprocessing_output_batch.py

# Create new schema validation CLI
src/validation/schema_validator.py (keep)
  + scripts/validation/data_quality/check_schema.py (new CLI wrapper)

# Feature Quality
scripts/utils/generate_validation_report.py
  → scripts/validation/feature_quality/report_nlp_metrics.py

scripts/utils/generate_validation_report_batch.py
  → scripts/validation/feature_quality/report_nlp_metrics_batch.py

# Extraction Quality
scripts/utils/generate_extractor_qa_report.py
  → scripts/validation/extraction_quality/report_extractor_qa.py

scripts/utils/generate_extractor_qa_report_batch.py
  → scripts/validation/extraction_quality/report_extractor_qa_batch.py

# Code Quality
scripts/utils/validation/validate_pydantic_v2.py
  → scripts/validation/code_quality/check_pydantic_v2.py
```

#### Phase 4: Refactor to Use Shared Utilities

Update batch scripts to use shared utilities:
```python
from scripts.validation._shared.checkpoint import CheckpointManager
from scripts.validation._shared.parallel import process_files_parallel
from scripts.validation._shared.metadata import get_run_metadata
```

Reduces code duplication by ~300-400 lines across batch scripts.

#### Phase 5: Create Master README

Create `scripts/validation/README.md` with:
- Overview of validation domains
- Quick reference for all validation scripts
- Usage examples for common workflows
- Integration guide for CI/CD

### Benefits of Proposed Structure

| Benefit | Impact |
|---------|--------|
| **Clear Separation of Concerns** | Easy to find relevant validation scripts by domain |
| **Reduced Duplication** | ~300-400 lines of shared code extracted into utilities |
| **Consistent Naming** | `check_*` vs `report_*` prefix clearly indicates script behavior |
| **Improved Scalability** | Adding new validation types requires minimal boilerplate |
| **Better Maintainability** | Changes to checkpoint/parallel logic only need to be made once |
| **Enhanced Reproducibility** | Shared metadata gathering ensures consistent reporting |

### Backward Compatibility

To maintain backward compatibility during migration:
1. **Keep old paths temporarily** with deprecation warnings
2. **Create symlinks** from old locations to new locations
3. **Update documentation** to reference new paths
4. **Deprecation timeline**: 2 releases before removal

```python
# Example deprecation warning in old scripts
import warnings
warnings.warn(
    "This script has moved to scripts/validation/data_quality/check_preprocessing_output.py. "
    "Please update your workflows. This compatibility shim will be removed in version X.X.",
    DeprecationWarning,
    stacklevel=2
)
```

## Recommendations

### Immediate Actions (High Priority)
1. **Extract shared utilities** to `scripts/validation/_shared/`
   - Start with `checkpoint.py` (used by 3 scripts)
   - Then `parallel.py` and `metadata.py`
2. **Create new directory structure** under `scripts/validation/`
3. **Move and rename** validation scripts to new locations with consistent naming

### Short-term Actions (Medium Priority)
4. **Refactor batch scripts** to use shared utilities
5. **Create schema validation CLI** wrapper for `src/validation/schema_validator.py`
6. **Write master README** with validation guide

### Long-term Actions (Low Priority)
7. **Extract validation logic** from scripts to `src/validation/` for reusability
8. **Add pre-commit hooks** that use validation scripts
9. **CI/CD integration guide** for all validation domains

## Success Metrics

- **Lines of duplicated code removed:** Target 300-400 lines
- **Time to add new validation script:** From 2-3 hours → 30 minutes (due to reusable utilities)
- **Developer onboarding time:** Reduced by clearer organization and documentation
- **Maintenance burden:** Reduced by centralizing checkpoint/parallel logic

## References

### Working Paths (Current Implementation)
- `scripts/utils/validation/validate_preprocessing_output_batch.py:78-124` - Checkpoint management
- `scripts/utils/generate_validation_report_batch.py:394-424` - Checkpoint management (duplicate)
- `scripts/utils/generate_extractor_qa_report_batch.py:272-302` - Checkpoint management (duplicate)
- `src/validation/schema_validator.py:18-83` - Well-structured validation class example

### Broken Paths (Issues)
- No CLI wrapper for `src/validation/schema_validator.py`
- Mixed responsibilities in `scripts/utils/validation/` (data + code quality)
- Report generation scripts outside validation directory

### Configuration Files Referenced
- `configs/qa_validation/features.yaml` - NLP feature thresholds
- `src/config/qa_validation.py` - HealthCheckValidator, ThresholdRegistry

## Appendix: Script Cross-Reference

### Current Scripts by Validation Domain

| Domain | Single-File Script | Batch Script | Core Logic |
|--------|-------------------|--------------|------------|
| **Data Quality** | `validate_preprocessing_output.py` | `validate_preprocessing_output_batch.py` | `src.config.qa_validation.HealthCheckValidator` |
| **Feature Quality (NLP)** | `generate_validation_report.py` | `generate_validation_report_batch.py` | Inline (sentiment/readability analyzers) |
| **Extraction Quality** | `generate_extractor_qa_report.py` | `generate_extractor_qa_report_batch.py` | Inline (QA metrics definitions) |
| **Schema Quality** | *(Missing)* | *(Missing)* | `src.validation.schema_validator.SchemaValidator` |
| **Code Quality** | `validate_pydantic_v2.py` | N/A | Inline (pattern matching) |

### Shared Patterns Across Batch Scripts

| Pattern | Occurrences | Lines Duplicated |
|---------|-------------|------------------|
| Checkpoint save/load | 3 scripts | ~120 lines total |
| ProcessPoolExecutor setup | 3 scripts | ~80 lines total |
| Worker initialization | 3 scripts | ~40 lines total |
| Metadata gathering | 3 scripts | ~60 lines total |
| JSON report generation | 4 scripts | ~100 lines total |

**Total duplicated code:** ~400 lines (conservative estimate)

---

*Research completed: 2025-12-27T13:35:13-06:00*
