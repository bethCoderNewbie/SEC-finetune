# Utils

Documentation for `src/utils/`: pipeline infrastructure — checkpointing, state management, parallel workers, progress logging, and the dead-letter queue.

## Start Here

| File | Purpose |
|------|---------|
| [GATEKEEPER_QUICK_START.md](GATEKEEPER_QUICK_START.md) | **Start here.** How validation gates integrate into the pipeline |
| [INCREMENTAL_PROCESSING_GUIDE.md](INCREMENTAL_PROCESSING_GUIDE.md) | State management and resumable runs via `StateManifest` |

## Deep Dives

| File | Purpose |
|------|---------|
| [RETRY_MECHANISM.md](RETRY_MECHANISM.md) | DLQ retry logic, timeout multipliers, and adaptive allocation |
| [GATEKEEPER_IMPLEMENTATION_SUMMARY.md](GATEKEEPER_IMPLEMENTATION_SUMMARY.md) | Design rationale for the gatekeeper validation pattern |

## Utility Modules

```
src/utils/
├── checkpoint.py        → CheckpointManager (crash recovery)
├── state_manager.py     → StateManifest (cross-run hash tracking)
├── worker_pool.py       → WorkerPool (async task dispatch)
├── parallel.py          → Parallel execution helpers
├── memory_semaphore.py  → Memory-aware concurrency gate
├── resource_tracker.py  → CPU/memory usage tracking
├── dead_letter_queue.py → DLQ for failed files
├── resume.py            → Resume logic for interrupted runs
├── progress_logger.py   → ProgressLogger (structured run log)
├── reporting.py         → MarkdownReportGenerator
├── naming.py            → Run directory and file naming
└── metadata.py          → Run metadata collection
```
