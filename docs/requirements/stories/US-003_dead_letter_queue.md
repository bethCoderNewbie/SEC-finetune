---
id: US-003
epic: EP-2 Resilience & Recovery
priority: P0
status: Implemented
source_prd: PRD-001, PRD-002
estimation: 3 points
---

# US-003: Dead Letter Queue for Malformed Filings

## The Story

> **As an** `ML Engineer`,
> **I want** malformed or unparseable filings routed to a Dead Letter Queue,
> **So that** the pipeline does not halt on bad input and the rest of the batch completes.

## Acceptance Criteria

### Scenario A: Malformed HTML triggers DLQ entry
```gherkin
Given a batch containing one filing with truncated or invalid HTML
When the parser raises an exception on that filing
Then the filing is captured by DeadLetterQueue with: file path, exception type, error message, timestamp
  And processing continues immediately with the next filing in the batch
  And the pipeline does not crash or pause
```

### Scenario B: DLQ drain attempt on final run
```gherkin
Given one or more filings in the Dead Letter Queue from a prior run
When the pipeline completes its primary batch
Then it attempts to re-process each DLQ entry once
  And successfully re-processed files are moved to the normal output directory
  And persistently-failing files remain in the DLQ with an updated failure count
```

### Scenario C: 404 / Permanent download error
```gherkin
Given a filing that returns HTTP 404 from EDGAR
When the downloader encounters this error
Then the file ID is immediately written to the DLQ with reason="404_not_found"
  And NO retry is attempted (retries are for transient 5xx / network errors only)
```

## Technical Notes

- Implementation: `DeadLetterQueue` (`src/utils/dead_letter_queue.py`)
- DLQ log location: `data/processed/{run_dir}/` (B3 pattern)
- Drain behaviour: invoked at batch completion before final report generation
- Status: ✅ Implemented (`DeadLetterQueue`, B3 fixed)
