---
id: US-004
epic: EP-1 Core Pipeline
priority: P0
status: Not implemented — CLI flag required; metadata alone is insufficient
source_prd: PRD-001, PRD-002
estimation: 2 points
---

# US-004: Sector-Specific Dataset Filtering (CLI Flag — Required)

## The Story

> **As a** `Data Scientist`,
> **I want** to filter filings by ticker or SIC code at the CLI before processing begins,
> **So that** I can build a "Tech Sector" training set without wasting compute processing 9,500 irrelevant filings only to manually filter afterward.

## Why This Is P0

At 10,000-filing scale, a post-processing filter is not a viable workaround. If SIC filtering is deferred to a manual step after the batch run, the Data Scientist must:
1. Run the full 10,000-filing batch (~2 hours minimum)
2. Write a one-off script to filter `sic_code` from 10,000 output files
3. Re-run feature engineering and train/test splitting on the filtered subset

A CLI flag costs ~2 points to implement. The absence of it costs hours of wasted compute on every model iteration cycle. This is not optional at scale.

## Acceptance Criteria

### Scenario A: Filter by SIC code prefix
```gherkin
Given a directory of filings from multiple SIC codes (including SIC 3571, 6020, 7372)
  And the pipeline is invoked with --sic 73
When the run completes
Then only filings where sic_code starts with "73" appear in the JSONL output directory
  And the RUN_REPORT.md shows: total_input=N, filtered_out=M, processed=N-M
  And filtered_out filings are not processed (no compute spent on them)
```

### Scenario B: Filter by exact ticker symbol
```gherkin
Given a directory of filings for multiple companies
  And the pipeline is invoked with --ticker AAPL
When the run completes
Then only filings where ticker == "AAPL" appear in the output directory
  And the batch_summary_{run_id}.json records: filter_type="ticker", filter_value="AAPL"
```

### Scenario C: Multiple filters are ANDed
```gherkin
Given --sic 73 and --ticker MSFT are both specified
When the pipeline runs
Then only filings matching BOTH conditions are processed
  And the RUN_REPORT.md shows the combined filter expression
```

### Scenario D: Filter matches no filings
```gherkin
Given --sic 9999 and no filings with that SIC code exist in the directory
When the pipeline runs
Then it exits with status 0
  And logs a warning: "Filter '--sic 9999' matched 0 of N input files. No output produced."
  And no output files or run directory are created
```

### Scenario E: No filter flag — all filings processed
```gherkin
Given the pipeline is invoked with no --sic or --ticker flag
When it runs
Then all filings in the input directory are processed (current behaviour preserved)
```

## Technical Notes

- `sic_code` and `ticker` are extracted by `SECFilingParser` and present in `SegmentedRisks`
- Filter must happen **before** `ParallelProcessor` dispatches work — not post-hoc on output files
- Implementation: add `--sic` / `--ticker` to `argparse` in the batch CLI entry point; add `SectorFilter` pass before `ResumeFilter`
- Status: ❌ Not implemented. Metadata is present in output but no pre-processing filter exists.
