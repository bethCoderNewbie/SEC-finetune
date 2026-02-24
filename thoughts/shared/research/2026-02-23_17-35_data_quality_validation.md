---
title: Data Quality Validation — Current State Research
date: 2026-02-23
author: beth
git_commit: cd7dc5a (initial); fixes applied same session
branch: main
status: UPDATED
---

# Data Quality Validation — Current State Research

## Revision Log

| Date | Change |
|------|--------|
| 2026-02-23 (initial) | Full system audit |
| 2026-02-23 (rev 1) | Fix: `_get_identity_field()` for v2 schema; batch script self-inclusion bug |
| 2026-02-23 (rev 2) | Quality gate: 50 ≤ char_count ≤ 2000, word_count ≥ 20, min_segment_count wired |

---

## 1. System Architecture

The DQV system is layered across four planes:

```
Layer 4 ─ Batch / Diagnostic Scripts   scripts/validation/**/*.py
Layer 3 ─ Schema Validation            src/validation/schema_validator.py
Layer 2 ─ Inline Gatekeeper            HealthCheckValidator (src/config/qa_validation.py:593)
Layer 1 ─ Config-Driven Thresholds     configs/qa_validation/*.yaml  →  ThresholdRegistry
```

**Entry points:**
- `pipeline.process_and_validate()` — inline gatekeeper called per filing (`pipeline.py:570`)
- `HealthCheckValidator.check_run(run_dir)` — batch post-hoc check (`qa_validation.py:696`)
- `HealthCheckValidator.check_single(data)` — single in-memory dict check (`qa_validation.py:639`)
- `SchemaValidator.validate_batch(file_paths)` — standalone JSON/identity check (`schema_validator.py:84`)

---

## 2. Threshold Inventory

Five YAML files are merged by `_get_config()` (`qa_validation.py:58`) into a single registry.

| File | Categories | Thresholds | Blocking |
|------|-----------|-----------|---------|
| `extraction.yaml` | extraction_accuracy, content_quality | 8 | 5 |
| `parsing.yaml` | parser_performance, parser_stability | 4 | 3 |
| `cleaning.yaml` | cleaner_hygiene, cleaner_continuity, segmentation_distribution, segmentation_quality | 13 | 7 |
| `features.yaml` | sentiment_analysis, sentiment_validation, readability_analysis, readability_validation | 21 | 12 |
| `health_check.yaml` | identity_completeness, data_cleanliness, content_substance, domain_rules | 16 | 12 |
| **Total** | **13 categories** | **~62 thresholds** | **~39 blocking** |

### Key Blocking Thresholds (health_check.yaml — inline gatekeeper)

| Threshold Key | Target | Operator | Blocking | Notes |
|--------------|--------|----------|---------|-------|
| `cik_present_rate` | 1.0 | `>=` | true | All files must have CIK |
| `company_name_present_rate` | 1.0 | `>=` | true | All files must have company name |
| `html_artifact_rate` | 0.0 | `==` | true | Zero-tolerance for HTML tags in segments |
| `empty_segment_rate` | 0.0 | `==` | true | Zero-tolerance for zero-length segments |
| `short_segment_rate` | 0.0 | `<=` | **true** | char_count < 50 (tightened from 5% non-blocking) |
| `max_char_segment_rate` | 0.0 | `<=` | **true** | char_count > 2000 — **new** |
| `min_word_count_rate` | 0.0 | `<=` | **true** | word_count < 20 — **new** |
| `min_segment_count` | 1 | `>=` | true | ≥ 1 segment per filing — **now wired** |
| `duplicate_rate` | 0.0 | `==` | true | No duplicate filings (SHA-256 hash) |
| `amendment_flag_not_amended` | 0.0 | `<=` | true | Amended filings blocked (ADR-011) |
| `min_file_size_kb` | 100 KB | `>=` | true | Corrupt download floor |

---

## 3. HealthCheckValidator — 5-Check Framework

Implemented in `qa_validation.py:639`. Called from `pipeline.py:621`.

```
check_single(data) / check_run(run_dir)
├── _check_identity()      CIK, company_name, SIC rates
├── _check_cleanliness()   HTML tag rate, page number artifact rate
├── _check_substance()     empty/short/over-char segments, word count gates,
│                          min_segment_count per-filing, file size, extraction yield
├── _check_domain()        duplicate rate, risk keywords, segment duplicates
└── _check_amendments()    ADR-011: amendment_flag blocking gate
```

**Schema compatibility:** Two helpers on `HealthCheckValidator`:
- `_get_segments(data)` — tries `segments` then `chunks` (v1 flat / v2 structured)
- `_get_identity_field(data, field)` — tries top-level then `document_info` sub-dict

Both are required because v2 JSON (emitted by `_build_output_data()`) wraps identity
fields under `document_info` while `model_dump()` exposes them flat.

### Class constants governing substance checks

```python
MIN_SEGMENT_LENGTH = 50   # preprocessing.min_segment_length (char floor)
MAX_SEGMENT_CHARS  = 2000 # preprocessing.max_segment_length (char ceiling)
MIN_SEGMENT_WORDS  = 20   # classifier training quality gate (raised from 10)
MAX_SEGMENT_WORDS  = 380  # RFC-003 Option A ceiling; ~512 tokens at 1.35 tok/word
```

---

## 4. Segment Quality Gate (Rev 2)

**Requirement:** every output segment must satisfy `50 ≤ char_count ≤ 2000` and
`word_count ≥ 20`; every processed filing must produce `≥ 1 segment`.
Configurable via `preprocessing.min_segment_length` / `max_segment_length`.

### Changes applied

**`configs/qa_validation/health_check.yaml`**

| Threshold | Before | After |
|-----------|--------|-------|
| `short_segment_rate` | target=0.05, blocking=false | target=0.0, blocking=**true**, warn=0.02 |
| `max_char_segment_rate` | *(not present)* | **added** target=0.0, blocking=true, warn=0.02 |
| `min_word_count_rate` | *(not present)* | **added** target=0.0, blocking=true, warn=0.05 |
| `min_segment_count` | defined, never called | still target=1, blocking=true — now **wired** in code |

**`configs/qa_validation/cleaning.yaml`**
- `word_count_filter_pass` description updated: "≥ 10 words" → "≥ 20 words"

**`src/config/qa_validation.py` — `_check_substance()`**

Added tracking variables `over_char_segments`, `under_word_segments`.
`under_word_segments` counts segments where `0 < word_count < MIN_SEGMENT_WORDS`
(empty segments are excluded — already counted by `empty_segment_rate`).

Per-filing `min_segment_count` wired as:
```python
threshold = self.registry.get("min_segment_count")
if threshold:
    for data in file_data:
        seg_count = len(self._get_segments(data))
        results.append(ValidationResult.from_threshold(threshold, seg_count))
```

### Validation run result (20260223_172129 — 6 files)

All new gates correctly fired on corpus pre-dating the quality gate:

| File | min_word_count_rate | max_char_segment_rate |
|------|--------------------|-----------------------|
| part1item1 | **FAIL** 22.9% | WARN 0.57% |
| part1item1a | **FAIL** 25.2% | WARN 0.79% |
| part1item1c | **FAIL** 25.0% | — |
| part2item7 | **FAIL** 23.3% | — |
| part2item7a | PASS | — |
| part2item8 | **FAIL** 21.4% | WARN 0.60% |

**Finding:** ~22-25% of current segments have fewer than 20 words. These are
pre-quality-gate segments produced when the minimum was 10 words. The segmenter
(`src/preprocessing/segmenter.py`) enforces `min_length` (char floor) via
`preprocessing.min_segment_length` but does not enforce a word count floor
independent of character length. Segments between 10-19 words slip through if
they are ≥ 50 chars. The corpus needs reprocessing once the segmenter enforces
`word_count ≥ 20` at production time.

---

## 5. Fixes Applied This Session

### Fix A — v2 schema identity field lookup (`qa_validation.py`)

**Root cause:** `_check_identity()` and `_check_amendments()` called `data.get("cik")` etc.
V2 structured JSON (from `_build_output_data()`) wraps these under `document_info`.

**Fix:** Added `_get_identity_field(data, field)` static method that checks top-level
first, then `document_info`:
```python
@staticmethod
def _get_identity_field(data: Dict, field: str):
    value = data.get(field)
    if value is None:
        value = data.get("document_info", {}).get(field)
    return value
```
Updated `_check_identity()` (3 calls) and `_check_amendments()` (1 call) to use it.

**Effect:** identity failures dropped from 6/6 → 0/6 (no false NO-GOs).

### Fix B — batch script self-inclusion bug (`check_preprocessing_batch.py:391`)

**Root cause:** file discovery used `run_dir.glob("*.json")` filtered only by `_` prefix.
The report written to `validation_report.json` was picked up on subsequent runs.

**Fix:** Added `and f != output_path` to the filter expression.

---

## 6. Corpus Quality Audit (7-Check Diagnostic)

`scripts/validation/data_quality/check_corpus_quality_audit.py` runs 7 independent
checks **not** hooked into the inline gatekeeper:

| Check | Issue | Severity | Threshold |
|-------|-------|----------|-----------|
| A | ToC dot-leader lines in segments | Critical | > 1% exits 1 |
| B | Zero-segment filings | Critical | > 1% exits 1 |
| C | Numeric token runs (4+ consecutive) | High | diagnostic only |
| D | Abbreviation-split segments (first word ≤3 chars) | High | diagnostic only |
| E | Segment-level exact duplicates (SHA-256) | High | diagnostic only |
| F | Modal-verb-only keyword matches | Medium | diagnostic only |
| G | yield_ppm HTML vs text denominator delta | Medium | diagnostic only |

**Checks C and D remain orphaned** — no corresponding threshold in `health_check.yaml`.

---

## 7. Remaining Gaps (Priority Order)

| # | Gap | Impact | Affected Files |
|---|-----|--------|---------------|
| 1 | 2 failing tests (Fix 4A regression + Mock bug) | CI blocked | `test_validation_integration.py:87,209` |
| 2 | 2 collection errors (_worker_parser + validator_fix) | Test suite skips | `test_pipeline_global_workers.py`, `test_validator_fix.py` |
| 3 | Segmenter does not enforce `word_count ≥ 20` | ~22-25% corpus non-compliant | `src/preprocessing/segmenter.py` |
| 4 | Checks C/D (numeric runs, abbrev-split) not gated inline | Data quality leakage | `qa_validation.py`, `health_check.yaml` |
| 5 | `SchemaValidator` ↔ `HealthCheckValidator` identity duplication | Maintenance debt | `schema_validator.py`, `qa_validation.py` |
| 6 | No Stage 0/1 thresholds | Coverage gap | `health_check.yaml` (new section needed) |
| 7 | `risk_keyword_present` non-blocking | Potential false passes | `health_check.yaml` |
| 8 | `html_artifact_rate` uses `==` not `<=` on float | Semantic oddity | `health_check.yaml:72` |

---

## 8. Integration Points

```
scripts/data_preprocessing/batch_parse.py
  └── pipeline.process_and_validate(file, validator=HealthCheckValidator())
        ├── PASS → result.save_to_json(output_dir)
        └── FAIL → quarantine_dir/*.json + *_FAILURE_REPORT.md
                   + manifest.record_failure(quarantine_path=..., validation_report=...)
```

`StateManifest` (`src/utils/state_manager.py`) tracks quarantine paths and validation
reports per file. The quarantine directory is named `quarantine_<run_id>` within
the output directory.

---

## 9. What Is Working Well

- **Config-driven architecture**: thresholds tunable via YAML only, no code changes
- **Amendment blocking**: `amendment_flag_not_amended` correctly implements ADR-011 with None→SKIP for pre-iXBRL filings
- **SIC-aware file size**: Financial/REIT filers (SIC 6000-6799) get 150 MB ceiling vs 50 MB
- **Dual-schema support**: `_get_segments()` and `_get_identity_field()` handle v1/v2 JSON
- **Quarantine pattern**: failures isolated with markdown reports and manifest tracking
- **Warn-zone semantics**: `warn_threshold` on new quality gates gives CONDITIONAL (not NO-GO) for minor violations (<2% over-char, <5% under-word), preserving signal without hard blocking edge cases
