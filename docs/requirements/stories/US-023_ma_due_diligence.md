---
id: US-023
epic: EP-7
priority: P0
status: not_started
source_prd: PRD-004
estimation: 3d
---

## The Story

As a **Corporate Development Analyst**, I want a side-by-side risk category comparison of
acquisition targets exported to CSV, so that I can identify material liabilities and risk
concentrations before issuing a letter of intent.

---

## Acceptance Criteria

### Scenario: Side-by-side CSV export for two acquisition targets

```gherkin
Given a labelled corpus containing 10-K filings for two candidate CIKs: "0001111111" and "0002222222"
When the user runs:
  python -m sec_intel query --ciks 0001111111,0002222222 --run-dir <run_dir> --output csv > targets.csv
Then the command exits with code 0
  And targets.csv contains a header row with columns: company, cik, filing_date, category, confidence, text, citation_url
  And rows from both companies are present in the file
  And every row has a non-empty category value drawn from the standard taxonomy
```

### Scenario: CSV rows are sorted by company then confidence descending

```gherkin
Given targets.csv produced by the query above
When the analyst opens the file in Excel
Then rows are ordered by cik (ascending) then by confidence (descending) within each company
```

### Scenario: High-confidence regulatory segments are identifiable

```gherkin
Given targets.csv for two acquisition candidates
When the analyst filters to category == "regulatory" and confidence >= 0.80
Then at least one row is returned for any target that has regulatory risk segments
  And the text field contains the verbatim segment text (not truncated)
  And citation_url is present and begins with "https://www.sec.gov/"
```

---

## Technical Notes

- **CLI flag:** `--output csv` routes to `src/cli/export.py` (PRD-004 Phase 3)
- **Sort order:** Implemented in `export.py`; sort key `(cik, -confidence)`
- **Citation URL:** Required for this use case — M&A teams need to verify original filing language; `citation_url` must be non-null for all exported segments
- **Current status:** Blocked on PRD-004 Phase 2 (classifier) and Phase 3 (CSV exporter)
- **Connection to US-018:** Source traceability (US-018) and citation builder overlap; see PRD-004 Q-05
