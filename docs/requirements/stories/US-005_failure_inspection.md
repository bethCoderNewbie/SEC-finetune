---
id: US-005
epic: EP-5 Observability
priority: P1
status: Partially Implemented
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
**Status (run `20260223_182806`):** ⚠️ Partially met. RUN_REPORT.md lists failed filings and
total_failed count. Failure reason is always `"unknown"` — no stage breakdown
(parse/extract/clean/segment) or exception class is surfaced. `_progress.log` carries the
actual reason ("No sections extracted from filing") but RUN_REPORT.md does not include it.
Gap: `MarkdownReportGenerator` must propagate the DLQ error message and originating stage into
the report.

### Scenario B: DLQ log is human-readable
```gherkin
Given a Dead Letter Queue with 5 entries
When I read the DLQ log file
Then each entry includes: filename, timestamp, exception_type, message, retry_count
  And entries are readable as plain text (not binary)
```
**Status (run `20260223_182806`):** ❌ Not met. No standalone DLQ log file is written to the
run directory. Failure detail is spread across `_progress.log` (human-readable warnings) and
`batch_summary_{run_id}.json` (machine-readable results list). A dedicated DLQ log file with
the specified fields does not exist.

### Scenario C: Progress log captures per-file elapsed time
```gherkin
Given a batch run that processed 50 filings
When I read _progress.log
Then each line contains: filename, processing stage, elapsed_seconds, status (ok | fail | timeout)
  And the log is written incrementally (visible before the run ends)
```
**Status (run `20260223_182806`):** ✅ Substantially met. `_progress.log` is written
incrementally. Format per line:
- Success: `[timestamp] [N/959] OK: {file} -> {segs} segs, {elapsed}s, SIC={code}`
- Warning: `[timestamp] WARNING: [N/959] WARN: {file} - {reason}`

Gap: processing stage (parse/extract/clean/segment) is not explicit in the log line.

### Scenario D: Parse success rate ≥95% on stratified sample
```gherkin
Given a stratified random sample of ≥30 filings spanning ≥5 SIC sectors and filing years 2019–2024
When the pipeline processes the full sample
Then (total_submitted − dlq_size) / total_submitted ≥ 0.95
  And the success rate is present in RUN_REPORT.md under a "Parse Success Rate" heading
  And the success rate is present in batch_summary_{run_id}.json as a numeric field
```
**Status (run `20260223_182806`, 2026-02-23):** ❌ KPI not met.

| Metric | Value | Spec | Pass? |
|--------|-------|------|-------|
| Total filings | 959 | ≥ 30 | ✅ |
| Distinct SIC codes | 88 | ≥ 5 sectors | ✅ |
| success + warning | 861 | — | — |
| Parse success rate | (816+45)/959 = **89.8%** | ≥ 95% | ❌ |
| DLQ (error status) | 98 | — | — |
| Quarantined (warning) | 45 | — | — |

Root cause: 98+ filings fail with "No sections extracted from filing" (Stage 2:
`SECSectionExtractor`) — concentrated in CAH (Cardinal Health), COP (ConocoPhillips),
and C (Citigroup) ticker clusters across years 2021–2025. These filings parse successfully
(Stage 1) but yield zero sections at extraction (Stage 2). The `error` reason recorded in
`batch_summary` is `"unknown"` — exception type and message are not propagated.

Additional gaps for the `Then` clauses:
- RUN_REPORT.md does not have a "Parse Success Rate" heading (shows "85.1% Success Rate" in
  executive summary prose).
- `batch_summary_{run_id}.json` has no `parse_success_rate` numeric field; rate must be
  computed from `successful`, `warnings`, `failed`, `total_files`.

## Technical Notes

- Run report: `MarkdownReportGenerator` → `data/processed/{run_dir}/RUN_REPORT.md`
- Progress log: `ProgressLogger` → `data/processed/{run_dir}/_progress.log`
- DLQ: `DeadLetterQueue` — no standalone log file written; detail in `batch_summary` results list
- Latest measured run: `20260223_182806` (959 filings, git SHA `3ef72af`)
- Failure root cause: `SECSectionExtractor` returns zero sections for CAH/COP/C filings —
  investigate SGML/HTML structure of these filers before next run
- Open items to close this story:
  1. Propagate exception type + originating stage into RUN_REPORT.md per-filing failure table
  2. Write a standalone DLQ log file (plaintext, one entry per failure) to the run directory
  3. Add `parse_success_rate` as a named numeric field in `batch_summary_{run_id}.json`
  4. Add "Parse Success Rate" heading to RUN_REPORT.md template
  5. Fix zero-section extraction for CAH/COP/C to push rate above 95%
