# Progress Logger Utility

**Location:** `src/utils/progress_logger.py`

Thread-safe and process-safe progress logging utility for real-time monitoring of batch processing scripts.

## Problem Solved

When running long batch processing scripts (parsing, feature extraction, etc.), users often experience:
- **No visible output** due to Python stdout buffering (especially on Windows)
- **Uncertainty** about whether the process is running, stuck, or slow
- **Inability to monitor progress** in real-time
- **Lost context** when processes crash without logging

The `ProgressLogger` utility solves these issues by providing:
- ✅ **Auto-flush** to file and console for immediate visibility
- ✅ **Timestamped logs** for permanent record keeping
- ✅ **Thread-safe** and **process-safe** file writes
- ✅ **Progress updates** with carriage return support
- ✅ **Context manager** support for clean resource management

## Quick Start

### Basic Usage

```python
from src.utils.progress_logger import ProgressLogger

# Method 1: Context manager (recommended)
with ProgressLogger("output/progress.log") as logger:
    logger.log("Processing started")
    for i, file in enumerate(files, 1):
        logger.log(f"[{i}/{len(files)}] Processing: {file.name}")

# Method 2: Manual close
logger = ProgressLogger("output/progress.log")
logger.log("Processing started")
logger.close()
```

### Batch Processing

```python
from src.utils.progress_logger import BatchProgressLogger

with BatchProgressLogger("output/progress.log", total_items=100) as logger:
    for item in items:
        logger.log_item_start(item.name)

        try:
            # Process item
            result = process(item)
            logger.log_item_success(item.name, f"Processed in {elapsed:.1f}s")
        except Exception as e:
            logger.log_item_error(item.name, str(e))

        # Update progress every 10 items
        if logger.current_item % 10 == 0:
            logger.update_progress()

    # Log summary
    logger.log_summary()
```

### Convenience Function

```python
from src.utils.progress_logger import create_progress_logger

logger = create_progress_logger("output/dir", log_filename="_progress.log")
logger.log("Quick and easy!")
logger.close()
```

## Features

### 1. ProgressLogger (Base Class)

**Basic logging with auto-flush:**

```python
logger = ProgressLogger("output/progress.log", console=True)

# Standard logging
logger.log("Processing started")  # Timestamped by default
logger.log("Custom message", timestamp=False)  # No timestamp

# Categorized logging
logger.error("Something went wrong")
logger.warning("Potential issue detected")
logger.success("Operation completed successfully")

# Section headers
logger.section("Data Processing Phase", char="=", width=80)

# Progress updates (overwrites in console, logs permanently to file)
for i in range(100):
    logger.progress(f"Progress: {i}/100")
```

**Output modes:**
- `console=True` (default): Output to both file and console
- `console=False`: Output to file only (quiet mode)
- `quiet=True`: Minimize console output (only show progress updates)

### 2. BatchProgressLogger (Extended Class)

**Specialized for batch processing with automatic counters:**

```python
logger = BatchProgressLogger("output/progress.log", total_items=50)

# Track item processing
logger.log_item_start("file_001.html")
logger.log_item_success("file_001.html", "42 segments extracted")
logger.log_item_error("file_002.html", "Malformed HTML")
logger.log_item_warning("file_003.html", "Missing metadata")

# Update progress indicator
logger.update_progress()  # Uses internal counter

# Generate summary
logger.log_summary()  # Shows total, success, warnings, errors, success rate
```

**Auto-tracked metrics:**
- `current_item`: Current item number (auto-incremented)
- `success_count`: Number of successful items
- `error_count`: Number of failed items
- `warning_count`: Number of warnings

### 3. Real-time Monitoring

**Monitor logs while script runs:**

```bash
# PowerShell
Get-Content data/interim/parsed/RUN_ID/_progress.log -Wait

# Git Bash / Linux
tail -f data/interim/parsed/RUN_ID/_progress.log

# Windows CMD (poor UX, but works)
type data\interim\parsed\RUN_ID\_progress.log
```

## Integration Examples

### Example 1: Integrate into `batch_parse.py`

```python
from src.utils.progress_logger import BatchProgressLogger

def batch_parse_filings(output_dir, html_files, quiet=False):
    # Initialize logger
    progress_logger = BatchProgressLogger(
        log_path=output_dir / "_progress.log",
        total_items=len(html_files),
        console=not quiet,
        quiet=quiet
    )

    for idx, html_file in enumerate(html_files, 1):
        progress_logger.log_item_start(html_file.name)

        try:
            # Parse file
            filing = parser.parse_filing(html_file)
            progress_logger.log_item_success(
                html_file.name,
                f"{len(filing)} elements parsed"
            )
        except Exception as e:
            progress_logger.log_item_error(html_file.name, str(e))

        # Update progress every 10 files
        if idx % 10 == 0:
            progress_logger.update_progress()

    # Log summary
    progress_logger.log_summary()
    progress_logger.close()
```

### Example 2: Integrate into `run_preprocessing_pipeline.py`

```python
from src.utils.progress_logger import ProgressLogger

def run_batch_pipeline(input_files, quiet=False):
    progress_logger = ProgressLogger(
        log_path=PROCESSED_DATA_DIR / "_progress.log",
        console=not quiet,
        quiet=quiet
    )

    progress_logger.section(f"Batch Pipeline: {len(input_files)} files")

    for i, file in enumerate(input_files, 1):
        progress_logger.log(f"[{i}/{len(input_files)}] Processing: {file.name}")

        # Process file
        result = process(file)

        if result['status'] == 'success':
            progress_logger.log(
                f"[{i}/{len(input_files)}] ✓ {file.name} → "
                f"{result['num_segments']} segments"
            )
        else:
            progress_logger.error(
                f"[{i}/{len(input_files)}] {file.name} - {result['error']}"
            )

    progress_logger.close()
```

## Log File Format

**Example output:**

```
=== Progress Log Started: 2025-12-30T18:30:00.000000 ===
================================================================================
Batch Processing: 100 items
================================================================================
[2025-12-30 18:30:01] [1/100] Processing: AAPL_10K_2024.html
[2025-12-30 18:30:02] [1/100] ✓ SUCCESS: AAPL_10K_2024.html - 42 segments extracted
[2025-12-30 18:30:02] [2/100] Processing: MSFT_10K_2024.html
[2025-12-30 18:30:03] [2/100] ✓ SUCCESS: MSFT_10K_2024.html - 38 segments extracted
[2025-12-30 18:30:03] Progress: 2/100 (2.0%) | Success: 2 | Errors: 0
...
[2025-12-30 18:35:00] ERROR: [50/100] TSLA_10K_2024.html - Malformed HTML structure
...
================================================================================
Batch Processing Summary
================================================================================
Total items: 100
Processed: 100
Successful: 98
Warnings: 1
Errors: 1
Success rate: 98.0%
=== Progress Log Ended: 2025-12-30T18:35:30.000000 ===
```

## Thread Safety

The `ProgressLogger` uses `threading.Lock()` to ensure thread-safe file writes:

```python
# Safe for concurrent access
logger = ProgressLogger("shared_log.log")

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(process_file, f, logger) for f in files]
```

**Note:** For `ProcessPoolExecutor` (multiprocessing), each worker should create its own logger instance, or pass a shared log path and use file locking.

## Best Practices

### 1. Always Use Context Manager

```python
# ✅ Good: Automatically closes file
with ProgressLogger("output.log") as logger:
    logger.log("Processing...")

# ❌ Bad: Must remember to close
logger = ProgressLogger("output.log")
logger.log("Processing...")
logger.close()  # Easy to forget!
```

### 2. Log File Naming Convention

Use underscore prefix for internal/temporary files:

```python
# ✅ Good: Indicates internal file
output_dir / "_progress.log"
output_dir / "_checkpoint.json"

# ❌ Avoid: Looks like user-facing output
output_dir / "progress.log"
```

### 3. Periodic Progress Updates

Update progress periodically, not every iteration:

```python
# ✅ Good: Update every 10 items
for i, item in enumerate(items, 1):
    process(item)
    if i % 10 == 0:
        logger.update_progress()

# ❌ Bad: Too many updates (slower, cluttered log)
for i, item in enumerate(items, 1):
    process(item)
    logger.update_progress()  # Every iteration!
```

### 4. Use Appropriate Log Level

```python
# Success (expected outcome)
logger.log_item_success(file, "Processed successfully")

# Warning (unexpected but handled)
logger.log_item_warning(file, "Section not found, using default")

# Error (failed to process)
logger.log_item_error(file, "Invalid format")
```

## API Reference

### ProgressLogger

**Constructor:**
```python
ProgressLogger(
    log_path: Path | str,
    console: bool = True,      # Output to console
    quiet: bool = False,       # Minimize console output
    append: bool = True        # Append to existing log
)
```

**Methods:**
- `log(message, timestamp=True)` - Log a message
- `progress(message, timestamp=False)` - Log progress update (overwrites in console)
- `section(title, char="=", width=80)` - Log section header
- `error(message)` - Log error with ERROR prefix
- `warning(message)` - Log warning with WARNING prefix
- `success(message)` - Log success with SUCCESS prefix
- `close()` - Close log file

### BatchProgressLogger

**Constructor:**
```python
BatchProgressLogger(
    log_path: Path | str,
    total_items: int,          # Total items to process
    console: bool = True,
    quiet: bool = False,
    append: bool = True
)
```

**Methods:**
All `ProgressLogger` methods, plus:
- `log_item_start(item_name)` - Log item processing start
- `log_item_success(item_name, details="")` - Log item success
- `log_item_error(item_name, error)` - Log item error
- `log_item_warning(item_name, warning)` - Log item warning
- `update_progress(current=None)` - Update progress indicator
- `log_summary()` - Log processing summary with statistics

**Attributes:**
- `total_items` - Total items to process
- `current_item` - Current item number (auto-incremented)
- `success_count` - Successful items
- `error_count` - Failed items
- `warning_count` - Warnings

### Convenience Function

```python
create_progress_logger(
    output_dir: Path | str,
    log_filename: str = "_progress.log",
    **kwargs
) -> ProgressLogger
```

## Performance Considerations

### Buffering

The logger uses **line buffering** (`buffering=1`) to auto-flush after each line:

```python
self._file = open(log_path, mode='a', buffering=1)  # Line buffering
```

This ensures immediate visibility with minimal performance impact.

### File I/O Overhead

Each `log()` call writes to file. For extremely high-frequency logging (>1000 messages/sec), consider batching:

```python
# For very high frequency, buffer messages
messages = []
for i in range(10000):
    messages.append(f"Processing {i}")
    if len(messages) >= 100:
        logger.log("\n".join(messages))
        messages.clear()
```

## Troubleshooting

### Issue: Still not seeing output in real-time

**Solution 1:** Ensure unbuffered Python output
```bash
PYTHONUNBUFFERED=1 python script.py
```

**Solution 2:** Check if log file is being written
```bash
# Check file size updates
ls -lh output/_progress.log

# Monitor file in real-time
tail -f output/_progress.log
```

**Solution 3:** Verify logger is initialized correctly
```python
# Add debug output
logger = ProgressLogger("output.log", console=True)
print(f"Logger initialized: {logger.log_path}")  # Verify path
```

### Issue: UnicodeEncodeError on Windows

If you see encoding errors with special characters (✓, ✗, etc.):

```python
# Use ASCII-safe characters
logger.log_item_success(item, "OK - processed successfully")  # Not "✓"
logger.log_item_error(item, "FAIL - error occurred")  # Not "✗"
```

### Issue: Log file grows too large

For very long runs, implement log rotation:

```python
from logging.handlers import RotatingFileHandler

# Use Python's logging with rotation
import logging
handler = RotatingFileHandler(
    "progress.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
```

## See Also

- **Demo script:** `examples/05_progress_logging_demo.py`
- **Integration examples:** `scripts/data_preprocessing/batch_parse.py`
- **Research document:** `thoughts/shared/research/2025-12-30_18-02-19_batch_parsing_slow_no_output.md`
