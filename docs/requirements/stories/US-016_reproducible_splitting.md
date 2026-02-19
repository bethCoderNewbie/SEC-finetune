---
id: US-016
epic: EP-6 ML Readiness
priority: P1
status: Not implemented
source_prd: PRD-003
estimation: 3 points
---

# US-016: Deterministic Train/Val/Test Split by Company Group

## The Story

> **As a** `Data Scientist`,
> **I want** a deterministic train/val/test split utility that groups all segments from the same company into the same split,
> **So that** the model never sees risk language from a company in training that it will be evaluated on in the test set — preventing data leakage and over-optimistic evaluation metrics.

## Why Company-Grouped Splitting Matters

A naive random split distributes AAPL 2020 segments into train and AAPL 2021 segments into test. Because the same company copies boilerplate language year-over-year, a model that memorises AAPL's writing style will appear to generalise when it is actually leaking. Grouping by `cik` (company identifier) ensures the split boundary is at the company level, not the segment level.

## Acceptance Criteria

### Scenario A: All segments for a company land in exactly one split
```gherkin
Given a corpus of segments from 500 distinct companies (keyed by cik)
  And split ratios train=0.70, val=0.15, test=0.15 are configured
When the split utility runs
Then every segment where cik == "0000320193" (AAPL) is in the same split (train OR val OR test — never mixed)
  And this holds for all 500 companies in the corpus
```

### Scenario B: Split is deterministic given the same RANDOM_SEED
```gherkin
Given RANDOM_SEED=42 is set in the environment
  And the split utility runs twice on the same corpus
When I compare the two split manifests
Then the set of cik values in each split is identical across both runs
  And adding a new company to the corpus does not reshuffle existing company assignments
```

### Scenario C: Split output files are JSONL-compatible
```gherkin
Given the split utility completes
When I inspect the output directory
Then it contains: train.jsonl, val.jsonl, test.jsonl
  And each file is a valid JSONL file readable by datasets.load_dataset("json", ...)
  And each record contains a split field: "train" | "val" | "test"
```

### Scenario D: Split sizes respect configured ratios within tolerance
```gherkin
Given train=0.70, val=0.15, test=0.15 and a corpus of 500 companies
When the split completes
Then the actual company-count ratio is within ±3% of the configured ratio for each split
  And the shortfall is documented in a splits_manifest.json alongside the split ratios, company counts per split, and segment counts per split
```

### Scenario E: Minority classes are not lost to the test set
```gherkin
Given a corpus where the "Environmental" risk class has only 40 segments across 3 companies
When the split runs
Then at least 1 of those 3 companies (and its Environmental segments) is in the training split
  And splits_manifest.json includes a per-class segment distribution per split
```

## Technical Notes

- Group key: `cik` (not `ticker` — CIK is the canonical EDGAR company identifier and never changes)
- Splitting algorithm: `GroupShuffleSplit` from `sklearn.model_selection` (groups=cik values) with `random_state=RANDOM_SEED`
- Output: `data/processed/{run_dir}/splits/train.jsonl`, `val.jsonl`, `test.jsonl`, `splits_manifest.json`
- `splits_manifest.json` must record: `random_seed`, `ratios`, `company_counts`, `segment_counts`, `label_distribution_per_split`
- Scenario E requires post-split validation: if any class has 0 segments in training, log a `StratificationWarning`
- Status: ❌ Not implemented
