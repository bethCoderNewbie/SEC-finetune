---
id: US-013
epic: EP-6 ML Readiness
priority: P1
status: Not implemented
source_prd: PRD-003
estimation: 2 points
---

# US-013: Class Balance Report After Batch Run

## The Story

> **As a** `Data Scientist`,
> **I want** a label distribution report generated after every batch run,
> **So that** I can identify class imbalances before training and plan oversampling or undersampling strategies rather than discovering skew after a failed training run.

## Acceptance Criteria

### Scenario A: Label distribution report in the run directory
```gherkin
Given a batch run that produced N JSONL records with risk_label populated
When the run completes
Then batch_summary_{run_id}.json contains a label_distribution key
  And label_distribution maps each of the 12 taxonomy classes to: count (int), pct (float), is_minority (bool)
  And is_minority is true when pct < 5.0 (configurable threshold)
```

### Scenario B: Imbalance warning in RUN_REPORT.md
```gherkin
Given a corpus where the "Environmental" class contains fewer than 2% of all segments
When RUN_REPORT.md is generated
Then it includes a "⚠️ Class Imbalance Warning" section
  And it lists each minority class with its count and percentage
  And it recommends: "Consider oversampling minority classes or adjusting the train/val/test split weights before fine-tuning."
```

### Scenario C: Unlabeled corpus (classifier not yet integrated)
```gherkin
Given a batch run where risk_label is null on all records (classifier not wired in)
When the run completes
Then batch_summary_{run_id}.json contains label_distribution: null
  And RUN_REPORT.md notes: "Label distribution unavailable — classifier not integrated (see US-001)"
  And no warning or error is raised
```

### Scenario D: Report is machine-readable for downstream tools
```gherkin
Given the batch_summary_{run_id}.json
When I load it in Python with json.load()
Then label_distribution is a dict keyed by class name (str) with numeric values
  And it is directly consumable by pandas for plotting: pd.DataFrame(label_distribution).T.plot(kind="bar")
```

## Technical Notes

- Computed in `MarkdownReportGenerator` (`src/utils/reporting.py`) from the final JSONL output
- Taxonomy classes: the 12 defined in `configs/features/risk_analysis.yaml`
- Minority threshold: configurable in `configs/config.yaml` under `reporting.minority_class_threshold` (default: 5.0%)
- Requires `risk_label` to be populated (depends on US-001 JSONL + classifier integration from PRD-002 §11 item 2)
- Status: ❌ Not implemented
