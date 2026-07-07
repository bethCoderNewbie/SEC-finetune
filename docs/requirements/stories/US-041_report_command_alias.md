---
id: US-041
epic: EP-8
priority: P2
status: Not implemented
source_prd: PRD-005
estimation: S (1–2 days)
---

# US-041: `report` Command Alias

## The Story

As a **Financial Analyst**, I want to run `report <ticker>` as a shorthand alias for
`analyze company <ticker> --format md`, so that I can generate a Markdown risk report with a
minimal command without remembering the full `analyze company` subcommand syntax.

## Acceptance Criteria

### Scenario: report command produces identical output to analyze company

```gherkin
Given a preprocessed run directory containing AAPL 10-K segments
When I run: python -m src.analysis.cli report AAPL
Then the command exits 0
And the output path printed to stdout points to a report.md file in a stamped data/reports/ directory
And the contents of report.md are identical to those produced by: python -m src.analysis.cli analyze company AAPL --format md
```

### Scenario: report command respects --format flag

```gherkin
Given a preprocessed run directory containing AAPL 10-K segments
When I run: python -m src.analysis.cli report AAPL --format json
Then report.json is written (not report.md)
And the file contents validate against the AnalysisResult Pydantic schema
```

### Scenario: report command passes --year and --run-dir through

```gherkin
Given a preprocessed run directory containing AAPL 2023 segments
When I run: python -m src.analysis.cli report AAPL --year 2023 --run-dir <path>
Then the command resolves to the 2023 filing in the specified run directory
And report.json["inputs"]["fiscal_year"] equals "2023"
```

## Technical Notes

- **Implementation:** `report` is a thin dispatch alias in `src/analysis/cli.py` that calls the
  same `analyze_company()` handler as `analyze company`. No separate agent or skill needed.
- **Phase:** Phase F (F-5 in PRD-005 §6).
- **Priority:** P2 — Phase F item; depends on Phase A–E being complete.
- **Depends on:** US-033 (analyze company command, Phase A).
- **CLI module:** `src/analysis/cli.py`
