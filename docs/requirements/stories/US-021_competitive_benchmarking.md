---
id: US-021
epic: EP-7
priority: P0
status: not_started
source_prd: PRD-004
estimation: 3d
---

## The Story

As a **Strategic Analyst**, I want to query competitor 10-K risk factors by category in a
single CLI command, so that I can benchmark our disclosed risk posture against peers without
reading 300-page filings.

---

## Acceptance Criteria

### Scenario: Single-competitor risk profile by category

```gherkin
Given a labelled corpus containing at least one processed 10-K for ticker "MSFT"
  And the corpus index is available at the path specified by --run-dir
When the user runs:
  python -m sec_intel query --ciks 0000789019 --category cybersecurity --run-dir <run_dir> --output json
Then the command exits with code 0
  And stdout contains a JSON object with key "results"
  And results[0].company_name equals "MICROSOFT CORPORATION"
  And every segment in results[0].risk_segments has risk_category == "cybersecurity"
  And every segment has a confidence field with value between 0.0 and 1.0
```

### Scenario: Multi-company comparison returns one entry per company

```gherkin
Given a labelled corpus containing 10-K filings for both "AAPL" (CIK 0000320193) and "MSFT" (CIK 0000789019)
When the user runs:
  python -m sec_intel query --ciks 0000320193,0000789019 --category regulatory --run-dir <run_dir> --output json
Then the command exits with code 0
  And "results" contains exactly 2 entries
  And each entry has a distinct cik value
  And each entry lists only segments where risk_category == "regulatory"
```

### Scenario: Query latency is within bound

```gherkin
Given a labelled corpus of 309 filings
When the user runs a category query across 5 CIKs
Then the command completes in under 5 seconds (wall clock)
```

---

## Technical Notes

- **CLI entrypoint:** `src/cli/query.py` (to be created in PRD-004 Phase 3)
- **Classifier:** `src/inference/classifier.py` produces `risk_category` + `confidence` per segment
- **Input:** `SegmentedRisks` JSON files in `--run-dir`, pre-labelled by the classifier
- **CIK lookup:** CIK is stored in `SegmentedRisks.cik` and `SegmentedRisks.company_name`
- **Current status:** Blocked on PRD-004 Phase 2 (classifier); corpus has no category labels
