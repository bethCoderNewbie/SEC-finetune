---
id: US-019
epic: EP-5 Observability
priority: P1
status: Not wired — pipeline exists; scheduler not configured
source_prd: PRD-002
estimation: 3 points
dod: The system runs the full ingestion pipeline automatically every 24 hours without manual intervention.
---

# US-019: Automated Daily Ingestion

## The Story

> **As a** `Data Manager`,
> **I want** the system to automatically check for new SEC filings every day and process them,
> **So that** we are always working with the most up-to-date information without anyone needing to remember to run the pipeline.

## Definition of Done (Plain Language)

At the same time every day, the system wakes up, downloads any new 10-K/10-Q filings published to EDGAR in the last 24 hours, runs the full pipeline on them, and adds the results to the existing processed corpus. No human action is required.

## Acceptance Criteria

### Scenario A: Scheduled job runs and processes new filings
```gherkin
Given a cron job or GitHub Actions workflow scheduled for 02:00 UTC daily
When the scheduler triggers
Then the downloader fetches all 10-K/10-Q filings published to EDGAR in the prior 24 hours
  And the preprocessing pipeline runs on only the new files (ResumeFilter skips already-processed)
  And new JSONL records are appended to the existing corpus
  And a run report is saved to the stamped run directory with the date in its name
```

### Scenario B: No new filings — job exits cleanly
```gherkin
Given the scheduler triggers on a day when EDGAR published no new 10-K/10-Q filings
When the pipeline runs
Then it exits with status 0 and logs: "No new filings since last run. Nothing to process."
  And no empty run directory is created
```

### Scenario C: Failure notification on pipeline error
```gherkin
Given the daily run encounters an unrecoverable error (e.g., EDGAR is unreachable)
When the pipeline exits with a non-zero status code
Then the scheduler logs the failure with: run_date, exit_code, last_error_message
  And an alert is written to a failures.log file (or GitHub Actions job annotation)
  And the next day's scheduled run still proceeds independently
```

### Scenario D: Run is idempotent — re-running does not duplicate records
```gherkin
Given the daily run completed successfully yesterday
When the scheduler triggers again today on the same corpus
Then StateManager's .manifest.json prevents any already-processed files from being re-processed
  And the JSONL corpus contains no duplicate records from the repeated trigger
```

## Technical Notes

- Scheduler options: GitHub Actions `schedule:` cron (simplest for single-contributor project) or Airflow/Dagster (PRD-002 §4.1 open question)
- Downloader: `sec-downloader` already supports date-range queries; wire `--since-date yesterday` into the daily entrypoint
- Idempotency: guaranteed by `ResumeFilter` + `StateManager.manifest.json`
- Failure logging: write to `logs/ingestion_failures.log`; GitHub Actions will surface exit code as job failure
- Existing partial implementation: `docs/ops/DRIFT_DETECTION_GITHUB_ACTIONS.md` covers the CI/CD scaffold; daily ingestion uses the same pattern
- Status: ❌ Not wired — pipeline exists; no scheduler configured
