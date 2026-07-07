---
id: US-035
epic: EP-8
priority: P0
status: Not implemented
source_prd: PRD-005
estimation: S (1–2 days)
---

# US-035: Multi-Format Report Export

## The Story

As a **Data Scientist**, I want to export analysis reports as Markdown, JSON, or CSV using the
`--format` flag, so that I can integrate analysis results into downstream tools without manual
format conversion.

## Acceptance Criteria

### Scenario: Default format is Markdown

```gherkin
Given a successful analyze company run for AAPL
When no --format flag is specified
Then the analysis run directory contains a file named report.md
And report.md begins with a level-1 Markdown heading containing the company name and ticker
And report.md contains a section titled "Risk Label Distribution"
And report.md contains a section titled "Risk Clusters"
```

### Scenario: JSON format requested

```gherkin
Given ticker AAPL has preprocessed output available
When I run: python -m src.analysis.cli analyze company AAPL --format json
Then the analysis run directory contains a file named report.json
And report.json is valid JSON parseable by Python json.loads()
And report.json["schema_version"] equals "1.0"
And report.json["summary"]["total_segments"] is an integer
And report.json["clusters"] is a list
```

### Scenario: CSV format requested

```gherkin
Given ticker AAPL has preprocessed output available
When I run: python -m src.analysis.cli analyze company AAPL --format csv
Then the analysis run directory contains a file named report.csv
And report.csv is parseable as a CSV with headers
And the CSV contains columns: ticker, fiscal_year, chunk_id, risk_label, sasb_topic, confidence, text
And the CSV contains one row per analyzed segment
```

### Scenario: Invalid format value rejected

```gherkin
Given any valid ticker
When I run: python -m src.analysis.cli analyze company AAPL --format xlsx
Then the command exits with code 1
And stderr contains the text "invalid choice: xlsx"
And no files are written to data/reports/
```

### Scenario: Output path printed to stdout on success

```gherkin
Given any successful analysis run with any --format
When the command exits with code 0
Then stdout contains the absolute path to the report file written
```

## Technical Notes

- **Skill module:** `src/analysis/skills/reporter.py`
  - `format_report(analysis: AnalysisResult, fmt: str) → str` — renders to string
  - `export_report(content: str, run_dir: Path, fmt: str) → Path` — writes file, returns path
- **Formats supported:** `md`, `json`, `csv` (argparse `choices=["md", "json", "csv"]`)
- **Markdown renderer:** stdlib `str` formatting (no Jinja2 required)
- **JSON serializer:** `AnalysisResult.model_dump_json(indent=2)` (Pydantic V2)
- **CSV writer:** Python stdlib `csv.DictWriter`; one row per segment in `chunks[]`
- **File names:** `report.md`, `report.json`, `report.csv` — always in the analysis run directory
- **stdout print:** `print(str(report_path))` — absolute path; no trailing newline beyond what print adds
