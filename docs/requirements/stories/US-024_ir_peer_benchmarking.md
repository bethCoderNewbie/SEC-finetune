---
id: US-024
epic: EP-7
priority: P1
status: not_started
source_prd: PRD-004
estimation: 2d
---

## The Story

As an **IR Manager**, I want to benchmark our risk disclosure language against a peer-group
cohort filtered by SIC code, so that I can anticipate analyst questions about risk
concentration before earnings calls.

---

## Acceptance Criteria

### Scenario: Peer-group query returns cohort frequency table

```gherkin
Given a labelled corpus containing filings for at least 5 companies with SIC code 6022
When the user runs:
  python -m sec_intel query --peer-group SIC:6022 --run-dir <run_dir> --output json
Then the command exits with code 0
  And the JSON output contains a top-level key "cohort_summary"
  And cohort_summary contains each risk_category with a count of segments across all cohort companies
  And cohort_summary is sorted by count descending
```

### Scenario: Own-company segments appear alongside peer context

```gherkin
Given a labelled corpus containing a filing for "Our Bank" (CIK 0009999999) with SIC 6022
  And the corpus contains at least 4 other SIC 6022 filings
When the user runs:
  python -m sec_intel query --ciks 0009999999 --peer-group SIC:6022 --run-dir <run_dir>
Then results[0].cik equals "0009999999"
  And the output also contains cohort_summary covering all SIC 6022 companies including ours
```

### Scenario: SIC code with no filings in corpus returns a structured error

```gherkin
Given a corpus that contains no filings with SIC code 9999
When the user runs:
  python -m sec_intel query --peer-group SIC:9999 --run-dir <run_dir>
Then the command exits with code 1
  And stderr contains: "No filings found for peer-group SIC:9999"
```

---

## Technical Notes

- **CLI flag:** `--peer-group SIC:<code>` implemented in `src/cli/query.py` (PRD-004 Phase 4)
- **SIC code source:** SIC code must be present in `SegmentedRisks.metadata`; currently not stored — adding it is a Phase 1 schema extension
- **cohort_summary shape:** `{"cybersecurity": 142, "regulatory": 98, "financial": 75, ...}` — counts across all companies in the cohort
- **Current status:** Blocked on PRD-004 Phase 2 (classifier) and Phase 4 (peer-group filter); also blocked on SIC code being added to filing metadata
