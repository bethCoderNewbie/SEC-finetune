# Preprocessing Pipeline Incident Report

## Executive Summary

**Date:** 2025-11-18
**Component:** SEC Filing Preprocessing Pipeline
**Severity:** Medium
**Status:** Resolved

---

## Issue Description

### Primary Issue: RecursionError During HTML Parsing

When running the preprocessing pipeline on SEC 10-K filings, a `RecursionError: maximum recursion depth exceeded` occurred during the parsing phase.

**Error Location:** `src/preprocessing/parser.py:337` -> `sec_parser` library
**Root Cause:** Python's default recursion limit (1000) was exceeded when processing deeply nested HTML structures in SEC filings.

### Secondary Issues Identified

1. **Incomplete Sentiment Dictionary Warning**
   - Message: `Dictionary has 3917 words, expected ~20000. Dictionary may be incomplete.`
   - Impact: Non-blocking, but sentiment analysis may be less comprehensive

2. **Table Metrics Warning from sec_parser**
   - Message: `Failed to get table metrics: 'NoneType' object has no attribute 'text'`
   - Impact: Non-blocking warning from external library

---

## Technical Analysis

### Stack Trace Analysis

```
RecursionError: maximum recursion depth exceeded
  File "sec_parser/processing_steps/individual_semantic_element_extractor.py", line 57
    processing_log = element.processing_log.copy()
  File "copy.py", line 35
    return copy.deepcopy(self)
```

### Root Cause

The `sec_parser` library uses recursive processing to handle nested HTML elements. For complex SEC filings (like AAPL 10-K), the HTML structure can be deeply nested with:
- Nested tables
- Multiple levels of div containers
- Complex formatting structures

When the parser attempts to `deepcopy` processing logs during element extraction, Python's recursion limit is exceeded.

---

## Resolution

### Fix Applied

Modified `src/preprocessing/parser.py` to temporarily increase Python's recursion limit during parsing:

```python
# Increase recursion limit for deeply nested HTML in SEC filings
original_recursion_limit = sys.getrecursionlimit()
sys.setrecursionlimit(10000)

try:
    # Parse HTML into semantic elements
    if form_type_enum == FormType.FORM_10K:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Invalid section type for")
            elements = parser.parse(html_content)
    else:
        elements = parser.parse(html_content)

    # Build semantic tree
    tree = sp.TreeBuilder().build(elements)
finally:
    # Restore original recursion limit
    sys.setrecursionlimit(original_recursion_limit)
```

### Why This Fix Works

1. **Temporary Elevation:** Only increases limit during parsing, then restores original
2. **Safe Restoration:** Uses `try/finally` to ensure limit is always restored
3. **Sufficient Headroom:** 10,000 provides enough depth for even the most complex filings

---

## Troubleshooting Guide

### Common Errors and Solutions

#### 1. RecursionError: maximum recursion depth exceeded

**Symptoms:**
- Pipeline crashes during parsing step
- Long traceback showing recursive calls to `deepcopy`

**Solutions:**
- Ensure the recursion limit fix is in place (parser.py lines 332-351)
- For extremely complex filings, increase limit to 15000 or 20000
- Check if filing HTML is malformed (may need pre-processing)

#### 2. Dictionary Incomplete Warning

**Symptoms:**
- `Dictionary has 3917 words, expected ~20000. Dictionary may be incomplete.`

**Solutions:**
- Check that Loughran-McDonald dictionary file exists at the configured path
- Verify file is complete and not truncated
- Re-download dictionary from source if needed

#### 3. No Output in Batch Mode (Windows)

**Symptoms:**
- Batch mode runs but shows no progress
- Only stderr warnings visible

**Explanation:**
- On Windows, `ProcessPoolExecutor` child processes have stdout buffering issues
- Print statements from child processes may not propagate to parent

**Solutions:**
- Progress is still being made; wait for completion
- Check output files in `data/processed/` directory
- Review `batch_processing_summary.json` after completion

#### 4. Pipeline Hangs on Specific Filing

**Symptoms:**
- Processing stops on one file
- High CPU/memory usage

**Solutions:**
- Check filing size (very large files >50MB may need special handling)
- Verify file isn't corrupted
- Try processing file individually with verbose logging

---

## Debugging Best Practices

### 1. Test Single Files First

Always test with a single file before batch processing:

```bash
python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K_2024.html
```

### 2. Use Smaller Batch Sizes for Testing

Start with 2 workers to catch errors early:

```bash
python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --batch --workers 2
```

### 3. Check Intermediate Outputs

Inspect files in these directories to isolate issues:
- `data/interim/parsed/` - After parsing step
- `data/interim/extracted/` - After extraction/cleaning
- `data/processed/` - Final output

### 4. Add Verbose Logging

For debugging specific issues, add logging to `run_pipeline()`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# In run_pipeline():
logger.debug(f"Processing: {input_file}")
```

### 5. Memory Profiling

For large batches, monitor memory usage:

```python
import tracemalloc
tracemalloc.start()
# ... run pipeline ...
current, peak = tracemalloc.get_traced_memory()
print(f"Current memory: {current / 10**6:.1f}MB; Peak: {peak / 10**6:.1f}MB")
```

---

## Code Quality Guidelines

### 1. Exception Handling

Always wrap external library calls with proper exception handling:

```python
try:
    result = external_library_call()
except ExternalLibraryError as e:
    logger.error(f"External library failed: {e}")
    # Provide fallback or re-raise with context
    raise ProcessingError(f"Failed to process {file}: {e}") from e
```

### 2. Resource Management

Use context managers or try/finally for resource cleanup:

```python
# Good
try:
    sys.setrecursionlimit(10000)
    # ... process ...
finally:
    sys.setrecursionlimit(original_limit)

# Also good
with tempfile.NamedTemporaryFile() as tmp:
    # ... use tmp file ...
```

### 3. Progress Reporting in Batch Mode

For better visibility in concurrent processing:

```python
from tqdm import tqdm

with ProcessPoolExecutor(max_workers=workers) as executor:
    futures = [executor.submit(process, f) for f in files]
    for future in tqdm(as_completed(futures), total=len(files)):
        result = future.result()
```

### 4. Type Hints and Documentation

Always include type hints and docstrings:

```python
def process_single_file(args: tuple[Path, bool, bool]) -> dict[str, Any]:
    """
    Process a single SEC filing.

    Args:
        args: Tuple of (input_file, save_intermediates, extract_sentiment)

    Returns:
        Dictionary with processing result including status and metrics

    Raises:
        ProcessingError: If file cannot be parsed
    """
```

### 5. Configuration Over Hardcoding

Use configuration files instead of hardcoded values:

```python
# Bad
sys.setrecursionlimit(10000)

# Better (in config.py)
RECURSION_LIMIT = 10000

# Or even better (in settings.yaml)
preprocessing:
  recursion_limit: 10000
```

---

## Testing Recommendations

### Unit Tests to Add

1. **Test recursion limit restoration**
   ```python
   def test_recursion_limit_restored():
       original = sys.getrecursionlimit()
       parser.parse_from_content(html_content)
       assert sys.getrecursionlimit() == original
   ```

2. **Test with deeply nested HTML**
   ```python
   def test_deeply_nested_html():
       nested_html = "<div>" * 500 + "content" + "</div>" * 500
       result = parser.parse_from_content(nested_html)
       assert result is not None
   ```

3. **Test batch processing failure handling**
   ```python
   def test_batch_handles_failures():
       files = [good_file, bad_file, good_file]
       results = run_batch_pipeline(files)
       assert sum(r['status'] == 'error' for r in results) == 1
   ```

---

## Performance Considerations

### Batch Processing

- **Optimal workers:** Usually CPU count - 1 for CPU-bound tasks
- **Memory:** Each worker loads full filing into memory; monitor with large files
- **I/O:** Consider SSD for faster file reading with many files

### Estimated Processing Times

| File Count | Workers | Estimated Time |
|------------|---------|----------------|
| 10 files   | 4       | ~2-3 minutes   |
| 50 files   | 4       | ~10-15 minutes |
| 100+ files | 4       | ~25-35 minutes |

---

## Future Improvements

1. **Add progress bar** using `tqdm` for batch processing
2. **Implement retry logic** for transient failures
3. **Add memory monitoring** to prevent OOM errors
4. **Create filing validator** to pre-check HTML structure
5. **Update sentiment dictionary** to full 20K+ words

---

## Contact

For questions about this incident or the preprocessing pipeline:
- Review code at: `scripts/02_data_preprocessing/run_preprocessing_pipeline.py`
- Parser module: `src/preprocessing/parser.py`
