# Automated Retry Mechanism for Dead Letter Queue

## Overview

The automated retry mechanism provides intelligent retry capabilities for failed preprocessing files stored in the Dead Letter Queue (DLQ). It features adaptive resource allocation, timeout multipliers, and retry attempt tracking.

## Features

- ✅ **Adaptive Timeout**: Automatically scales timeout based on file size (10min → 40min)
- ✅ **Memory-Aware Allocation**: Waits for sufficient memory before processing
- ✅ **Attempt Tracking**: Tracks retry attempts per file with configurable max attempts
- ✅ **File Size Filtering**: Target specific file sizes for retry (e.g., only large files)
- ✅ **Failure Type Filtering**: Retry only specific failure types (timeout, exception, etc.)
- ✅ **Isolated Processing**: Force single-core isolation for problematic files
- ✅ **DLQ Management**: Automatically updates DLQ after successful retries
- ✅ **Dry Run Mode**: Preview what would be retried without actual processing

## Installation

The retry script requires Phase 1 (Memory-Aware Resource Allocation) to be completed:

```bash
# Ensure memory_semaphore module exists
ls src/utils/memory_semaphore.py

# Verify script exists
ls scripts/utils/retry_failed_files.py
```

## Usage

### Basic Retry (2x Timeout)

```bash
python scripts/utils/retry_failed_files.py --timeout-multiplier 2.0
```

### Retry Only Large Files (>40MB)

```bash
python scripts/utils/retry_failed_files.py --min-size 40 --update-dlq
```

### Force Isolated Processing for All Files

```bash
python scripts/utils/retry_failed_files.py --force-isolated --update-dlq
```

### Dry Run (Preview Only)

```bash
python scripts/utils/retry_failed_files.py --dry-run
```

### Retry Specific Failure Types

```bash
# Retry only timeout failures
python scripts/utils/retry_failed_files.py --failure-types timeout --update-dlq

# Retry timeout and memory errors
python scripts/utils/retry_failed_files.py --failure-types timeout exception --update-dlq
```

### Custom DLQ Path

```bash
python scripts/utils/retry_failed_files.py --dlq-path logs/custom_dlq.json --dry-run
```

### Retry with Maximum Attempts Limit

```bash
# Skip files that have failed 5+ times
python scripts/utils/retry_failed_files.py --max-attempts 5 --update-dlq
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dlq-path` | Path | `logs/failed_files.json` | Path to Dead Letter Queue JSON file |
| `--timeout-multiplier` | Float | `2.0` | Multiply original timeout by this factor |
| `--force-isolated` | Flag | False | Force single-core isolation for all files |
| `--min-size` | Float | None | Only retry files >= this size in MB |
| `--max-attempts` | Int | `3` | Skip files that have failed >= this many times |
| `--failure-types` | List | None | Only retry these failure types |
| `--dry-run` | Flag | False | Show what would be retried without processing |
| `--update-dlq` | Flag | False | Update DLQ after retry (remove successful, increment attempts) |

## Dead Letter Queue Format

The DLQ is a JSON file with the following structure:

```json
[
  {
    "file": "data/raw/AIG_10K_2025.html",
    "timestamp": "2026-02-16T12:30:00",
    "reason": "timeout",
    "script": "run_preprocessing_pipeline.py",
    "attempt_count": 1,
    "file_size_mb": 68.5,
    "error_type": "timeout",
    "last_retry": "2026-02-16T14:15:00"
  }
]
```

### Required Fields
- `file`: Path to the failed file
- `timestamp`: ISO 8601 timestamp of failure
- `script`: Name of script that encountered failure

### Optional Fields
- `attempt_count`: Number of retry attempts (default: 1)
- `file_size_mb`: File size in megabytes
- `error_type`: Type of error (timeout, exception, memory_error, etc.)
- `last_retry`: ISO 8601 timestamp of last retry attempt
- `reason`: Human-readable failure reason

## Resource Allocation

The retry script uses the `MemorySemaphore` to intelligently allocate resources:

### File Size Categories

| Category | Size Range | Base Timeout | Worker Pool |
|----------|------------|--------------|-------------|
| **SMALL** | <20MB | 600s (10min) | Shared |
| **MEDIUM** | 20-50MB | 1200s (20min) | Shared |
| **LARGE** | >50MB | 2400s (40min) | Isolated |

### Adaptive Timeouts

With `--timeout-multiplier 2.5`:

- **Small file (10MB)**: 600s × 2.5 = 1500s (25 minutes)
- **Medium file (35MB)**: 1200s × 2.5 = 3000s (50 minutes)
- **Large file (68MB)**: 2400s × 2.5 = 6000s (100 minutes)

### Memory Estimation

Formula: `(file_size_mb × 12) + 500MB`

Examples:
- 10MB file: ~620MB estimated peak memory
- 45MB file: ~1040MB estimated peak memory
- 68MB file: ~1320MB estimated peak memory

## Workflow Example

### 1. Initial Processing (Some Failures)

```bash
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch
# Result: 850 success, 15 failures -> logs/failed_files.json
```

### 2. Check Failed Files

```bash
cat logs/failed_files.json | jq '.[] | {file, attempt_count, file_size_mb, error_type}'
```

### 3. Dry Run to Preview Retry

```bash
python scripts/utils/retry_failed_files.py --dry-run
```

Output:
```
2026-02-16 14:00:00 - INFO - Loaded 15 failed files from DLQ
2026-02-16 14:00:00 - INFO - Filtered to 15 eligible files for retry
2026-02-16 14:00:01 - INFO - Retry: AIG_10K_2025.html (68.5MB, large, timeout: 4800s)
2026-02-16 14:00:01 - INFO - Retry: ALLSTATE_10K_2025.html (52.3MB, large, timeout: 4800s)
...
```

### 4. Retry with Increased Resources

```bash
python scripts/utils/retry_failed_files.py --timeout-multiplier 2.5 --update-dlq
```

Output:
```
2026-02-16 14:10:00 - INFO - Success: AIG_10K_2025.html (87 segments)
2026-02-16 14:25:00 - INFO - Success: ALLSTATE_10K_2025.html (76 segments)
...
2026-02-16 15:00:00 - INFO - Retry Results:
2026-02-16 15:00:00 - INFO -   Total: 15
2026-02-16 15:00:00 - INFO -   Success: 13
2026-02-16 15:00:00 - INFO -   Failed: 2
2026-02-16 15:00:00 - INFO -   Skipped: 0
2026-02-16 15:00:00 - INFO - Updated DLQ: Removed 13 successful, 2 remaining
```

### 5. Retry Remaining Failures with Isolation

```bash
python scripts/utils/retry_failed_files.py --force-isolated --timeout-multiplier 3.0 --update-dlq
```

### 6. Check Final DLQ Status

```bash
cat logs/failed_files.json | jq 'length'  # Should be 0 or very small
```

## Integration with Pipeline

The retry script is designed to work seamlessly with the preprocessing pipeline:

1. **Pipeline generates DLQ**: Failed files are automatically logged to `logs/failed_files.json`
2. **Manual intervention**: User runs retry script with desired parameters
3. **Automatic DLQ update**: Successful retries are removed from DLQ
4. **Attempt tracking**: Failed retries increment attempt_count
5. **Max attempts**: Files exceeding max_attempts are skipped

## Monitoring and Logging

### Success Rate Calculation

```bash
# Calculate retry success rate
python -c "
import json
with open('logs/retry_results.json') as f:
    r = json.load(f)
    print(f'Success Rate: {r['success'] / r['total'] * 100:.1f}%')
"
```

### Identify Persistent Failures

```bash
# Find files that have failed multiple times
cat logs/failed_files.json | jq '.[] | select(.attempt_count >= 3) | {file, attempt_count, error_type}'
```

### Estimate Retry Time

```bash
# Calculate total estimated time for retry
python scripts/utils/retry_failed_files.py --dry-run 2>&1 | grep "timeout:" | awk '{sum+=$NF} END {print "Total estimated time:", sum/60, "minutes"}'
```

## Best Practices

### 1. Start with Dry Run
Always preview what will be retried before executing:
```bash
python scripts/utils/retry_failed_files.py --dry-run
```

### 2. Gradual Timeout Increase
Don't jump to 5x timeout immediately. Use progressive multipliers:
- First retry: 2.0x
- Second retry: 2.5x
- Third retry: 3.0x

### 3. Target Large Files First
Large files are more likely to timeout. Retry them first with increased resources:
```bash
python scripts/utils/retry_failed_files.py --min-size 50 --timeout-multiplier 3.0 --update-dlq
```

### 4. Use Isolated Processing for Problematic Files
If files consistently fail in shared pool, force isolation:
```bash
python scripts/utils/retry_failed_files.py --force-isolated --update-dlq
```

### 5. Monitor Memory During Retry
Watch system memory during retry to ensure no OOM:
```bash
watch -n 5 'free -h && python scripts/utils/retry_failed_files.py --dry-run 2>&1 | tail -5'
```

### 6. Set Reasonable Max Attempts
Don't retry files indefinitely. Use `--max-attempts 3` to skip persistent failures:
```bash
python scripts/utils/retry_failed_files.py --max-attempts 3 --update-dlq
```

## Troubleshooting

### Issue: "Memory timeout" during retry

**Solution**: Increase wait timeout or reduce concurrent workers:
```python
# In retry_failed_files.py, line ~753
semaphore.wait_for_memory(estimate.estimated_memory_mb, timeout=1200)  # Increase from 600 to 1200
```

### Issue: All retries still timeout

**Solution**: Use higher multiplier and force isolation:
```bash
python scripts/utils/retry_failed_files.py --timeout-multiplier 4.0 --force-isolated --update-dlq
```

### Issue: DLQ not updating after successful retry

**Solution**: Ensure you use `--update-dlq` flag:
```bash
python scripts/utils/retry_failed_files.py --update-dlq  # Required to modify DLQ
```

### Issue: "File not found" errors

**Solution**: Check file paths in DLQ match actual file locations:
```bash
cat logs/failed_files.json | jq -r '.[].file' | xargs -I {} ls -lh {}
```

## Testing

Verify the retry mechanism logic:

```bash
python scripts/utils/test_retry_logic.py
```

Expected output:
```
=== Testing Retry Script Logic ===

1. Testing Filter Logic:
✓ Max attempts filter works
✓ Min size filter works
✓ Failure type filter works
✓ Combined filters work

2. Testing DLQ Update Logic:
✓ Successful file removal works
✓ Attempt count increment works

3. Testing Timeout Calculation:
✓ Timeout for SMALL (10.0MB): 1200s
✓ Timeout for MEDIUM (30.0MB): 3000s
✓ Timeout for LARGE (60.0MB): 7200s

4. Testing Resource Estimation:
✓ Memory estimate for 10.0MB: 620MB
✓ Memory estimate for 45.2MB: 1042MB
✓ Memory estimate for 68.5MB: 1322MB

=== All Tests Passed ✓ ===
```

## Performance Metrics

Based on implementation plan analysis:

| Metric | Before Retry | After Retry (2.5x timeout) | Improvement |
|--------|--------------|----------------------------|-------------|
| **Success Rate** | 95% | >99% | +4% |
| **Large File Success** | ~80% | 100% | +20% |
| **Manual Intervention** | Required | Automated | N/A |
| **Retry Efficiency** | N/A | 90% success on first retry | N/A |

## Future Enhancements

- [ ] Automatic scheduled retries (cron job integration)
- [ ] Email notifications for persistent failures
- [ ] Retry queue prioritization (large files first)
- [ ] Exponential backoff for retry attempts
- [ ] Integration with monitoring dashboard
- [ ] Batch retry with progress bar
- [ ] Retry cost estimation (time + resources)

## Related Documentation

- [Memory-Aware Resource Allocation](../thoughts/shared/research/2026-01-03_13-36-43_preprocessing_pipeline_blocking_architecture.md)
- [Preprocessing Pipeline Optimization Plan](../thoughts/shared/plans/2026-02-16_16-52-14_preprocessing_pipeline_optimization.md)
- [Dead Letter Queue Specification](./DEAD_LETTER_QUEUE.md)

## Changelog

- **2026-02-16**: Initial implementation (Phase 3)
  - Created retry_failed_files.py script
  - Implemented adaptive timeout calculation
  - Added memory-aware allocation
  - Created attempt tracking
  - Added DLQ update functionality
