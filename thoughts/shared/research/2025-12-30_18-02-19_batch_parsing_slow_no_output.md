---
date: 2025-12-30T18:02:19-06:00
git_commit: 2048284f892511c47a38808233aa1418fd8e73c1
branch: main
repository: SEC finetune
researcher: bethCoderNewbie
status: completed
type: root_cause_analysis
related_files:
  - scripts/data_preprocessing/batch_parse.py
  - scripts/data_preprocessing/run_preprocessing_pipeline.py
---

# Root Cause Analysis: Batch Parsing Slow with No Output or Checkpoint Progress

## Problem Statement

User reported that batch parsing scripts run too slow with no visible output or checkpoint progress when running:
```bash
python scripts/data_preprocessing/batch_parse.py --continue-run 20251212_171015_batch_parse_ea45dd2
```

## Investigation Summary

### Current State (Evidence)

**Run Directory Status:**
- Total HTML files in `data/raw/`: 887 files
- Parsed files in run directory: 317 files
- Checkpoint shows: 207/862 files processed successfully
- Checkpoint timestamp: 2025-12-18T09:50:03 (12 days ago)
- Checkpoint still exists (not removed, meaning run never completed)
- Gap: 110 files parsed AFTER last checkpoint (317 - 207 = 110)

**Python Environment:**
- `sys.stdout.line_buffering`: False
- `sys.stdout.isatty()`: False (not a TTY)
- Platform: Windows (win32)

### Root Cause #1: Stdout Buffering (Primary Issue)

**How It Should Work:**
Progress should print immediately for each file when NOT in quiet mode:

```python
# batch_parse.py:504
if not quiet:
    print(f"\n[{idx}/{len(html_files)}] Processing: {html_file.name}")
```

**How It Actually Works:**
- Python's `print()` without `flush=True` buffers output
- Windows terminals buffer stdout aggressively, especially when `isatty() = False`
- Carriage returns (`end='\r'`) exacerbate buffering issues
- Output only appears when:
  - Buffer fills completely (~4KB-8KB)
  - Newline encountered
  - Program exits
  - Explicit `sys.stdout.flush()` called

**Evidence:**
- `batch_parse.py:592`: Uses `end='\r'` without flush
- `batch_parse.py:504`: Uses standard `print()` without flush
- `run_preprocessing_pipeline.py:762,766-771`: Same issue

**Affected Lines:**
- `batch_parse.py:504` - Main progress output
- `batch_parse.py:592` - Quiet mode progress (`end='\r'`)
- `run_preprocessing_pipeline.py:762` - Quiet mode progress
- `run_preprocessing_pipeline.py:766-771` - Detailed progress

### Root Cause #2: ProcessPoolExecutor Output Isolation

**How It Should Work:**
Worker processes should stream output to parent process in real-time.

**How It Actually Works:**
```python
# run_preprocessing_pipeline.py:740-776
with ProcessPoolExecutor(
    max_workers=max_workers,
    initializer=_init_worker,
    initargs=(extract_sentiment,),
    max_tasks_per_child=50
) as executor:
    # Worker stdout is isolated from parent process
    for i, future in enumerate(as_completed(future_to_file), 1):
        result = future.result()  # No streaming output from workers
```

**Evidence:**
- `run_preprocessing_pipeline.py:740`: Uses ProcessPoolExecutor without stdout redirection
- Worker processes (`process_single_file_fast`) print directly but output doesn't reach parent
- Only parent process prints progress AFTER each worker completes

**Affected Components:**
- `run_preprocessing_pipeline.py:460-605` - Worker function `process_single_file_fast()`
- `run_preprocessing_pipeline.py:715-776` - Main processing loop `_process_chunk()`

### Root Cause #3: Checkpoint Interval Too Large

**Current Behavior:**
- Default checkpoint interval: 10 files (`batch_parse.py:785`)
- Checkpoint saves at: `batch_parse.py:606-615`
- Last checkpoint: File #207 (EQR_10K_2024.html)
- Actual progress: File #317 (110 files beyond checkpoint)

**Evidence:**
```json
// _checkpoint.json
{
  "processed_files": [...], // Last: "EQR_10K_2024.html"
  "metrics": {
    "total_files": 862,
    "successful": 207,  // But 317 files actually parsed!
    "failed_or_skipped": 33
  },
  "timestamp": "2025-12-18T09:50:03.782788"
}
```

**Impact:**
- Users see checkpoint showing 207/862 while 317 files actually processed
- Creates illusion that process is stuck when it's actually running
- 110-file gap = ~11 checkpoint intervals missed

### Secondary Issue: Long Processing Time Per File

**Observed Behavior:**
- 317 files processed since Dec 18th (12 days ago)
- Rate: ~26 files/day or ~1.1 files/hour
- Expected rate: 10-60 seconds per file = 60-360 files/hour

**Possible Causes:**
1. Process was paused/stopped manually
2. System resource constraints (CPU, memory)
3. Parsing specific files takes very long (malformed HTML, large files)
4. Process is actually hung on a specific file

## Working vs Broken Paths

### Working Path (What Should Happen)
1. User runs `python scripts/data_preprocessing/batch_parse.py --continue-run RUN_ID`
2. Script loads existing run directory at `batch_parse.py:832-850`
3. Resume mode enabled automatically at `batch_parse.py:859`
4. For each file, prints: `[{idx}/{total}] Processing: {filename}` at `batch_parse.py:504`
5. Checkpoint saves every 10 files at `batch_parse.py:606-615`
6. User sees real-time progress in terminal
7. On completion, checkpoint deleted at `batch_parse.py:668-669`

### Broken Path (What Actually Happens)
1. User runs command ✓
2. Script loads run directory ✓
3. Resume mode enabled ✓
4. For each file:
   - Print called at `batch_parse.py:504` ✓
   - **BUT output buffered, not displayed** ✗
5. Checkpoint saves every 10 files ✓
6. **User sees NO output** ✗
7. **User cannot tell if process is running, stuck, or slow** ✗
8. **Checkpoint shows stale data (207 vs 317 actual)** ✗

## Impact Analysis

**User Impact:**
- Cannot monitor progress in real-time
- Cannot determine if process is hung or running slowly
- Stale checkpoint data misleads about actual progress
- No visibility into which file is currently being processed

**System Impact:**
- Process IS working (317 files parsed)
- But appears broken due to lack of feedback
- Users may kill working processes thinking they're stuck

## Solutions

### Solution 1: Add flush=True to All Print Statements (Immediate Fix)

**Change Required:**
```python
# batch_parse.py:504
print(f"\n[{idx}/{len(html_files)}] Processing: {html_file.name}", flush=True)

# batch_parse.py:592
print(f"Progress: {idx}/{len(html_files)}", end='\r', flush=True)

# run_preprocessing_pipeline.py:762
print(f"Progress: {current}/{total_files}", end='\r', flush=True)

# run_preprocessing_pipeline.py:766-771
print(f"[{current}/{total_files}] OK: ...", flush=True)
```

**Files to Modify:**
- `batch_parse.py:504, 592, 561, 566, 619, 625, 638`
- `run_preprocessing_pipeline.py:762, 766, 769, 771, 774`

### Solution 2: Force Unbuffered Output via Environment Variable

**User Workaround (No Code Changes):**
```bash
# Windows CMD
set PYTHONUNBUFFERED=1
python scripts/data_preprocessing/batch_parse.py --continue-run RUN_ID

# PowerShell
$env:PYTHONUNBUFFERED=1
python scripts/data_preprocessing/batch_parse.py --continue-run RUN_ID

# Git Bash
PYTHONUNBUFFERED=1 python scripts/data_preprocessing/batch_parse.py --continue-run RUN_ID
```

**Permanent Fix (Add to script top):**
```python
# batch_parse.py:56 (after imports)
import os
os.environ['PYTHONUNBUFFERED'] = '1'
```

### Solution 3: Reduce Checkpoint Interval

**Change Required:**
```python
# batch_parse.py:785 (argparse default)
parser.add_argument(
    '--checkpoint-interval',
    type=int,
    default=5,  # Changed from 10 to 5
    help='Save checkpoint every N files (default: 5)'
)
```

**Or user can specify:**
```bash
python scripts/data_preprocessing/batch_parse.py --continue-run RUN_ID --checkpoint-interval 1
```

### Solution 4: Add Progress Bar (Enhanced UX)

**Use tqdm library:**
```python
# batch_parse.py (add import)
from tqdm import tqdm

# batch_parse.py:502 (replace loop)
for idx, html_file in enumerate(tqdm(html_files, desc="Parsing"), 1):
    # ... existing code
```

**Benefit:** Built-in flush, ETA estimation, visual progress bar

### Solution 5: Add Real-time File Status Logging

**Create progress log file:**
```python
# batch_parse.py:502
progress_log = output_dir / "_progress.log"
with open(progress_log, 'a', buffering=1) as log:  # Line buffering
    for idx, html_file in enumerate(html_files, 1):
        log.write(f"[{datetime.now()}] Processing {idx}/{len(html_files)}: {html_file.name}\n")
        # ... existing code
```

**User can monitor in real-time:**
```bash
# Windows PowerShell
Get-Content data/interim/parsed/RUN_ID/_progress.log -Wait

# Git Bash
tail -f data/interim/parsed/RUN_ID/_progress.log
```

## Recommended Action Plan

### Immediate (Stop the Pain)
1. **Add `flush=True`** to all progress print statements (Solution 1)
2. **Document workaround** in README: use `PYTHONUNBUFFERED=1` (Solution 2)

### Short-term (Next Week)
3. **Reduce default checkpoint interval** to 5 files (Solution 3)
4. **Add progress log file** for real-time monitoring (Solution 5)

### Long-term (Nice to Have)
5. **Integrate tqdm** for better UX (Solution 4)
6. **Add process heartbeat** - touch a `.heartbeat` file every N seconds to prove liveness
7. **Add estimated time remaining** based on average file processing time

## Verification Steps

After implementing Solution 1 (flush=True):

1. Run batch parse with small test set:
```bash
python scripts/data_preprocessing/batch_parse.py --pattern "*_10K_2025.html" --run-name test_flush
```

2. Verify output appears immediately for each file
3. Monitor checkpoint updates every 5-10 files
4. Check progress log (if implemented)

## Success Criteria

- ✅ User sees output within 1 second of file processing starting
- ✅ Progress updates appear in real-time (not batched)
- ✅ Checkpoint updates reflect actual progress within 5-10 files
- ✅ User can monitor progress via console OR log file
- ✅ No ambiguity about whether process is running or stuck

## Related Issues

- Similar issue likely affects other batch scripts in `scripts/` directory
- Check: `scripts/data_collection/download_sec_filings.py`
- Check: `scripts/feature_engineering/extract_features.py`

## References

- Python buffering docs: https://docs.python.org/3/library/sys.html#sys.stdout
- PYTHONUNBUFFERED: https://docs.python.org/3/using/cmdline.html#envvar-PYTHONUNBUFFERED
- ProcessPoolExecutor: https://docs.python.org/3/library/concurrent.futures.html#processpoolexecutor
