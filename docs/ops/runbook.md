# SEC Pipeline — Operational Runbook

**Audience:** Engineers running or debugging the batch preprocessing pipeline.
**Scope:** `scripts/data_preprocessing/run_preprocessing_pipeline.py` and all `src/utils/` components.

Symptoms are organized by observable signal. Do not read the PRD when the pipeline is on fire.

---

## Quick-Reference Commands

```bash
# Start a fresh batch run
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --workers 4

# Resume after crash (skips already-written output files)
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --resume

# Process single file (debugging)
python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html

# Inspect the DLQ
cat logs/failed_files.json | python -m json.tool | head -60

# Inspect the latest run report
ls -lt data/processed/ | head -5
cat data/processed/<latest_run_dir>/RUN_REPORT.md

# Check checkpoint state
cat data/processed/<latest_run_dir>/_checkpoint.json | python -m json.tool
```

---

## Symptom: `_progress.log` Has Stalled

**Severity:** High
**Trigger:** No new log lines in `_progress.log` for > 15 minutes.

### Diagnosis

```bash
# 1. Is the process still alive?
pgrep -f run_preprocessing_pipeline

# 2. Check CPU
top -p $(pgrep -f preprocessing | head -1)
```

| CPU reading | Interpretation |
|:------------|:---------------|
| ~0% | Process is hung on a lock or blocking I/O |
| ~100% (single core) | Stuck in a tight loop — likely a large regex or infinite segmentation loop |
| High across multiple cores | Workers running normally; progress log may have a flush delay |

### Resolution

1. **Kill the run:**
   ```bash
   pkill -f run_preprocessing_pipeline
   ```

2. **Identify the stuck file** from the last line of `_progress.log`:
   ```bash
   tail -20 data/processed/<run_dir>/_progress.log
   ```

3. **Move the stuck file to DLQ manually** (add to `logs/failed_files.json`) or exclude it:
   ```bash
   # Exclude by moving out of data/raw/ temporarily
   mv data/raw/<stuck_file>.html /tmp/
   ```

4. **Resume the run:**
   ```bash
   python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --resume
   ```
   `CheckpointManager` will skip all files already written to the run directory.

5. **Restore the excluded file** after the batch completes, then retry it alone:
   ```bash
   mv /tmp/<stuck_file>.html data/raw/
   python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/<stuck_file>.html
   ```

---

## Symptom: High Failure Rate in RUN_REPORT.md

**Severity:** High
**Trigger:** `RUN_REPORT.md` shows success rate < 80%, or DLQ has > 200 entries.

### Diagnosis

```bash
# 1. Check DLQ for common error patterns
python -c "
import json
data = json.load(open('logs/failed_files.json'))
from collections import Counter
errors = Counter(r.get('error', 'unknown')[:80] for r in data)
for err, count in errors.most_common(10):
    print(f'{count:4d}  {err}')
"

# 2. Check if failures are clustered (same SIC, same company)
python -c "
import json
data = json.load(open('logs/failed_files.json'))
print([r['file'] for r in data[:20]])
"
```

### Common Causes

| DLQ error pattern | Cause | Fix |
|:------------------|:------|:----|
| `Section 'part1item1a' not found` | Filing uses non-standard Item 1A label | Check `src/preprocessing/constants.py`; add label variant |
| `FileNotFoundError` | File moved or corrupt download | Re-download from EDGAR |
| `timeout` / `TimeoutError` | File too large for current timeout | Increase `--chunk-size` or add file to large-file list |
| `ValidationError` | Pydantic rejected the parsed output | Inspect raw file for missing CIK/SIC in EDGAR header |
| `KeyError: 'sic_code'` | Old output schema loaded from checkpoint | Delete `_checkpoint.json` and re-run without `--resume` |

### Resolution

1. Fix the root cause (code change or re-download).
2. Run the retry script against the DLQ:
   ```bash
   python scripts/utils/retry_failed_files.py
   ```
3. If retry succeeds, the DLQ removes those entries automatically.

---

## Symptom: `ZeroDivisionError` During Test Collection

**Severity:** Medium (blocks CI; known bug)
**Trigger:** `pytest --collect-only` fails with `ZeroDivisionError` in `test_validator_fix.py`.

### Diagnosis

This is a known collection error documented in PRD-002 OQ-7.

```bash
pytest tests/validation/test_validator_fix.py -x 2>&1 | tail -20
```

### Resolution (Temporary)

Exclude the broken file from CI runs:
```bash
pytest tests/ --ignore=tests/validation/test_validator_fix.py --ignore=tests/unit/test_pipeline_global_workers.py
```

Track fix in OQ-7 (PRD-002).

---

## Symptom: Workers Exit Silently (No Output, No Error)

**Severity:** High
**Trigger:** Batch run completes immediately with 0 successes, no DLQ entries, no error logs.

### Diagnosis

```bash
# Check if workers initialized
grep -i "worker" data/processed/<run_dir>/_progress.log | head -10

# Run a single file with verbose output
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
  --input data/raw/<any_file>.html 2>&1 | tee /tmp/debug.log
```

### Common Causes

| Cause | Resolution |
|:------|:-----------|
| `init_preprocessing_worker()` crashed (import error, missing model) | Check `logs/` for import error; re-install `sentence-transformers` and `spacy` |
| `en_core_web_sm` not downloaded | `python -m spacy download en_core_web_sm` |
| `data/raw/` is empty | Verify input directory |
| `--resume` with no valid checkpoint | Delete `_checkpoint.json` and run fresh |

---

## Symptom: Output JSON Missing `sic_code` / `cik`

**Severity:** Medium
**Trigger:** Output `{stem}_segmented_risks.json` has `"sic_code": null` for many filings.

### Diagnosis

`sic_code` is extracted from the EDGAR `<SEC-HEADER>` block by `sec-parser`. It is absent when:

1. The filing was downloaded without the full EDGAR wrapper (just the document body)
2. The filing is an exhibit, not a primary 10-K/10-Q document

```bash
# Check EDGAR header presence in raw file
head -50 data/raw/<suspect_file>.html | grep -i "SEC-HEADER\|SIC\|CIK"
```

### Resolution

- If header is missing: re-download the full filing from EDGAR (not just the document URL)
- If header is present but not parsed: open a bug against `sec-parser==0.54.0`
- Validate after a run: `sic_code_present_rate` threshold in `configs/qa_validation/health_check.yaml`
  requires ≥ 95%; failures will appear in `RUN_REPORT.md`

---

## Symptom: `data/processed/.manifest.json` Is Corrupt

**Severity:** Medium
**Trigger:** `StateManager` raises `json.JSONDecodeError` on startup.

### Cause

`StateManager` uses atomic writes (temp file + rename), but a `SIGKILL` mid-rename can leave a
zero-byte temp file. The manifest file itself should not be corrupt; a temp file (`*.tmp`) may
be present alongside it.

### Resolution

```bash
# Check for orphaned temp files
ls -la data/processed/.manifest*.tmp 2>/dev/null

# If manifest is actually corrupt, delete it (state will be rebuilt from output files on next run)
mv data/processed/.manifest.json data/processed/.manifest.json.bak
# Re-run; StateManager creates a fresh manifest
```

---

## Routine Maintenance

### Prune old run directories

```bash
# List run dirs older than 30 days
find data/processed -maxdepth 1 -type d -mtime +30 -name "*_preprocessing_*"

# Delete (review before running)
find data/processed -maxdepth 1 -type d -mtime +30 -name "*_preprocessing_*" -exec rm -rf {} +
```

### Verify test suite after any `src/` change

```bash
pytest tests/ \
  --ignore=tests/validation/test_validator_fix.py \
  --ignore=tests/unit/test_pipeline_global_workers.py \
  -q
```

Expected: ≥ 658 passed, 0 errors (excludes 2 known broken collection files).
