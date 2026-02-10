---
date: 2025-12-30T18:25:00-06:00
date_short: 2025-12-30
timestamp: 2025-12-30_18-25
git_commit: 2048284
git_commit_full: 2048284f892511c47a38808233aa1418fd8e73c1
branch: main
repository: SEC finetune
researcher: bethCoderNewbie
---

# Parser Timeout Fixes - Revised Plan

## Context

**Research Document:** `thoughts/shared/research/2025-12-30_18-20-45_parser_performance_analysis.md`

**Problem:** Parser experiences timeouts and hangs on large files (up to 68MB). Current architecture has no timeout mechanism, causing indefinite blocking.

**Critical Constraint:** Must maintain **data quality parity** across all file sizes. Large files (from large companies like AIG, Allstate) cannot receive degraded feature extraction, as this would introduce systematic bias into the ML training dataset.

---

## Desired End State

After implementation, the user will have:

1. **Robust timeout handling** preventing indefinite worker hangs
2. **Resource isolation** for large files (single-core processing with high memory)
3. **Dead letter queue** for failed files with retry mechanism
4. **Health monitoring** to track slow/problematic files
5. **100% feature parity** across all file sizes (no degraded mode)
6. **> 99% completion rate** with aggressive timeouts (20 minutes per file)

---

## Anti-Scope (What We're NOT Doing)

❌ **Regex-based HTML chunking** - Corrupts HTML structure by splitting mid-tag
❌ **Degraded mode for large files** - Skipping tables/sanitization introduces dataset bias
❌ **Linear timeout scaling** - Parsing is O(N^1.5) to O(N^2), not linear
❌ **BeautifulSoup for large files** - Too slow; use lxml C-based parser instead
❌ **File size rejection** - Must process all files to avoid bias
❌ **Streaming/progressive parsing** - sec-parser doesn't support it; out of scope

---

## Implementation Strategy

### Phase 1: Critical Stability Fixes (P0)

**Goal:** Prevent indefinite hangs and add visibility into failures.

#### 1.1 Add Timeout to ParallelProcessor

**File:** `src/utils/parallel.py`

**Current Code (Line 152-154):**
```python
for idx, future in enumerate(as_completed(future_to_item), 1):
    result = future.result()  # ⚠️ Blocks indefinitely
    results.append(result)
```

**New Code:**
```python
# Add timeout parameter to __init__
def __init__(
    self,
    max_workers: Optional[int] = None,
    initializer: Optional[Callable] = None,
    max_tasks_per_child: int = 50,
    task_timeout: int = 1200  # 20 minutes default
):
    self.max_workers = max_workers
    self.initializer = initializer
    self.max_tasks_per_child = max_tasks_per_child
    self.task_timeout = task_timeout

# Modify _process_parallel
def _process_parallel(self, items, worker_func, progress_callback, verbose, max_workers):
    """Process items in parallel with timeout handling."""
    results = []
    failed_items = []  # Track timeouts for dead letter queue

    with ProcessPoolExecutor(...) as executor:
        future_to_item = {
            executor.submit(worker_func, item): item
            for item in items
        }

        for idx, future in enumerate(as_completed(future_to_item), 1):
            item = future_to_item[future]

            try:
                # Add timeout to future.result()
                result = future.result(timeout=self.task_timeout)

                if verbose:
                    elapsed = result.get('elapsed_time', 0)
                    if elapsed > 300:  # Warn if > 5 minutes
                        logger.warning(f"Slow task ({elapsed:.1f}s): {result.get('file')}")

            except concurrent.futures.TimeoutError:
                logger.error(f"Task timeout ({self.task_timeout}s): {item}")
                result = {
                    'status': 'error',
                    'file': str(item),
                    'error': f'Processing timeout ({self.task_timeout}s)',
                    'error_type': 'timeout'
                }
                failed_items.append(item)

            except Exception as e:
                logger.error(f"Task failed with exception: {item} - {e}")
                result = {
                    'status': 'error',
                    'file': str(item),
                    'error': str(e),
                    'error_type': 'exception'
                }
                failed_items.append(item)

            results.append(result)

            if progress_callback:
                progress_callback(idx, result)

    # Write failed items to dead letter queue
    if failed_items:
        self._write_dead_letter_queue(failed_items)

    return results

def _write_dead_letter_queue(self, failed_items):
    """Write failed items to logs/failed_files.json for retry."""
    import json
    from datetime import datetime

    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)

    dlq_file = log_dir / 'failed_files.json'

    # Load existing failures
    if dlq_file.exists():
        with open(dlq_file, 'r') as f:
            failures = json.load(f)
    else:
        failures = []

    # Add new failures with timestamp
    timestamp = datetime.now().isoformat()
    for item in failed_items:
        failures.append({
            'file': str(item),
            'timestamp': timestamp,
            'reason': 'timeout'
        })

    # Save updated failures
    with open(dlq_file, 'w') as f:
        json.dump(failures, indent=2, fp=f)

    logger.info(f"Wrote {len(failed_items)} failed items to {dlq_file}")
```

**Success Criteria:**
- Workers do not hang indefinitely
- Timeout errors logged and tracked
- Failed files written to `logs/failed_files.json`

---

#### 1.2 Add Elapsed Time Tracking to Worker

**File:** `src/preprocessing/pipeline.py`

**Modify Worker Function (Line 36-95):**
```python
import time

def _process_single_filing_worker(args: tuple) -> Dict[str, Any]:
    """Worker function with elapsed time tracking."""
    file_path, config_dict, form_type, output_dir, overwrite = args
    file_path = Path(file_path)

    start_time = time.time()

    try:
        config = PipelineConfig(**config_dict) if config_dict else PipelineConfig()
        pipeline = SECPreprocessingPipeline(config)

        # ... existing processing code ...

        result = pipeline.process_risk_factors(...)

        elapsed_time = time.time() - start_time

        if result:
            return {
                'status': 'success',
                'file': file_path.name,
                'result': result,
                'num_segments': len(result),
                'sic_code': result.sic_code,
                'company_name': result.company_name,
                'elapsed_time': elapsed_time,  # Add timing
                'file_size_mb': file_path.stat().st_size / (1024 * 1024)
            }
        # ... rest of function

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error("Failed to process %s (%.1fs): %s", file_path.name, elapsed_time, e)
        return {
            'status': 'error',
            'file': file_path.name,
            'result': None,
            'error': str(e),
            'elapsed_time': elapsed_time,
            'file_size_mb': file_path.stat().st_size / (1024 * 1024)
        }
```

---

#### 1.3 Update Configuration

**File:** `configs/config.yaml`

**Add to preprocessing section:**
```yaml
preprocessing:
  # Task timeout configuration
  # 20 minutes = 1200 seconds (offline processing can tolerate latency)
  task_timeout: 1200

  # Resource limits
  max_workers: null  # Auto-detect based on CPU count
  max_tasks_per_child: 50  # Restart workers for memory management

  # File size monitoring (for logging only, not rejection)
  warn_file_size_mb: 50

  # Recursion limits (dynamic scaling)
  recursion_limit_base: 10000
  recursion_limit_per_mb: 2000
  recursion_limit_max: 100000  # Increased from 50,000

  # HTML sanitization
  sanitizer:
    enabled: true  # ALWAYS enabled for all files
    flatten_nesting: true  # Use existing lxml-based approach
```

**Rationale:**
- 20-minute timeout accommodates O(N^2) parsing complexity
- No file size rejection - process all files to avoid bias
- Sanitization always enabled to maintain feature parity

---

### Phase 2: Resource Isolation (P1)

**Goal:** Isolate large files to prevent memory contention.

#### 2.1 Add Memory-Based Semaphore

**File:** `src/utils/parallel.py`

**Add Semaphore Logic:**
```python
import multiprocessing

class ParallelProcessor:
    def __init__(
        self,
        max_workers: Optional[int] = None,
        initializer: Optional[Callable] = None,
        max_tasks_per_child: int = 50,
        task_timeout: int = 1200,
        memory_limit_gb: Optional[float] = None  # New parameter
    ):
        self.max_workers = max_workers
        self.initializer = initializer
        self.max_tasks_per_child = max_tasks_per_child
        self.task_timeout = task_timeout
        self.memory_limit_gb = memory_limit_gb

    def _estimate_memory_usage(self, item) -> float:
        """Estimate memory usage for processing an item (in GB)."""
        # For file paths, estimate based on file size
        if isinstance(item, (str, Path)):
            file_path = Path(item) if isinstance(item, str) else item
            if file_path.exists():
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                # Rough estimate: 15x file size for DOM tree in memory
                return (file_size_mb * 15) / 1024  # Convert to GB

        # For tuples (worker args), extract file path
        if isinstance(item, tuple) and len(item) > 0:
            return self._estimate_memory_usage(item[0])

        return 1.0  # Default 1GB estimate

    def _adjust_workers_for_memory(self, items: List, max_workers: int) -> int:
        """Adjust worker count based on memory constraints."""
        if self.memory_limit_gb is None:
            return max_workers

        # Estimate total memory needed for concurrent workers
        max_memory_per_item = max(
            self._estimate_memory_usage(item) for item in items
        )

        # Calculate safe worker count
        safe_workers = int(self.memory_limit_gb / max_memory_per_item)
        safe_workers = max(1, safe_workers)  # At least 1 worker

        if safe_workers < max_workers:
            logger.warning(
                f"Reducing workers from {max_workers} to {safe_workers} "
                f"based on memory limit ({self.memory_limit_gb}GB)"
            )

        return min(max_workers, safe_workers)

    def _process_parallel(self, items, worker_func, progress_callback, verbose, max_workers):
        """Process items in parallel with memory-aware worker count."""

        # Adjust workers based on memory constraints
        max_workers = self._adjust_workers_for_memory(items, max_workers)

        # ... rest of existing code ...
```

**Configuration Update:**
```yaml
preprocessing:
  # Memory management
  # Set to null for auto-detect, or specify available RAM in GB
  # Example: 16 (GB) for a 16GB machine
  memory_limit_gb: null  # Auto-detect available memory
```

---

#### 2.2 Single-Core Isolation for Very Large Files

**File:** `src/preprocessing/pipeline.py`

**Add Large File Detection:**
```python
class SECPreprocessingPipeline:
    def process_batch(
        self,
        file_paths: List[Union[str, Path]],
        form_type: str = "10-K",
        output_dir: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
        max_workers: Optional[int] = None,
        verbose: bool = False
    ) -> List[SegmentedRisks]:
        """Process multiple filings with intelligent resource allocation."""

        if not file_paths:
            logger.warning("No file paths provided for batch processing")
            return []

        # Separate large files for single-core processing
        large_file_threshold_mb = 50
        normal_files = []
        large_files = []

        for fp in file_paths:
            fp_path = Path(fp)
            if fp_path.exists():
                file_size_mb = fp_path.stat().st_size / (1024 * 1024)
                if file_size_mb > large_file_threshold_mb:
                    large_files.append(fp)
                else:
                    normal_files.append(fp)
            else:
                logger.warning(f"File not found: {fp}")

        logger.info(
            f"Processing {len(normal_files)} normal files and "
            f"{len(large_files)} large files (> {large_file_threshold_mb}MB)"
        )

        all_results = []

        # Process normal files in parallel
        if normal_files:
            logger.info(f"Processing {len(normal_files)} normal files with {max_workers or 'auto'} workers")
            results = self._process_files_batch(
                normal_files, form_type, output_dir, overwrite, max_workers, verbose
            )
            all_results.extend(results)

        # Process large files sequentially (single-core isolation)
        if large_files:
            logger.info(f"Processing {len(large_files)} large files sequentially (single-core)")
            results = self._process_files_batch(
                large_files, form_type, output_dir, overwrite, max_workers=1, verbose=True
            )
            all_results.extend(results)

        return all_results

    def _process_files_batch(
        self,
        file_paths: List[Union[str, Path]],
        form_type: str,
        output_dir: Optional[Union[str, Path]],
        overwrite: bool,
        max_workers: Optional[int],
        verbose: bool
    ) -> List[SegmentedRisks]:
        """Internal method to process a batch of files."""

        config_dict = self.config.model_dump() if self.config else {}

        worker_args = [
            (file_path, config_dict, form_type, output_dir, overwrite)
            for file_path in file_paths
        ]

        processor = ParallelProcessor(
            max_workers=max_workers,
            max_tasks_per_child=50,
            task_timeout=1200  # 20 minutes
        )

        processing_results = processor.process_batch(
            items=worker_args,
            worker_func=_process_single_filing_worker,
            verbose=verbose
        )

        # ... existing result extraction code ...

        return results
```

**Success Criteria:**
- Large files (> 50MB) processed sequentially to avoid memory contention
- Normal files processed in parallel with memory-aware worker count
- No OOM errors during batch processing

---

### Phase 3: HTML Cleaning Optimization (P2)

**Goal:** Replace regex-based flattening with robust C-based lxml cleaner.

#### 3.1 Replace Regex Chunking with lxml

**File:** `src/preprocessing/sanitizer.py`

**Current Problematic Code (Line 357-404):**
```python
def _flatten_nesting(self, html: str) -> str:
    """Remove redundant nested tags to reduce HTML depth."""
    # ... regex-based approach with DOTALL flag ...
    for _ in range(5):  # Limit iterations
        html = re.sub(
            r'<div[^>]*>\s*(<div[^>]*>.*?</div>)\s*</div>',
            r'\1', html, flags=re.IGNORECASE | re.DOTALL  # ⚠️ Catastrophic backtracking
        )
```

**New Approach using lxml:**
```python
from lxml import html as lxml_html
from lxml.html.clean import Cleaner

def _flatten_nesting(self, html_str: str) -> str:
    """
    Remove redundant nested tags using lxml (C-based, fast and safe).

    This replaces regex-based chunking, which was architecturally unsound
    (splitting mid-tag corrupts HTML structure).
    """
    try:
        # Parse HTML using lxml (C-based parser, fast)
        doc = lxml_html.fromstring(html_str)

        # Unwrap redundant nested tags
        for tag_name in ['div', 'span', 'font']:
            for element in doc.xpath(f'.//{tag_name}'):
                # If element has only one child of the same type, unwrap
                children = list(element)
                if len(children) == 1 and children[0].tag == tag_name:
                    # Unwrap: replace element with its child
                    parent = element.getparent()
                    if parent is not None:
                        index = parent.index(element)
                        parent.remove(element)
                        parent.insert(index, children[0])

        # Convert back to string
        return lxml_html.tostring(doc, encoding='unicode')

    except Exception as e:
        logger.warning(f"lxml flattening failed, using original HTML: {e}")
        return html_str  # Fallback to original
```

**Add Dependency:**
```toml
# pyproject.toml
[project]
dependencies = [
    "lxml>=4.9.0",  # C-based HTML parser
    # ... existing dependencies ...
]
```

**Success Criteria:**
- No regex catastrophic backtracking on large files
- HTML structure preserved (no mid-tag splits)
- Performance improvement for large files (lxml is C-based)

---

### Phase 4: Retry Mechanism (P2)

**Goal:** Retry failed files with aggressive resource allocation.

#### 4.1 Create Retry Script

**File:** `scripts/utils/retry_failed_files.py`

```python
#!/usr/bin/env python3
"""
Retry files from dead letter queue with aggressive resource allocation.

Usage:
    python scripts/utils/retry_failed_files.py
    python scripts/utils/retry_failed_files.py --max-workers 1 --timeout 3600
"""

import argparse
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from src.preprocessing.pipeline import SECPreprocessingPipeline, PipelineConfig
from src.utils.parallel import ParallelProcessor

logger = logging.getLogger(__name__)


def load_failed_files() -> List[str]:
    """Load failed files from dead letter queue."""
    dlq_file = Path('logs/failed_files.json')

    if not dlq_file.exists():
        logger.info("No failed files found in dead letter queue")
        return []

    with open(dlq_file, 'r') as f:
        failures = json.load(f)

    # Extract unique file paths
    failed_paths = list(set(f['file'] for f in failures))
    logger.info(f"Found {len(failed_paths)} failed files in dead letter queue")

    return failed_paths


def retry_files(
    file_paths: List[str],
    max_workers: int = 1,
    timeout: int = 3600,
    output_dir: str = "data/interim/segmented"
) -> Dict[str, Any]:
    """
    Retry failed files with aggressive resource allocation.

    Args:
        file_paths: List of file paths to retry
        max_workers: Number of workers (default: 1 for single-core isolation)
        timeout: Timeout per file in seconds (default: 3600 = 1 hour)
        output_dir: Output directory for results

    Returns:
        Dictionary with success/failure counts
    """
    logger.info(f"Retrying {len(file_paths)} files with {max_workers} workers, {timeout}s timeout")

    # Use aggressive configuration
    config = PipelineConfig(
        deep_clean=False,  # Skip NLP deep cleaning for speed
        sanitizer={'enabled': True}  # Keep sanitization for quality
    )

    pipeline = SECPreprocessingPipeline(config)

    # Create processor with aggressive timeout
    processor = ParallelProcessor(
        max_workers=max_workers,
        max_tasks_per_child=10,  # More frequent worker restarts
        task_timeout=timeout
    )

    # Prepare worker arguments
    config_dict = config.model_dump()
    worker_args = [
        (Path(fp), config_dict, "10-K", output_dir, True)
        for fp in file_paths
    ]

    # Process with verbose logging
    results = processor.process_batch(
        items=worker_args,
        worker_func=lambda args: pipeline._process_single_filing_worker(args),
        verbose=True
    )

    # Count successes and failures
    successes = [r for r in results if r.get('status') == 'success']
    failures = [r for r in results if r.get('status') == 'error']

    logger.info(f"Retry complete: {len(successes)} succeeded, {len(failures)} failed")

    # Update dead letter queue (remove successes)
    if successes:
        _update_dlq_after_retry([r['file'] for r in successes])

    return {
        'total': len(file_paths),
        'successes': len(successes),
        'failures': len(failures),
        'success_rate': len(successes) / len(file_paths) if file_paths else 0
    }


def _update_dlq_after_retry(succeeded_files: List[str]):
    """Remove successfully retried files from dead letter queue."""
    dlq_file = Path('logs/failed_files.json')

    with open(dlq_file, 'r') as f:
        failures = json.load(f)

    # Remove succeeded files
    remaining = [
        f for f in failures
        if f['file'] not in succeeded_files
    ]

    with open(dlq_file, 'w') as f:
        json.dump(remaining, indent=2, fp=f)

    logger.info(f"Removed {len(succeeded_files)} succeeded files from dead letter queue")


def main():
    parser = argparse.ArgumentParser(description='Retry failed files with aggressive resources')
    parser.add_argument('--max-workers', type=int, default=1,
                       help='Number of workers (default: 1 for isolation)')
    parser.add_argument('--timeout', type=int, default=3600,
                       help='Timeout per file in seconds (default: 3600)')
    parser.add_argument('--output-dir', type=str, default='data/interim/segmented',
                       help='Output directory for results')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load and retry failed files
    failed_files = load_failed_files()

    if not failed_files:
        logger.info("No files to retry")
        return

    results = retry_files(
        failed_files,
        max_workers=args.max_workers,
        timeout=args.timeout,
        output_dir=args.output_dir
    )

    print("\n=== Retry Results ===")
    print(f"Total files: {results['total']}")
    print(f"Successes: {results['successes']}")
    print(f"Failures: {results['failures']}")
    print(f"Success rate: {results['success_rate']:.1%}")


if __name__ == '__main__':
    main()
```

**Usage:**
```bash
# Retry with single-core isolation and 1-hour timeout
python scripts/utils/retry_failed_files.py

# Retry with aggressive 2-hour timeout
python scripts/utils/retry_failed_files.py --timeout 7200

# Check dead letter queue
cat logs/failed_files.json
```

---

## Success Criteria (Updated)

### Data Integrity (Primary)
✅ **0% variance** in feature extraction schema between 1MB and 68MB files
✅ **100% feature parity** - All files get same extraction logic (no degraded mode)
✅ **Bias check** - Distribution of "Risk Factors" shows no drop-off for files > 40MB

### Throughput (Secondary)
✅ **> 99% completion rate** with 20-minute timeout
✅ **Dead letter queue** captures failed files for retry
✅ **Retry script** recovers > 90% of initially failed files

### Performance Monitoring
✅ **Timeout rate** < 1% on first attempt
✅ **Processing time** logged for all files
✅ **Memory usage** stays within configured limits
✅ **No indefinite hangs** - All tasks complete or timeout

---

## Verification

### Automated Verification
```bash
# Run full batch processing with new timeout handling
python scripts/data_preprocessing/batch_parse.py \
    --input-dir data/raw \
    --output-dir data/interim/segmented \
    --max-workers 4 \
    --verbose

# Check dead letter queue
cat logs/failed_files.json

# Retry failed files
python scripts/utils/retry_failed_files.py --timeout 3600

# Verify completion rate
python -c "
import json
from pathlib import Path

# Count total files
total = len(list(Path('data/raw').glob('*.html')))

# Count successful outputs
successful = len(list(Path('data/interim/segmented').glob('*_segmented.json')))

# Count remaining failures
dlq = Path('logs/failed_files.json')
failures = len(json.load(open(dlq))) if dlq.exists() else 0

print(f'Total files: {total}')
print(f'Successful: {successful}')
print(f'Failures: {failures}')
print(f'Completion rate: {successful/total:.1%}')
"
```

### Manual Verification
1. **Check feature parity:**
   ```python
   # Compare features from small vs large files
   from src.preprocessing.pipeline import process_filing

   small_file = process_filing("data/raw/small_10k.html")
   large_file = process_filing("data/raw/AIG_10K_2025.html")

   # Verify same keys
   assert small_file.to_dict().keys() == large_file.to_dict().keys()

   # Verify risk factors extracted (not null)
   assert len(small_file.segments) > 0
   assert len(large_file.segments) > 0
   ```

2. **Monitor slow files:**
   ```bash
   # Grep logs for slow task warnings
   grep "Slow task" logs/preprocessing.log

   # Example output:
   # Slow task (487.3s): AIG_10K_2025.html
   # Slow task (312.1s): AFL_10K_2024.html
   ```

3. **Verify no bias:**
   ```python
   # Check risk factor count distribution by file size
   import pandas as pd
   from pathlib import Path
   import json

   results = []
   for f in Path('data/interim/segmented').glob('*_segmented.json'):
       data = json.load(open(f))
       file_size_mb = Path(f'data/raw/{data["file_name"]}').stat().st_size / (1024*1024)
       results.append({
           'file_size_mb': file_size_mb,
           'num_segments': len(data['segments'])
       })

   df = pd.DataFrame(results)

   # Group by size buckets
   df['size_bucket'] = pd.cut(df['file_size_mb'], bins=[0, 10, 20, 40, 100])
   print(df.groupby('size_bucket')['num_segments'].describe())

   # Should show no drop-off in larger buckets
   ```

---

## Rollback Plan

If issues arise after deployment:

1. **Revert timeout changes:**
   ```bash
   git revert <commit-hash>
   ```

2. **Disable dead letter queue:**
   ```python
   # Comment out in src/utils/parallel.py
   # self._write_dead_letter_queue(failed_items)
   ```

3. **Restore original timeout:**
   ```yaml
   # configs/config.yaml
   preprocessing:
     task_timeout: null  # Disable timeout (original behavior)
   ```

---

## Notes

- **Offline processing tolerance:** 20-minute timeout is acceptable because this is batch processing, not real-time. Data quality > speed.
- **No degraded mode:** Maintaining feature parity is critical for ML model fairness. Large companies (large files) must get equal treatment.
- **lxml not BeautifulSoup:** lxml is C-based (faster), BeautifulSoup is Python (slower). For 68MB files, speed matters.
- **Single-core for large files:** Isolating large files prevents memory contention and OOM errors. Small performance trade-off for stability.
- **Dead letter queue:** Essential for operational visibility. We must know which files failed and why.
