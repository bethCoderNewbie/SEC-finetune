---
id: US-027
epic: EP-7
priority: P1
status: not_started
source_prd: PRD-004
estimation: 2d
---

## The Story

As a **Portfolio Manager**, I want a composite risk prioritization score (1–100) for every
company in my watchlist, so that I can triage 50 companies in minutes rather than manually
reading each filing.

---

## Acceptance Criteria

### Scenario: Prioritization score is present in every filing result

```gherkin
Given a labelled corpus with filings for CIKs "0000320193" and "0000789019"
When the user runs:
  python -m sec_intel query --ciks 0000320193,0000789019 --run-dir <run_dir> --output json
Then results[0].analytics.prioritization_score is an integer between 1 and 100
  And results[1].analytics.prioritization_score is an integer between 1 and 100
```

### Scenario: High-risk filing scores higher than low-risk filing

```gherkin
Given a labelled corpus containing:
  - "HighRiskCo" with 30 segments, average confidence 0.92, majority in cybersecurity (severity_weight 1.4)
  - "LowRiskCo" with 5 segments, average confidence 0.65, majority in macro (severity_weight 0.8)
When the user queries both companies
Then HighRiskCo.analytics.prioritization_score > LowRiskCo.analytics.prioritization_score
```

### Scenario: Score >= 70 is visually flagged in CLI output

```gherkin
Given a filing whose computed prioritization_score is 75
When the user runs the query with --output json
Then results[*].analytics.prioritization_score equals 75
  And when run without --output (default text mode), the company name is prefixed with "[ELEVATED]" in stdout
```

### Scenario: Score formula is configurable, not hardcoded

```gherkin
Given configs/risk_taxonomy.yaml with cybersecurity.severity_weight changed from 1.4 to 2.0
When the user re-runs the query for the same corpus
Then HighRiskCo.analytics.prioritization_score increases relative to the prior run
  And no source code change is required
```

---

## Technical Notes

- **Scorer:** `src/inference/scorer.py` (PRD-004 Phase 6); formula: `score = clip(sum(severity_weight[cat] × segment_count[cat] × mean_confidence[cat]) × normalization_factor, 1, 100)`
- **Severity weights:** Defined in `configs/risk_taxonomy.yaml` under each category's `severity_weight` key; default weights documented in `docs/architecture/data_dictionary.md`
- **Normalization factor:** Calibrated so that a filing with 20 segments at confidence 0.80 in a weight-1.0 category scores approximately 50; see PRD-004 Q-07
- **CLI text mode flag:** Score ≥ 70 triggers `[ELEVATED]` prefix in stdout; score < 70 has no prefix
- **Current status:** Blocked on PRD-004 Phase 6 (scorer); Phase 2 (classifier) must complete first to populate confidence values
