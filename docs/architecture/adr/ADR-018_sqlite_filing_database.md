---
# ADR-018: SQLite Filing Database for Pre-Computed Classification Cache

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-08-13 |
| **Author** | Beth |
| **Supersedes** | PRD-005 §10 Tech Req #6 ("No new database dependency") |
| **References** | PRD-005, ADR-007, ADR-017 |

---

## Context

The analysis layer (PRD-005 / ADR-017) forces users to wait 5–10 minutes per filing
because three architectural bottlenecks compound on every command invocation:

1. **Filing lookup is O(n) glob-and-parse.** `filing_loader._find_segmented_files()`
   (`src/analysis/skills/filing_loader.py:83-99`) runs `rglob("*_segmented.json")` across
   the entire processed directory, opens every JSON file, parses `document_info`, and
   checks ticker + fiscal_year. With 4,345 files in the current run directory, this means
   thousands of JSON parses to find one match. Measured cost: **1,435ms per lookup**.

2. **Classification is re-computed from scratch every time.** `classify_filing()`
   (`src/analysis/skills/classifier.py:53-57`) instantiates a new `SegmentAnnotator`,
   which loads the BART-MNLI model onto the device (5–10 seconds for model loading alone),
   then runs NLI inference over 30–100 segments (1–5 minutes). Zero classification results
   are persisted. Running `analyze company AAPL` followed by `compare AAPL MSFT`
   re-classifies AAPL from scratch.

3. **The orchestrator's in-process cache dies with the process.**
   `AnalysisOrchestrator._context` (`src/analysis/orchestrator.py:147`) is an ephemeral
   dict. It provides zero benefit across CLI invocations.

At S&P 500 scale (500 companies × 5 years × 5 sections = 12,500+ files), the glob-based
lookup is unusable. The state manager (`src/utils/state_manager.py:16-18`) already
diagnosed this: "When parallelizing, migrate to file locking or SQLite."

PRD-005 §10 Tech Req #6 states "No new database dependency." This was appropriate when
the analysis layer was a prototype with <200 filings. At production scale with 4,345+
filings and pre-computation requirements, a derived index is necessary.

---

## Decision

### 1. Use SQLite (not PostgreSQL)

Single-developer project. No multi-user web server. File-based workflow. SQLite is
embedded, zero-config, and handles 12,500+ records trivially. WAL mode supports concurrent
reads from Streamlit while a background job writes. PostgreSQL adds operational overhead
(daemon, connection management, backup, credentials) with no benefit at this scale.

**Implemented in:** `src/storage/database.py:FilingDatabase`

### 2. Three-Table Schema

```sql
filings         — one row per (ticker, fiscal_year, form_type, section_id)
classifications — one row per classified segment, FK → filings
risk_scores     — one row per filing, FK → filings
```

Indexes on `(ticker, fiscal_year)`, `(sic_code, fiscal_year)`, `(form_type, fiscal_year)`,
`(risk_label, ticker)` cover the critical query patterns identified in RFC-008.

**Implemented in:** `src/storage/database.py:_SCHEMA_SQL` (lines 34–78)

### 3. Database Supplements JSON — Does Not Replace It

Stamped run directories (ADR-007) remain the authoritative source. The database is a
derived index. If deleted, `backfill_from_run_dir()` reconstructs it from JSON files.
This preserves the immutable audit trail.

**Implemented in:** `src/storage/database.py:FilingDatabase.backfill_from_run_dir()`

### 4. Cache Invalidation via Classifier Version Hash

SEC filings are immutable (amendments get new accession numbers). Classification results
invalidate only when the classifier configuration changes. A short hash of
`model_name:confidence_threshold:gate_threshold:merge_lo:merge_hi` tracks the active
configuration. `classify-all` re-classifies only filings where `classifier_version`
doesn't match the current config.

```python
version_inputs = f"{model_name}:{confidence_threshold}:{gate_threshold}:{merge_lo}:{merge_hi}"
classifier_version = hashlib.sha256(version_inputs.encode()).hexdigest()[:12]
```

**Implemented in:** `src/storage/database.py:compute_classifier_version()`

### 5. DB Lookup With Glob Fallback

All DB-backed lookups (filing loader, classifier cache, SIC ticker search) fall back to
the original glob/re-compute path if the DB file does not exist. This ensures the system
works identically on a fresh checkout with no database.

**Implemented in:**
- `src/analysis/skills/filing_loader.py:_find_segmented_files_via_db()` (lines 80–97)
- `src/analysis/skills/classifier.py:_try_cached_classifications()` (lines 37–79)
- `src/analysis/orchestrator.py:_find_tickers_for_sic_via_db()` (lines 611–633)

### 6. Admin CLI for Database Operations

```
python -m src.storage.cli status           # DB statistics
python -m src.storage.cli backfill <dir>   # import from run dir
python -m src.storage.cli backfill-latest  # import from most recent run dir
python -m src.storage.cli classify-all     # batch classify (loads model once)
```

**Implemented in:** `src/storage/cli.py`

### 7. Configuration

`AnalysisConfig.db_path` defaults to `data/sec_filings.db`. Overridable via
`SEC_ANALYSIS__DB_PATH` environment variable (ADR-006 pattern).

**Implemented in:** `src/config/analysis.py:45`

---

## Consequences

### Positive

- Filing lookup drops from 1,435ms (glob) to 0.036ms (index) — **40,000x speedup**.
- Pre-computed classifications serve in <1ms. No BART model loading on cache hit.
- Batch classification loads `SegmentAnnotator` once for all filings, amortizing the
  5–10 second model load across thousands of filings instead of paying it per-command.
- `backfill_from_run_dir()` imports 4,335 records in 3.2 seconds (1,358 records/s).
  Full reconstruction from JSON is fast enough to be a recovery path, not a migration.
- DB file is 1.9 MB for 238 tickers × 5 years — negligible storage overhead.
- `data/sec_filings.db` is excluded by `.gitignore:112` (`*.db` rule). No risk of
  committing binary data.

### Negative / Trade-offs

- **New dependency on SQLite** — contradicts PRD-005 §10 Tech Req #6. This ADR
  supersedes that requirement with justification (scale forced the change).
- **Stale DB risk** — if a user runs preprocessing and creates a new run directory without
  re-backfilling, the DB returns paths from the old run. No automatic invalidation exists.
  Mitigation: `backfill-latest` CLI command; future work could hook into the preprocessing
  pipeline's exit to auto-backfill.
- **No schema migration mechanism** — `CREATE TABLE IF NOT EXISTS` means column additions
  require deleting and re-creating the DB. Acceptable for a single-developer project where
  the DB is a derived artifact; would need `alembic` or equivalent if the schema stabilizes
  and classifications become expensive to recompute.
- **No connection pooling** — each DB lookup opens a fresh `sqlite3.Connection`. Adds
  ~0.5ms overhead per call. Acceptable for CLI usage; would need a singleton or thread-local
  pool if used in a web server context (Phase 4).

---

## Supersedes

PRD-005 §10, Technical Requirement #6:
> "No new database dependency — all state in files (`data/reports/`); no SQLite, Redis,
> or similar."

This requirement is superseded. SQLite is now a production dependency of the analysis
layer. The decision is justified by the measured 40,000x lookup speedup and the
requirement for pre-computed classification caching at S&P 500 scale.

---

## References

- `src/storage/database.py` — `FilingDatabase` class, schema, backfill, queries
- `src/storage/cli.py` — admin CLI commands
- `src/storage/__init__.py` — package exports
- `src/config/analysis.py:45` — `db_path` configuration field
- `src/analysis/skills/filing_loader.py:80-97` — DB-backed lookup with fallback
- `src/analysis/skills/classifier.py:37-79` — classification cache check
- `src/analysis/orchestrator.py:611-633` — SIC ticker DB lookup
- `src/utils/state_manager.py:16-18` — original recommendation to migrate to SQLite
- `scripts/data_preprocessing/classify_batch.py` — batch classification script
- ADR-007 — stamped run directories (authoritative source; DB supplements)
- ADR-017 — agentic analysis orchestration (query patterns driving schema design)
