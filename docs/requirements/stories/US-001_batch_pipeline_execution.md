---
id: US-001
epic: EP-1 Core Pipeline
priority: P0
status: Partial — batch mode implemented; output is JSON, not JSONL (gap)
source_prd: PRD-001, PRD-002
estimation: 5 points
---

# US-001: Batch Pipeline Execution with JSONL Output

## The Story

> **As a** `Data Scientist`,
> **I want** to run the full pipeline on a directory of HTML filings and receive JSONL output,
> **So that** I get a HuggingFace/Dask-compatible training dataset without manual format conversion.

## Why JSONL, not JSON

Standard JSON requires loading the entire file into memory. At 10,000+ filings with 30–100 segments each, a single aggregate JSON file is not streamable. JSONL (one complete JSON object per line) is the native format for `datasets.load_dataset("json", ...)`, Dask, and Spark — each record is independent, enabling streaming reads and partial loads.

## Acceptance Criteria

### Scenario A: Happy path — valid filings produce JSONL output
```gherkin
Given a directory data/raw/ containing one or more EDGAR HTML filings
  And the pipeline is invoked with python scripts/data_preprocessing/run_preprocessing_pipeline.py --input-dir data/raw/
When the run completes
Then each filing produces a {stem}_segmented_risks.jsonl in the stamped run directory
  And each line of the file is a valid, self-contained JSON object (one segment per line)
  And the file is readable by datasets.load_dataset("json", data_files="*.jsonl")
  And a RUN_REPORT.md summarises total processed, failed, and skipped counts
  And a batch_summary_{run_id}.json is written with machine-readable metrics
```

### Scenario B: JSONL record schema
```gherkin
Given a processed JSONL file
When I read one line and parse it as JSON
Then the record contains: cik, company_name, form_type, filing_date, ticker, sic_code, segment_id, segment_index, text, word_count, char_count, risk_label, confidence, pipeline_version, git_sha
  And text is the cleaned segment prose (no ToC lines, no table numeric rows)
  And risk_label and confidence are present (set to null if classifier not yet integrated)
```

### Scenario C: Empty input directory
```gherkin
Given a directory data/raw/ containing no HTML files
When the pipeline is invoked
Then it exits with a non-zero status code
  And logs "No input files found" to stderr
  And no run directory is created
```

### Scenario D: Mixed valid and malformed filings
```gherkin
Given a directory containing 10 valid filings and 2 malformed (truncated) HTML files
When the pipeline runs
Then all 10 valid filings produce JSONL output in the run directory
  And the 2 malformed filings appear in the Dead Letter Queue log
  And the run summary counts: processed=10, failed=2
  And the exit code is 0 (partial success is not a crash)
```

## Technical Notes

- Entry point: `scripts/data_preprocessing/run_preprocessing_pipeline.py`
- CLI flags: `--input-dir`, `--workers`, `--chunk-size`, `--resume`
- Output layout: `data/processed/{YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/`
- **Gap:** Current code writes JSON via `SegmentedRisks.save_to_json()`. Requires adding `save_to_jsonl()` that emits one record per segment (see PRD-002 §11 item 1)
- HuggingFace compatibility: `datasets.load_dataset("json", data_files="path/*.jsonl")`
- Status: ⚠️ Batch mode implemented; JSONL format not yet emitted (blocking for training pipeline)
