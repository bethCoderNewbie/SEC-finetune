# ADR-007: Immutable Stamped Run Directories for Output Provenance

**Status:** Accepted
**Date:** 2026-02-16
**Author:** @bethCoderNewbie

---

## Context

Early pipeline runs wrote output files directly into `data/processed/` with no versioning.
Re-running the pipeline over the same input files would silently overwrite previous results,
making it impossible to:

- Compare output quality across pipeline versions
- Trace which git commit produced a given labeled JSONL file
- Roll back to a previous run's output if a pipeline bug was introduced

## Decision

Each batch run writes to a new **stamped directory** under `data/processed/`:

```
data/processed/{YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/
```

Where:
- `YYYYMMDD_HHMMSS` is the wall-clock time the run started (UTC)
- `git_sha` is the 7-character short SHA of `HEAD` at run time (from `src/config/run_context.py`)

Within each run directory:

| File | Purpose |
|:-----|:--------|
| `_progress.log` | `ProgressLogger` output — one line per file |
| `_checkpoint.json` | Crash recovery state (deleted on success) |
| `RUN_REPORT.md` | Human-readable summary from `MarkdownReportGenerator` |
| `batch_summary_{run_id}_{ts}.json` | Machine-readable summary (naming.py convention) |
| `{stem}_segmented_risks.json` | Per-filing output |

A cross-run **state manifest** at `data/processed/.manifest.json` (managed by `StateManager`)
tracks which input file hashes have been processed, enabling `ResumeFilter` to skip already-done
files across separate runs.

## Consequences

**Positive:**
- Every output file is traceable to an exact git commit
- Re-running after a bug fix produces a new directory; old output is never overwritten
- Run directories are self-contained — the full run can be inspected or deleted atomically

**Negative:**
- `data/processed/` grows unbounded; old run directories must be pruned manually
  (no automated retention policy yet)
- Git SHA embedded in the directory name becomes stale if commits are rewritten (do not force-push)
- `.manifest.json` is a single file shared across all run directories — concurrent runs from
  multiple machines would corrupt it (single-machine assumption; see ADR-005)

## Supersedes

Flat `data/processed/` output layout from PRD-001.

## References

- `src/config/run_context.py` — git SHA extraction
- `src/utils/naming.py` — run directory naming convention
- `src/utils/state_manager.py` — `.manifest.json`
- `scripts/data_preprocessing/run_preprocessing_pipeline.py:26-31` — output layout docstring
- CHANGELOG: 2026-02-16/17
