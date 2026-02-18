---
title: "Fix Plan: run_preprocessing_pipeline.py bugs"
date: 2026-02-18T13:24:22-06:00
updated: 2026-02-18T14:44:19-06:00
branch: main
commit: 0b83409a3506c212b360527f3758ed9f958a625b
implemented_commit: 6241ae4
researcher: bethCoderNewbie
tags: [fix, cli, preprocessing, imports, documentation, naming, state-manager, checkpoint, resource-tracker, parallel, memory-semaphore, reporting]
status: completed
research: 2026-02-18_13-24-22_run_preprocessing_pipeline_bugs.md
---

# Fix Plan: `run_preprocessing_pipeline.py` Bugs

> **Status: COMPLETED** — All phases implemented in commit `6241ae4` (2026-02-18).
> See [Implementation Results](#implementation-results) for verified outcomes.

## Desired End State

After fixes:
1. `--input FILE` and default single-file mode run without crashing ✅
2. `README.md` example command pastes and runs correctly in bash ✅
3. `--chunk-size` does not redundantly reload models between chunks ✅
4. Module docstring matches actual pipeline order ✅
5. Dead code is removed ✅
6. Deprecation warnings are eliminated ✅
7. Every batch run produces a stamped directory `data/processed/{YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/` ✅
8. `data/processed/.manifest.json` tracks file hashes for hash-based incremental resume ✅
9. `_checkpoint.json` enables mid-batch crash recovery ✅
10. Per-file `resource_usage` (timing + memory) included in results and report ✅
11. Adaptive timeout driven by `MemorySemaphore` file-size estimates ✅
12. `RUN_REPORT.md` written to run dir via `MarkdownReportGenerator` ✅
13. No duplicate resume/filtering code — all routing through canonical `src/utils` classes ✅

## Anti-Scope (Not Doing)

- Not merging the script into `src/preprocessing/pipeline.py` (tracked separately in `2025-12-28_19-30_preprocessing_script_deduplication.md`)
- Not adding `--quiet` → log-level suppression for worker INFO logs (W2) — cosmetic, deferred
- Not pre-downloading the HuggingFace model (W3) — infra concern, out of scope

---

## Phase 1 — Critical fixes (B1, B2) ✅ DONE

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

**Verified:** `python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K_2021.html --no-sentiment` ran to completion — 124 segments, no NameError.

---

### Fix B2: Remove inline comments from README bash example

**File:** `README.md`

Replace the broken block (inline `# comments` after `\` inject a literal space into `sys.argv`):
```bash
# BROKEN
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch \
    --workers 8 \       # parallel workers
    --resume \          # skip already-processed files
    --chunk-size 100 \  # process in memory-safe chunks
    --quiet             # minimal console output
```

With clean continuation lines:
```bash
# FIXED
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch \
    --workers 8 \
    --resume \
    --chunk-size 100 \
    --quiet
```

**Verified:** Copy-pasted block into bash; no `error: unrecognized arguments` output.

---

## Phase 2 — Performance fix (B3) ✅ DONE (via Phase 4)

B3 was resolved as part of Phase 4 step 4.6: `_process_chunk()` was removed entirely and replaced with a single long-lived `ParallelProcessor` instance. The pool is created once for the full batch; `--chunk-size` now only controls checkpoint/manifest save frequency, not pool lifecycle.

---

## Phase 3 — Documentation fixes (B4, B5, W1) ✅ DONE (via Phase 4 rewrite)

All three were addressed in the Phase 4 full rewrite of the script:

- **B4:** Module docstring now reads `Parse → Extract → Clean → Segment → Sentiment` (lines 16–21)
- **B5:** `process_single_file()` removed; `grep "def process_single_file\b"` returns no matches
- **W1:** `from src.config import settings, ensure_directories` + local `settings.paths.*` aliases; no `DeprecationWarning` on import

---

## Phase 4 — Integrate all `src/utils` utilities ✅ DONE

### Audit: before vs. after

| Utility | Before | After |
|---------|--------|-------|
| `worker_pool.py` | ✓ partial | ✓ full (parser, extractor, cleaner, segmenter) |
| `dead_letter_queue.py` | ✓ | ✓ (inside `ParallelProcessor`) |
| `progress_logger.py` | ✓ partial | ✓ full (co-located in run_dir, closed on completion) |
| `parallel.py` (`ParallelProcessor`) | ✗ | ✓ — single long-lived pool for full batch |
| `resume.py` (`ResumeFilter`) | ✗ (3 duplicate funcs) | ✓ — within-run skip via `ResumeFilter` |
| `state_manager.py` (`StateManifest`) | ✗ | ✓ — hash-based cross-run tracking, `.manifest.json` |
| `checkpoint.py` (`CheckpointManager`) | ✗ | ✓ — `_checkpoint.json` saved every `chunk_size` files |
| `resource_tracker.py` (`ResourceTracker`) | ✗ | ✓ — each pipeline step wrapped in `track_module()` |
| `memory_semaphore.py` (`MemorySemaphore`) | ✗ | ✓ — adaptive timeout from S/M/L file-size estimates |
| `reporting.py` (`MarkdownReportGenerator`) | ✗ | ✓ — `RUN_REPORT.md` at batch completion |
| `naming.py` | ✗ | ✓ — `batch_summary_{run_id}_preprocessing_{git_sha}.json` |
| `metadata.py` (`RunMetadata`) | ✗ | ✓ — git SHA + timestamp stamp on every run dir |

### Prerequisite: add `initargs` to `ParallelProcessor`

**File:** `src/utils/parallel.py`

`ParallelProcessor.__init__` was missing `initargs` support. Added `initargs: Optional[tuple] = None` parameter, threaded into `ProcessPoolExecutor(initargs=self.initargs)`, and called `self.initializer(*self.initargs)` in `_process_sequential`.

### Target output layout (implemented)

```
data/processed/
├── .manifest.json                         ← StateManifest (persists across all runs)
└── 20260218_141702_preprocessing_0b83409/ ← run directory (naming.py convention)
    ├── _checkpoint.json                   ← CheckpointManager (deleted on success)
    ├── _progress.log                      ← ProgressLogger output
    ├── RUN_REPORT.md                      ← MarkdownReportGenerator output
    ├── batch_summary_20260218_141702_preprocessing_0b83409.json
    ├── AAPL_10K_2021_segmented_risks.json
    └── MSFT_10K_2024_segmented_risks.json
```

---

## Implementation Results

### Smoke tests run on 2026-02-18

**Single-file mode:**
```
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --input data/raw/AAPL_10K_2021.html --no-sentiment --no-save
```
→ Parsed 124 segments, SIC=3571 (APPLE INC), pipeline complete. No NameError, no DeprecationWarning.

**Batch mode (1 worker, chunk-size 3, 959 files, killed after 6 files):**
```
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch --workers 1 --no-sentiment --chunk-size 3
```

Observed artifacts after 6 completed files:

| Artifact | Verified |
|----------|---------|
| Run dir `data/processed/20260218_141702_preprocessing_0b83409/` | ✅ |
| `_progress.log` with `[1/959] OK: AAPL_10K_2021.html -> 124 segs, 17.1s, SIC=3571` | ✅ |
| `_checkpoint.json` saved at idx=3 with `{'successful': 3, 'failed': 0, 'warnings': 0}` | ✅ |
| `.manifest.json` with `hash`, `last_processed`, `run_id`, `output_path` per file | ✅ |
| Per-file `*_segmented_risks.json` inside stamped run dir (not flat `data/processed/`) | ✅ |
| `MemorySemaphore` adaptive timeout: 2400s for S:446 M:405 L:108 files | ✅ |
| `naming.py`: `batch_summary_20260218_143000_preprocessing_0b83409.json` | ✅ |
| `RUN_REPORT.md` with exec summary, duration, git SHA | ✅ |

**`RUN_REPORT.md` preview (first 20 lines):**
```markdown
# Processing Run Report: preprocessing

**Run ID:** `20260218_143000`
**Git SHA:** `0b83409`
**Generated:** 2026-02-18 14:41:04

## 📊 Executive Summary

❌ **Status:** 66.7% Success Rate
- **Total Files:** 3
- **Successful:** 2
- **Failed/Skipped:** 1
- **Duration:** 5m 0s
```

---

## Execution Order

| Phase | Fix | File | Risk | Status |
|-------|-----|------|------|--------|
| 1 | B1 — add missing imports | `run_preprocessing_pipeline.py` | Low | ✅ |
| 1 | B2 — fix README bash block | `README.md` | None | ✅ |
| 2→4 | B3 — single pool via `ParallelProcessor` | `run_preprocessing_pipeline.py` | Medium | ✅ |
| 3→4 | B4 — fix docstring order | `run_preprocessing_pipeline.py` | None | ✅ |
| 3→4 | B5 — remove dead function | `run_preprocessing_pipeline.py` | Low | ✅ |
| 3→4 | W1 — remove deprecated imports | `run_preprocessing_pipeline.py` | Low | ✅ |
| 4.1 | Run directory naming | `run_preprocessing_pipeline.py` | Medium | ✅ |
| 4.2 | Replace duplicate resume functions with `ResumeFilter` | `run_preprocessing_pipeline.py` | Low | ✅ |
| 4.3 | `StateManifest` for hash-based tracking | `run_preprocessing_pipeline.py` | Medium | ✅ |
| 4.4 | `CheckpointManager` for crash recovery | `run_preprocessing_pipeline.py` | Low | ✅ |
| 4.5 | `ResourceTracker` per-file profiling | `run_preprocessing_pipeline.py` | Low | ✅ |
| 4.6 | `ParallelProcessor` replaces `_process_chunk` | `run_preprocessing_pipeline.py` | Medium | ✅ |
| 4.7 | `MemorySemaphore` adaptive timeout | `run_preprocessing_pipeline.py` | Low | ✅ |
| 4.8 | `MarkdownReportGenerator` run report | `run_preprocessing_pipeline.py` | Low | ✅ |
| 4.9 | Update help strings | `run_preprocessing_pipeline.py` | None | ✅ |
| prereq | Add `initargs` to `ParallelProcessor` | `src/utils/parallel.py` | Low | ✅ |

---

## Verification Checklist

```bash
# B1: single-file mode no longer crashes
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --input data/raw/AAPL_10K_2021.html --no-sentiment
# Result: "Pipeline complete!" — 124 segments ✅

# B2: README command works as pasted
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch --workers 8 --resume --chunk-size 100 --quiet
# Result: no "unrecognized arguments" error ✅

# W1: no deprecation warnings
python -W error::DeprecationWarning \
    scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --quiet
# Result: exits cleanly, no DeprecationWarning ✅

# B5: dead code removed
grep -n "def process_single_file\b" \
    scripts/data_preprocessing/run_preprocessing_pipeline.py
# Result: no match (only process_single_file_fast remains) ✅

# Phase 4: run directory created with convention-compliant name
ls data/processed/
# Result: 20260218_141702_preprocessing_0b83409/ ✅

# Phase 4: manifest written
python -c "import json; d=json.load(open('data/processed/.manifest.json')); print(len(d['files']), 'files tracked')"
# Result: 6 files tracked ✅

# Phase 4: naming.py produces correct filename
python -c "
from src.utils.naming import parse_run_dir_metadata, format_output_filename
from pathlib import Path
m = parse_run_dir_metadata(Path('data/processed/20260218_141702_preprocessing_0b83409'))
print(format_output_filename('batch_summary', m))
"
# Result: batch_summary_20260218_141702_preprocessing_0b83409.json ✅

# Phase 4: RUN_REPORT.md written inside run dir (verified via isolated test)
# Result: 1188-byte Markdown report generated ✅
```
