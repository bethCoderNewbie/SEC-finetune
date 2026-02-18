# Phase 3 Installation Guide - Automated Retry Mechanism

## Quick Install

```bash
# Install/update all dependencies (including psutil)
pip install -e .

# Verify installation
python scripts/utils/test_imports.py
```

## What Was Added

The `psutil>=5.9.0` dependency was added to `pyproject.toml` for memory monitoring.

### Before:
```toml
# Data handling
"pandas>=2.0.0",
"numpy>=1.24.0",
"dill>=0.3.7",

# Visualization and UI
```

### After:
```toml
# Data handling
"pandas>=2.0.0",
"numpy>=1.24.0",
"dill>=0.3.7",

# System utilities
"psutil>=5.9.0",  # For memory monitoring and resource tracking

# Visualization and UI
```

## Full Dependency Status

All required dependencies for the retry mechanism:

| Dependency | Required For | Status in pyproject.toml |
|------------|--------------|--------------------------|
| `psutil>=5.9.0` | Memory monitoring | ✅ **ADDED** (line ~53) |
| `pydantic>=2.12.4` | Data validation | ✅ Already present (line 69) |
| `sec-parser==0.54.0` | SEC filing parsing | ✅ Already present (line 37) |
| `spacy>=3.7.0` | Text cleaning | ✅ Already present (line 43) |
| `sentence-transformers>=2.2.2` | Risk segmentation | ✅ Already present (line 45) |

## Installation Steps

### Option 1: Clean Install (Recommended)

```bash
# 1. Navigate to project root
cd /home/beth/work/SEC-finetune

# 2. Install with updated dependencies
pip install -e .

# 3. Download spaCy model (if not already installed)
python -m spacy download en_core_web_sm

# 4. Verify all imports work
python scripts/utils/test_imports.py

# 5. Test retry script
python scripts/utils/retry_failed_files.py --help
```

### Option 2: Install Only psutil

```bash
# If you don't want to reinstall everything
pip install psutil>=5.9.0

# Verify
python -c "import psutil; print(f'psutil {psutil.__version__} installed')"
```

## Verification

### 1. Test Imports

```bash
python scripts/utils/test_imports.py
```

Expected output:
```
Testing imports for retry_failed_files.py...

✓ Standard library imports (argparse, json, logging, pathlib, datetime)
✓ psutil 5.9.x
✓ src.preprocessing.pipeline
✓ src.utils.memory_semaphore
✓ src.utils.parallel
✓ retry_failed_files module

============================================================
✅ ALL IMPORTS SUCCESSFUL - Retry script is ready to use!
============================================================
```

### 2. Test Retry Script Help

```bash
python scripts/utils/retry_failed_files.py --help
```

Expected output:
```
usage: retry_failed_files.py [-h] [--dlq-path DLQ_PATH]
                             [--timeout-multiplier TIMEOUT_MULTIPLIER]
                             [--force-isolated] [--min-size MIN_SIZE]
                             [--max-attempts MAX_ATTEMPTS]
                             [--failure-types FAILURE_TYPES [FAILURE_TYPES ...]]
                             [--dry-run] [--update-dlq]

Retry failed files from Dead Letter Queue
...
```

### 3. Test Dry Run

```bash
python scripts/utils/retry_failed_files.py --dlq-path logs/failed_files_example.json --dry-run
```

Expected output:
```
2026-02-16 19:00:00 - INFO - Loaded 2 failed files from DLQ
2026-02-16 19:00:00 - INFO - Filtered to 2 eligible files for retry
2026-02-16 19:00:00 - INFO - Retry: sample_filing.html (45.2MB, medium, timeout: 2400s)
2026-02-16 19:00:00 - INFO - Retry: large_filing.html (68.5MB, large, timeout: 4800s)
2026-02-16 19:00:00 - INFO -
Retry Results:
2026-02-16 19:00:00 - INFO -   Total: 2
2026-02-16 19:00:00 - INFO -   Success: 0
2026-02-16 19:00:00 - INFO -   Failed: 0
2026-02-16 19:00:00 - INFO -   Skipped: 0
```

### 4. Run Logic Tests

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

## Troubleshooting

### Issue: ModuleNotFoundError: No module named 'psutil'

**Solution:**
```bash
pip install -e .
# OR
pip install psutil>=5.9.0
```

### Issue: ModuleNotFoundError: No module named 'src'

**Solution:** Ensure you're running from project root with PYTHONPATH set:
```bash
cd /home/beth/work/SEC-finetune
PYTHONPATH=/home/beth/work/SEC-finetune python scripts/utils/retry_failed_files.py --help
```

### Issue: ModuleNotFoundError: No module named 'pydantic'

**Solution:** The `pydantic` module had a breaking change. Ensure you have v2.12.4+:
```bash
pip install 'pydantic>=2.12.4'
```

### Issue: ImportError in sanitizer.py

**Solution:** The sanitizer module needs pydantic. Install all dependencies:
```bash
pip install -e .
```

### Issue: spaCy model not found (en_core_web_sm)

**Solution:**
```bash
python -m spacy download en_core_web_sm
# OR
python scripts/utils/setup_nlp_models.py
```

## Environment Setup (One-Time)

For a fresh environment:

```bash
# 1. Create virtual environment (if needed)
python -m venv venv
source venv/bin/activate  # On Linux/Mac
# OR
venv\Scripts\activate  # On Windows

# 2. Install project with all dependencies
pip install -e .

# 3. Download spaCy model
python -m spacy download en_core_web_sm

# 4. Verify installation
python scripts/utils/test_imports.py

# 5. Run tests
python scripts/utils/test_retry_logic.py

# 6. Test retry script
python scripts/utils/retry_failed_files.py --help
```

## What's Installed

After running `pip install -e .`, you'll have:

**Core Dependencies:**
- psutil (system memory monitoring)
- pydantic (data validation)
- sec-parser (SEC filing parsing)
- spacy (NLP text processing)
- sentence-transformers (semantic embeddings)
- pandas, numpy (data handling)
- torch, transformers (deep learning)
- beautifulsoup4, lxml (HTML parsing)
- And many more...

**Project Structure:**
- `src/` package is editable (changes reflect immediately)
- Scripts can import from `src.*`
- All utilities available

## Next Steps

Once installation is complete:

1. **Test with Example DLQ:**
   ```bash
   python scripts/utils/retry_failed_files.py --dlq-path logs/failed_files_example.json --dry-run
   ```

2. **Use with Real DLQ (when available):**
   ```bash
   python scripts/utils/retry_failed_files.py --dry-run
   python scripts/utils/retry_failed_files.py --timeout-multiplier 2.0 --update-dlq
   ```

3. **Read Documentation:**
   - Complete guide: `docs/RETRY_MECHANISM.md`
   - Quick start: `scripts/utils/RETRY_QUICK_START.md`

## Dependency Changes Summary

**File:** `pyproject.toml`

**Change:** Added `psutil>=5.9.0` to dependencies section (line ~53)

**Reason:** Required by `src/utils/memory_semaphore.py` for:
- Monitoring system memory usage
- Checking available RAM before processing
- Preventing OOM crashes

**Installation Command:** `pip install -e .`

**Verification:** `python scripts/utils/test_imports.py`

---

**Status:** ✅ Ready for installation

After running `pip install -e .`, the retry mechanism will be fully functional.
