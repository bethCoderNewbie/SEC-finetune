# Data Health Check - Usage Guide

## Overview

The Data Health Check validation system ensures that preprocessing output meets MLOps quality standards before being used for model training. It validates data across four quality dimensions:

1. **Completeness** - Are required identity fields present (CIK, company name)?
2. **Cleanliness** - Is the text free of HTML artifacts and page numbers?
3. **Substance** - Are segments meaningful (non-empty, sufficient length)?
4. **Consistency** - Are there duplicate filings? Do risk keywords exist?

## Quick Start

### Basic Usage

```bash
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/20251212_161906_preprocessing_ea45dd2
```

### With Verbose Output

```bash
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
    --verbose
```

### Save Report to File

```bash
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
    --output reports/health_check_20251227.json
```

### For CI/CD Pipelines

```bash
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
    --fail-on-warn
```

## Batch Validation (100+ Files)

For large preprocessing runs with many files, use the batch validation script with parallel processing:

### Basic Batch Validation

```bash
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2
```

### Parallel Processing (Recommended for Large Batches)

```bash
# Use 8 parallel workers for faster validation
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2 \
    --max-workers 8
```

**Performance**: Validated 317 files in 36 seconds using 8 workers (~8.8 files/second)

### With Checkpointing and Resume

```bash
# Start validation with checkpoint every 20 files
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2 \
    --max-workers 8 \
    --checkpoint-interval 20

# If interrupted (Ctrl+C), resume from checkpoint
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2 \
    --max-workers 8 \
    --resume
```

### Custom Output Location

```bash
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2 \
    --max-workers 8 \
    --output reports/batch_validation_20251227.json
```

### Batch Validation Output

```
Starting batch validation on: data/interim/parsed/20251212_171015_batch_parse_ea45dd2
Found 317 JSON files in: data/interim/parsed/20251212_171015_batch_parse_ea45dd2
Using 8 parallel workers
Progress: 317/317
Completed in 36.15 seconds
Report saved to: data/interim/parsed/20251212_171015_batch_parse_ea45dd2/validation_report.json

============================================================
Batch Validation: PASS
============================================================
  Run directory: data/interim/parsed/20251212_171015_batch_parse_ea45dd2
  Total files: 317
  Validated: 317

  File Status:
    Passed: 310
    Warned: 5
    Failed: 2
    Errors: 0

  Blocking Checks (across all files):
    Total: 951
    Passed: 945
    Failed: 6
    Warned: 0

============================================================
Result: PASSED WITH WARNINGS
============================================================
```

### Batch Validation Features

| Feature | Description |
|---------|-------------|
| **Parallel Processing** | Use `--max-workers N` to validate multiple files simultaneously (default: CPU count) |
| **Checkpointing** | Automatically saves progress every N files (default: 10) for crash recovery |
| **Smart Resume** | Use `--resume` to skip already-validated files from checkpoint |
| **Consolidated Report** | Single JSON file with per-file results + aggregate summary |
| **Progress Tracking** | Real-time progress display (file count and percentage) |
| **Verbose Mode** | Use `--verbose` to see per-file validation status as files are processed |

### Checkpoint System

The batch validator automatically saves checkpoints during long runs:

1. **Checkpoint Location**: `{run-dir}/_validation_checkpoint.json`
2. **Checkpoint Interval**: Every N files (default: 10, configurable with `--checkpoint-interval`)
3. **Checkpoint Contents**: List of processed files, validation results, and metrics
4. **Auto-Cleanup**: Checkpoint file is automatically deleted on successful completion
5. **Resume**: If a run is interrupted, use `--resume` to continue from the last checkpoint

**Example checkpoint structure:**
```json
{
  "processed_files": ["file1.json", "file2.json", "..."],
  "results": [
    {"file": "file1.json", "overall_status": "PASS", "..."},
    {"file": "file2.json", "overall_status": "PASS", "..."}
  ],
  "metrics": {
    "total_files": 317,
    "processed": 150
  },
  "timestamp": "2025-12-27T13:30:00"
}
```

## Understanding the Output

### Console Output Structure

```
Running health check on: data/processed/20251212_161906_preprocessing_ea45dd2

==================================================
Data Health Check: PASS
==================================================
  Run directory: data/processed/20251212_161906_preprocessing_ea45dd2
  Files checked: 1
  Timestamp: 2025-12-27T12:45:14.775689

  Blocking Checks:
    Passed: 5/5
    Failed: 0
    Warned: 0

==================================================
Validation Details:
==================================================
  [PASS] CIK Present Rate
         Actual: 1.0000 | Target: 1.0
  [PASS] Company Name Present Rate
         Actual: 1.0000 | Target: 1.0
  [PASS] SIC Code Present Rate
         Actual: 1.0000 | Target: 0.95
  [PASS] HTML Artifact Rate
         Actual: 0.0000 | Target: 0.0
  [PASS] Page Number Artifact Rate
         Actual: 0.0000 | Target: 0.0
  [PASS] Empty Segment Rate
         Actual: 0.0000 | Target: 0.0
  [PASS] Short Segment Rate
         Actual: 0.0000 | Target: 0.05
  [PASS] Duplicate Rate
         Actual: 0.0000 | Target: 0.0
  [PASS] Risk Keyword Present
         Actual: True | Target: True

==================================================
Result: ALL CHECKS PASSED
==================================================
```

### Report Components

1. **Header** - Shows overall status (PASS/WARN/FAIL)
2. **Summary** - Files checked, timestamp, blocking check counts
3. **Validation Details** - Individual check results (shown with `--verbose`)
4. **Final Result** - Clear pass/fail verdict

### Status Meanings

| Status | Symbol | Meaning |
|--------|--------|---------|
| PASS   | [PASS] | Check met target threshold |
| WARN   | [WARN] | Check below target but above warning threshold |
| FAIL   | [FAIL] | Check failed to meet minimum threshold |
| SKIP   | [----] | Check skipped (no data available) |
| N/A    | [----] | Not applicable |

## Exit Codes

The script returns specific exit codes for automation:

| Exit Code | Condition |
|-----------|-----------|
| 0 | All checks passed |
| 1 | One or more blocking checks failed |
| 1 | Warnings detected (when using `--fail-on-warn`) |

### CI/CD Integration Example

```bash
#!/bin/bash
# Run preprocessing
python scripts/data_preprocessing/run_preprocessing_pipeline.py

# Get latest run directory
RUN_DIR=$(ls -td data/processed/2025* | head -1)

# Validate output
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir "$RUN_DIR" \
    --output reports/health_check.json \
    --fail-on-warn

# Exit code propagates to CI/CD
exit $?
```

## Validation Checks

### 1. Identity Completeness

Ensures all required metadata fields are present:

| Check | Target | Blocking | Description |
|-------|--------|----------|-------------|
| CIK Present Rate | 100% | Yes | All files must have CIK (Central Index Key) |
| Company Name Present Rate | 100% | Yes | All files must have company name |
| SIC Code Present Rate | 95% | No | 95% of files should have SIC code |

**Why it matters:** Missing identity fields prevent proper data tracking and sector analysis.

### 2. Data Cleanliness

Validates that text is free of preprocessing artifacts:

| Check | Target | Blocking | Description |
|-------|--------|----------|-------------|
| HTML Artifact Rate | 0% | Yes | No HTML tags should remain in text |
| Page Number Artifact Rate | 0% | No | No page number artifacts |

**Why it matters:** HTML and page numbers are noise that degrades model training quality.

**Example failures:**
- HTML: `<div class="header">Risk Factors</div>`
- Page numbers: `Page 12 of 45` or `12`

### 3. Content Substance

Ensures segments contain meaningful content:

| Check | Target | Blocking | Description |
|-------|--------|----------|-------------|
| Empty Segment Rate | 0% | Yes | No zero-length text segments |
| Short Segment Rate | ≤5% | No | Max 5% segments below 50 characters |

**Why it matters:** Empty or very short segments provide no value for training and indicate extraction issues.

### 4. Domain Rules

SEC-specific business logic validation:

| Check | Target | Blocking | Description |
|-------|--------|----------|-------------|
| Duplicate Rate | 0% | Yes | No duplicate filings (hash-based) |
| Risk Keyword Present | True | No | Risk sections should contain risk keywords |

**Why it matters:** Duplicates waste computational resources; missing risk keywords suggest extraction errors.

**Risk keywords detected:** risk, adverse, material, uncertain, may, could, might, potential

## JSON Report Format

When using `--output`, the report is saved as JSON:

```json
{
  "status": "PASS",
  "timestamp": "2025-12-27T12:45:14.775689",
  "run_directory": "data/processed/20251212_161906_preprocessing_ea45dd2",
  "files_checked": 1,
  "blocking_summary": {
    "total_blocking": 5,
    "passed": 5,
    "failed": 0,
    "warned": 0,
    "all_pass": true
  },
  "validation_table": [
    {
      "category": "identity_completeness",
      "metric": "cik_present_rate",
      "display_name": "CIK Present Rate",
      "target": 1.0,
      "actual": 1.0,
      "status": "PASS",
      "go_no_go": "GO"
    }
    // ... more validation results
  ]
}
```

## Programmatic Usage

### Python API

```python
from pathlib import Path
from src.config.qa_validation import HealthCheckValidator

# Create validator
validator = HealthCheckValidator()

# Run checks on a directory
report = validator.check_run(Path("data/processed/20251212_161906_preprocessing_ea45dd2"))

# Access results
print(f"Status: {report['status']}")
print(f"Files checked: {report['files_checked']}")
print(f"Blocking checks passed: {report['blocking_summary']['passed']}")

# Iterate through individual checks
for check in report['validation_table']:
    if check['status'] != 'PASS':
        print(f"Failed check: {check['display_name']}")
        print(f"  Actual: {check['actual']}, Target: {check['target']}")
```

### Custom Thresholds

Thresholds are defined in `configs/qa_validation/health_check.yaml`:

```python
from src.config.qa_validation import ThresholdRegistry

# Get a specific threshold
threshold = ThresholdRegistry.get("cik_present_rate")
print(f"Target: {threshold.target}")
print(f"Blocking: {threshold.blocking}")

# Get all thresholds in a category
identity_checks = ThresholdRegistry.by_category("identity_completeness")

# Get all blocking thresholds
critical_checks = ThresholdRegistry.blocking_thresholds()
```

## Configuration

### Modifying Thresholds

Edit `configs/qa_validation/health_check.yaml` to adjust thresholds:

```yaml
thresholds:
  identity_completeness:
    cik_present_rate:
      display_name: CIK Present Rate
      metric_type: rate
      target: 1.0          # Change this to adjust target
      operator: ">="
      blocking: true       # Set false to make non-blocking
      warn_threshold: 0.95 # Add warning threshold
      description: All files must have CIK
      tags: [identity, schema, blocking, health_check]
```

### Adding New Checks

1. Add threshold definition to `health_check.yaml`
2. Implement check logic in `src/config/qa_validation.py` (HealthCheckValidator class)
3. Add the check to the appropriate method (`_check_identity`, `_check_cleanliness`, etc.)

## Troubleshooting

### No JSON files found

**Error:** `Error: No JSON files found`

**Solution:** Ensure the run directory contains `.json` output files from preprocessing. Check that you're pointing to the correct directory.

```bash
# List contents of run directory
ls data/processed/20251212_161906_preprocessing_ea45dd2/
```

### All checks show SKIP

**Cause:** JSON files have unexpected structure or missing fields

**Solution:** Verify JSON files match the expected schema with identity fields (cik, company_name) and segments array.

### Blocking checks failing

**Typical failures:**

1. **CIK/Company Name missing** - Check parser configuration
2. **HTML artifacts present** - Review cleaner configuration
3. **Empty segments** - Check segmenter logic
4. **Duplicates detected** - Review input data for duplicate filings

**Debug steps:**
```python
# Inspect a JSON file
import json
with open("data/processed/.../filing.json") as f:
    data = json.load(f)
    print(data.keys())
    print(data.get("segments", [])[:2])  # First 2 segments
```

## Reference

### Command Line Options

```
--run-dir PATH       Directory containing JSON output files to validate (required)
--output, -o PATH    Output JSON report file (optional)
--fail-on-warn       Exit with code 1 on warnings (useful for CI/CD)
--verbose, -v        Show detailed validation table
```

### Related Files

- **Validator:** `src/config/qa_validation.py` (HealthCheckValidator class)
- **Thresholds:** `configs/qa_validation/health_check.yaml`
- **Single-File Script:** `scripts/validation/data_quality/check_preprocessing_single.py`
- **Batch Script:** `scripts/validation/data_quality/check_preprocessing_batch.py`
- **Tests:** `tests/validation/test_health_check.py`

### Design Documentation

- `thoughts/shared/plans/2025-12-20_data_health_check_implementation.md` - Implementation plan
- `thoughts/shared/research/2025-12-20_14-30_data_health_check_architecture.md` - Architecture design

## Best Practices

1. **Run after every preprocessing run** - Catch issues early
2. **Use `--fail-on-warn` in CI/CD** - Enforce strict quality gates
3. **Save reports with timestamps** - Track quality over time
4. **Review failed checks immediately** - Don't proceed with bad data
5. **Monitor warning trends** - Address degrading metrics proactively

## Example Workflow

```bash
# 1. Run preprocessing
python scripts/data_preprocessing/run_preprocessing_pipeline.py

# 2. Validate output
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/$(ls -t data/processed | head -1) \
    --verbose \
    --output reports/health_check_$(date +%Y%m%d_%H%M%S).json

# 3. If validation passes, proceed to training
# 4. If validation fails, debug and re-run preprocessing
```
