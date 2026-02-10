---
date: 2025-12-15T12:00:00-05:00
researcher: bichn
git_commit: 1843e0d
branch: main
repository: SEC finetune
topic: "Restructuring tests/preprocessing for Separation of Concerns"
tags: [research, refactoring, testing, architecture]
status: complete
last_updated: 2025-12-15
last_updated_by: bichn
---

# Research: Restructuring tests/preprocessing for Separation of Concerns

**Date**: 2025-12-15T12:00:00-05:00
**Researcher**: bichn
**Git Commit**: 1843e0d
**Branch**: main
**Repository**: SEC finetune

## Research Question

How can we reorganize the `tests/preprocessing` directory to better reflect the `src/preprocessing` structure, strictly separate fast unit tests from slower integration tests, and improve maintainability?

## Summary

The current `tests/preprocessing` directory is flat and mixes different testing concerns. Some files (like `test_extractor.py`) rely heavily on real data fixtures, effectively acting as integration tests, while others test specific logic. The naming conventions (e.g., `test_cleaner.py` vs `src/preprocessing/cleaning.py`) are inconsistent.

I recommend splitting the directory into `unit/` and `integration/` subdirectories. Unit tests should be fast and mocked where possible, while integration tests can continue to use the heavy data fixtures. Renaming test files to 1:1 match their source counterparts will improve discoverability.

## Detailed Findings

### 1. Current Directory Structure & Naming Mismatches

The current flat structure makes it difficult to distinguish between types of tests.

#### Working Path
`src/preprocessing` has a clean, modular structure:
- `cleaning.py`
- `extractor.py`
- `parser.py`
- `segmenter.py`

#### Broken Path (Inconsistent Mapping)
`tests/preprocessing` does not mirror this structure 1:1:
- `test_cleaner.py` tests `cleaning.py` (Naming mismatch)
- `test_parser_section_recall.py` is a specific metric/integration test for `parser.py`, but implies it's the *only* test for the parser.
- `test_extractor.py` mixes logic checks with "real data" validation.

### 2. Test Types Mixed

Analysis of file content reveals a mix of concerns:

- **`test_extractor.py`**: Docstring says "validating extraction quality using real SEC filing data". It uses `data/raw/*.html`. This is an **Integration Test**.
- **`test_segmenter.py`**: Docstring says "validating risk factor segmentation quality using real SEC filing data". Uses `segmented_data` fixture. This is an **Integration Test**.
- **`test_cleaner.py`**: Tests `TextCleaner` but also checks "Data Integrity" on real files. Mixed concerns.
- **`test_parser_section_recall.py`**: Explicitly checks "Key Section Recall > 99%". This is a **Quality/Integration Test**.

## Code References

| File:Line | Description | Status |
|-----------|-------------|--------|
| `tests/preprocessing/test_cleaner.py` | Tests `src/preprocessing/cleaning.py` | Mismatched Name |
| `tests/preprocessing/test_parser_section_recall.py` | Quality metrics for Parser | Integration |
| `tests/preprocessing/test_extractor.py` | Validates `extractor.py` with real data | Integration |
| `tests/preprocessing/test_segmenter.py` | Validates `segmenter.py` with real data | Integration |

## Architecture Insights

### Proposed Architecture

```text
tests/
└── preprocessing/
    ├── __init__.py
    ├── conftest.py             # Shared fixtures (e.g. sample_html, mock_data)
    ├── unit/                   # FAST: Isolated logic tests
    │   ├── __init__.py
    │   ├── test_cleaning.py    # Renamed from test_cleaner.py (logic only)
    │   ├── test_extractor.py   # Logic only (regex, small inputs)
    │   ├── test_parser.py      # Logic only
    │   └── test_segmenter.py   # Logic only
    └── integration/            # SLOW: Real files, quality metrics
        ├── __init__.py
        ├── test_parser_recall.py # Renamed from test_parser_section_recall.py
        ├── test_full_pipeline.py # End-to-end flow
        └── test_quality_metrics.py # (Optional) grouping of quality checks
```

## Recommendations

### Priority 1: Create Directory Structure & Move Files

1. Create `tests/preprocessing/unit` and `tests/preprocessing/integration`.
2. Move existing "heavy" tests to `integration/`.
   - `test_parser_section_recall.py` -> `integration/test_parser_recall.py`
   - `test_extractor.py` -> `integration/test_extractor_quality.py` (or keep as base and strip unit tests out later)
   - `test_segmenter.py` -> `integration/test_segmenter_quality.py`

### Priority 2: Standardize Naming

Rename files to match `src` modules exactly in the `unit/` folder:
- `test_cleaner.py` -> `unit/test_cleaning.py`

### Priority 3: Extract Unit Tests

Create true unit tests in `unit/` that do *not* require the `extracted_data` or `test_10k_files` fixtures, enabling fast feedback loops.
