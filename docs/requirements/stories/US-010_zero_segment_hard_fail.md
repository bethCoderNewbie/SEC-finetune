---
id: US-010
epic: EP-2 Resilience & Recovery
priority: P0
status: Not implemented — targeted by PRD-003 Phase 1
source_prd: PRD-003
estimation: 1 point
---

# US-010: Zero-Segment Filing Produces Hard FAIL

## The Story

> **As an** `ML Engineer`,
> **I want** a filing that produces zero segments to fail QA validation with a blocking FAIL status,
> **So that** silent empty training examples are never written to the output corpus.

## Acceptance Criteria

### Scenario A: Zero-segment output triggers blocking FAIL
```gherkin
Given a filing that is parsed and extracted without error
  But the segmenter produces total_segments == 0
When HealthCheckValidator runs on the result
Then it returns ValidationResult(check_name="segment_count", status=FAIL, is_blocking=True)
  And the overall QA status is FAIL (not PASS)
  And the filing is not written to the output directory — it is routed to the DLQ
```

### Scenario B: Zero-segment FAIL appears in run report
```gherkin
Given a batch in which one filing produced zero segments
When the run completes
Then RUN_REPORT.md lists that filing under "QA Failures" with reason: "Zero segments produced — extraction failed"
  And the batch summary shows qa_fail_count >= 1
```

### Scenario C: Non-empty filings are unaffected
```gherkin
Given a filing that produces total_segments == 47
When HealthCheckValidator runs
Then it does not trigger the zero-segment check
  And validation proceeds normally through all other checks
```

## Technical Notes

- Fix target: `src/config/qa_validation.py:787-788`
- Both `_check_cleanliness` and `_check_substance` must be updated
- Root cause: empty-list early-return allowed `determine_overall_status([])` to return PASS
- See PRD-003 §4.1 for exact code change
- Test: `tests/test_qa_validation.py` — `total_segments=0` → `FAIL`
