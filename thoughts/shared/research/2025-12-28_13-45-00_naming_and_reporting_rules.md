---
date: 2025-12-28T13:45:00-06:00
researcher: beth
git_commit: 648bf25
branch: main
repository: SEC finetune
status: complete
last_updated: 2025-12-28
last_updated_by: beth
topic: Production Naming Standards & Reporting Guidelines 
---

# Research: Production Naming Standards & Reporting Guidelines

## 1. Executive Summary
This document defines the **Production Standards** for Phase 3.3 and beyond. It upgrades the project from "script-based conventions" to "engineering standards" designed for **reproducibility** (MLOps) and **maintainability** (Software Engineering).

**Core Philosophy:** Naming must reduce cognitive load. A developer should know *what* a variable contains, *what* a function does, and *where* a file belongs just by reading its name.

---

## 2. Production Naming Standards

### 2.1 The "Semantics First" Rule
Names must describe **intent** and **units** where applicable.

| Category | Pattern | Bad Example | Production-Ready Example | Why? |
|----------|---------|-------------|--------------------------|------|
| **Booleans** | `is_<adj>`, `has_<noun>`, `should_<verb>` | `valid`, `flag`, `done` | `is_valid`, `has_errors`, `should_retry` | ambiguous flags cause logic bugs |
| **Collections** | Plural Noun or `*_list` | `file`, `data` | `file_paths`, `risk_factors`, `user_ids` | `file` implies a single object |
| **Units** | `noun_<unit>` | `timeout`, `size`, `duration` | `timeout_seconds`, `size_bytes`, `duration_ms` | avoids "is this ms or seconds?" bugs |
| **Functions** | `verb_<noun>` | `process()`, `handler()` | `parse_filing()`, `handle_validation_error()` | Verbs describe side effects |
| **Private** | `_snake_case` | `helper()`, `temp()` | `_normalize_text()`, `_load_cache()` | explicit API boundaries |

### 2.2 Class Naming (Architectural Clarity)
Classes must reveal their pattern or responsibility via suffixes.

*   **Validators:** `*Validator` (e.g., `HealthCheckValidator`) - returns boolean/status.
*   **Managers/Controllers:** `*Manager` (e.g., `StateManifest`) - maintains state/logic.
*   **Data Models:** `*Config`, `*Schema` (e.g., `PipelineConfig`) - distinct from logic.
*   **Formatters/Reporters:** `*Formatter` (e.g., `ReportFormatter`) - purely transformational.

### 2.3 Artifact Naming (Reproducibility)
Generated files must be sortable and uniquely identifiable.

**Convention:** `reports/preprocessing_validation_summary_{run_id}.md`

**Structure:**
```
preprocessing_validation_summary_{timestamp}_{stage}_{git_sha}.md
                 │                    │         │        │
                 │                    │         │        └─ Code version (reproducibility)
                 │                    │         └────────── Pipeline stage
                 │                    └──────────────────── When (chronological sorting)
                 └───────────────────────────────────────── What (pipeline + operation)
```

**Rationale:**
- **Descriptive:** Clearly states: preprocessing pipeline + validation operation + summary type
- **Centralization:** All reports in `reports/` directory (established pattern)
- **Auditability:** Unique per run prevents overwriting
- **Reproducibility:** Includes git commit for exact code version
- **Sortable:** Timestamp-first enables chronological listing

**Example:**
*   `reports/preprocessing_validation_summary_20251228_133000_batch_parse_648bf25.md`

### 2.4 Testing Conventions
Tests must tell a story about behavior, not just coverage.

*   **File:** `tests/preprocessing/test_cleaning.py` (Mirrors `src` structure)
*   **Class:** `TestTextCleaner` (Mirrors class under test)
*   **Method:** `test_<method_name>_<condition>_<expected_result>`
    *   *Bad:* `test_clean`
    *   *Good:* `test_clean_html_with_malformed_tags_returns_empty_string`

---

## 3. Reporting System Design (Phase 3.3)

### 3.1 Architecture
The `ReportFormatter` class in `src/utils/reporting.py` (Phase 3.1) acts as the single source of truth for generating audit trails.

**Input:**
*   `RunMetadata` (ID, Date, Git Commit, User)
*   `BatchStats` (Total, Passed, Failed, Skipped)
*   `ValidationResults` (List of file results with status and reasons)

**Output:**
*   Markdown file (Audit Trail) - Saved to `reports/` with timestamped name.
*   Console Output (Immediate Feedback) - Brief summary for the operator.

### 3.2 Target File Location
*   **Implementation:** `src/utils/reporting.py`
*   **Test:** `tests/utils/test_reporting.py`
*   **Usage:** `scripts/data_preprocessing/batch_parse.py`

---

## 4. Canonical Report Template: `preprocessing_validation_summary_{run_id}.md`

This template illustrates the application of these standards:
1.  **Traceability:** Includes Commit SHA and User.
2.  **Clarity:** Uses standard status icons and tables.
3.  **Reproducibility:** snapshots configuration.
4.  **Interactivity:** Links to specific files.

```markdown
# Preprocessing Validation Summary

**Run ID:** `20251228_133000_batch_parse_648bf25`
**Date:** 2025-12-28 14:30:00 UTC
**Git Commit:** `648bf25`
**User:** `bethCoderNewbie`

## 1. Executive Overview

| Metric | Count | % of Total |
|--------|-------|------------|
| **Total Files** | **1,000** | 100% |
| ✅ **Passed** | 985 | 98.5% |
| ⚠️ **Warnings** | 10 | 1.0% |
| ❌ **Failed** | 5 | 0.5% |
| ⏭️ **Skipped** | 0 | 0.0% |

**Status:** 🟢 **PASSED** (with minor warnings)

---

## 2. Failure Analysis (Blockers)
*Files that were NOT written to disk due to critical validation errors.*

**Quarantine Directory:** `data/quarantine_20251228_133000_batch_parse_648bf25/`

| File Name | Error Type | Reason |
|-----------|------------|--------|
| `NVDA_2023_10K.html` | `SchemaValidationError` | Missing required 'Item 1A' section |
| `TSLA_2022_10K.html` | `EncodingError` | UTF-8 decode failed at byte 0x80 |
| `AAPL_2020_10K.html` | `DataQualityError` | Extracted text length (50 chars) < min_segment_length (1000) |
| `GOOG_2021_10K.html` | `ParseError` | Malformed HTML structure |
| `MSFT_2019_10K.html` | `SecurityError` | Detected potential script injection pattern |

---

## 3. Warning Analysis (Non-Blocking)
*Files that were processed but require attention.*

| File Name | Warning Type | Detail |
|-----------|--------------|--------|
| **[AMZN_2023_10K.html](./AMZN_2023_10K.html)** | `LowConfidence` | Risk section identification confidence (0.65) < threshold (0.8) |
| **[META_2022_10K.html](./META_2022_10K.html)** | `FormattingIssue` | Excessive non-breaking spaces detected |
| ... (8 more) | | |

---

## 4. Configuration Snapshot

* **Cleaner Version:** `v2.1.0` (spaCy enhanced)
* **Parameters:**
    * `remove_html`: `True`
    * `lemmatization`: `True` (en_core_web_sm)
    * `min_segment_length`: `100`

---
*Generated by `sec-filing-analyzer` preprocessing pipeline.*
```

---

## 5. Implementation Roadmap for Phase 3.3

1.  **Modify `src/utils/reporting.py`**:
    *   Add `generate_markdown_report(metadata, stats, failures, warnings) -> str`.
    *   Use descriptive variable names (e.g., `validation_failures` not `fails`).
    *   Implement templating using f-strings for zero dependencies.
    *   Add relative linking for interactive reports.
2.  **Update `batch_parse.py`**:
    *   Call generation at end of run.
    *   Write to `reports/preprocessing_validation_summary_{run_id}.md`.
3.  **Testing**:
    *   Verify markdown syntax validity.
    *   Verify correct categorization of Pass/Warn/Fail.
    *   Verify links are correctly formatted.
