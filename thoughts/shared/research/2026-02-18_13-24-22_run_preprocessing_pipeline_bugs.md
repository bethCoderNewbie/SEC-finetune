---
title: "Bug & Warning Audit: run_preprocessing_pipeline.py batch invocation"
date: 2026-02-18T13:24:22-06:00
branch: main
commit: 0b83409a3506c212b360527f3758ed9f958a625b
researcher: bethCoderNewbie
tags: [bug, cli, preprocessing, batch, import, documentation]
status: completed
---

# Bug & Warning Audit: `run_preprocessing_pipeline.py` Batch Invocation

## Executive Summary

Running the documented batch command against 961 unprocessed HTML filings reveals **2 crash-level bugs**, **1 performance bug**, **2 documentation bugs**, and **3 runtime warnings**. The script's single-file mode (`--input`) is completely broken (NameError crash). Batch mode (`--batch`) starts correctly but punishes users of `--chunk-size` with unnecessary model reloads. The README example command fails immediately due to a bash quoting mistake.

---

## Invocation Under Test

```bash
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch \
    --workers 8 \
    --resume \
    --chunk-size 100 \
    --quiet
```

Environment: 961 HTML files in `data/raw/`, 0 already processed, CUDA available, `all-MiniLM-L6-v2` cached locally via HuggingFace.

---

## Warnings (non-fatal, observed at startup)

### W1 — Four `DeprecationWarning`s at import time

**Location:** `scripts/data_preprocessing/run_preprocessing_pipeline.py:57–64`

```
DeprecationWarning: 'RAW_DATA_DIR' is deprecated.
  Use 'settings.paths.raw_data_dir' instead.
DeprecationWarning: 'PARSED_DATA_DIR' is deprecated.
  Use 'settings.paths.parsed_data_dir' instead.
DeprecationWarning: 'EXTRACTED_DATA_DIR' is deprecated.
  Use 'settings.paths.extracted_data_dir' instead.
DeprecationWarning: 'PROCESSED_DATA_DIR' is deprecated.
  Use 'settings.paths.processed_data_dir' instead.
```

**Root cause:** The script imports four legacy path constants from `src/config/__init__.py` that `src/config/legacy.py` has marked deprecated. Emitted before `main()` executes; the `--quiet` flag has no effect.

**Fix:** Replace all four with `settings.paths.*` equivalents.

---

### W2 — Worker `INFO` logs bypass `--quiet`

**Location:** `_init_worker()` → `init_preprocessing_worker()` → `src/utils/worker_pool.py`

```
INFO - Initializing preprocessing worker (models loaded once per process)
INFO - Use pytorch device_name: cuda:0
INFO - Load pretrained SentenceTransformer: all-MiniLM-L6-v2
```

Printed 8× (once per worker) at startup. The `--quiet` flag suppresses `print()` calls only; it does not lower the `logging` level. Users see 24+ INFO lines regardless.

**Fix:** Either add `--quiet` → `logging.WARNING` level mapping in `main()`, or accept this as expected behaviour.

---

### W3 — 24 simultaneous HuggingFace HEAD requests at worker startup

**Location:** `SentenceTransformer('all-MiniLM-L6-v2')` called in each of 8 workers

```
INFO - HTTP Request: HEAD .../all-MiniLM-L6-v2/resolve/main/modules.json  307
INFO - HTTP Request: HEAD .../all-MiniLM-L6-v2/resolve/.../modules.json   200
INFO - HTTP Request: HEAD .../config_sentence_transformers.json            307
```

Each worker makes 2–3 HEAD requests to resolve the HuggingFace cache entry. With 8 workers this is ~24 simultaneous requests. Succeeds when the model is cached, but can cause transient failures on poor connectivity or corporate proxies. No retry logic or rate-limit protection.

**Fix:** Pre-download the model before launching workers, or pass the local cache path explicitly.

---

## Bugs

### B1 — `NameError`: four processor classes missing from imports *(Critical — crashes single-file mode)*

**Location:** `run_pipeline()`, lines 185, 201, 223, 261

**Observed crash:**
```
Traceback (most recent call last):
  File "scripts/data_preprocessing/run_preprocessing_pipeline.py", line 985, in <module>
    main()
  File "...", line 969, in main
    run_pipeline(...)
  File "...", line 185, in run_pipeline
    parser = SECFilingParser()
             ^^^^^^^^^^^^^^^
NameError: name 'SECFilingParser' is not defined
```

**Root cause:** `run_pipeline()` instantiates all four processor classes directly, but only the data-model classes were imported (lines 53–55):

| Class used in `run_pipeline()` | Line | Imported? |
|-------------------------------|------|-----------|
| `SECFilingParser` | 185 | ✗ |
| `SECSectionExtractor` | 201 | ✗ |
| `TextCleaner` | 223 | ✗ |
| `RiskSegmenter` | 261 | ✗ |
| `ParsedFiling` | type hint | ✓ |
| `ExtractedSection` | type hint | ✓ |
| `SegmentedRisks` | type hint | ✓ |

**Blast radius:**
- `--input FILE` mode → crashes immediately
- Default (no args) mode → crashes immediately
- `--batch` mode → **NOT affected** (uses `process_single_file_fast()` via worker pool)
- `process_single_file()` (lines 417–459) also calls `run_pipeline()` → also broken, but it is itself unreachable dead code (see B5)

**Fix:** Add the four missing imports to the top-of-file import block.

```python
from src.preprocessing.parser import SECFilingParser, ParsedFiling
from src.preprocessing.extractor import SECSectionExtractor, ExtractedSection
from src.preprocessing.cleaning import TextCleaner
from src.preprocessing.segmenter import RiskSegmenter, SegmentedRisks, RiskSegment
```

---

### B2 — README batch command fails: `error: unrecognized arguments` *(High — documented command broken)*

**Location:** `README.md`, "Command-Line Scripts" section, lines 215–232

**Observed error:**
```
run_preprocessing_pipeline.py: error: unrecognized arguments:
```
(the unrecognized argument is a literal space character `' '`)

**Root cause:** In bash, `\` acts as a line-continuation **only when it is the last character on the line** (immediately before `\n`). The README example uses the pattern `\       # comment` — the `\` is followed by spaces, not by `\n`. Bash therefore interprets `\ ` as "escaped space", injecting a bare ` ` (space) token into `sys.argv`.

Verified:
```bash
$ python -c "import sys; print(sys.argv)" foo \       # bar
['-c', 'foo', ' ']   # ← space is a positional argument
```

**Broken form (README as written):**
```bash
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch \
    --workers 8 \       # parallel workers       ← \ NOT at EOL
    --resume \          # skip already-processed files
    --chunk-size 100 \  # process in memory-safe chunks
    --quiet             # minimal console output
```

**Fix:** Remove inline comments from the shell snippet (comments belong outside the block, or in a separate line):
```bash
# Batch with options
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch \
    --workers 8 \
    --resume \
    --chunk-size 100 \
    --quiet
```

---

### B3 — `--chunk-size` rebuilds the full worker pool per chunk *(Medium — performance regression)*

**Location:** `run_batch_pipeline()` → `_process_chunk()`, lines 672–707 / 744–863

**Root cause:** `_process_chunk()` creates a new `ProcessPoolExecutor` with `initializer=_init_worker` for every chunk. With `--chunk-size 100` and 961 files:

```
10 chunks × 8 workers × model-load = 80 SentenceTransformer + SentimentAnalyzer loads
```

Each load requires: tokenizer init + weights load + CUDA transfer. The stated purpose of chunking is memory safety, but destroying and recreating pools between chunks does not actually bound peak memory — the old pool must fully drain before the new one starts, and between-chunk GC is not guaranteed.

**Working path:** `run_batch_pipeline()` without `--chunk-size` → single `ProcessPoolExecutor` lives for the full run → models loaded 8× total (correct).

**Fix:** Create the `ProcessPoolExecutor` once outside the chunk loop, or document that `--chunk-size` trades startup overhead for per-chunk memory isolation.

---

### B4 — Module docstring documents wrong pipeline order *(Low — misleads developers)*

**Location:** `run_preprocessing_pipeline.py`, lines 17–21

```
# Documented (WRONG):
Pipeline Flow (with metadata preservation):
    1. Parse   -> ParsedFiling
    2. Clean   -> cleaned text       ← impossible; section not yet extracted
    3. Extract -> ExtractedSection
    4. Segment -> SegmentedRisks

# Actual order in both run_pipeline() and process_single_file_fast():
    1. Parse   -> ParsedFiling
    2. Extract -> ExtractedSection
    3. Clean   -> cleaned text
    4. Segment -> SegmentedRisks
```

Cleaning before extraction is logically impossible (you cannot clean a section you have not yet identified). The actual code does `Parse → Extract → Clean → Segment` in both code paths.

**Fix:** Correct the docstring order to match the code.

---

### B5 — `process_single_file()` is unreachable dead code *(Low — maintenance hazard)*

**Location:** Lines 417–459

`process_single_file()` is never called:
- `_process_chunk()` submits `process_single_file_fast` (line 782), not `process_single_file`
- `main()` calls `run_pipeline()` for single-file mode (line 969), not `process_single_file`

Additionally, `process_single_file()` at line 431 calls `run_pipeline()`, which crashes with B1. So even if a caller were added, it would immediately hit the NameError.

**Fix:** Remove the function entirely, or — if it was intended as the old slow path — add the missing imports (B1 fix) and document it as `run_pipeline_sequential()` for debugging.

---

## Summary Table

| ID | Severity | Mode affected | Description |
|----|----------|---------------|-------------|
| W1 | Low | All | 4× `DeprecationWarning` for legacy path constants |
| W2 | Low | `--batch` startup | Worker INFO logs ignore `--quiet` (8× repeated) |
| W3 | Low | `--batch` startup | 24 simultaneous HuggingFace HEAD requests |
| B1 | **Critical** | `--input`, default | `NameError`: 4 processor classes used but not imported in `run_pipeline()` |
| B2 | **High** | README example | Inline `# comments` after `\` inject space arg; argparse rejects it |
| B3 | Medium | `--chunk-size` | Worker pool rebuilt per chunk → 80 model loads for 961 files |
| B4 | Low | All (doc) | Docstring says Parse→Clean→Extract; actual is Parse→Extract→Clean |
| B5 | Low | N/A | `process_single_file()` is dead code; also inherits B1 crash |

---

## Working Path (Batch Mode)

The only fully functional invocation is batch mode without inline comments:

```bash
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch \
    --workers 8 \
    --resume \
    --quiet
```

`--chunk-size 100` works functionally (files are processed) but causes 80 unnecessary model-load cycles.
