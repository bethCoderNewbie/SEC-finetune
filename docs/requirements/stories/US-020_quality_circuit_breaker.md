---
id: US-020
epic: EP-2 Resilience & Recovery
priority: P0
status: Partial — per-filing QA checks exist; batch-level circuit breaker not implemented
source_prd: PRD-003
estimation: 2 points
dod: The system automatically halts the run and raises an alert if more than 5% of processed files fail quality checks.
---

# US-020: Quality Circuit Breaker (5% Batch Failure Threshold)

## The Story

> **As a** `Quality Owner`,
> **I want** the system to automatically stop processing and alert me if more than 5% of the data looks wrong,
> **So that** we don't accidentally train a model on a "garbage" corpus that corrupts all downstream reports and predictions.

## Definition of Done (Plain Language)

If 1 in 20 processed files fails its quality check (e.g., zero segments, ToC contamination, empty text), the pipeline stops immediately, writes a clear error to the run report, and does **not** write any more output files. The operator must investigate before restarting.

## Acceptance Criteria

### Scenario A: Circuit breaker trips at configured failure threshold
```gherkin
Given a batch of 200 filings and a qa_failure_threshold: 0.05 (5%) in configs/config.yaml
  And 11 filings have failed QA validation (5.5% failure rate)
When the pipeline processes the 11th failed filing
Then it immediately halts further processing (no more filings are dispatched to workers)
  And RUN_REPORT.md contains a "🚨 CIRCUIT BREAKER TRIPPED" section with: files_processed, files_failed, failure_rate_pct, threshold_pct
  And the pipeline exits with a non-zero status code (distinct from a per-filing DLQ failure)
  And no output files written after the threshold was crossed are committed to the run directory
```

### Scenario B: Failure rate below threshold — run continues normally
```gherkin
Given a batch of 200 filings and qa_failure_threshold: 0.05
  And only 9 filings have failed QA (4.5% failure rate)
When the 9th failed filing is processed
Then the pipeline continues processing the remaining filings
  And RUN_REPORT.md notes the failure rate without raising a circuit breaker alert
```

### Scenario C: Threshold is configurable and documented
```gherkin
Given qa_failure_threshold: 0.10 is set in configs/config.yaml
When the pipeline runs
Then the circuit breaker trips only at 10% failure rate, not 5%
  And the threshold value is recorded in batch_summary_{run_id}.json as qa_failure_threshold: 0.10
```

### Scenario D: Circuit breaker state is distinguishable from normal completion
```gherkin
Given the circuit breaker tripped at filing 110 of 200
When I examine the run outputs
Then the exit code is 2 (reserved for circuit-breaker halt, distinct from exit code 1 for general error)
  And the run directory contains a CIRCUIT_BREAKER_HALT.flag file (presence indicates abnormal stop)
  And any automated downstream step (e.g. model training) that checks for this flag will abort
```

## Technical Notes

- Distinct from US-010 (zero-segment per-filing FAIL): US-010 catches individual bad files; this story catches a **systemic** quality problem across the batch
- Implementation: counter in `ParallelProcessor` or `MarkdownReportGenerator` — check `qa_fail_count / files_processed` after each filing completes
- Config key: `qa_validation.batch_failure_threshold` (float, default: 0.05)
- Exit code convention: 0 = success, 1 = partial failure (DLQ entries), 2 = circuit breaker tripped
- CIRCUIT_BREAKER_HALT.flag: empty file written to run directory root; consumed by downstream automation
- Current state: `HealthCheckValidator` per-filing checks exist; no batch-level accumulator or halt logic
- Status: ⚠️ Partial — per-filing QA checks exist; batch-level circuit breaker not implemented
