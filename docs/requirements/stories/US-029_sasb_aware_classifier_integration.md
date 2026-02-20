---
id: US-029
epic: EP-6 ML Readiness
priority: P0
status: Not implemented
source_prd: PRD-002
estimation: 5 points
---

# US-029: SASB-Aware Classifier Integration into `process_batch()`

## The Story

> **As an** `ML Engineer`,
> **I want** `process_batch()` to emit `risk_label`, `sasb_topic`, `sasb_industry`, `confidence`, and `label_source` on every output segment using a SASB-aware classifier,
> **So that** every filing in the batch is labeled with both a cross-industry archetype and an industry-specific SASB material topic — without requiring any post-processing step.

## Acceptance Criteria

### Scenario A: All five classifier fields present in every output segment
```gherkin
Given a batch run completes on a directory containing at least one valid EDGAR filing
  And the classifier model is loaded and the taxonomy files exist (US-030)
When I inspect the per-filing JSON output
Then every RiskSegment record contains: risk_label (str), sasb_topic (str), sasb_industry (str), confidence (float), label_source (str)
  And risk_label is one of: cybersecurity, regulatory, financial, supply_chain, market, esg, macro, human_capital, other
  And label is an integer 0–8 (the archetype integer matching risk_label)
  And confidence is a float in [0.0, 1.0]
  And label_source is one of: classifier, heuristic
```

### Scenario B: Low-confidence segments fall back to heuristic
```gherkin
Given a segment where the classifier's top prediction confidence is 0.62
  And the confidence threshold is configured as 0.7 in configs/config.yaml
When process_batch() processes that segment
Then risk_label is set to "other"
  And label_source is set to "heuristic"
  And confidence records the raw classifier score (0.62) — not overwritten
  And sasb_topic is set to "Other" (the default heuristic crosswalk value)
```

### Scenario C: SASB enrichment is industry-specific via SIC code
```gherkin
Given a filing with sic_code "7372" (Software & IT Services)
  And a segment classified as archetype 0 (cybersecurity) with confidence 0.88
When process_batch() emits the output record
Then sasb_industry is "Software & IT Services"
  And sasb_topic is "Data_Security"
Given a second filing with sic_code "2911" (Oil & Gas E&P)
  And a segment classified as archetype 5 (esg) with confidence 0.84
When process_batch() emits the output record
Then sasb_industry is "Oil & Gas — Exploration & Production"
  And sasb_topic is "Greenhouse_Gas_Emissions"
```

### Scenario D: Unknown SIC code does not crash the pipeline
```gherkin
Given a filing with a sic_code not present in sasb_sics_mapping.json
When process_batch() processes that filing
Then sasb_industry is "Unknown"
  And sasb_topic is the default archetype mapping from archetype_to_sasb.yaml
  And the segment is emitted (not quarantined) — unknown SIC is a non-blocking warning
  And RUN_REPORT.md lists the unknown SIC code in a "Taxonomy Coverage Gaps" section
```

### Scenario E: Inference latency within P95 budget
```gherkin
Given a batch of 100 segments processed sequentially in CPU-only mode
When inference completes
Then the P95 per-segment latency is ≤ 500ms
  And the P99 per-segment latency is ≤ 1,000ms
  And batch_summary_{run_id}.json records: median_inference_ms, p95_inference_ms
```

## Technical Notes

- **Integration point:** Wire the SASB-aware classifier into `src/preprocessing/pipeline.py` —
  specifically the `process_batch()` method (or its per-file worker called by `ParallelProcessor`).
  `scripts/feature_engineering/auto_label.py` already implements SASB-aware zero-shot labeling
  (lines 157, 174, 200–207, 189) and is the reference implementation. The fine-tuned model
  replaces `facebook/bart-large-mnli` as the classification backend once training is complete.
- **Taxonomy lookup:** `TaxonomyManager.get_industry_for_sic(sic_code)` → `sasb_industry`.
  `archetype_to_sasb.yaml` crosswalk maps `(archetype_label, sasb_industry)` → `sasb_topic`.
  Both require US-030 to be completed first.
- **Confidence threshold:** Configurable via `configs/config.yaml` as `classifier.confidence_threshold`
  (default 0.7). Segments below threshold: `risk_label = "other"`, `label_source = "heuristic"`.
- **Model loading:** Fine-tuned model loaded via `ModelRegistry` (`src/models/registry/`).
  Default base model: `ProsusAI/finbert` (configured in `src/config/models.py:default_model`).
  Zero-shot fallback: `facebook/bart-large-mnli` (`zero_shot_model`).
- **Output column names:** `text` (not `input_text`) and `label` (int 0–8, not string) as required
  by `datasets.load_dataset("json", ...)` — see PRD-002 §2.2.
- **Blocked by:** US-030 (taxonomy data files must exist before SIC→SASB lookup works).
- Status: ❌ Not implemented
