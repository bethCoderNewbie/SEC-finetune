---
date: 2025-12-12T16:00:00-06:00
researcher: bethCoderNewbie
git_commit: ea45dd2
branch: main
repository: SEC finetune
topic: "MLOps System Improvements"
tags: [mlops, data-versioning, documentation, experiment-tracking, model-registry]
status: in_progress
last_updated: 2025-12-12
phase5_completed: 2025-12-12
last_updated_by: bethCoderNewbie
related_research: thoughts/shared/research/2025-12-12_15-17_mlops_research_system_analysis.md
---

# Plan: MLOps System Improvements

## Desired End State

The MLOps system will have improved:
1.  **Research document discoverability** through an auto-generated index.
2.  **Model registry standardization** with Pydantic-validated schemas.
3.  **Experiment tracking capabilities** within `RunContext` for metric logging.
4.  **Data-code linkage** via Git SHA in pipeline output directory names.

## Anti-Scope

*   Full integration with external MLOps platforms (MLflow, W&B) as a hard dependency.
*   Implementing a complex search engine for research documents; a simple indexed README is sufficient.
*   Overhauling the entire data versioning system (e.g., replacing existing Git-based versioning with DVC for all artifacts).

## Implementation Strategy

The improvements will be implemented in four distinct phases:

### Phase 1: Create Research Indexer

*   **Objective:** Develop a script to automatically generate an index of research documents.
*   **Tasks:**
    *   Create a Python script `scripts/utils/generate_research_index.py`.
    *   This script will:
        *   Scan `thoughts/shared/research/` for `.md` files.
        *   Parse the YAML frontmatter of each document to extract `date`, `topic`, `status`, and `tags`.
        *   Generate a `README.md` file in `thoughts/shared/research/` containing a Markdown table of all research documents, sorted by date.
    *   Add a new entry to `pyproject.toml` or `Makefile` for running this script.
*   **Affected Files:**
    *   `scripts/utils/generate_research_index.py` (new)
    *   `thoughts/shared/research/README.md` (generated)
    *   Possibly `pyproject.toml` or `Makefile` (for automation)

### Phase 2: Standardize Model Registry

*   **Objective:** Define and enforce a structured schema for model artifacts.
*   **Tasks:**
    *   Define a Pydantic `BaseModel` (e.g., `ModelRegistryEntry`) for model metadata in `src/models/registry/schemas.py`. This schema will include fields like `model_name`, `version`, `git_sha`, `training_config_path`, `metrics_path`, `artifact_paths`, `timestamp`, etc.
    *   Create a `ModelRegistryManager` class in `src/models/registry/manager.py` to handle:
        *   Creating new model entries (directories).
        *   Saving `metadata.json` (validated by `ModelRegistryEntry`) within each model's version directory.
        *   Loading model metadata.
    *   Establish the directory structure: `models/registry/{model_name}/{version}/`.
*   **Affected Files:**
    *   `src/models/registry/__init__.py` (new)
    *   `src/models/registry/schemas.py` (new)
    *   `src/models/registry/manager.py` (new)
    *   Potentially `scripts/training/train_model.py` (to integrate with the new manager).

### Phase 3: Enhance `RunContext`

*   **Objective:** Extend `RunContext` to support metric logging and optional Git SHA inclusion in output paths.
*   **Tasks:**
    *   Modify `src/config/run_context.py`:
        *   Add a `save_metrics(self, metrics: Dict[str, Any])` method to `RunContext`. This method will serialize the `metrics` dictionary to `metrics.json` within the `output_dir`.
        *   Update the `__init__` method and `output_dir` property getter in `RunContext` to accept an optional `git_sha: Optional[str]` parameter. If provided, the `output_dir` path will be constructed to include the SHA (e.g., `data/processed/labeled/{timestamp}_{name}_{git_sha}/`).
*   **Affected Files:**
    *   `src/config/run_context.py`

### Phase 4: Refine Data Naming with Git SHA

*   **Objective:** Ensure pipeline outputs in `data/interim/` and `data/processed/` automatically include the Git SHA for strict versioning.
*   **Tasks:**
    *   Identify call sites where `RunContext` is used to create output directories for processed data (e.g., in `src/preprocessing/pipeline.py` or `scripts/data_preprocessing/batch_parse.py`).
    *   Retrieve the current Git SHA (e.g., using `hack/spec_metadata.sh` or a similar Python call) and pass it to the `RunContext` constructor when creating run directories for processed data.
    *   Update pipeline execution scripts to leverage this new functionality.
*   **Affected Files:**
    *   `src/preprocessing/pipeline.py` (if `RunContext` is initialized there)
    *   `scripts/data_preprocessing/batch_parse.py` (likely)
    *   Potentially other scripts in `scripts/` that produce versioned data artifacts.

### Phase 5: Standardize File Naming Convention (COMPLETED 2025-12-12)

*   **Objective:** Ensure all output files within a run share a consistent naming convention with the run's timestamp identifier.
*   **Executive Naming Convention:**
    ```
    {original_stem}_{run_id}_{output_type}.json
    ```
    Where:
    *   `original_stem`: The input file's stem (e.g., `AAPL_10K`)
    *   `run_id`: Timestamp in `YYYYMMDD_HHMMSS` format (shared across ALL files in the run)
    *   `output_type`: Describes the processing stage (e.g., `parsed`, `extracted_risks`, `cleaned_risks`, `segmented_risks`)

*   **Version Rule:** All files produced in a single run MUST share the same `run_id` timestamp. This ensures:
    1.  **Traceability:** Any output file can be traced back to its exact run
    2.  **Consistency:** Files processed together are easily identifiable
    3.  **Reproducibility:** Combined with git SHA in folder name, provides complete data-code linkage

*   **Directory Structure:**
    ```
    data/interim/parsed/{run_id}_{run_name}_{git_sha}/
    ├── AAPL_10K_{run_id}_parsed.json
    ├── MSFT_10K_{run_id}_parsed.json
    └── metrics.json

    data/interim/extracted/{run_id}_{run_name}_{git_sha}/
    ├── AAPL_10K_{run_id}_extracted_risks.json
    ├── AAPL_10K_{run_id}_cleaned_risks.json
    └── ...

    data/processed/{run_id}_{run_name}_{git_sha}/
    ├── AAPL_10K_{run_id}_segmented_risks.json
    ├── MSFT_10K_{run_id}_segmented_risks.json
    └── metrics.json
    ```

*   **Implementation Details:**
    *   `run_id` is passed through all pipeline functions
    *   Resume logic updated to match new naming pattern
    *   Functions updated: `run_pipeline()`, `process_single_file_fast()`, `run_batch_pipeline()`, `is_file_processed()`, `get_processed_files_set()`, `filter_unprocessed_files()`

*   **Affected Files:**
    *   `scripts/data_preprocessing/batch_parse.py` (lines 74-77)
    *   `scripts/data_preprocessing/run_preprocessing_pipeline.py` (multiple locations)

## Verification

After implementing each phase, the following verification steps will be performed:

1.  **Phase 1 Verification:**
    *   Run `python scripts/utils/generate_research_index.py`.
    *   Verify that `thoughts/shared/research/README.md` is created/updated with correct content and formatting.

2.  **Phase 2 Verification:**
    *   Write a temporary script or test to use `ModelRegistryManager` to register a dummy model.
    *   Verify that the model's directory structure is created correctly in `models/registry/`.
    *   Verify that `metadata.json` is saved with the correct schema and content.

3.  **Phase 3 Verification:**
    *   Write a temporary script or test to instantiate `RunContext` with a `git_sha`.
    *   Call `run.save_metrics({"accuracy": 0.9})`.
    *   Verify that the output directory name includes the Git SHA.
    *   Verify that `metrics.json` is created inside the output directory with the correct content.

4.  **Phase 4 Verification:**
    *   Execute a small-scale data processing run (e.g., using `scripts/data_preprocessing/batch_parse.py`).
    *   Inspect `data/interim/parsed/` and `data/processed/` directories.
    *   Verify that the newly created output directories include the current Git SHA in their names.

5.  **Phase 5 Verification:**
    *   Run `python scripts/data_preprocessing/batch_parse.py --run-name test_naming`
    *   Verify all output files share the same `run_id` timestamp in their filenames.
    *   Run `python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch --run-name test_pipeline`
    *   Verify extracted, cleaned, and segmented files all share the same `run_id`.
    *   Test resume functionality: re-run with `--resume` flag and verify already-processed files are correctly identified.
