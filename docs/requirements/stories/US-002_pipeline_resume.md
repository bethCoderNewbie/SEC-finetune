---
id: US-002
epic: EP-2 Resilience & Recovery
priority: P0
status: Implemented
source_prd: PRD-001, PRD-002
estimation: 3 points
---

# US-002: Pipeline Resume After Crash

## The Story

> **As an** `ML Engineer`,
> **I want** to resume a crashed pipeline run using the `--resume` flag,
> **So that** I don't lose hours of compute from a transient failure.

## Acceptance Criteria

### Scenario A: Resume after mid-run crash
```gherkin
Given a batch run that processed 60 of 100 filings before crashing
  And a _checkpoint.json exists in the run directory
When I invoke the pipeline with --resume pointing to that run directory
Then the pipeline skips the first 60 already-processed filings (ResumeFilter)
  And processes only the remaining 40 filings
  And the final RUN_REPORT.md reflects the complete 100-filing run
  And _checkpoint.json is deleted upon successful completion
```

### Scenario B: Resume flag on a fully completed run
```gherkin
Given a batch run that completed successfully (no _checkpoint.json present)
When I invoke the pipeline with --resume on the same run directory
Then all files are skipped (all already in .manifest.json)
  And the pipeline exits with status 0 and a message "All files already processed"
```

### Scenario C: Resume flag with no prior run directory
```gherkin
Given no prior run directory exists
When I invoke --resume with a path that does not exist
Then the pipeline exits with a non-zero status code
  And logs a clear error: "Resume directory not found: <path>"
```

## Technical Notes

- Checkpoint file: `data/processed/{run_dir}/_checkpoint.json`
- Resume state: `CheckpointManager` (`src/utils/checkpoint.py`)
- Skip logic: `ResumeFilter` (`src/utils/resume.py`) cross-references `.manifest.json`
- Status: ✅ Implemented (`--resume` + `CheckpointManager`)
