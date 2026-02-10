---
date: 2025-12-15T12:30:00-05:00
researcher: bichn
git_commit: 1843e0d
branch: main
repository: SEC finetune
topic: "Mitigation Strategy: Preserving QA Tests while Adding Unit Tests"
tags: [research, testing, qa_validation, refactoring]
status: complete
last_updated: 2025-12-15
last_updated_by: bichn
---

# Research: Mitigation Strategy: Preserving QA Tests while Adding Unit Tests

**Date**: 2025-12-15T12:30:00-05:00
**Researcher**: bichn
**Git Commit**: 1843e0d
**Branch**: main
**Repository**: SEC finetune

## Research Question

How can we structure the `tests/preprocessing` directory to support strict unit testing without disrupting the existing "QA Validation" tests that rely on real data and specialized fixtures?

## Summary

The existing tests in `tests/preprocessing/` (`test_cleaner.py`, `test_extractor.py`, `test_segmenter.py`, `test_parser_section_recall.py`) are deeply integrated with the project's **QA Validation Framework** (`src/config/qa_validation.py`). They function as acceptance/integration tests, consuming real data fixtures (`extracted_data`, `cleaned_data`) and validating against thresholds defined in `configs/qa_validation/*.yaml`.

**Recommendation:** Do not move or rename these existing files to avoid breaking the QA validation workflow. Instead, create a **parallel** `tests/unit/preprocessing/` directory for pure, fast unit tests. This approach adheres to the "Open/Closed Principle" applied to infrastructure: open for extension (new unit tests), closed for modification (existing QA tests).

## Detailed Findings

### 1. Existing Tests are QA Validation, Not Unit Tests

*   **`test_cleaner.py`**:
    *   Uses `cleaned_data` fixture (real JSON files from `data/interim`).
    *   Tests "Hygiene Metrics" like "No excessive whitespace ratio < 0.01".
    *   This is statistical validation of the *output*, not logic verification of the *code*.
*   **`test_extractor.py`**:
    *   Uses `test_10k_files` (raw HTML).
    *   Explicitly validates "Boundary Detection" on real files.
*   **`test_parser_section_recall.py`**:
    *   Validates recall rates against business requirements (>99%).
*   **QA Config Link**:
    *   `src/config/qa_validation.py` loads thresholds from `configs/qa_validation/cleaning.yaml` etc.
    *   These tests effectively implement the "Go/No-Go" logic described in `qa_validation.py` docstrings.

### 2. Integration with Conftest

`tests/conftest.py` is heavily opinionated towards these QA tests, providing session-scoped fixtures that load large datasets (`extracted_data`, `cleaned_data`). Modifying this setup to accommodate unit tests (which shouldn't load data) would be complex and risky.

### 3. Risk of Renaming

Renaming `test_cleaner.py` to `integration/test_cleaning_quality.py` would require:
1.  Updating any CI/CD scripts calling these specific tests.
2.  Potentially breaking imports if other tests inherit classes from them (unlikely but possible).
3.  Confusion for existing developers accustomed to running `pytest tests/preprocessing`.

## Architecture Insights

### Proposed Hybrid Architecture

We will introduce a `tests/unit` root directory (or `tests/unit/preprocessing`) to house the new strict unit tests. The existing `tests/preprocessing` will act as the "Regression/QA" suite.

```text
tests/
├── conftest.py               # Heavy fixtures (keep as is)
├── preprocessing/            # EXISTING (QA/Integration Suite)
│   ├── __init__.py
│   ├── test_cleaner.py       # Validates output quality
│   ├── test_extractor.py     # Validates extraction stats
│   ├── test_segmenter.py     # Validates segmentation stats
│   └── test_parser_section_recall.py
└── unit/                     # NEW (Strict Unit Tests)
    ├── __init__.py
    ├── preprocessing/
    │   ├── __init__.py
    │   ├── test_cleaning.py  # Tests cleaning.py logic (mocks)
    │   ├── test_extractor.py # Tests extractor.py logic (mocks)
    │   ├── test_parser.py    # Tests parser.py logic (mocks)
    │   └── test_segmenter.py # Tests segmenter.py logic (mocks)
    └── conftest.py           # Light fixtures (mocks only)

└── integration/              # SLOW
    ├── preprocessing/
    │   ├── __init__.py 
    │   ├── test_full_pipeline.py # End-to-end flow
        └── test_quality_metrics.py # (Optional) grouping of quality checks
```

## Recommendations

### Priority 1: Establish `tests/unit` Structure

Create the directory `tests/unit/preprocessing`. This is a non-destructive add-on.

### Priority 2: Create Unit Tests with Correct Naming

Populate `tests/unit/preprocessing/` with files that map 1:1 to `src/preprocessing/`:
*   `tests/unit/preprocessing/test_cleaning.py` (Tests `TextCleaner` class methods in isolation)
*   `tests/unit/preprocessing/test_extractor.py` (Tests regex patterns in isolation)

### Priority 3: Leave Existing Tests Alone

Do not rename `test_cleaner.py` or move it. Its name might be slightly inconsistent with `cleaning.py`, but it consistently represents the "cleaner QA" suite. We can add a docstring update to clarify its purpose if touched, but otherwise treat it as "Legacy/Stable".

### Priority 4: Verify Separation

Ensure `pytest tests/unit` runs in <1 second, proving independence from the heavy `conftest.py` fixtures (or override them in `tests/unit/conftest.py`).
