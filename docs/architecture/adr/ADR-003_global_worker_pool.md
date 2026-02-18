# ADR-003: Global Worker Pool — Models Loaded Once Per Worker

**Status:** Accepted
**Date:** 2026-02-10
**Author:** @bethCoderNewbie

---

## Context

The initial batch pipeline instantiated `SECFilingParser`, `SECSectionExtractor`, `TextCleaner`,
and `RiskSegmenter` (which loads `all-MiniLM-L6-v2` via `sentence-transformers`) **once per file**
inside the `multiprocessing.Pool` worker function.

Loading `all-MiniLM-L6-v2` takes ~2–4 seconds and ~350MB of RAM per load. At 10,000 filings this
wasted ~28 hours of model-load time and caused OOM errors when worker processes accumulated multiple
model copies during startup overlap.

## Decision

Use a **global worker pool pattern** via `src/utils/worker_pool.py`:

- `init_preprocessing_worker()` is passed as the `initializer` argument to `ProcessPoolExecutor`
- It runs **once per worker process** at startup, loading all four pipeline objects into
  process-global variables
- Worker functions retrieve objects via `get_worker_parser()`, `get_worker_cleaner()`,
  `get_worker_extractor()`, `get_worker_segmenter()` — no re-instantiation per file

`max_tasks_per_child=50` restarts workers periodically to prevent memory fragmentation accumulation
from long-running processes.

## Consequences

**Positive:**
- ~50× reduction in model-load overhead for large batches (measured: model load removed from hot path)
- Predictable per-worker memory footprint: 1 model copy × N workers (not N models × N files)
- `ResourceTracker` per-file timing now reflects true processing time, not initialization overhead

**Negative:**
- Worker state is invisible to the main process — bugs in global initialization are hard to observe
  without per-worker logging
- `max_tasks_per_child=50` adds periodic startup cost; tuning required for very small vs. very large
  file batches
- If `init_preprocessing_worker()` fails, the worker silently dies — the `ParallelProcessor` must
  detect dead workers via task timeout, not via explicit failure signal

## Supersedes

Replaces per-file instantiation pattern in the original `_process_single_filing_worker`.

## References

- `src/utils/worker_pool.py`
- `src/preprocessing/pipeline.py` — `_process_filing_with_global_workers()`
- `src/utils/parallel.py` — `ParallelProcessor`
- CHANGELOG: 2026-02-10 (commit `8bb512c`)
