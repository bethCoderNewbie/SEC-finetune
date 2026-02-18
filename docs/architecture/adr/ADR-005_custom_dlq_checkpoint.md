# ADR-005: Custom CheckpointManager and DeadLetterQueue over Off-the-Shelf Tools

**Status:** Accepted
**Date:** 2026-02-16
**Author:** @bethCoderNewbie

---

## Context

Batch pipelines that process 10,000+ files need two reliability primitives:

1. **Crash recovery** — resume from the last successful position after a process kill or OOM
2. **Failure isolation** — route bad files to a holding area without halting the batch

Evaluated options:

| Option | Pros | Cons |
|:-------|:-----|:-----|
| Celery + Redis | Industry standard; retry queues built-in | Requires running Redis daemon; network dependency; ops overhead |
| Apache Airflow | Full DAG orchestration; retry policies | Major dependency; overkill for single-machine batch; ~500MB overhead |
| DVC pipelines | Reproducibility tracking | Designed for data versioning, not crash recovery during a run |
| **Custom JSON-backed** | Zero new dependencies; portable; readable by humans | Single-process only; no distributed support |

Given the project is currently **single-machine batch** (not distributed), the weight of Celery
or Airflow is not justified.

## Decision

Implement lightweight custom versions:

**`CheckpointManager`** (`src/utils/checkpoint.py`):
- JSON file at `{run_dir}/_checkpoint.json`
- Schema: `{"processed_files": [...], "results": [...], "metrics": {...}, "timestamp": "..."}`
- `save()` called periodically during batch; `load()` on `--resume`; `cleanup()` deletes file on success
- No locks — designed for single-process use only

**`DeadLetterQueue`** (`src/utils/dead_letter_queue.py`):
- JSON file at `logs/failed_files.json`
- Accumulates failure records: file path, error message, timestamp, script name
- `add_failures()` after each batch; `remove_successes()` after retry; `drain()` on final run
- `scripts/utils/retry_failed_files.py` reads the DLQ to drive re-processing

**`StateManager`** (`src/utils/state_manager.py`):
- Cross-run hash tracking via `data/processed/.manifest.json`
- Atomic writes (temp file + rename) prevent corruption during crashes
- Quarantine tracking for files that fail QA validation

## Consequences

**Positive:**
- Zero new infrastructure dependencies — runs on any machine with Python
- DLQ and checkpoint files are plain JSON — inspectable with any text editor
- Atomic writes in `StateManager` prevent manifest corruption on crash

**Negative:**
- Single-process design: concurrent writes from multiple machines would corrupt the JSON files
  (documented design assumption in `state_manager.py`)
- If `SIGKILL` hits mid-write (before the atomic rename), the temp file is orphaned — requires
  manual cleanup. (Documented; low probability in practice.)
- If the project scales to distributed processing, all three must be replaced with a proper
  message queue and distributed lock (flagged for PRD-003)

## Supersedes

Nothing — first ADR on reliability infrastructure.

## References

- `src/utils/checkpoint.py`
- `src/utils/dead_letter_queue.py`
- `src/utils/state_manager.py`
- `scripts/utils/retry_failed_files.py`
- CHANGELOG: 2026-02-16 (commit `fae1fff`)
