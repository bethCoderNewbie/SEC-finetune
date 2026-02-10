# Validation Scripts - Quality Assurance System

## Overview

The validation system provides comprehensive quality assurance for SEC 10-K preprocessing data across four quality domains:

1. **Data Quality** - Validates preprocessing output (completeness, cleanliness, substance)
2. **Feature Quality** - Validates NLP features (sentiment, readability metrics)
3. **Extraction Quality** - Validates section extraction accuracy (boundaries, content)
4. **Code Quality** - Validates code compliance (Pydantic V2, schema definitions)

## Directory Structure

```
scripts/validation/
├── data_quality/
│   ├── check_preprocessing_batch.py    # Batch validation with parallel processing
│   └── check_preprocessing_single.py   # Single-file validation
│
├── feature_quality/
│   ├── check_nlp_batch.py             # Batch NLP feature validation
│   └── check_nlp_single.py            # Single-file NLP validation
│
├── extraction_quality/
│   ├── check_extractor_batch.py       # Batch extraction QA
│   └── check_extractor_single.py      # Single-file extraction QA
│
└── code_quality/
    └── check_pydantic_v2.py           # Pydantic V2 compliance validation
```

## Quick Reference - Migration Guide

If you're looking for scripts that were previously in `scripts/utils/` or `scripts/utils/validation/`, use this mapping:

| Old Path | New Path | Purpose |
|----------|----------|---------|
| `scripts/utils/validation/validate_preprocessing_output.py` | `scripts/validation/data_quality/check_preprocessing_single.py` | Single-file data health check |
| `scripts/utils/validation/validate_preprocessing_output_batch.py` | `scripts/validation/data_quality/check_preprocessing_batch.py` | Batch data health check |
| `scripts/utils/generate_validation_report.py` | `scripts/validation/feature_quality/check_nlp_single.py` | Single-file NLP validation |
| `scripts/utils/generate_validation_report_batch.py` | `scripts/validation/feature_quality/check_nlp_batch.py` | Batch NLP validation |
| `scripts/utils/generate_extractor_qa_report.py` | `scripts/validation/extraction_quality/check_extractor_single.py` | Single-file extraction QA |
| `scripts/utils/generate_extractor_qa_report_batch.py` | `scripts/validation/extraction_quality/check_extractor_batch.py` | Batch extraction QA |
| `scripts/utils/validation/validate_pydantic_v2.py` | `scripts/validation/code_quality/check_pydantic_v2.py` | Pydantic V2 compliance check |

## Naming Conventions

All validation scripts follow these naming conventions:

- **`check_*`** - Scripts that validate and return pass/fail status (exit code 0 or 1)
- **`*_batch`** - Batch processing version with parallel execution and checkpointing
- **`*_single`** - Single-file processing version for quick validation

## Quick Start by Domain

### 1. Data Quality Validation

Validates preprocessing output for completeness, cleanliness, and substance.

**Single File:**
```bash
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
    --verbose
```

**Batch (Parallel):**
```bash
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2 \
    --max-workers 8
```

**Detailed Guide:** See [docs/DATA_HEALTH_CHECK_GUIDE.md](../../docs/DATA_HEALTH_CHECK_GUIDE.md)

### 2. Feature Quality Validation

Validates NLP features including sentiment analysis and readability metrics.

**Single File:**
```bash
python scripts/validation/feature_quality/check_nlp_single.py \
    --processed-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
    --features-dir data/features/20251215_sentiment_features \
    --verbose
```

**Batch (Parallel):**
```bash
python scripts/validation/feature_quality/check_nlp_batch.py \
    --processed-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
    --features-dir data/features/20251215_sentiment_features \
    --max-workers 8
```

### 3. Extraction Quality Validation

Validates section extraction accuracy, boundaries, and content quality.

**Single File:**
```bash
python scripts/validation/extraction_quality/check_extractor_single.py \
    --file data/interim/extracted/AAPL_10K_2021_10-K_extracted_risks.json \
    --format markdown
```

**Batch (Parallel):**
```bash
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/20251212_203231_test_fix_ea45dd2 \
    --max-workers 8
```

**Detailed Guide:** See [docs/EXTRACTOR_QA_BATCH_GUIDE.md](../../docs/EXTRACTOR_QA_BATCH_GUIDE.md)

### 4. Code Quality Validation

Validates Pydantic V2 compliance and schema definitions.

```bash
python scripts/validation/code_quality/check_pydantic_v2.py
```

## Shared Utilities

All validation scripts leverage shared utilities from `src/utils/`:

### CheckpointManager (`src/utils/checkpoint.py`)

Provides crash recovery for long-running batch operations.

```python
from src.utils.checkpoint import CheckpointManager

checkpoint = CheckpointManager(run_dir / "_validation_checkpoint.json")
checkpoint.save(processed_files, results, metrics)
processed_files, results, metrics = checkpoint.load()
checkpoint.cleanup()
```

### ParallelProcessor (`src/utils/parallel.py`)

Wraps ProcessPoolExecutor for consistent parallel processing.

```python
from src.utils.parallel import ParallelProcessor

processor = ParallelProcessor(max_workers=8, initializer=init_worker)
results = processor.process_batch(
    items=files,
    worker_func=validate_file,
    progress_callback=checkpoint_callback,
    verbose=True
)
```

### RunMetadata (`src/utils/metadata.py`)

Collects comprehensive run environment metadata.

```python
from src.utils.metadata import RunMetadata

metadata = RunMetadata.gather()
# Returns: timestamp, python_version, platform, git_commit, git_branch, researcher, working_dir
```

### ReportFormatter (`src/utils/reporting.py`)

Provides consistent formatting for validation reports.

```python
from src.utils.reporting import ReportFormatter

ReportFormatter.print_summary(report, title="Validation Report", verbose=True)
status_icon = ReportFormatter.format_status_icon("PASS")  # Returns '[PASS]'
```

## Common Features Across All Batch Scripts

### Parallel Processing

All batch scripts support parallel processing with configurable workers:

```bash
--max-workers 8          # Use 8 parallel workers (default: CPU count)
--max-workers 1          # Sequential processing (no parallelization)
```

**Performance**: Typical speedup of 3-5x with 8 workers on large batches.

### Checkpoint and Resume

All batch scripts automatically checkpoint progress for crash recovery:

```bash
--checkpoint-interval 20  # Save checkpoint every 20 files (default: 10)
--resume                  # Resume from last checkpoint if interrupted
```

**Checkpoint Location**: `{run-dir}/_validation_checkpoint.json` or `_extractor_qa_checkpoint.json`

### Verbose Output

All scripts support verbose mode for detailed progress tracking:

```bash
--verbose, -v            # Show per-file validation status
```

### Exit Codes

All validation scripts return consistent exit codes:

| Exit Code | Condition |
|-----------|-----------|
| 0 | All checks passed |
| 1 | One or more checks failed or errors occurred |

## Best Practices

1. **Run validation after every preprocessing step** - Catch issues early in the pipeline
2. **Use batch scripts for large datasets** - Significantly faster with parallel processing
3. **Enable checkpointing for large batches** - Recover from interruptions without restarting
4. **Review failed checks immediately** - Don't proceed with invalid data
5. **Archive validation reports** - Track quality metrics over time
6. **Use `--verbose` during debugging** - Get detailed per-file status
7. **Monitor pass rates** - Track quality trends across runs

## CI/CD Integration

All validation scripts are designed for CI/CD integration with consistent exit codes:

```bash
#!/bin/bash
# Run preprocessing
python scripts/data_preprocessing/run_preprocessing_pipeline.py

# Get latest run directory
RUN_DIR=$(ls -td data/processed/2025* | head -1)

# Validate data quality
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir "$RUN_DIR" \
    --max-workers 8 \
    --output reports/data_quality.json

# Exit code propagates to CI/CD (0 = pass, 1 = fail)
if [ $? -ne 0 ]; then
    echo "Data quality validation failed!"
    exit 1
fi

echo "All validations passed! Proceeding with training..."
```

## Testing

Unit tests for shared utilities are located in `tests/unit/utils/`:

```bash
pytest tests/unit/utils/test_checkpoint.py
pytest tests/unit/utils/test_parallel.py
pytest tests/unit/utils/test_metadata.py
pytest tests/unit/utils/test_reporting.py
```

Integration tests for validation scripts are located in `tests/validation/`:

```bash
pytest tests/validation/test_health_check.py
pytest tests/validation/test_nlp_validation.py
pytest tests/validation/test_extractor_qa.py
```

## Troubleshooting

### No files found

**Error**: `No JSON files found in: {path}`

**Solution**: Verify the directory path contains the expected output files (`.json` files).

### Checkpoint compatibility issues

**Error**: `Failed to load checkpoint`

**Solution**: Delete the checkpoint file and re-run without `--resume`:

```bash
rm {run-dir}/_validation_checkpoint.json
```

### Parallel processing slower than sequential

**Cause**: Small batch sizes or very fast validation operations

**Solution**: Use sequential mode for small batches (< 10 files):

```bash
--max-workers 1
```

### Import errors for shared utilities

**Error**: `ModuleNotFoundError: No module named 'src.utils'`

**Solution**: Ensure you're running from the project root directory and `src/utils/` exists.

## Additional Documentation

- **Data Quality Guide**: [docs/DATA_HEALTH_CHECK_GUIDE.md](../../docs/DATA_HEALTH_CHECK_GUIDE.md)
- **Extraction Quality Guide**: [docs/EXTRACTOR_QA_BATCH_GUIDE.md](../../docs/EXTRACTOR_QA_BATCH_GUIDE.md)
- **Implementation Plan**: [thoughts/shared/plans/2025-12-27_validation_scripts_reorganization.md](../../thoughts/shared/plans/)
- **Research Document**: [thoughts/shared/research/2025-12-27_13-35_validation_scripts_reorganization.md](../../thoughts/shared/research/)

## Support

For questions or issues:
1. Check the detailed guides linked above
2. Review the research document for architectural decisions
3. Run with `--verbose` to get detailed output
4. Check checkpoint files for crash recovery details
