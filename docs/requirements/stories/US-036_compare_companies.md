---
id: US-036
epic: EP-8
priority: P1
status: Not implemented
source_prd: PRD-005
estimation: M (3–5 days)
---

# US-036: Compare Two Companies

## The Story

As a **Corporate Development Analyst**, I want to run `compare <ticker1> <ticker2>` and receive a
side-by-side risk profile comparison, so that I can identify divergent risk exposures between
two companies before making an acquisition decision.

## Acceptance Criteria

### Scenario: Two valid tickers compared

```gherkin
Given preprocessed segmented JSON exists for both AAPL and MSFT in data/processed/
When I run: python -m src.analysis.cli compare AAPL MSFT
Then the command exits with code 0
And report.json["inputs"]["tickers"] equals ["AAPL", "MSFT"]
And report.json["comparison"]["archetype_diff"] contains entries for all six SASB archetypes
And each archetype entry has "ticker_a_pct" and "ticker_b_pct" float fields
And report.md contains a table with one row per archetype and one column per ticker
```

### Scenario: One ticker missing from run directory

```gherkin
Given AAPL has preprocessed output but "ZZZZ" does not
When I run: python -m src.analysis.cli compare AAPL ZZZZ
Then the command exits with code 1
And stderr contains "FilingNotFoundError" and the string "ZZZZ"
```

### Scenario: Same fiscal year used for both tickers (default)

```gherkin
Given AAPL and MSFT both have fiscal year 2024 filings available
When I run: python -m src.analysis.cli compare AAPL MSFT
Then report.json["inputs"]["fiscal_year"] for both tickers is "2024"
```

## Technical Notes

- **Command:** `python -m src.analysis.cli compare <ticker1> <ticker2> [--year YYYY] [--format md|json|csv]`
- **Orchestration:** `AnalysisOrchestrator._parallel_dispatch()` spawns two `ClassifierAgent` instances (RFC-008 §2.1 Option C)
- **Skill:** `src/analysis/skills/comparator.py` (`diff_risk_profiles`)
- **Output field:** `ComparisonResult` in `src/analysis/models/analysis.py`
- **Resolve before Phase D:** OQ-A05 (same run-dir vs. mixed run-dirs)
