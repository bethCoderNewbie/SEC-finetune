---
# ADR-019: Boundary Quality Validation Gates

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-08-13 |
| **Author** | Beth |
| **Supersedes** | None |
| **References** | ADR-015, ADR-016, ADR-018, PRD-002 |

---

## Context

`HealthCheckValidator` (`src/config/qa_validation.py:593`) validates at the **batch** level
via `check_run()` and `check_single()`, checking identity completeness, cleanliness,
substance, and domain rules against configurable YAML thresholds. However, no per-filing
or per-record validation exists at the five system boundaries where data crosses from one
layer to another:

1. **DB ingestion** (`database.py:_import_segmented_json`) — only checks `ticker`/`fiscal_year`
2. **Classify boundary** (`database.py:classify_and_store`) — zero validation before annotator
3. **Annotator input** (`segment_annotator.py:annotate`) — trusts all segments have valid text
4. **JSONL export** (`segment_annotator.py:annotate_run_dir`) — writes records without schema validation
5. **CLI audit** (`storage/cli.py`) — no way to detect existing data quality issues in the DB

Bad data (zero segments, HTML artifacts, missing CIK, out-of-range confidence, invalid labels)
propagates silently from preprocessing into the DB and downstream. Every consumer makes
implicit trust assumptions about data quality, but nothing enforces them.

---

## Decision

### 1. Add per-filing and per-record validation gates at each boundary

Two pure functions in `src/validation/quality_gates.py`:

- **`validate_filing(data: Dict) -> FilingValidationResult`** — per-filing gate that checks
  structural pre-conditions (ticker present, fiscal_year 4-digit, filed_as_of_date present)
  then delegates to `HealthCheckValidator.check_single()` for rate-based checks.

- **`validate_classification_record(record: Dict) -> FilingValidationResult`** — per-record
  gate that validates PRD-002 section 2.2 required fields (text, label, risk_label, confidence,
  label_source, word_count, char_count, ticker) and ADR-015/ADR-016 value constraints.

### 2. Reuse existing infrastructure

- Rate-based checks (identity, cleanliness, substance, domain) delegate to
  `HealthCheckValidator.check_single()` — no threshold duplication.
- Value constraints import `ARCHETYPE_NAMES`, `ARCHETYPE_LABEL_MAP`, `_VALID_LABEL_SOURCES`
  from `src.analysis.segment_annotator` — not hardcoded lists.
- `FilingValidationResult` dataclass provides structured output with `is_valid`, `status`,
  `blocking_failures`, `warnings`, and `details` for logging/debugging.

### 3. Integrate at five boundaries

| Boundary | File | Behavior on failure |
|----------|------|-------------------|
| DB ingestion | `database.py:_import_segmented_json` | Log warning, return 0 (skip) |
| Classify | `database.py:classify_and_store` | Raise `ValueError` (caller catches) |
| Annotator input | `segment_annotator.py:annotate` | Filter degenerate segments inline |
| JSONL export | `segment_annotator.py:annotate_run_dir` | Skip invalid records with warning |
| CLI audit | `storage/cli.py:_run_quality_audit` | Report via `status --quality` flag |

### 4. CLI quality audit

`python -m src.storage.cli status --quality` runs aggregate SQL queries against the filings
and classifications tables to detect existing data quality issues (missing CIK, zero segments,
invalid labels, out-of-range confidence, invalid label sources).

---

## Consequences

### Positive

- Bad data caught at point of entry, not downstream where it causes silent corruption
- Structured `FilingValidationResult` enables programmatic logging and debugging
- CLI audit provides visibility into existing DB data quality without re-processing
- No new framework — two pure functions, minimal API surface

### Negative

- `_import_segmented_json` and `classify_and_store` are slightly slower (one
  `HealthCheckValidator.check_single()` call per filing, typically <10ms)
- `classify_and_store` double-loads the JSON file (once for validation, once for
  `SegmentedRisks`); acceptable for files typically <500KB processed once per filing
- Existing test fixtures needed updates to include valid segments that pass quality gates

---

## References

- ADR-018: SQLite filing database (defines the storage layer these gates protect)
- ADR-015: `label_source` namespace (constraints enforced by `validate_classification_record`)
- ADR-016: SASB 5-dimension taxonomy (constraints enforced by `validate_classification_record`)
- PRD-002 section 2.2: Feature schema (defines required classification record fields)
- `src/config/qa_validation.py:593-696`: `HealthCheckValidator.check_single()` implementation
- `src/validation/quality_gates.py`: Gate implementations
