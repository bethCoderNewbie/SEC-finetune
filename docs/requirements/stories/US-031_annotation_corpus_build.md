---
id: US-031
epic: EP-6 ML Readiness
priority: P0
status: Not implemented
source_prd: PRD-002
estimation: 8 points
---

# US-031: Build Quality-Gated Annotation Corpus

## The Story

> **As an** `ML Engineer`,
> **I want** a labeled annotation corpus with ≥ 500 examples per non-`other` archetype in the training split, a contamination-free test split of real EDGAR segments, and inter-annotator Cohen's Kappa ≥ 0.80 documented,
> **So that** the fine-tune training run has a quality-gated dataset and the Macro F1 ≥ 0.72 Phase 2 gate is measurable against a valid, uncontaminated evaluation baseline.

## Acceptance Criteria

### Scenario A: Test split held out before any LLM labeling
```gherkin
Given a pool of real EDGAR RiskSegment.text objects extracted by the PRD-002 pipeline
When the corpus build process begins
Then the first action is stratified random sampling of the test split (10% of total target size)
  And test split records are written to data/processed/annotation/test.jsonl immediately
  And no LLM labeling API calls are made until test.jsonl is written and SHA-256-checksummed
  And splits_manifest.json records: test_held_out_at (ISO 8601 timestamp), test_checksum (SHA-256 of test.jsonl)
```

### Scenario B: Training split meets minimum class size requirement
```gherkin
Given the annotation corpus train split at data/processed/annotation/train.jsonl
When I count records grouped by label (int 0–8)
Then every non-other archetype (labels 0–7) has at least 500 records
  And the other archetype (label 8) may have fewer than 500 records — it is populated by heuristic fallback
  And the class imbalance ratio (max_count / min_count) is documented in splits_manifest.json
  And if imbalance ratio > 5.0, a "⚠️ Imbalance Warning" is written to splits_manifest.json recommending weighted_cross_entropy_loss: true
```

### Scenario C: Test split contains only real EDGAR segments with human-verified labels
```gherkin
Given data/processed/annotation/test.jsonl
When I inspect every record in the file
Then every record has label_source == "human"
  And every record has human_verified == true
  And no record has label_source in ["llm_silver", "llm_synthetic", "heuristic"]
  And ticker and filing_date are non-null for every record (real EDGAR provenance required)
```

### Scenario D: No duplicate text across train, validation, and test splits
```gherkin
Given all three split files: train.jsonl, validation.jsonl, test.jsonl
When I compute SHA-256(record["text"]) for every record in all three files
Then no SHA-256 hash appears more than once across the combined set
  And splits_manifest.json records: dedup_checked_at (ISO 8601), cross_split_duplicates_found (int, must be 0)
```

### Scenario E: Inter-annotator agreement documented before training begins
```gherkin
Given a 50-example sample drawn from the human-verified portion of the annotation corpus
  And two domain experts independently labeled each example
When Cohen's Kappa is computed between the two label sets
Then kappa >= 0.80
  And the result is recorded in data/processed/annotation/iaa_report.json:
      {"kappa": <float>, "sample_size": 50, "evaluated_at": "<ISO 8601>", "annotators": ["<id1>", "<id2>"]}
  And training is blocked (Phase 2 gate fails) if kappa < 0.80
```

### Scenario F: LLM-synthetic records capped at 40% of training split
```gherkin
Given data/processed/annotation/train.jsonl after the full corpus build completes
When I count records by label_source
Then (count where label_source == "llm_synthetic") / total_train_count <= 0.40
  And splits_manifest.json records: synthetic_pct (float), synthetic_cap_enforced (bool)
```

### Scenario G: Corpus is loadable by HuggingFace datasets without modification
```gherkin
Given data/processed/annotation/train.jsonl, validation.jsonl, test.jsonl
When I run: dataset = datasets.load_dataset("json", data_files={"train": "train.jsonl", "validation": "validation.jsonl", "test": "test.jsonl"})
Then no exception is raised
  And dataset["train"].features includes: text (Value("string")), label (ClassLabel(names=[...]))
  And all records pass datasets' JSON parsing without null text or out-of-range label integers
```

## Technical Notes

- **File locations:** `data/processed/annotation/train.jsonl`, `validation.jsonl`, `test.jsonl`,
  `splits_manifest.json`, `iaa_report.json`. Raw LLM API responses stored in
  `data/processed/annotation/llm_responses/` for audit trail.
- **Hybrid pipeline (three layers):**
  1. **Real + LLM silver (≥ 60% of train):** Real EDGAR segments labeled by `scripts/feature_engineering/auto_label.py`
     using `TaxonomyManager` + `facebook/bart-large-mnli`. Confidence ≥ 0.80 → `label_source: "llm_silver"`.
     Confidence < 0.80 → queue for human review via US-028 annotation UI.
  2. **LLM synthetic (≤ 40% of train, gap-fill only):** Generated for archetype+industry pairs
     where real segment count < 300. Style-anchored with real 10-K excerpts. Never in test set.
  3. **Human IAA gate:** 50-example sample per SASB topic reviewed by two domain experts.
     Cohen's Kappa ≥ 0.80 required before training begins (QR-01).
- **JSONL schema** (full schema in PRD-002 §2.1.2):
  ```json
  {"text": "...", "label": 0, "sasb_topic": "Data_Security", "sasb_industry": "Software & IT Services",
   "sic_code": "7372", "ticker": "MSFT", "filing_date": "2023-10-15",
   "label_source": "llm_silver", "llm_confidence": 0.91, "human_verified": false}
  ```
- **Split ratios:** 80 / 10 / 10 (train / validation / test). Company-grouped (same CIK never
  in two splits) — see US-016 for the `GroupShuffleSplit` implementation.
- **Text quality gates (applied before writing to any split):**
  - `word_count >= 20` (configurable via `preprocessing.min_segment_length`)
  - `token_count <= MAX_LEN` (512 for FinBERT/DeBERTa; 8,192 for ModernBERT contingency)
  - No whitespace-only strings; UTF-8 only (reject mojibake)
- **Blocked by:** US-028 (annotation labeler UI — required for human label review),
  US-030 (taxonomy files — required for `auto_label.py` SASB enrichment).
- **Blocks:** Phase 2 exit criteria — Macro F1 ≥ 0.72 gate is unmeasurable without a
  valid, uncontaminated test split.
- Status: ❌ Not implemented
