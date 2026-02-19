---
id: US-005
epic: EP-5 Observability
priority: P1
status: Implemented
source_prd: PRD-001, PRD-002
estimation: 2 points
---

# US-005: Failure Inspection After Batch Run

## The Story

> **As a** `Data Scientist`,
> **I want** to inspect which filings failed and exactly why,
> **So that** I can improve parser and extractor logic iteratively without guessing.

## Acceptance Criteria

### Scenario A: Per-filing failure details in run report
```gherkin
Given a batch run in which 3 of 100 filings failed
When I open RUN_REPORT.md in the run directory
Then each failed filing has: file path, failure stage (parse/extract/clean/segment), exception class, truncated error message
  And a summary section shows total_failed=3 and failure_rate_pct
```

### Scenario B: DLQ log is human-readable
```gherkin
Given a Dead Letter Queue with 5 entries
When I read the DLQ log file
Then each entry includes: filename, timestamp, exception_type, message, retry_count
  And entries are readable as plain text (not binary)
```

### Scenario C: Progress log captures per-file elapsed time
```gherkin
Given a batch run that processed 50 filings
When I read _progress.log
Then each line contains: filename, processing stage, elapsed_seconds, status (ok | fail | timeout)
  And the log is written incrementally (visible before the run ends)
```

## Technical Notes

- Run report: `MarkdownReportGenerator` → `data/processed/{run_dir}/RUN_REPORT.md`
- Progress log: `ProgressLogger` → `data/processed/{run_dir}/_progress.log`
- DLQ log: `DeadLetterQueue` → `data/processed/{run_dir}/`
- Status: ✅ Implemented (`RUN_REPORT.md`, DLQ log, `_progress.log`)
