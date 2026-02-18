---
title: "Fix Plan: run_preprocessing_pipeline.py bugs"
date: 2026-02-18T13:24:22-06:00
branch: main
commit: 0b83409a3506c212b360527f3758ed9f958a625b
researcher: bethCoderNewbie
tags: [fix, cli, preprocessing, imports, documentation, naming, state-manager, checkpoint, resource-tracker, parallel, memory-semaphore, reporting]
status: ready
research: 2026-02-18_13-24-22_run_preprocessing_pipeline_bugs.md
---

# Fix Plan: `run_preprocessing_pipeline.py` Bugs

## Desired End State

After fixes:
1. `--input FILE` and default single-file mode run without crashing
2. `README.md` example command pastes and runs correctly in bash
3. `--chunk-size` does not redundantly reload models between chunks
4. Module docstring matches actual pipeline order
5. Dead code is removed
6. Deprecation warnings are eliminated
7. Every batch run produces a stamped directory `data/processed/{YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/`
8. `data/processed/.manifest.json` tracks file hashes for hash-based incremental resume
9. `_checkpoint.json` enables mid-batch crash recovery
10. Per-file `resource_usage` (timing + memory) included in results and report
11. Adaptive timeout driven by `MemorySemaphore` file-size estimates
12. `RUN_REPORT.md` written to run dir via `MarkdownReportGenerator`
13. No duplicate resume/filtering code — all routing through canonical `src/utils` classes

## Anti-Scope (Not Doing)

- Not merging the script into `src/preprocessing/pipeline.py` (tracked separately in `2025-12-28_19-30_preprocessing_script_deduplication.md`)
- Not adding `--quiet` → log-level suppression for worker INFO logs (W2) — cosmetic, deferred
- Not pre-downloading the HuggingFace model (W3) — infra concern, out of scope

---

## Phase 1 — Critical fixes (B1, B2)

### Fix B1: Add missing imports to `run_preprocessing_pipeline.py`

**File:** `scripts/data_preprocessing/run_preprocessing_pipeline.py`

Replace lines 53–55:
```python
# BEFORE
from src.preprocessing.parser import ParsedFiling
from src.preprocessing.extractor import ExtractedSection
from src.preprocessing.segmenter import SegmentedRisks, RiskSegment
```

With:
```python
# AFTER
from src.preprocessing.parser import SECFilingParser, ParsedFiling
from src.preprocessing.extractor import SECSectionExtractor, ExtractedSection
from src.preprocessing.cleaning import TextCleaner
from src.preprocessing.segmenter import RiskSegmenter, SegmentedRisks, RiskSegment
```

**Verify:** `python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K_2021.html --no-sentiment` runs to completion without NameError.

---

### Fix B2: Remove inline comments from README bash example

**File:** `README.md`

Replace the broken block:
```bash
# Batch with options
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch \
    --workers 8 \       # parallel workers
    --resume \          # skip already-processed files
    --chunk-size 100 \  # process in memory-safe chunks
    --quiet             # minimal console output
```

With clean continuation lines (comments above each flag if explanation needed):
```bash
# Batch with options
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch \
    --workers 8 \
    --resume \
    --chunk-size 100 \
    --quiet
```

**Verify:** Copy-paste the block into a bash shell; no `error: unrecognized arguments` output.

---

## Phase 2 — Performance fix (B3)

### Fix B3: Hoist `ProcessPoolExecutor` outside the chunk loop

**File:** `scripts/data_preprocessing/run_preprocessing_pipeline.py`

**Current flow** (`run_batch_pipeline` lines 672–707):
```python
for chunk_idx, chunk in enumerate(chunks, 1):
    chunk_results = _process_chunk(chunk, ...)  # creates + destroys pool each iteration
```

**Target flow:**

Option A (preferred — single long-lived pool, process in batches of `chunk_size`):
```python
with ProcessPoolExecutor(
    max_workers=max_workers,
    initializer=_init_worker,
    initargs=(extract_sentiment,),
    max_tasks_per_child=50,
) as executor:
    for chunk_idx, chunk in enumerate(chunks, 1):
        _submit_chunk_to_executor(executor, chunk, ...)
```

Option B (simpler — document the trade-off, don't change code):
Add a note in `run_batch_pipeline`'s docstring and the `--chunk-size` help string that each chunk recreates the worker pool (model reload cost = `chunk_count × max_workers × load_time`).

**Recommendation:** Option A for correctness; Option B as a quick patch if Option A requires significant refactor of `_process_chunk`.

**Verify:** With `--chunk-size 10` and 20 files, log should show worker initialization only once (8 lines), not twice (16 lines).

---

## Phase 3 — Documentation fixes (B4, B5, W1)

### Fix B4: Correct module docstring pipeline order

**File:** `scripts/data_preprocessing/run_preprocessing_pipeline.py`, lines 17–21

```python
# BEFORE
Pipeline Flow (with metadata preservation):
    1. Parse   -> ParsedFiling (sic_code, sic_name, cik, company_name)
    2. Clean   -> cleaned text
    3. Extract -> ExtractedSection (metadata preserved)
    4. Segment -> SegmentedRisks (metadata preserved)

# AFTER
Pipeline Flow (with metadata preservation):
    1. Parse   -> ParsedFiling (sic_code, sic_name, cik, company_name)
    2. Extract -> ExtractedSection (metadata preserved)
    3. Clean   -> cleaned text
    4. Segment -> SegmentedRisks (metadata preserved)
```

---

### Fix B5: Remove dead `process_single_file()` function

**File:** `scripts/data_preprocessing/run_preprocessing_pipeline.py`, lines 417–459

Delete `process_single_file()` entirely. It is never called by any live code path. Its logic is fully superseded by `process_single_file_fast()`.

**Verify:** `grep -n "process_single_file(" scripts/data_preprocessing/run_preprocessing_pipeline.py` returns only the `_fast` variant.

---

### Fix W1: Replace deprecated path constants

**File:** `scripts/data_preprocessing/run_preprocessing_pipeline.py`

```python
# BEFORE (lines 57–64)
from src.config import (
    RAW_DATA_DIR,
    PARSED_DATA_DIR,
    EXTRACTED_DATA_DIR,
    PROCESSED_DATA_DIR,
    settings,
    ensure_directories
)

# AFTER
from src.config import settings, ensure_directories

RAW_DATA_DIR       = settings.paths.raw_data_dir
PARSED_DATA_DIR    = settings.paths.parsed_data_dir
EXTRACTED_DATA_DIR = settings.paths.extracted_data_dir
PROCESSED_DATA_DIR = settings.paths.processed_data_dir
```

> Using local aliases preserves all downstream references without touching every call-site.

**Verify:** No `DeprecationWarning` lines appear when the script is imported.

---

## Phase 4 — Integrate all `src/utils` utilities

### Audit: current usage vs. available utilities

| Utility | Used now? | Gap |
|---------|-----------|-----|
| `worker_pool.py` | ✓ | — |
| `dead_letter_queue.py` | ✓ | — |
| `progress_logger.py` | ✓ | — |
| `parallel.py` (`ParallelProcessor`) | ✗ | Script has own `ProcessPoolExecutor` in `_process_chunk()` |
| `resume.py` (`ResumeFilter`) | ✗ | Script has 3 duplicate functions: `is_file_processed`, `get_processed_files_set`, `filter_unprocessed_files` |
| `state_manager.py` (`StateManifest`) | ✗ | Resume uses output-existence only; no hash-based change detection, no `run_config` snapshot |
| `checkpoint.py` (`CheckpointManager`) | ✗ | No crash recovery between chunks |
| `resource_tracker.py` (`ResourceTracker`) | ✗ | No per-file timing or memory data in results |
| `memory_semaphore.py` (`MemorySemaphore`) | ✗ | No adaptive timeout; hard-coded `task_timeout=1200` default |
| `reporting.py` (`MarkdownReportGenerator`) | ✗ | End-of-run produces plain `batch_processing_summary.json`, no markdown report |
| `naming.py` | ✗ | Output files use ad-hoc `{stem}_segmented_risks.json` flat to `data/processed/` |
| `metadata.py` (`RunMetadata`) | ✗ | No git SHA or timestamp stamped on runs |

---

### Target output layout

```
data/processed/
├── .manifest.json                         ← StateManifest (persists across all runs)
├── 20260218_132815_preprocessing_0b83409/ ← run directory (naming.py convention)
│   ├── _checkpoint.json                   ← CheckpointManager (deleted on success)
│   ├── RUN_REPORT.md                      ← MarkdownReportGenerator output
│   ├── batch_summary.json                 ← JSON for programmatic access
│   ├── AAPL_10K_2021_segmented_risks.json
│   └── MSFT_10K_2024_segmented_risks.json
└── 20260219_094512_preprocessing_abc1234/ ← next run
    └── ...
```

---

### Step 4.1 — Run directory naming (`naming.py` + `metadata.py`)

**Replace** the flat `PROCESSED_DATA_DIR / f"{stem}_segmented_risks.json"` pattern.

```python
# In main(), before run_batch_pipeline():
from src.utils.metadata import RunMetadata
from datetime import datetime

run_meta = RunMetadata.gather()
# run_meta["git_commit"] = "0b83409"
# run_meta["timestamp"]  = "2026-02-18T13:28:15..."

run_id = datetime.fromisoformat(run_meta["timestamp"]).strftime("%Y%m%d_%H%M%S")
git_sha = run_meta["git_commit"][:7]
run_dir = settings.paths.processed_data_dir / f"{run_id}_preprocessing_{git_sha}"
run_dir.mkdir(parents=True, exist_ok=True)
```

Pass `run_dir` (not `PROCESSED_DATA_DIR`) as `output_dir` to `run_batch_pipeline()`.

Individual file output path inside workers:
```python
# In process_single_file_fast(), output path construction:
output_path = output_dir / f"{input_file.stem}_segmented_risks.json"
# → data/processed/20260218_132815_preprocessing_0b83409/AAPL_10K_2021_segmented_risks.json
```

---

### Step 4.2 — Replace 3 duplicate resume functions (`resume.py`)

**Delete** `is_file_processed()` (lines 104–116), `get_processed_files_set()` (lines 119–133), `filter_unprocessed_files()` (lines 136–154).

**Replace** with `ResumeFilter` in `main()` for within-run resume (i.e., if a run dir already exists from a crashed prior run):

```python
from src.utils.resume import ResumeFilter

if args.resume and run_dir.exists():
    resume_filter = ResumeFilter(
        output_dir=run_dir,
        output_suffix="_segmented_risks.json",
    )
    html_files = resume_filter.filter_unprocessed(html_files, quiet=args.quiet)
```

Cross-run resume (skip files processed in *any* prior run) is handled by `StateManifest` in step 4.3.

---

### Step 4.3 — Hash-based incremental tracking + config snapshot (`state_manager.py`)

`StateManifest` lives at `data/processed/.manifest.json` and persists across all runs. It replaces the output-existence resume check with content-hash change detection, and records the full run config for reproducibility.

```python
from src.utils.state_manager import StateManifest, compute_file_hash

# In main(), after building run_dir:
manifest = StateManifest(settings.paths.processed_data_dir / ".manifest.json")
manifest.load()
manifest.update_run_config(run_meta)   # captures git SHA, branch, timestamp, platform

# Cross-run resume: skip files whose content hash is unchanged since last success
if args.resume:
    html_files = [f for f in html_files if manifest.should_process(f)]

# After each successful file (called from result-collection loop in run_batch_pipeline):
manifest.record_success(
    input_path=input_path,
    output_path=output_path,
    run_id=run_id,
)

# After each failed file:
manifest.record_failure(
    input_path=input_path,
    run_id=run_id,
    reason=result.get("error", "unknown"),
)

# Save manifest atomically after every chunk:
manifest.save()

# At end of run, prune deleted source files:
manifest.prune_deleted_files(settings.paths.raw_data_dir)
manifest.save()
```

---

### Step 4.4 — Crash recovery (`checkpoint.py`)

`CheckpointManager` saves progress after each chunk so a crash can resume mid-batch.

```python
from src.utils.checkpoint import CheckpointManager

# In run_batch_pipeline(), after creating run_dir:
checkpoint = CheckpointManager(run_dir / "_checkpoint.json")

# Resume from mid-run checkpoint if it exists:
if args.resume and checkpoint.exists():
    processed_set, prior_results, metrics = checkpoint.load()
    html_files = [f for f in html_files if f.name not in processed_set]
    results.extend(prior_results)

# After each chunk completes:
checkpoint.save(
    processed_files=[r["file"] for r in results],
    results=results,
    metrics={"successful": successful, "failed": failed, "warnings": warnings},
)

# On successful completion:
checkpoint.cleanup()
```

---

### Step 4.5 — Per-file resource profiling (`resource_tracker.py`)

Wrap each step in `process_single_file_fast()` with `ResourceTracker`. Include timing and memory in the result dict for aggregation into the run report.

```python
from src.utils.resource_tracker import ResourceTracker

def process_single_file_fast(args):
    input_file, save_intermediates = args
    tracker = ResourceTracker()

    with tracker.track_module("parse"):
        filing = get_worker_parser().parse_filing(...)

    with tracker.track_module("extract"):
        risk_section = get_worker_extractor().extract_risk_factors(filing)

    with tracker.track_module("clean"):
        cleaned_text = get_worker_cleaner().clean_text(...)

    with tracker.track_module("segment"):
        segmented_risks = get_worker_segmenter().segment_extracted_section(...)

    usage = tracker.finalize()

    return {
        ...existing keys...,
        "resource_usage": usage.to_dict(),
        # e.g. {"elapsed_time": 14.2, "peak_memory_mb": 940, "module_timings": {...}}
    }
```

---

### Step 4.6 — Replace `_process_chunk()` with `ParallelProcessor` (`parallel.py`)

This consolidates B3 (pool rebuild) and the custom executor logic in a single change. `ParallelProcessor` keeps one long-lived pool for the full batch and already integrates `DeadLetterQueue`.

```python
from src.utils.parallel import ParallelProcessor

# In run_batch_pipeline(), replacing _process_chunk():
processor = ParallelProcessor(
    max_workers=max_workers,
    initializer=_init_worker,
    initargs=(extract_sentiment,),   # ParallelProcessor passes initargs to ProcessPoolExecutor
    max_tasks_per_child=50,
    task_timeout=adaptive_timeout,   # from MemorySemaphore (step 4.7)
)

processing_results = processor.process_batch(
    items=task_args,
    worker_func=process_single_file_fast,
    progress_callback=_on_progress,
    verbose=not quiet,
)
```

> Note: `ParallelProcessor.__init__` currently does not accept `initargs`. Add `initargs: Optional[tuple] = None` parameter and thread it into `ProcessPoolExecutor(initializer=..., initargs=...)`.

---

### Step 4.7 — Adaptive timeout (`memory_semaphore.py`)

Replace hard-coded `task_timeout=1200` with a per-batch adaptive value derived from file sizes.

```python
from src.utils.memory_semaphore import MemorySemaphore, FileCategory

# In run_batch_pipeline(), before creating ParallelProcessor:
semaphore = MemorySemaphore()
estimates = [semaphore.get_resource_estimate(Path(fp)) for fp in html_files]
adaptive_timeout = max(est.recommended_timeout_sec for est in estimates)

large_count = sum(1 for e in estimates if e.category == FileCategory.LARGE)
if large_count:
    logger.info(f"{large_count} large files detected; timeout={adaptive_timeout}s")
```

---

### Step 4.8 — Markdown run report (`reporting.py`)

Replace plain `batch_processing_summary.json` with a `MarkdownReportGenerator` report written into the run dir, plus a JSON file for programmatic access.

```python
from src.utils.reporting import MarkdownReportGenerator

# After processing completes:
generator = MarkdownReportGenerator()
report_md = generator.generate_run_report(
    run_id=run_id,
    run_name="preprocessing",
    metrics={
        "total_files": total_files,
        "successful": successful,
        "failed_or_skipped": failed + warnings,
        "quarantined": failed,
        "form_type": "10-K/10-Q",
        "run_id": run_id,
    },
    output_dir=run_dir,
    manifest_stats=manifest.get_statistics(),
    failed_files=manifest.get_failed_files(),
    git_sha=git_sha,
    config_snapshot=run_meta,
    start_time=start_iso,
    end_time=datetime.now().isoformat(),
)

(run_dir / "RUN_REPORT.md").write_text(report_md)

# Also write JSON summary for backward compatibility / downstream scripts:
import json
(run_dir / "batch_summary.json").write_text(
    json.dumps({
        "version": "3.0",
        "run_id": run_id,
        "git_sha": git_sha,
        "total_files": total_files,
        "successful": successful,
        "warnings": warnings,
        "failed": failed,
        "run_dir": str(run_dir),
        "manifest": str(settings.paths.processed_data_dir / ".manifest.json"),
        "results": processing_results,
    }, indent=2)
)
```

---

### Step 4.9 — Update `--resume` and `--chunk-size` help strings

With the new architecture, the semantics of both flags change:

```python
parser.add_argument(
    '--resume',
    action='store_true',
    help=(
        'Skip files already processed in any prior run (hash-based via StateManifest). '
        'Also resumes mid-run from checkpoint if run dir exists.'
    )
)
parser.add_argument(
    '--chunk-size',
    type=int,
    default=None,
    help=(
        'Save manifest and checkpoint every N files. '
        'Does NOT restart the worker pool between chunks (single long-lived pool). '
        'Recommended: 100–200 for crash-recovery granularity on large batches.'
    )
)
```

---

## Execution Order

| Phase | Fix | File | Risk |
|-------|-----|------|------|
| 1 | B1 — add missing imports | `run_preprocessing_pipeline.py` | Low — additive only |
| 1 | B2 — fix README bash block | `README.md` | None |
| 2 | B3 — hoist executor via `ParallelProcessor` | `run_preprocessing_pipeline.py` | Medium — replaces `_process_chunk` |
| 3 | B4 — fix docstring order | `run_preprocessing_pipeline.py` | None |
| 3 | B5 — remove dead function | `run_preprocessing_pipeline.py` | Low — no callers |
| 3 | W1 — remove deprecated imports | `run_preprocessing_pipeline.py` | Low — aliases preserve call-sites |
| 4.1 | Run directory naming | `run_preprocessing_pipeline.py` | Medium — changes output contract |
| 4.2 | Replace duplicate resume functions with `ResumeFilter` | `run_preprocessing_pipeline.py` | Low — same logic, canonical impl |
| 4.3 | `StateManifest` for hash-based tracking | `run_preprocessing_pipeline.py` | Medium — new `.manifest.json` |
| 4.4 | `CheckpointManager` for crash recovery | `run_preprocessing_pipeline.py` | Low — additive |
| 4.5 | `ResourceTracker` per-file profiling | `run_preprocessing_pipeline.py` | Low — additive |
| 4.6 | `ParallelProcessor` replaces `_process_chunk` | `run_preprocessing_pipeline.py` | Medium — also fixes B3 |
| 4.7 | `MemorySemaphore` adaptive timeout | `run_preprocessing_pipeline.py` | Low — already used in `pipeline.py` |
| 4.8 | `MarkdownReportGenerator` run report | `run_preprocessing_pipeline.py` | Low — additive |
| 4.9 | Update help strings | `run_preprocessing_pipeline.py` | None |

---

## Verification Checklist

```bash
# B1: single-file mode no longer crashes
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --input data/raw/AAPL_10K_2021.html --no-sentiment
# Expected: "Pipeline complete!" with segment count

# B2: README command works as pasted
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch --workers 8 --resume --chunk-size 100 --quiet
# Expected: no "unrecognized arguments" error

# W1: no deprecation warnings
python -W error::DeprecationWarning \
    scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --quiet
# Expected: exits cleanly, no DeprecationWarning raised as error

# B5: dead code removed
grep -n "def process_single_file\b" \
    scripts/data_preprocessing/run_preprocessing_pipeline.py
# Expected: no match (only process_single_file_fast remains)

# Phase 4: run directory created with convention-compliant name
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch --workers 4 --quiet
ls data/processed/
# Expected: 20260218_??????_preprocessing_??????7/ directory

# Phase 4: manifest written
ls data/processed/.manifest.json
# Expected: file exists

# Phase 4: RUN_REPORT.md written inside run dir
ls data/processed/20260218_*/RUN_REPORT.md
# Expected: file exists

# Phase 4: no more flat _segmented_risks.json in data/processed/ root
ls data/processed/*_segmented_risks.json 2>/dev/null
# Expected: no output (all files now inside run subdirectory)
```
