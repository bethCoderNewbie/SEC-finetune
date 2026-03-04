---
title: GPU in Worker Processes — cudaErrorLaunchFailure Root Cause
date: 2026-03-03
author: beth
commit: 3bc89d7b4d89db8397f82130c3135c9a555c7870
branch: main
status: PENDING — no safe multi-worker GPU path confirmed yet
---

# GPU in Worker Processes — cudaErrorLaunchFailure Root Cause

## Problem Statement

Running `--batch` with the default worker count produces `cudaErrorLaunchFailure = 719`
in the segmentation workers. This was triggered by removing the `_in_worker` CPU guard
in `src/preprocessing/segmenter.py:102`.

## What We Know

### Commit history of the two relevant changes

| Commit  | Change |
|---------|--------|
| `3ef72af` | `SentenceTransformer(model_name)` — no `device=` arg, default `fork` start method, **2.2s/file** |
| `3bc89d7` | Added `forkserver` to `parallel.py` AND `_in_worker` CPU guard to `segmenter.py` simultaneously |

The CPU guard and forkserver were introduced in the **same commit**, not independently.

### Why `3ef72af` worked with GPU in workers

- Linux default start method = `fork`
- Parent process never touches CUDA (only launches the pool)
- Each forked worker inherits no CUDA context → initializes its own from scratch
- N workers each hold their own independent GPU context → **worked cleanly**

### Why GPU in workers fails now

The CPU guard comment ("Worker subprocesses share the same physical GPU concurrently,
which causes cudaErrorLaunchFailure") is **imprecise but not entirely wrong**.

The actual failure mode is **VRAM exhaustion from N concurrent model loads**:
- `all-MiniLM-L6-v2` ≈ 90 MB VRAM per worker
- Default workers = `min(cpu_count, file_count)` — likely 8+ on this machine
- 8 × 90 MB models + per-batch encode buffers → OOM → `cudaErrorLaunchFailure` on kernel launch

The `forkserver` start method is **not the cause**. The server process never touches CUDA;
initializers run post-fork in each worker. Context isolation is clean.

### The `_in_worker` guard is correct (keep it)

Removing the guard restores GPU in workers but hits VRAM limits with N > ~2 workers.
The guard is the safe default. The comment in the code should be updated to reflect
the real reason (VRAM saturation) rather than the imprecise "concurrent context" framing.

## Options for getting GPU throughput

| Option | Command | Wall-clock (960 files) | Risk |
|--------|---------|------------------------|------|
| Sequential GPU (`--workers 1`) | `--batch --workers 1` | 960 × 2.2s ≈ 35 min | None |
| Parallel CPU (current default) | `--batch` | 960 × 140s ÷ 8 = 28 min | None |
| Parallel GPU with limited workers | `--batch --workers 2` + remove guard | ~960 × 2.2s ÷ 2 = 18 min | VRAM dependent |

Parallel CPU (~28 min) is currently **faster wall-clock** than sequential GPU (~35 min)
for a full 960-file batch. The GPU advantage only becomes dominant at `--workers 3+`
which risks VRAM failure.

## Open Questions

1. How much VRAM is available on this machine? (`nvidia-smi` would tell us)
2. If VRAM ≥ ~300 MB free, `--workers 2` + guard removed would be safe and fastest.
3. Is `max_tasks_per_child` recycling a factor? After 50 tasks a worker restarts and
   re-initializes the model. If VRAM isn't freed between recycles on the old worker,
   peak VRAM = (N+1) × model_size briefly.

## Recommended Next Step

Run `nvidia-smi` to determine available VRAM, then decide whether to:
- Update the comment only (keep guard, document real reason)
- Allow `--workers 2` with guard removed (if VRAM permits)
- Add a `--gpu-workers` flag that explicitly opts into GPU at reduced parallelism

## Key Files

- `src/preprocessing/segmenter.py:94–111` — `_in_worker` guard and device selection
- `src/utils/parallel.py:77–84` — forkserver context selection
- `src/utils/parallel.py:124–128` — auto worker count logic
