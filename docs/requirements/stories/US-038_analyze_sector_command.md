---
id: US-038
epic: EP-8
priority: P1
status: Not implemented
source_prd: PRD-005
estimation: M (3–5 days)
---

# US-038: Analyze Sector Command

## The Story

As a **Strategic Analyst**, I want to run `analyze sector <sic>` and receive aggregated risk
themes across all preprocessed filings in that SIC cohort, so that I can benchmark a single
company's risk profile against its industry peers.

## Acceptance Criteria

### Scenario: Sector with multiple filings

```gherkin
Given at least 5 preprocessed segmented JSON files exist for SIC code "3571"
When I run: python -m src.analysis.cli analyze sector 3571
Then the command exits with code 0
And report.json["inputs"]["sic_code"] equals "3571"
And report.json["sector"]["filing_count"] equals the number of distinct tickers found
And report.json["sector"]["archetype_distribution"] contains all six SASB archetypes
And report.json["sector"]["top_risk_themes"] is a list of at least 3 strings
```

### Scenario: Sector with fewer than minimum filings

```gherkin
Given only 2 preprocessed segmented JSON files exist for SIC code "1234"
When I run: python -m src.analysis.cli analyze sector 1234
Then the command exits with code 0
And stderr contains a warning: "Only 2 filing(s) found for SIC 1234; results may not be representative"
And report.json is still written
```

### Scenario: No filings found for SIC code

```gherkin
Given no preprocessed segmented JSON files exist for SIC code "9999"
When I run: python -m src.analysis.cli analyze sector 9999
Then the command exits with code 1
And stderr contains "No preprocessed filings found for SIC code 9999"
```

## Technical Notes

- **Command:** `python -m src.analysis.cli analyze sector <sic> [--year YYYY] [--run-dir <path>] [--format md|json|csv]`
- **Minimum filing threshold:** 5 (warn if fewer; OQ-A03); still executes and writes report
- **SIC lookup:** scan `--run-dir` for files matching `*_segmented.json` and filter by `document_info.sic_code`
- **Orchestration:** `AnalysisOrchestrator._parallel_dispatch()` spawns one `ClassifierAgent` per filing (RFC-008 §2.1 Option C)
- **Skill:** `src/analysis/skills/comparator.py` (`aggregate_sector`)
- **Output field:** `SectorProfile` in `src/analysis/models/analysis.py`
- **Resolve before Phase D:** OQ-A03 (minimum filing count)
