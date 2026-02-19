---
id: US-022
epic: EP-7
priority: P1
status: not_started
source_prd: PRD-004
estimation: 2d
---

## The Story

As a **Risk Manager**, I want to query a public supplier's or partner's 10-K for financial
and operational risk signals by category, so that I can update our vendor risk register
with audited, structured data before contract renewal.

---

## Acceptance Criteria

### Scenario: Supplier risk summary across all categories

```gherkin
Given a labelled corpus containing a 10-K for supplier CIK "0001234567"
When the user runs:
  python -m sec_intel query --ciks 0001234567 --run-dir <run_dir> --output json
Then the command exits with code 0
  And the result for CIK 0001234567 contains risk_segments grouped by risk_category
  And each segment has a confidence value
  And each segment has a citation_url field (may be null if accession number is unavailable)
```

### Scenario: Filter to financial and supply-chain risk only

```gherkin
Given a labelled corpus containing a 10-K for supplier CIK "0001234567"
When the user runs:
  python -m sec_intel query --ciks 0001234567 --category financial --run-dir <run_dir>
Then every returned segment has risk_category == "financial"
  And segments with risk_category == "supply_chain" are absent from the output
```

### Scenario: Missing CIK returns a structured error, not a stack trace

```gherkin
Given a labelled corpus that does not contain any filing for CIK "0000000001"
When the user runs:
  python -m sec_intel query --ciks 0000000001 --run-dir <run_dir> --output json
Then the command exits with code 1
  And stderr contains the message: "No filings found for CIK 0000000001"
  And stdout is empty
```

---

## Technical Notes

- **CLI entrypoint:** `src/cli/query.py` (PRD-004 Phase 3)
- **CIK source:** Risk Manager obtains CIK from EDGAR company search; no ticker-to-CIK resolution is in scope for v0.4.0
- **Citation URL:** `src/inference/citation.py` constructs the EDGAR viewer URL (PRD-004 Q-02 is unresolved — implement with direct filing URL first)
- **Current status:** Blocked on PRD-004 Phase 2 (classifier)
