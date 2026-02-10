# SEC Section Extractor - Batch QA Report Guide

## Overview

The Batch Extractor QA Report generates comprehensive quality assessment reports for multiple extracted risk factor files in parallel. It validates extraction accuracy, content quality, and benchmarking metrics across large batches of files.

## Quick Start

### Basic Usage

```bash
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/20251212_203231_test_fix_ea45dd2
```

### Parallel Processing (Recommended)

```bash
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/20251212_203231_test_fix_ea45dd2 \
    --max-workers 8
```

**Performance**: Validated 23 files in 8.88 seconds using 8 workers (~2.6 files/second)

### Generate Markdown Report

```bash
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/20251212_203231_test_fix_ea45dd2 \
    --format markdown \
    --output reports/extractor_qa_batch_20251227.md
```

### With Checkpointing and Resume

```bash
# Start batch QA with checkpoint every 20 files
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/20251212_203231_test_fix_ea45dd2 \
    --max-workers 8 \
    --checkpoint-interval 20

# Resume from checkpoint if interrupted
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/20251212_203231_test_fix_ea45dd2 \
    --resume
```

## QA Metrics

The batch QA report validates 8 metrics across 3 categories:

### 1. Boundary Detection (Critical)

| Metric | Target | Blocking | Description |
|--------|--------|----------|-------------|
| **Valid Section Identifier** | Matches Item 1A pattern | Yes | Ensures section identifier contains valid Item 1A variants |
| **Section Has Title** | Non-empty | Yes | Verifies extracted section has a title |

### 2. Content Quality

| Metric | Target | Blocking | Description |
|--------|--------|----------|-------------|
| **Title Mentions Risk** | Contains "risk" | No | Title should mention risk factors |
| **Substantial Content** | >1,000 chars | Yes | Minimum content length threshold |
| **No Page Headers** | Zero occurrences | No | No page header artifacts in text |
| **Has Subsections** | >0 subsections | No | Section should have subsections |

### 3. Benchmarking

| Metric | Target | Blocking | Description |
|--------|--------|----------|-------------|
| **Character Count in Range** | 5,000 - 50,000 chars | No | Content length within expected bounds |
| **Risk Keyword Density** | >0.5% | No | Percentage of risk-related keywords |

**Risk Keywords**: risk, risks, adverse, adversely, material, materially, uncertain, uncertainty, may, could, might, potential

## Output Formats

### JSON Report (Default)

```json
{
  "status": "WARN",
  "timestamp": "2025-12-27T14:30:00",
  "run_directory": "data/interim/extracted/20251212_203231_test_fix_ea45dd2",
  "total_files": 23,
  "files_validated": 23,
  "overall_summary": {
    "passed": 4,
    "warned": 19,
    "failed": 0,
    "errors": 0
  },
  "metric_statistics": {
    "valid_identifier": {
      "display_name": "Valid Section Identifier",
      "category": "Boundary Detection",
      "blocking": true,
      "passed": 23,
      "failed": 0,
      "warned": 0,
      "pass_rate": 1.0
    }
    // ... more metrics
  },
  "per_file_results": [
    {
      "file": "AAPL_10K_2021_10-K_20251212_203231_extracted_risks.json",
      "overall_status": "WARN",
      "metrics": {
        "valid_identifier": {"status": "PASS", "actual": "part1item1a", ...},
        "has_title": {"status": "PASS", "actual": "'Item 1A. Risk Factors'", ...}
        // ... more metrics
      }
    }
    // ... more files
  ]
}
```

### Markdown Report

```bash
--format markdown
```

Generates a comprehensive markdown report with:
- Executive summary with file status counts
- Metric performance table with pass rates
- Detailed findings by category
- Failed files section with specific metric failures
- Overall status and recommendations

**Example output:**

```
# SEC Section Extractor QA Report (Batch)

**Status**: `WARN`

## 1. Executive Summary

**File Status Summary**:
*   ✅ **Passed**: 4
*   ⚠️ **Warned**: 19
*   ❌ **Failed**: 0
*   🔴 **Errors**: 0

### Metric Performance

| Metric Category | Metric Name | Pass Rate | Passed | Failed | Warned | Blocking |
|-----------------|-------------|-----------|--------|--------|--------|----------|
| **Boundary Detection** | Valid Section Identifier 🔒 | 100.0% | 23 | 0 | 0 | Yes |
| **Boundary Detection** | Section Has Title 🔒 | 100.0% | 23 | 0 | 0 | Yes |
...
```

## Command Line Options

```
--run-dir PATH              Directory containing extracted risk JSON files (required)
--output, -o PATH           Output path for report (default: {run-dir}/extractor_qa_report.{ext})
--format {json,markdown}    Output format: json or markdown (default: json)
--max-workers INT           Number of parallel workers (default: CPU count, use 1 for sequential)
--checkpoint-interval INT   Save checkpoint every N files (default: 10)
--resume                    Resume from checkpoint if exists
--verbose, -v               Show detailed progress per file
```

## Understanding Results

### Overall Status

| Status | Meaning |
|--------|---------|
| PASS   | All files passed all blocking checks |
| WARN   | Some files have warnings on non-blocking metrics |
| FAIL   | One or more files failed blocking checks |
| ERROR  | Errors occurred during validation (check individual file errors) |

### Per-File Status

| Status | Meaning |
|--------|---------|
| PASS   | All metrics passed for this file |
| WARN   | Some non-blocking metrics failed |
| FAIL   | One or more blocking metrics failed |
| ERROR  | Exception during validation |

### Metric Performance

**Pass Rate** = (Passed Files / Total Validated Files) × 100%

- **100% pass rate**: All files passed this metric
- **80-99% pass rate**: Most files passed, some improvements needed
- **<80% pass rate**: Significant issues, investigate failures

## Example Workflow

### 1. Run Batch Extraction

```bash
python scripts/data_preprocessing/batch_extract.py \
    --parsed-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2 \
    --output-dir data/interim/extracted/20251227_extraction_batch \
    --max-workers 8
```

### 2. Generate Batch QA Report

```bash
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/20251227_extraction_batch \
    --max-workers 8 \
    --format markdown \
    --output reports/extractor_qa_20251227.md
```

### 3. Review Results

```bash
# View summary in terminal
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/20251227_extraction_batch \
    --verbose

# Open markdown report
cat reports/extractor_qa_20251227.md
```

### 4. Fix Issues

If failures are detected:
1. Review failed files in the report
2. Check specific metric failures
3. Fix extraction logic in `src/preprocessing/extractor.py`
4. Re-run extraction on failed files
5. Re-validate

## Checkpoint System

The batch QA script automatically saves checkpoints during long runs:

1. **Checkpoint Location**: `{run-dir}/_extractor_qa_checkpoint.json`
2. **Checkpoint Interval**: Every N files (default: 10)
3. **Checkpoint Contents**: Processed files, validation results, metrics
4. **Auto-Cleanup**: Deleted on successful completion
5. **Resume**: Use `--resume` to continue from last checkpoint

**Example checkpoint:**
```json
{
  "processed_files": ["file1.json", "file2.json", ...],
  "results": [
    {"file": "file1.json", "overall_status": "PASS", ...},
    {"file": "file2.json", "overall_status": "WARN", ...}
  ],
  "metrics": {
    "total_files": 100,
    "processed": 50
  },
  "timestamp": "2025-12-27T14:00:00"
}
```

## CI/CD Integration

### Example Pipeline

```bash
#!/bin/bash
# Extract risk factors
python scripts/data_preprocessing/batch_extract.py \
    --parsed-dir data/interim/parsed/latest \
    --output-dir data/interim/extracted/latest \
    --max-workers 8

# Validate extraction quality
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/latest \
    --output reports/extractor_qa_latest.json \
    --max-workers 8

# Check exit code
if [ $? -ne 0 ]; then
    echo "Extractor QA failed! Review report at reports/extractor_qa_latest.json"
    exit 1
fi

echo "Extractor QA passed! Proceeding with pipeline..."
```

### Exit Codes

| Exit Code | Condition |
|-----------|-----------|
| 0 | All checks passed (PASS or WARN status) |
| 1 | Critical failures detected (FAIL status) |

## Performance

**Benchmark Results**:
- **Sequential**: ~1-2 files/second
- **Parallel (8 workers)**: ~2-3 files/second
- **23 files**: ~9 seconds with 8 workers
- **100 files**: ~35-40 seconds with 8 workers

**Bottlenecks**:
- JSON file I/O dominates processing time
- Regex pattern matching on large text
- Checkpoint writes every N files

## Troubleshooting

### No extracted risk files found

**Error**: `No extracted risk JSON files found in: {path}`

**Solution**: Ensure the directory contains `*extracted*.json` files from the extraction pipeline.

```bash
# Check directory contents
ls data/interim/extracted/20251227_extraction_batch/*extracted*.json
```

### All files showing errors

**Cause**: JSON files have unexpected structure or missing fields

**Solution**: Verify JSON files match expected schema:

```python
import json
with open("file_extracted_risks.json") as f:
    data = json.load(f)
    print(data.keys())  # Should have: version, text, identifier, title, subsections, elements
```

### Low pass rates on specific metrics

**Page Headers**: Check if cleaner is properly removing page headers
**Keyword Density**: Verify text contains risk-related content
**Character Count**: May indicate extraction captured too much/little text

## Related Files

- **Batch Script**: `scripts/validation/extraction_quality/check_extractor_batch.py`
- **Single Report Script**: `scripts/validation/extraction_quality/check_extractor_single.py`
- **Extractor Module**: `src/preprocessing/extractor.py`
- **Constants**: `src/preprocessing/constants.py` (PAGE_HEADER_PATTERN)
- **Tests**: `tests/preprocessing/test_extractor.py`

## Best Practices

1. **Run QA after extraction** - Validate quality before proceeding to cleaning
2. **Use parallel processing** - Significantly speeds up large batches
3. **Review markdown reports** - Human-readable format for detailed analysis
4. **Monitor pass rates over time** - Track extraction quality improvements
5. **Fix critical failures immediately** - Don't proceed with failed extractions
6. **Archive reports** - Keep historical QA reports for auditing
