# Changelog

All significant changes to the SEC 10-K Risk Factor Analyzer are recorded here.
Format: newest first. Dates are the date of the commit or implementation.

---

## 2026-02-18 — Documentation Reorganization (Four Pillars)

**Commits:** `2ee61c4`, `469d6cd`

- Reorganized `docs/` around four audience pillars: Context, Architecture, Operations, Data
- Added per-directory `README.md` index files for all `docs/` subdirectories
- Updated root `docs/README.md` with full directory table and naming conventions
- Added coverage of all `src/utils/` modules to documentation

---

## 2026-02-17 — Pipeline Bug Fixes (B1–B5)

**Commits:** `c6110c0`, `535110d`

- Integrated all `src/utils/` (worker pool, DLQ, resource tracker, progress logger, resume filter) into `run_preprocessing_pipeline.py`
- Fixed five bugs identified in the B1–B5 fix plan:
  - B1: Missing utility imports in run script
  - B2: Checkpoint resume not wiring through pipeline
  - B3: DLQ not draining on final run
  - B4: Worker count not respecting memory limits
  - B5: Progress logger not flushing on pipeline exit

---

## 2026-02-17 — Test Suite (186 Tests)

**Commit:** `0b83409`

- Added unit tests for all new utilities and Pydantic models
- 186 tests covering: worker pool, resource tracker, DLQ, checkpoint, resume filter, progress logger, all config models

---

## 2026-02-16 — Worker Pool, Resource Tracker, DLQ Utilities

**Commits:** `fae1fff`, `61ede9f`

- Added `src/utils/worker_pool.py`: memory-aware worker pool with configurable concurrency
- Added `src/utils/resource_tracker.py`: per-filing memory and CPU tracking
- Added `src/utils/dlq.py`: dead-letter queue for failed filings with retry support
- Added `src/utils/interim_saver.py`: periodic interim saves during long runs
- Added `src/utils/resume_filter.py`: skip already-processed filings on restart
- Added pipeline resume support via checkpoint state

---

## 2026-02-10 — Memory-Aware Resource Allocation

**Commits:** `ef06967`, `8bb512c`

- Implemented Phase 1 memory-aware resource allocation
- Global worker pattern for production pipeline
- Removed sanitization from hot path (performance optimization)
- Added preprocessing timeout handling

---

## 2026-01-03 to 2026-01-04 — Validation Framework & Test Infrastructure

**Commits:** `80b3c73`, `648bf25`, `7942943`

- Added corpus validation utility for topic modeling
- Added data health check validation system for preprocessing output
- Added gatekeeper workflow with configurable validation gates
- Added comprehensive research templates

---

## 2025-12-12 — HTML Sanitizer (Pre-Parser Cleaning)

**Module:** `src/preprocessing/sanitizer.py`

Added `HTMLSanitizer` to clean raw HTML **before** sec-parser processing. The pipeline is now 5 steps:

```
SANITIZE → PARSE → EXTRACT → CLEAN → SEGMENT
```

**Options (all configurable via `configs/config.yaml`):**

| Option | Default | Description |
|--------|---------|-------------|
| `decode_entities` | `true` | `&amp;` → `&`, `&nbsp;` → space |
| `normalize_unicode` | `true` | NFKC normalization |
| `remove_invisible_chars` | `true` | Zero-width spaces, control chars |
| `normalize_quotes` | `true` | Curly → straight quotes |
| `remove_edgar_header` | `false` | **Disabled** — breaks CIK/SIC metadata |
| `remove_edgar_tags` | `false` | **Disabled** — breaks sec-parser structure |
| `flatten_nesting` | `true` | Remove redundant nested tags |
| `fix_encoding` | `false` | Mojibake fix (requires `ftfy`) |

**Measured on AAPL_10K_2021.html:** 1.9% HTML reduction, 54 segments extracted, metadata preserved.

---

## 2025-12-12 — Preprocessing Pipeline Restructure

**Module:** `src/preprocessing/pipeline.py` (new)

Complete restructure for end-to-end metadata preservation:

- New `SECPreprocessingPipeline` orchestrator class
- New `PipelineConfig` as Pydantic V2 `BaseModel` (replaces `@dataclass`)
- New `SegmentedRisks` and `RiskSegment` Pydantic models — metadata travels with every segment
- `ExtractedSection` extended with filing-level metadata: `sic_code`, `sic_name`, `cik`, `ticker`, `company_name`, `form_type`
- `SegmentedRisks.save_to_json()` / load methods
- Output format bumped to **v2.0** (structured JSON with top-level metadata)

**Bug fixes:**
- `cleaning.py`: Fixed `deep_clean=True` failing when spaCy wasn't pre-initialized (lazy init)
- `segmenter.py`: Replaced `print()` with `logging`

---

## 2025-12-03 — Configuration Modularization

**Module:** `src/config/` (replaces `src/config.py`)

Refactored monolithic `src/config.py` (1,126 lines) into 16 domain-specific modules:

```
src/config/
├── __init__.py       # Main Settings class + global instance
├── _loader.py        # Single cached YAML loader (was 5 duplicates)
├── paths.py
├── sec_parser.py
├── models.py
├── preprocessing.py
├── extraction.py
├── sec_sections.py
├── testing.py
├── run_context.py
├── legacy.py         # Deprecation warnings for old imports
└── features/
    ├── sentiment.py
    ├── topic_modeling.py
    ├── readability.py
    └── risk_analysis.py
```

No breaking changes — legacy imports continue to work but emit `DeprecationWarning`.

**Metrics:** 1,126-line file → ~65 avg lines/file; YAML loader: 5 → 1 (cached); module-level I/O: 5 → 0 (lazy).

---

## 2025-11-17 (approx.) — sec-parser Integration

**Commits:** `ea45dd2` area

Complete rewrite of `parser.py` and `extractor.py` to use the `sec-parser` library:

- `SECFilingParser` replaces regex-based `FilingParser` — uses semantic tree
- `SECSectionExtractor` replaces regex section matching — navigates hierarchical tree
- `RiskFactorExtractor` convenience wrapper for Item 1A extraction
- `sec-parser==0.54.0` **pinned** for reproducibility
- Python minimum bumped from 3.8 → **3.10**
- Added `pyproject.toml` tool configs: `black`, `ruff`, `mypy`, `isort`, `pytest-cov`
- Created `requirements-dev.txt` separating dev from runtime deps
- Created `.env.example` environment variable template
- Added `examples/01_basic_extraction.py` and `examples/02_complete_pipeline.py`

**Breaking changes:**
- Input format: now requires HTML (not TXT)
- Return types: dataclasses, not strings — use `.text`, `.subsections`, `.elements`

---

## Version Reference

| Component | Version |
|-----------|---------|
| Project | 0.1.0 |
| Python | ≥ 3.10 |
| sec-parser | 0.54.0 (pinned) |
| Pydantic | ≥ 2.12.4 (V2 enforced) |
