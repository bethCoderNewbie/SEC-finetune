---
id: US-033
epic: EP-8
priority: P0
status: Not implemented
source_prd: PRD-005
estimation: M (3–5 days)
---

# US-033: Analyze Company Command

## The Story

As a **Financial Analyst**, I want to run `python -m src.analysis.cli analyze company <ticker>`
and receive a structured risk report, so that I can analyze a company's risk posture without
writing custom Python code.

## Acceptance Criteria

### Scenario: Happy path — ticker with preprocessed output exists

```gherkin
Given a stamped preprocessing run directory exists under data/processed/
And the run directory contains a file matching <ticker>_*_part1item1a_segmented.json
When I run: python -m src.analysis.cli analyze company AAPL
Then the command exits with code 0
And a new analysis run directory is created at data/reports/{YYYYMMDD_HHMMSS}_analysis_{git_sha}/
And the run directory contains a file named report.md
And the run directory contains a file named report.json
And report.json validates against the AnalysisResult Pydantic schema
And report.json["inputs"]["ticker"] equals "AAPL"
And report.json["summary"]["total_segments"] is an integer greater than 0
And report.json["summary"]["risk_label_distribution"] contains all six SASB archetypes as keys
```

### Scenario: Ticker not found in any run directory

```gherkin
Given no preprocessed segmented JSON file exists for ticker "ZZZZ"
When I run: python -m src.analysis.cli analyze company ZZZZ
Then the command exits with code 1
And stderr contains the text "FilingNotFoundError"
And no files are written to data/reports/
```

### Scenario: Explicit run directory specified

```gherkin
Given a stamped run directory RUN_DIR contains MSFT_*_part1item1a_segmented.json
When I run: python -m src.analysis.cli analyze company MSFT --run-dir RUN_DIR
Then the command exits with code 0
And report.json["inputs"]["run_dir"] equals RUN_DIR
```

### Scenario: Specific fiscal year requested

```gherkin
Given multiple AAPL segmented files exist across fiscal years 2022, 2023, 2024
When I run: python -m src.analysis.cli analyze company AAPL --year 2023
Then the command exits with code 0
And report.json["inputs"]["fiscal_year"] equals "2023"
And the segments analyzed come from the 2023 filing only
```

## Technical Notes

- **CLI module:** `src/analysis/cli.py` (new)
- **Orchestrator:** `src/analysis/orchestrator.py` (`AnalysisOrchestrator._tool_loop()`)
- **Filing lookup:** `src/analysis/skills/filing_loader.py` (`load_filing`)
- **Output schema:** `src/analysis/models/analysis.py` (`AnalysisResult`)
- **Run directory convention:** ADR-007 applied to `data/reports/`
- **Exit codes:** 0 = success, 1 = user input error (ticker not found, invalid args), 2 = skill/agent failure
- **Default `--year`:** most recent `fiscal_year` field found in available segmented files for the ticker
- **Default `--run-dir`:** latest stamped directory in `data/processed/` (by directory name sort descending)
