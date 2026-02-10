---
date: 2025-12-30T14:25:51-06:00
date_short: 2025-12-30
timestamp: 2025-12-30_14-25-51
researcher: bethCoderNewbie
git_commit: 648bf25
git_commit_full: 648bf2589f7382a0fc89da6a1c8b35d2e05c7e87
branch: main
repository: SEC finetune
topic: "Validation Scripts Architecture - Separation of Concerns & Naming Conventions"
tags: [research, validation, qa-metrics, architecture, code-organization]
status: complete
last_updated: 2025-12-30
last_updated_by: bethCoderNewbie
---

# Research: Validation Scripts Architecture Analysis

**Date**: 2025-12-30T14:25:51-06:00
**Researcher**: bethCoderNewbie
**Git Commit**: 648bf25
**Branch**: main
**Repository**: SEC finetune
**Topic**: Validation Scripts Architecture - Separation of Concerns & Naming Conventions

## Research Question

Analyze the `scripts/validation/` directory to understand:
1. **Separation of Concerns**: How validation responsibilities are divided across quality domains
2. **Naming Conventions**: How scripts are named to communicate purpose and processing mode
3. **Parsed Data Quality Validation**: Which scripts validate parsed SEC filing output

## Executive Summary

The validation system enforces **4 quality domains** with **3,453 LOC** across 7 Python scripts. Each domain has **dual modes** (single-file and batch) following a consistent **`check_*`** naming convention. The architecture leverages **5 shared utilities** (`CheckpointManager`, `ParallelProcessor`, `RunMetadata`, `ReportFormatter`, `HealthCheckValidator`) for crash recovery, parallel processing, and standardized reporting.

**Answer**: Parsed data quality is validated by `scripts/validation/data_quality/check_preprocessing_*.py` scripts using `HealthCheckValidator` from `src/config/qa_validation.py`.

## Directory Structure & LOC Analysis

```
scripts/validation/                     Total: 3,453 LOC
├── README.md                          (324 lines - comprehensive guide)
│
├── data_quality/                      ⭐ VALIDATES PARSED DATA
│   ├── check_preprocessing_single.py  (159 LOC)
│   └── check_preprocessing_batch.py   (589 LOC)
│
├── extraction_quality/
│   ├── check_extractor_single.py      (260 LOC)
│   └── check_extractor_batch.py       (1,064 LOC)
│
├── feature_quality/
│   ├── check_nlp_single.py            (306 LOC)
│   └── check_nlp_batch.py             (830 LOC)
│
└── code_quality/
    └── check_pydantic_v2.py           (245 LOC)
```

## Separation of Concerns - 4 Quality Domains

### 1. Data Quality (Parsed Filings Validation) ⭐

**Purpose**: Validates preprocessing pipeline output (parsed SEC filings)

**Scripts**:
- `check_preprocessing_single.py` - Single-file validation
- `check_preprocessing_batch.py` - Batch parallel validation with checkpointing

**What It Validates**:
```yaml
Completeness:
  - identity_cik_present         # CIK number present?
  - identity_company_name_present # Company name present?
  - has_segments                 # Segments extracted?

Cleanliness:
  - html_artifact_ratio          # < 0.05 (95% clean text)
  - page_number_ratio            # < 0.10 (90% free of page numbers)

Substance:
  - avg_segment_word_count       # > 100 words (meaningful content)
  - non_empty_segment_ratio      # > 0.95 (95% segments have content)
  - risk_keyword_presence        # Risk keywords exist?
```

**Validator**: `src/config/qa_validation.py:HealthCheckValidator`

**Config Source**: `configs/qa_validation/health_check.yaml`

**Exit Codes**:
- `0` = All checks PASS (or WARN without `--fail-on-warn`)
- `1` = One or more checks FAIL

**Usage Examples**:
```bash
# Single file
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
    --verbose

# Batch (8 parallel workers)
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2 \
    --max-workers 8 \
    --checkpoint-interval 20 \
    --verbose
```

**Code References**:
- `check_preprocessing_single.py:86` - Instantiates `HealthCheckValidator()`
- `check_preprocessing_single.py:87` - Runs `validator.check_run(run_dir)`
- `check_preprocessing_batch.py:118-119` - Uses shared validator in worker process
- `check_preprocessing_batch.py:388` - Checkpoint save location `_validation_checkpoint.json`

### 2. Extraction Quality (Section Boundary Validation)

**Purpose**: Validates section extraction accuracy and content boundaries

**Scripts**:
- `check_extractor_single.py` - Single-file QA report
- `check_extractor_batch.py` - Batch QA with parallel processing

**What It Validates**:
- Section boundary detection (Item 1, 1A, 7, 7A)
- Content extraction completeness
- Title/header classification accuracy
- Flat tree traversal correctness

**Related Research**: `thoughts/shared/research/2025-12-03_19-45_parser_qa_metrics.md`

**Usage Examples**:
```bash
# Single file with markdown output
python scripts/validation/extraction_quality/check_extractor_single.py \
    --file data/interim/extracted/AAPL_10K_2021_10-K_extracted_risks.json \
    --format markdown

# Batch with 8 workers
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/20251212_203231_test_fix_ea45dd2 \
    --max-workers 8
```

**Code References**:
- `check_extractor_single.py:1-50` - Runs pytest tests and parses output
- `check_extractor_batch.py:1-1064` - Parallel batch processing with checkpoint

### 3. Feature Quality (NLP Metrics Validation)

**Purpose**: Validates NLP features (sentiment, readability metrics)

**Scripts**:
- `check_nlp_single.py` - Single-file NLP validation
- `check_nlp_batch.py` - Batch NLP validation

**What It Validates**:
- Sentiment analysis metrics (Loughran-McDonald dictionary)
- Readability metrics (Flesch-Kincaid, FOG index, etc.)
- Feature extraction completeness

**Usage Examples**:
```bash
# Single file
python scripts/validation/feature_quality/check_nlp_single.py \
    --processed-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
    --features-dir data/features/20251215_sentiment_features \
    --verbose

# Batch with 8 workers
python scripts/validation/feature_quality/check_nlp_batch.py \
    --processed-dir data/processed/20251212_161906_preprocessing_ea45dd2 \
    --features-dir data/features/20251215_sentiment_features \
    --max-workers 8
```

### 4. Code Quality (Compliance Validation)

**Purpose**: Validates Pydantic V2 compliance and schema definitions

**Scripts**:
- `check_pydantic_v2.py` - Scans codebase for Pydantic V2 compliance

**What It Validates**:
- Pydantic V2 migration compliance
- Schema definition correctness
- Deprecated pattern usage

**Usage**:
```bash
python scripts/validation/code_quality/check_pydantic_v2.py
```

## Naming Convention Analysis

### Pattern: `check_*`

**Rule**: All validation scripts use the `check_*` prefix to indicate validation operations

**Convention Breakdown**:
```
check_{domain}_{mode}.py

Where:
- domain = preprocessing | extractor | nlp | pydantic_v2
- mode   = single | batch (omitted for singletons like pydantic_v2)
```

**Examples**:
```
check_preprocessing_single.py  → Single-file data quality validation
check_preprocessing_batch.py   → Batch data quality validation
check_extractor_single.py      → Single-file extraction QA
check_extractor_batch.py       → Batch extraction QA
check_nlp_single.py            → Single-file NLP validation
check_nlp_batch.py             → Batch NLP validation
check_pydantic_v2.py           → Code compliance check (no mode needed)
```

### Dual-Mode Architecture

**Single-File Scripts** (`*_single.py`):
- **Purpose**: Quick validation of one file or directory
- **Processing**: Sequential (no parallelization)
- **Output**: Console summary + optional JSON report
- **Use Case**: Debugging, spot-checking, CI validation of single runs

**Batch Scripts** (`*_batch.py`):
- **Purpose**: Validate all files in a directory
- **Processing**: Parallel via `ProcessPoolExecutor`
- **Checkpointing**: Crash recovery with resume capability
- **Output**: Consolidated JSON report with per-file and aggregate metrics
- **Use Case**: Large-scale validation, regression testing, quality monitoring

**Shared Features Across Both Modes**:
- `--verbose` flag for detailed output
- `--output` flag for JSON report export
- Exit code 0 (pass) or 1 (fail)
- `--fail-on-warn` to treat warnings as failures (CI/CD)

## Shared Utilities Architecture

### 1. CheckpointManager (`src/utils/checkpoint.py`)

**Purpose**: Crash recovery for long-running batch operations

**Usage Pattern**:
```python
checkpoint = CheckpointManager(run_dir / "_validation_checkpoint.json")

# Save periodically
checkpoint.save(processed_files, results, metrics)

# Resume from checkpoint
if resume and checkpoint.exists():
    processed_set, results, metrics = checkpoint.load()

# Cleanup after success
checkpoint.cleanup()
```

**Checkpoint Format**:
```json
{
  "processed_files": ["file1.json", "file2.json"],
  "results": [{...}, {...}],
  "metrics": {"total_files": 100, "processed": 50},
  "timestamp": "2025-12-30T14:25:51.123456"
}
```

**Code References**:
- `src/utils/checkpoint.py:9-50` - CheckpointManager class definition
- `check_preprocessing_batch.py:388` - Checkpoint instantiation
- `check_preprocessing_batch.py:458-463` - Checkpoint save callback

### 2. ParallelProcessor (`src/utils/parallel.py`)

**Purpose**: Consistent parallel processing with ProcessPoolExecutor

**Usage Pattern**:
```python
processor = ParallelProcessor(
    max_workers=8,
    initializer=_init_worker,
    max_tasks_per_child=50
)

results = processor.process_batch(
    items=task_args,
    worker_func=validate_single_file_worker,
    progress_callback=checkpoint_callback,
    verbose=True
)
```

**Features**:
- Automatic worker initialization
- Memory management (`max_tasks_per_child=50`)
- Progress tracking with callbacks
- Graceful fallback to sequential mode

**Code References**:
- `src/utils/parallel.py:11-50` - ParallelProcessor class
- `check_preprocessing_batch.py:436-440` - Processor instantiation
- `check_preprocessing_batch.py:469-474` - Batch processing call

### 3. HealthCheckValidator (`src/config/qa_validation.py`)

**Purpose**: Data quality validation against configurable thresholds

**Architecture**:
```
HealthCheckValidator
    ↓
ThresholdRegistry (loads from configs/qa_validation/health_check.yaml)
    ↓
ValidationResult (compares actual vs. threshold)
    ↓
Report Generation (status, blocking_summary, validation_table)
```

**Threshold Categories**:
```yaml
identity:
  - identity_cik_present
  - identity_company_name_present

cleanliness:
  - html_artifact_ratio
  - page_number_ratio

substance:
  - avg_segment_word_count
  - non_empty_segment_ratio
  - risk_keyword_presence
  - has_segments
```

**Code References**:
- `src/config/qa_validation.py:1-100` - Schema definitions and loader
- `check_preprocessing_single.py:86-87` - Validator instantiation and execution
- `configs/qa_validation/health_check.yaml` - Threshold configuration

### 4. RunMetadata (`src/utils/metadata.py`)

**Purpose**: Collects comprehensive run environment metadata

**Metadata Collected**:
- Timestamp (ISO 8601)
- Python version
- Platform (OS, architecture)
- Git commit hash and branch
- Researcher/username
- Working directory

**Code References**:
- `src/utils/metadata.py` - RunMetadata class
- Used by all batch scripts for report headers

### 5. ReportFormatter (`src/utils/reporting.py`)

**Purpose**: Standardized formatting for validation reports

**Features**:
- Status icons (`[PASS]`, `[FAIL]`, `[WARN]`, `[ERR ]`)
- Table formatting for validation results
- Summary printing with pass/fail counts

**Code References**:
- `src/utils/reporting.py` - ReportFormatter class
- Used by all validation scripts for consistent output

## Parsed Data Quality Validation - Deep Dive

### Working Path: check_preprocessing_single.py

**How It Works** (`check_preprocessing_single.py:84-92`):
```python
# 1. Instantiate validator
validator = HealthCheckValidator()

# 2. Run validation on directory
report = validator.check_run(args.run_dir)

# 3. Handle error case
if report.get("status") == "ERROR":
    print(f"Error: {report.get('message', 'Unknown error')}")
    sys.exit(1)
```

**Report Structure**:
```json
{
  "status": "PASS" | "WARN" | "FAIL" | "ERROR",
  "run_directory": "data/processed/...",
  "files_checked": 10,
  "timestamp": "2025-12-30T14:25:51",
  "blocking_summary": {
    "total_blocking": 7,
    "passed": 7,
    "failed": 0,
    "warned": 0
  },
  "validation_table": [
    {
      "display_name": "Identity: CIK Present",
      "status": "PASS",
      "actual": "True",
      "target": "> 0.99"
    },
    ...
  ]
}
```

**Output Format** (`check_preprocessing_single.py:102-148`):
```
==================================================
Data Health Check: PASS
==================================================
  Run directory: data/processed/20251212_161906_preprocessing_ea45dd2
  Files checked: 10
  Timestamp: 2025-12-30T14:25:51

  Blocking Checks:
    Passed: 7/7
    Failed: 0
    Warned: 0

==================================================
Validation Details:
==================================================
  [PASS] Identity: CIK Present
         Actual: True | Target: > 0.99
  [PASS] Identity: Company Name Present
         Actual: True | Target: > 0.99
  [PASS] Cleanliness: HTML Artifact Ratio
         Actual: 0.0123 | Target: < 0.05
  ...

==================================================
Result: ALL CHECKS PASSED
==================================================
```

### Working Path: check_preprocessing_batch.py

**Parallel Processing Architecture** (`check_preprocessing_batch.py:69-73`):
```python
# Global worker state (initialized once per worker process)
_worker_validator: Optional[HealthCheckValidator] = None

def _init_worker() -> None:
    """Initialize validator once per worker process."""
    global _worker_validator
    _worker_validator = HealthCheckValidator()
```

**Worker Function** (`check_preprocessing_batch.py:164-230`):
```python
def validate_single_file_worker(args: Tuple[Path, Path, bool]) -> Dict[str, Any]:
    """
    Worker function for parallel validation (uses global _worker_validator).

    Creates temporary directory, copies file, runs validation, cleans up.
    Returns structured result dict with status, validation_results, blocking_summary.
    """
    file_path, run_dir, verbose = args

    # Create temp directory (unique per worker PID)
    temp_dir = run_dir / f"_temp_validation_{os.getpid()}"
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / file_path.name

    # Copy file to temp location
    shutil.copy(file_path, temp_file)

    # Run validation using global validator
    report = _worker_validator.check_run(temp_dir)

    # Clean up temp file
    temp_file.unlink()
    temp_dir.rmdir()

    return {
        'file': file_path.name,
        'overall_status': report['status'],
        'validation_results': report['validation_table'],
        'blocking_summary': report['blocking_summary'],
        ...
    }
```

**Checkpointing Logic** (`check_preprocessing_batch.py:453-463`):
```python
def checkpoint_callback(idx: int, result: Dict):
    """Save checkpoint periodically."""
    all_results.append(result)
    processed_files.append(result['file'])

    if idx % checkpoint_interval == 0:
        current_metrics = {
            "total_files": total_files_found,
            "processed": len(processed_files)
        }
        checkpoint.save(processed_files, all_results, current_metrics)
```

**Consolidated Report Generation** (`check_preprocessing_batch.py:237-300`):
```python
def generate_consolidated_report(
    run_dir: Path,
    per_file_results: List[Dict]
) -> Dict[str, Any]:
    """
    Aggregate all validation results into consolidated report.

    Counts:
    - File-level statuses (passed, warned, failed, errors)
    - Blocking check summaries across all files

    Determines overall status:
    - FAIL if any failed or blocking_failed > 0
    - WARN if any warned or blocking_warned > 0
    - PASS otherwise
    """
    passed = sum(1 for r in per_file_results if r['overall_status'] == 'PASS')
    warned = sum(1 for r in per_file_results if r['overall_status'] == 'WARN')
    failed = sum(1 for r in per_file_results if r['overall_status'] == 'FAIL')
    errors = sum(1 for r in per_file_results if r['status'] == 'error')

    # Aggregate blocking checks
    total_blocking = sum(r['blocking_summary'].get('total_blocking', 0)
                         for r in per_file_results if r['status'] == 'success')
    blocking_passed = sum(r['blocking_summary'].get('passed', 0)
                          for r in per_file_results if r['status'] == 'success')
    # ...

    return {
        "status": overall_status,
        "overall_summary": {...},
        "blocking_summary": {...},
        "per_file_results": per_file_results
    }
```

## Validation Threshold Configuration

**Config Source**: `configs/qa_validation/health_check.yaml`

**Threshold Schema** (from `src/config/qa_validation.py:92-100`):
```python
class MetricType(str, Enum):
    RATE = "rate"           # 0.0 - 1.0 (precision, recall, success_rate)
    COUNT = "count"         # Integer counts (segment_count, word_count)
    SCORE = "score"         # 0 - 100 scale (gini, obfuscation_score)
    LATENCY = "latency"     # Seconds (p95_latency, avg_processing_time)
    BOOLEAN = "boolean"     # True/False (is_implemented, is_idempotent)
    RANGE = "range"         # Min-max bounded (char_count, fk_grade)
```

**Example Threshold Definition** (YAML):
```yaml
thresholds:
  identity:
    identity_cik_present:
      display_name: "Identity: CIK Present"
      metric_type: "boolean"
      target: "True"
      operator: "=="
      blocking: true
      description: "CIK number must be present in filing metadata"

    identity_company_name_present:
      display_name: "Identity: Company Name Present"
      metric_type: "boolean"
      target: "True"
      operator: "=="
      blocking: true
      description: "Company name must be present in filing metadata"

  cleanliness:
    html_artifact_ratio:
      display_name: "Cleanliness: HTML Artifact Ratio"
      metric_type: "rate"
      target: 0.05
      operator: "<"
      blocking: true
      description: "HTML tags and attributes should be < 5% of text"

    page_number_ratio:
      display_name: "Cleanliness: Page Number Ratio"
      metric_type: "rate"
      target: 0.10
      operator: "<"
      blocking: false
      description: "Page numbers should be < 10% of text"
```

**Validation Logic** (ThresholdRegistry):
```python
# Get threshold
threshold = ThresholdRegistry.get("html_artifact_ratio")

# Compare actual vs. target
result = ValidationResult.from_threshold(threshold, actual=0.0123)

# result.status → "PASS" (0.0123 < 0.05)
# result.go_no_go → "GO"
# result.blocking → True
```

## Migration History

**Legacy Paths** (before validation reorganization):
```
scripts/utils/validation/validate_preprocessing_output.py
    → scripts/validation/data_quality/check_preprocessing_single.py

scripts/utils/validation/validate_preprocessing_output_batch.py
    → scripts/validation/data_quality/check_preprocessing_batch.py
```

**Migration Rationale**:
- Centralize all validation scripts in `scripts/validation/`
- Enforce domain separation (data/extraction/feature/code quality)
- Standardize naming (`check_*` prefix)
- Extract shared utilities to `src/utils/`

**Documentation**:
- `scripts/validation/README.md:33-44` - Migration mapping table
- `thoughts/shared/plans/2025-12-27_validation_scripts_reorganization.md` - Implementation plan

## CI/CD Integration Pattern

**Exit Code Contract**:
- `0` = All checks passed (or warnings without `--fail-on-warn`)
- `1` = One or more checks failed

**Example CI Script** (from `scripts/validation/README.md:234-255`):
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

## Code References Summary

### Data Quality Scripts
- `scripts/validation/data_quality/check_preprocessing_single.py:86-87` - Validator instantiation
- `scripts/validation/data_quality/check_preprocessing_batch.py:69-73` - Worker initialization
- `scripts/validation/data_quality/check_preprocessing_batch.py:164-230` - Worker function
- `scripts/validation/data_quality/check_preprocessing_batch.py:388` - Checkpoint manager
- `scripts/validation/data_quality/check_preprocessing_batch.py:453-463` - Checkpoint callback

### Shared Utilities
- `src/utils/checkpoint.py:9-50` - CheckpointManager class
- `src/utils/parallel.py:11-50` - ParallelProcessor class
- `src/utils/metadata.py` - RunMetadata class
- `src/utils/reporting.py` - ReportFormatter class

### QA Validation Config
- `src/config/qa_validation.py:1-100` - Schema definitions and ThresholdRegistry
- `configs/qa_validation/health_check.yaml` - Threshold configuration

### Documentation
- `scripts/validation/README.md:1-324` - Comprehensive validation guide
- `scripts/validation/README.md:46-53` - Naming conventions
- `scripts/validation/README.md:179-219` - Common features

## Related Research

- `thoughts/shared/research/2025-12-03_19-45_parser_qa_metrics.md` - Parser QA metrics
- `thoughts/shared/plans/2025-12-27_validation_scripts_reorganization.md` - Reorganization plan
- `docs/DATA_HEALTH_CHECK_GUIDE.md` - Data quality validation guide
- `docs/EXTRACTOR_QA_BATCH_GUIDE.md` - Extraction quality guide

## Key Architectural Insights

### 1. Domain-Driven Separation
Each quality domain has dedicated scripts with clear boundaries:
- **Data Quality** → Validates parsed filing structure and content
- **Extraction Quality** → Validates section boundaries and extraction accuracy
- **Feature Quality** → Validates NLP feature correctness
- **Code Quality** → Validates compliance and schema definitions

### 2. Dual-Mode Pattern
Every validation operation has two modes:
- **Single** → Fast, sequential, debugging-friendly
- **Batch** → Parallel, checkpointed, production-scale

### 3. Shared Utility Layer
Common concerns extracted to `src/utils/`:
- Checkpointing → Crash recovery
- Parallelization → ProcessPoolExecutor wrapper
- Metadata → Environment capture
- Reporting → Standardized output formatting

### 4. Configuration-Driven Thresholds
Thresholds are externalized to YAML configs:
- Easy adjustment without code changes
- Schema-validated via Pydantic V2
- Category-based organization
- Blocking vs. non-blocking distinction

### 5. Exit Code Contract
Consistent CI/CD integration via exit codes:
- `0` = Safe to proceed
- `1` = Must fix before proceeding

## Answers to Research Questions

### Q1: How are validation responsibilities separated?

**Answer**: 4 quality domains with dedicated subdirectories:

1. **`data_quality/`** - Validates parsed filing output (identity, cleanliness, substance)
2. **`extraction_quality/`** - Validates section extraction accuracy
3. **`feature_quality/`** - Validates NLP feature correctness
4. **`code_quality/`** - Validates code compliance

Each domain has dual modes (single/batch) with consistent interfaces.

### Q2: What naming conventions are used?

**Answer**: `check_{domain}_{mode}.py` pattern:

- **Prefix**: `check_*` indicates validation operation
- **Domain**: `preprocessing` | `extractor` | `nlp` | `pydantic_v2`
- **Mode**: `single` | `batch` (omitted for singletons)

**Examples**:
- `check_preprocessing_single.py` - Single-file data quality
- `check_preprocessing_batch.py` - Batch data quality
- `check_extractor_batch.py` - Batch extraction QA

### Q3: Which scripts validate parsed data quality?

**Answer**: `scripts/validation/data_quality/` directory:

- **`check_preprocessing_single.py`** - Validates single run directory
- **`check_preprocessing_batch.py`** - Validates all files in run directory (parallel)

**Validator**: `src/config/qa_validation.py:HealthCheckValidator`

**Config**: `configs/qa_validation/health_check.yaml`

**Metrics Validated**:
- Identity: CIK present, company name present
- Cleanliness: HTML artifact ratio < 5%, page number ratio < 10%
- Substance: Avg segment word count > 100, non-empty segment ratio > 95%, risk keywords present

**Exit Codes**: 0 (pass), 1 (fail)

## Open Questions

1. **Threshold Tuning**: Are current thresholds (e.g., `html_artifact_ratio < 0.05`) calibrated against real-world data distributions?
2. **Performance Benchmarks**: What is the typical speedup with 8 workers vs. sequential for batch validation?
3. **Checkpoint Overhead**: How much disk I/O overhead does checkpointing add? Is checkpoint interval optimal?
4. **Error Handling**: Should validation scripts distinguish between "data quality issues" and "pipeline failures"?
5. **Report Aggregation**: Should we build a time-series tracker to monitor quality metrics across runs?
