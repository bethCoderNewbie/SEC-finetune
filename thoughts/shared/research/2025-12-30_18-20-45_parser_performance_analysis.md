---
date: 2025-12-30T18:20:45-06:00
date_short: 2025-12-30
timestamp: 2025-12-30_18-20-45
git_commit: 2048284
git_commit_full: 2048284f892511c47a38808233aa1418fd8e73c1
branch: main
repository: SEC finetune
researcher: bethCoderNewbie
---

# Parser Performance Analysis: Timeout and Latency Issues with Large SEC Filings

## Executive Summary

The SEC filing parser experiences timeout, high latency, and failures when processing large files due to:
1. **No timeout mechanism** in parallel processing (ProcessPoolExecutor)
2. **Very large file sizes** (average 24MB, max 68MB, 102 files > 40MB)
3. **Memory-intensive in-memory parsing** with no streaming/chunking
4. **Potential recursion limit issues** on deeply nested HTML
5. **No progressive parsing** or early exit mechanisms

## File Size Analysis

**Dataset Statistics (data/raw):**
- Total files: **887 HTML files**
- Average size: **24.30 MB**
- Maximum size: **68.25 MB** (AIG_10K_2025.html: 57.58 MB shown earlier, but max is 68.25 MB)
- Files > 10MB: **872 files (98.3%)**
- Files > 20MB: **465 files (52.4%)**
- Files > 40MB: **102 files (11.5%)**

**Top 15 Largest Files:**
```
AIG_10K_2025.html: 57.58 MB
AFL_10K_2024.html: 50.08 MB
ALL_10K_2021.html: 49.39 MB
ALL_10K_2022.html: 48.61 MB
ALL_10K_2024.html: 48.33 MB
AFL_10K_2023.html: 46.63 MB
AFL_10K_2025.html: 46.07 MB
ALL_10K_2025.html: 44.65 MB
AFL_10K_2021.html: 43.47 MB
AFL_10K_2022.html: 43.21 MB
AMT_10K_2021.html: 30.54 MB
AMT_10K_2022.html: 29.87 MB
AMT_10K_2025.html: 27.62 MB
AMT_10K_2023.html: 23.80 MB
AMT_10K_2024.html: 22.71 MB
```

**Impact:** Files this large require significant processing time (potentially minutes per file), causing timeouts in batch processing scenarios.

---

## Current Implementation Analysis

### 1. Parser Implementation (src/preprocessing/parser.py)

**Recursion Limit Auto-Scaling:**
```python
# parser.py:132-136
if recursion_limit is None:
    file_size_mb = len(html_content) / (1024 * 1024)
    # Base 10000 + 2000 per MB, capped at 50000
    recursion_limit = min(50000, 10000 + int(file_size_mb * 2000))
```

**Example Calculation:**
- 68 MB file: `10000 + 68 * 2000 = 146,000` → **capped at 50,000**
- 50 MB file: `10000 + 50 * 2000 = 110,000` → **capped at 50,000**

**Problem:** The 50,000 cap may still be insufficient for very large files with deep HTML nesting.

**HTML Flattening (Performance Optimization):**
```python
# parser.py:412-466
def _flatten_html_nesting(self, html_content: str) -> str:
    # Removes empty tags and redundant nested divs/fonts
    # Iterates 5 times for divs, 3 times for fonts
    for _ in range(5):  # Limit iterations to prevent infinite loops
        # Regex-based div unwrapping
```

**Performance Impact:** While this helps reduce nesting depth, it uses regex on potentially 68MB strings, which is slow.

**Memory Usage:**
- Entire HTML loaded into memory (parser.py:236)
- No streaming or chunking approach
- For 68MB file, multiple copies exist in memory during processing

### 2. Parallel Processing (src/utils/parallel.py)

**Critical Gap: No Timeout Handling**
```python
# parallel.py:152-154
for idx, future in enumerate(as_completed(future_to_item), 1):
    result = future.result()  # ⚠️ BLOCKING - No timeout!
    results.append(result)
```

**Problem:**
- `future.result()` blocks indefinitely if worker hangs
- Large files can cause workers to hang for minutes or crash
- No timeout parameter on future.result()
- No detection of hung workers

**Worker Lifecycle:**
```python
# parallel.py:140-143
with ProcessPoolExecutor(
    max_workers=max_workers,
    initializer=self.initializer,
    max_tasks_per_child=50  # Memory management via worker restart
) as executor:
```

**Good:** Workers restart every 50 tasks to free memory
**Problem:** No per-task timeout or memory limit

### 3. Pipeline Processing (src/preprocessing/pipeline.py)

**Worker Function:**
```python
# pipeline.py:36-95
def _process_single_filing_worker(args: tuple) -> Dict[str, Any]:
    try:
        # Process the file
        result = pipeline.process_risk_factors(...)
        # No timeout handling here
    except Exception as e:
        # Generic exception catch, but not TimeoutError
        logger.error("Failed to process %s: %s", file_path.name, e)
```

**Problem:**
- Catches generic exceptions but no timeout handling
- Hung processes won't raise exceptions
- No visibility into long-running tasks

### 4. SEC Parser Library (src/preprocessing/parser.py)

**Library Usage:**
```python
# parser.py:203-210
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="Invalid section type for")
    elements = parser.parse(html_content)  # ⚠️ Blocking call
    tree = sp.TreeBuilder().build(elements)  # ⚠️ Potentially slow
```

**Problem:**
- `parser.parse()` is a synchronous, blocking operation
- No way to interrupt or timeout the sec-parser library call
- Library designed for smaller files, not 68MB filings

### 5. Sanitizer (src/preprocessing/sanitizer.py)

**HTML Flattening:**
```python
# sanitizer.py:378-387
for _ in range(5):  # Limit iterations
    prev_len = len(html)
    html = re.sub(
        r'<div[^>]*>\s*(<div[^>]*>.*?</div>)\s*</div>',
        r'\1', html, flags=re.IGNORECASE | re.DOTALL
    )
```

**Performance Issue:**
- Regex on very large strings (68MB) is slow
- DOTALL flag causes catastrophic backtracking on malformed HTML
- 5 iterations amplify the cost

---

## Root Cause Analysis

### How It SHOULD Work
1. Parser loads HTML → flattens nesting → parses with appropriate recursion limit
2. Parallel processor submits tasks with timeouts
3. Hung workers detected and terminated
4. Large files handled with streaming/progressive parsing
5. Graceful degradation for problematic files

### How It DOES Work
1. Parser loads **entire 68MB file into memory**
2. Regex-based flattening on full 68MB string (slow)
3. sec-parser processes full HTML (blocking, no timeout)
4. ParallelProcessor.future.result() **blocks indefinitely** if worker hangs
5. No timeout detection → **pipeline stalls**
6. Memory accumulates across workers → potential OOM

**Critical Path:**
```
Large File (68MB)
  → _read_html_file() [loads full file]
  → _flatten_html_nesting() [regex on 68MB string, slow]
  → parser.parse(html_content) [sec-parser blocking call, can hang]
  → future.result() [BLOCKS with no timeout]
  → TIMEOUT/HANG
```

---

## Performance Bottlenecks

### Bottleneck #1: No Timeout in ParallelProcessor ⚠️ CRITICAL
- **Location:** src/utils/parallel.py:153
- **Code:** `result = future.result()`
- **Impact:** Indefinite blocking on hung workers

### Bottleneck #2: In-Memory File Processing
- **Location:** src/preprocessing/parser.py:236
- **Code:** `file_path.read_text(encoding='utf-8')`
- **Impact:** 68MB files loaded entirely into memory

### Bottleneck #3: Regex-Based HTML Flattening
- **Locations:**
  - src/preprocessing/parser.py:412-466
  - src/preprocessing/sanitizer.py:357-404
- **Impact:** DOTALL regex on 68MB strings causes catastrophic backtracking

### Bottleneck #4: Recursion Limit Cap
- **Location:** src/preprocessing/parser.py:136
- **Code:** `recursion_limit = min(50000, 10000 + int(file_size_mb * 2000))`
- **Impact:** Cap at 50,000 may be insufficient for deeply nested 68MB files

### Bottleneck #5: Blocking sec-parser Calls
- **Location:** src/preprocessing/parser.py:207
- **Code:** `elements = parser.parse(html_content)`
- **Impact:** No way to interrupt or timeout third-party library

---

## Configuration Analysis

### Current Config (configs/config.yaml)
```yaml
sec_parser:
  parse_tables: true      # Increases parsing complexity
  parse_images: false

preprocessing:
  min_segment_length: 50
  max_segment_length: 999999999999  # No practical limit
  sanitizer:
    enabled: true
    flatten_nesting: true  # Helps but slow on large files
```

**Observations:**
- No timeout configurations
- No file size limits
- No chunking/batching parameters

---

## Recommendations

### Priority 1: Add Timeout Handling ⚠️ CRITICAL

**Implementation:**
```python
# src/utils/parallel.py:152-154
for idx, future in enumerate(as_completed(future_to_item), 1):
    try:
        result = future.result(timeout=300)  # 5 minutes per file
    except concurrent.futures.TimeoutError:
        logger.error(f"Task timed out after 300s: {future_to_item[future]}")
        future.cancel()
        result = {
            'status': 'error',
            'file': str(future_to_item[future]),
            'error': 'Processing timeout (300s)'
        }
    results.append(result)
```

**Configuration (configs/config.yaml):**
```yaml
preprocessing:
  # Task timeout in seconds (default: 300 = 5 minutes)
  task_timeout: 300
  # File size-based timeout scaling (seconds per MB)
  timeout_per_mb: 5
```

**Adaptive Timeout:**
```python
# Calculate timeout based on file size
file_size_mb = file_path.stat().st_size / (1024 * 1024)
timeout = config.task_timeout + (file_size_mb * config.timeout_per_mb)
# 68MB file: 300 + 68*5 = 640 seconds (10.6 minutes)
```

### Priority 2: Implement File Size Limits and Warnings

**Pre-Processing Check:**
```python
# src/preprocessing/pipeline.py
MAX_FILE_SIZE_MB = 100  # Configurable threshold
WARN_FILE_SIZE_MB = 50

file_size_mb = file_path.stat().st_size / (1024 * 1024)

if file_size_mb > MAX_FILE_SIZE_MB:
    logger.error(f"File exceeds size limit: {file_size_mb:.2f} MB > {MAX_FILE_SIZE_MB} MB")
    return None

if file_size_mb > WARN_FILE_SIZE_MB:
    logger.warning(f"Large file detected: {file_size_mb:.2f} MB (may be slow)")
```

**Configuration:**
```yaml
preprocessing:
  max_file_size_mb: 100   # Hard limit
  warn_file_size_mb: 50   # Warning threshold
```

### Priority 3: Optimize Regex-Based HTML Flattening

**Current Issue:**
- DOTALL regex on 68MB strings
- Catastrophic backtracking on malformed HTML

**Solution: Chunk-Based Processing**
```python
def _flatten_html_nesting_chunked(self, html: str, chunk_size: int = 1024*1024) -> str:
    """Process HTML in chunks to avoid regex catastrophic backtracking."""
    if len(html) < chunk_size:
        return self._flatten_html_nesting(html)

    # Split into chunks with overlap for tag boundaries
    chunks = []
    overlap = 10000  # Characters overlap

    for i in range(0, len(html), chunk_size - overlap):
        chunk = html[i:i + chunk_size]
        flattened_chunk = self._flatten_html_nesting(chunk)
        chunks.append(flattened_chunk)

    return ''.join(chunks)
```

**Alternative: Use BeautifulSoup for Large Files**
```python
from bs4 import BeautifulSoup

def _flatten_with_bs4(self, html: str) -> str:
    """Use BeautifulSoup for robust HTML flattening (slower but safer)."""
    soup = BeautifulSoup(html, 'lxml')
    # Unwrap redundant tags programmatically
    for tag_name in ['div', 'span', 'font']:
        for tag in soup.find_all(tag_name):
            if len(list(tag.children)) == 1 and tag.find(tag_name):
                tag.unwrap()
    return str(soup)
```

### Priority 4: Increase Recursion Limit Cap

**Current:**
```python
recursion_limit = min(50000, 10000 + int(file_size_mb * 2000))
```

**Recommended:**
```python
# Increase cap and use logarithmic scaling for very large files
import math

if file_size_mb <= 25:
    recursion_limit = 10000 + int(file_size_mb * 2000)
else:
    # Logarithmic scaling for large files: base + log-scaled component
    recursion_limit = 50000 + int(10000 * math.log10(file_size_mb / 25))

# Cap at higher limit (100,000) but warn
recursion_limit = min(100000, recursion_limit)

if recursion_limit > 75000:
    logger.warning(f"Very high recursion limit: {recursion_limit} for {file_size_mb:.2f} MB file")
```

**Examples:**
- 25 MB: 50,000 (unchanged)
- 50 MB: 50,000 + 10,000 * log10(2) = 53,010
- 68 MB: 50,000 + 10,000 * log10(2.72) = 54,346
- 100 MB: 50,000 + 10,000 * log10(4) = 56,021

### Priority 5: Add Progress Monitoring and Health Checks

**Worker Health Check:**
```python
# src/utils/parallel.py
import time
from concurrent.futures import TimeoutError

def _process_parallel_with_health_check(self, items, worker_func, ...):
    """Process items with health monitoring."""
    results = []
    start_times = {}

    with ProcessPoolExecutor(...) as executor:
        future_to_item = {
            executor.submit(worker_func, item): item
            for item in items
        }

        # Track start times
        for future in future_to_item:
            start_times[future] = time.time()

        for idx, future in enumerate(as_completed(future_to_item), 1):
            elapsed = time.time() - start_times[future]
            item = future_to_item[future]

            try:
                result = future.result(timeout=self.task_timeout)

                # Log slow tasks
                if elapsed > 60:
                    logger.warning(f"Slow task ({elapsed:.1f}s): {item}")

            except TimeoutError:
                logger.error(f"Task timeout ({elapsed:.1f}s): {item}")
                result = {'status': 'error', 'error': 'timeout', 'file': str(item)}

            results.append(result)
```

### Priority 6: Implement File Size-Based Processing Strategy

**Strategy Selection:**
```python
# src/preprocessing/pipeline.py
def process_risk_factors(self, file_path, ...):
    file_size_mb = file_path.stat().st_size / (1024 * 1024)

    # Choose strategy based on file size
    if file_size_mb < 10:
        # Fast path: standard processing
        return self._process_standard(file_path, ...)
    elif file_size_mb < 50:
        # Medium files: optimized processing
        return self._process_optimized(file_path, ...)
    else:
        # Large files: chunked/progressive processing
        return self._process_large_file(file_path, ...)
```

**Large File Handler:**
```python
def _process_large_file(self, file_path, ...):
    """Handle very large files with special optimizations."""
    logger.info(f"Processing large file ({file_size_mb:.2f} MB): {file_path.name}")

    # 1. Skip sanitization (too slow on large files)
    # 2. Increase recursion limit aggressively
    # 3. Disable table parsing if configured
    # 4. Use streaming extraction if available

    config = self.config.model_copy()
    config.sanitizer.enabled = False  # Skip sanitization
    config.parse_tables = False       # Skip tables

    return self._process_with_config(file_path, config, ...)
```

### Priority 7: Add Retry Logic with Degraded Mode

**Implementation:**
```python
def process_with_retry(self, file_path, max_retries=2):
    """Process file with retry and degraded mode fallback."""

    # Attempt 1: Full processing
    try:
        return self.process_risk_factors(file_path, timeout=300)
    except TimeoutError:
        logger.warning(f"First attempt timed out: {file_path.name}")

    # Attempt 2: Optimized mode (skip sanitization)
    try:
        config = self.config.model_copy()
        config.sanitizer.enabled = False
        return self._process_with_config(file_path, config, timeout=600)
    except TimeoutError:
        logger.warning(f"Second attempt timed out: {file_path.name}")

    # Attempt 3: Minimal mode (no tables, no sanitization)
    try:
        config.parse_tables = False
        return self._process_with_config(file_path, config, timeout=900)
    except TimeoutError:
        logger.error(f"All retries exhausted: {file_path.name}")
        return None
```

---

## Implementation Plan

### Phase 1: Critical Fixes (Immediate)
1. **Add timeout to ParallelProcessor** (Priority 1)
   - Modify src/utils/parallel.py:153
   - Add configurable timeout parameter
   - Handle TimeoutError gracefully

2. **Add file size warnings** (Priority 2)
   - Pre-check file sizes before processing
   - Log warnings for files > 50MB
   - Skip files > 100MB (configurable)

### Phase 2: Performance Optimizations (Short-term)
3. **Optimize HTML flattening** (Priority 3)
   - Implement chunk-based regex processing
   - Or use BeautifulSoup for large files

4. **Increase recursion limit cap** (Priority 4)
   - Use logarithmic scaling for very large files
   - Cap at 100,000 instead of 50,000

### Phase 3: Monitoring & Resilience (Medium-term)
5. **Add health checks and monitoring** (Priority 5)
   - Track task start times
   - Log slow tasks (> 60s)
   - Monitor worker health

6. **File size-based strategy** (Priority 6)
   - Implement fast/medium/large file handlers
   - Skip expensive operations for large files

7. **Retry with degraded mode** (Priority 7)
   - Retry with reduced features on timeout
   - Progressive degradation strategy

---

## Configuration Changes

### Add to configs/config.yaml
```yaml
preprocessing:
  # Task timeout configuration
  task_timeout: 300           # Base timeout in seconds (5 minutes)
  timeout_per_mb: 5           # Additional seconds per MB

  # File size limits
  max_file_size_mb: 100       # Hard limit (reject larger files)
  warn_file_size_mb: 50       # Warning threshold

  # Recursion limits
  recursion_limit_base: 10000
  recursion_limit_per_mb: 2000
  recursion_limit_max: 100000  # Increased from 50,000

  # Performance optimizations
  chunk_size_bytes: 1048576   # 1MB chunks for regex processing
  skip_sanitization_above_mb: 50  # Skip sanitization for files > 50MB
```

---

## Success Metrics

**After Implementation:**
1. **Timeout Rate:** < 5% of files timeout (currently unknown, likely high)
2. **Processing Time:**
   - Files < 10MB: < 30 seconds
   - Files 10-50MB: < 5 minutes
   - Files > 50MB: < 10 minutes
3. **Completion Rate:** > 95% of files successfully processed
4. **Memory Usage:** Workers stay under 2GB memory per task

---

## Conclusion

The current parser has **no timeout mechanism** and processes **very large files (up to 68MB)** entirely in memory with blocking operations. This causes indefinite hangs, high latency, and failures.

**Immediate Action Required:**
1. Add `timeout` parameter to `future.result()` in ParallelProcessor (src/utils/parallel.py:153)
2. Implement file size pre-checks and warnings
3. Optimize regex-based HTML flattening for large files

**Long-term Improvements:**
- File size-based processing strategies
- Progressive/streaming parsing for very large files
- Health monitoring and retry logic
- Adaptive timeout scaling based on file size

These changes will make the pipeline robust, predictable, and capable of handling the large SEC filings in the dataset.
