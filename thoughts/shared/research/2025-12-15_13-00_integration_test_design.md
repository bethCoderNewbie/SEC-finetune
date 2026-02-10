---
date: 2025-12-15T13:00:00-05:00
researcher: bichn
git_commit: 1843e0d
branch: main
repository: SEC finetune
topic: "Design for tests/integration Directory"
tags: [research, architecture, integration_testing, scalability]
status: complete
last_updated: 2025-12-15
last_updated_by: bichn
---

# Research: Design for `tests/integration` Directory

**Date**: 2025-12-15T13:00:00-05:00
**Researcher**: bichn
**Git Commit**: 1843e0d
**Branch**: main
**Repository**: SEC finetune

## Research Question

How should we design the `tests/integration` directory to ensure strict separation of concerns, scalability, and maintainability, while respecting the existing codebase patterns?

## Summary

The current `tests/` directory is partially organized by module (`preprocessing`, `features`) but lacks a dedicated home for integration tests, despite `tests/__init__.py` mentioning a `test_integration/` folder. Existing files like `test_cleaner.py` and `test_extractor.py` contain mixed unit and integration classes (e.g., `TestExtractorIntegrationWithRealFiles`).

**Recommendation:** formalized `tests/integration/` to house true end-to-end and heavy subsystem tests. This directory should mirror the `src/` structure where applicable (e.g., `tests/integration/preprocessing/`) but focus on **flows** rather than **units**.

## Detailed Findings

### 1. Existing "Hidden" Integration Tests
Many files currently house integration tests under the guise of unit tests:
*   `tests/preprocessing/test_cleaner.py`: Contains `class TestCleanerIntegration`.
*   `tests/preprocessing/test_extractor.py`: Contains `class TestExtractorIntegrationWithRealFiles`.
*   `tests/conftest.py`: Defines a `"integration"` marker, showing the *intent* was there.

### 2. Missing Directory
`tests/__init__.py` claims `test_integration/` exists, but it does not in the file system. This suggests a drift between design intent and implementation.

### 3. Scalability Concerns
*   **Current:** As the system grows, adding more "real file" tests to `tests/preprocessing` will make the default test suite prohibitively slow.
*   **Proposed:** Moving these to `tests/integration` allows developers to run `pytest tests/unit` for fast feedback and `pytest tests/integration` (or on CI) for deep validation.

## Architecture Insights

### Proposed Directory Structure

```text
tests/
├── unit/                       # FAST: Mocks only
│   ├── preprocessing/
│   ├── features/
│   └── conftest.py             # Minimal fixtures
├── integration/                # SLOW: Real IO, Models, DB
│   ├── __init__.py
│   ├── conftest.py             # Heavy fixtures (inherits/imports from root conftest)
│   ├── preprocessing/          # Subsystem Integration
│   │   ├── test_cleaning_flow.py
│   │   └── test_extraction_flow.py
│   ├── features/
│   │   └── test_sentiment_flow.py
│   └── pipelines/              # End-to-End Pipelines
│       └── test_full_ingestion.py
└── preprocessing/              # LEGACY/QA (Keep for now, migrate slowly)
```

## Recommendations

### Priority 1: Create `tests/integration`

Create the directory structure `tests/integration`.

### Priority 2: Move Explicit Integration Classes

Identify classes explicitly named `*Integration*` (like `TestCleanerIntegration` in `test_cleaner.py`) and move them to new files in `tests/integration/preprocessing/`.

*   **Source:** `tests/preprocessing/test_cleaner.py` -> `TestCleanerIntegration` class
*   **Dest:** `tests/integration/preprocessing/test_cleaning_integration.py`

This separates the *types* of testing without deleting the old files immediately (which still hold the unit tests).

### Priority 3: Shared Fixtures

Ensure `tests/integration/conftest.py` can access the heavy fixtures (like `extracted_data`) from the root `tests/conftest.py`. Since `pytest` fixture scoping is hierarchical, this should work automatically if `tests/conftest.py` remains the root.

### Priority 4: Pytest Configuration

Update `pytest.ini` (or `pyproject.toml`) to default to running unit tests, requiring a flag or explicit path for integration tests to prevent accidental long runs.
