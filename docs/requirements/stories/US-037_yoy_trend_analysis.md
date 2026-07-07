---
id: US-037
epic: EP-8
priority: P1
status: Not implemented
source_prd: PRD-005
estimation: M (3–5 days)
---

# US-037: Year-Over-Year Trend Analysis

## The Story

As a **Risk Manager**, I want to run `trend <ticker> --years N` and see which risk clusters grew,
shrank, or disappeared, so that I can detect emerging or receding risk themes without reading
multiple filings manually.

## Acceptance Criteria

### Scenario: Trend across three fiscal years

```gherkin
Given AAPL has preprocessed segmented JSON for fiscal years 2022, 2023, and 2024
When I run: python -m src.analysis.cli trend AAPL --years 3
Then the command exits with code 0
And report.json["trend"]["year_pairs"] contains entries for (2022→2023) and (2023→2024)
And each year pair entry contains "new_clusters", "removed_clusters", and "shifted_clusters" lists
And each cluster entry has a "similarity_score" float between 0.0 and 1.0
```

### Scenario: Fewer fiscal years available than requested

```gherkin
Given AAPL only has preprocessed output for fiscal years 2023 and 2024
When I run: python -m src.analysis.cli trend AAPL --years 5
Then the command exits with code 0
And stderr contains a warning: "Only 2 fiscal year(s) available for AAPL; analyzing 1 year pair"
And report.json["trend"]["year_pairs"] contains exactly 1 entry (2023→2024)
```

### Scenario: Only one fiscal year available — cannot compute trend

```gherkin
Given AAPL only has preprocessed output for fiscal year 2024
When I run: python -m src.analysis.cli trend AAPL --years 2
Then the command exits with code 1
And stderr contains "Insufficient data: trend requires at least 2 fiscal years"
```

## Technical Notes

- **Command:** `python -m src.analysis.cli trend <ticker> [--years N] [--run-dir <path>] [--format md|json|csv]`
- **Default `--years`:** 3
- **Algorithm:** Sentence-embedding cosine similarity (RFC-008 §2.3 Option B); thresholds: new < 0.70, shifted 0.70–0.85, stable ≥ 0.85
- **Model:** `all-MiniLM-L6-v2` (already in `src/utils/worker_pool.py`)
- **Skill:** `src/analysis/skills/delta_detector.py` (`detect_yoy_delta`)
- **Output field:** `YoYDelta` in `src/analysis/models/analysis.py`
- **Orchestration:** Sequential (tool-use loop per year pair); not parallel (OQ-A05 resolved as sequential for trend)
