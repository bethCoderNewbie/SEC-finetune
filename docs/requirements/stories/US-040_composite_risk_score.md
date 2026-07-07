---
id: US-040
epic: EP-8
priority: P1
status: Not implemented
source_prd: PRD-005
estimation: S (1–2 days)
---

# US-040: Composite Risk Score

## The Story

As a **Portfolio Manager**, I want a composite risk score (1–100) per company in the analysis
report, so that I can triage a watchlist of companies in minutes without reading full reports.

## Acceptance Criteria

### Scenario: Risk score present in analyze company output

```gherkin
Given a successful analyze company run for AAPL
When report.json is read
Then report.json["summary"]["composite_risk_score"] is an integer between 1 and 100 inclusive
```

### Scenario: Higher score for filing with more high-confidence, high-concentration risks

```gherkin
Given filing A with 80% of segments labeled "governance" or "business_model" at confidence > 0.80
And filing B with 50% of segments labeled "other" at confidence < 0.50
When composite_risk_score is computed for both filings
Then filing A's composite_risk_score is greater than filing B's composite_risk_score
```

### Scenario: Score appears in Markdown report

```gherkin
Given a successful analyze company run for any ticker
When report.md is read
Then report.md contains the text "Composite Risk Score:" followed by an integer
```

### Scenario: Score present in CSV export

```gherkin
Given a successful analyze company run with --format csv
When report.csv is read
Then the CSV header row contains a column named "composite_risk_score"
And every data row has the same integer value in that column (filing-level, not segment-level)
```

## Technical Notes

- **Skill module:** `src/analysis/skills/scorer.py` (`score_risk`)
- **Formula (initial):** `round(100 * weighted_avg)` where weights = segment confidence scores;
  frequency weights by archetype concentration (archetypes with ≥ 20% share contribute more).
  Formula to be finalized when OQ-A02 is resolved (before Phase D).
- **Output field:** `RiskScore` model with `score: int` (1–100), `breakdown: dict[str, float]` (per-archetype weighted contribution)
- **Deterministic:** given identical segment inputs and confidence scores, score is always identical (`RANDOM_SEED=42` not applicable here; no randomness)
- **Resolve before Phase D:** OQ-A02 (scoring formula)
