---
id: US-025
epic: EP-7
priority: P1
status: not_started
source_prd: PRD-004
estimation: 1d
---

## The Story

As an **Account Executive**, I want to extract the top stated challenges from a prospect's
most recent 10-K, so that I can tailor my sales pitch directly to the leadership team's
publicly disclosed pain points.

---

## Acceptance Criteria

### Scenario: Top-N segments by confidence for a single company

```gherkin
Given a labelled corpus containing a 10-K for prospect CIK "0005678901"
When the user runs:
  python -m sec_intel query --ciks 0005678901 --limit 5 --run-dir <run_dir> --output json
Then the command exits with code 0
  And results[0].risk_segments contains exactly 5 segments
  And the segments are ordered by confidence descending
  And each segment has a non-empty risk_category
  And each segment has a non-empty text field
```

### Scenario: Most recent filing is used when multiple years are present

```gherkin
Given a corpus containing 10-K filings for CIK "0005678901" for years 2022, 2023, and 2024
When the user runs:
  python -m sec_intel query --ciks 0005678901 --limit 3 --run-dir <run_dir>
Then results[0].filing_date is the most recent filing date available for that CIK
  And segments from the 2022 or 2023 filings do not appear in the output
```

### Scenario: --limit flag limits total segments, not per category

```gherkin
Given a labelled corpus with a filing that has 50 classified segments
When the user passes --limit 3
Then the output contains exactly 3 segments total (not 3 per category)
  And the 3 segments have the highest confidence scores in the entire filing
```

---

## Technical Notes

- **CLI flag:** `--limit N` implemented in `src/cli/query.py` (PRD-004 Phase 3)
- **Most-recent logic:** When multiple filing years are present for a CIK, select the one with the latest `filing_date` in `SegmentedRisks.filing_date`
- **Sort key:** `confidence DESC` across all categories before applying `LIMIT`
- **Use case note:** Sales users need short, high-confidence, category-labelled excerpts — not full risk dumps. The `--limit` flag is the primary control.
- **Current status:** Blocked on PRD-004 Phase 2 (classifier) and Phase 3 (query CLI)
