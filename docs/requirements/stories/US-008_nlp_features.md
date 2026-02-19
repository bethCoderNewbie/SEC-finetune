---
id: US-008
epic: EP-6 ML Readiness
priority: P0
status: Not implemented as unified output — features exist in separate scripts (gap)
source_prd: PRD-001, PRD-002
estimation: 5 points
dod: The output file includes columns for mood (sentiment) and complexity (readability) alongside every risk segment.
---

# US-008: NLP Features Inline in Primary JSONL Output

## The Story

> **As a** `Data Scientist`,
> **I want** sentiment, readability, and topic model features attached inline to each JSONL record,
> **So that** I can load one file and train immediately — without complex joins between the primary output and separate feature files.

## Definition of Done (Plain Language)

The output JSONL file includes a **mood score** (positive / neutral / negative sentiment) and a **complexity score** (reading difficulty grade) directly on the same line as each risk segment. No separate file or join is needed.

## Why This Is P0

Features stored in a separate file require a join key (segment\_id + filing date + company) that must be maintained across multiple pipeline runs. When the primary output schema changes (e.g., new segmentation logic), the separate feature files go stale silently. Inline features eliminate the join, eliminate stale-data risk, and make the JSONL record a single source of truth for model training. This is the "unified output" principle.

## Acceptance Criteria

### Scenario A: Sentiment features present in every JSONL record
```gherkin
Given a processed JSONL file produced by the batch pipeline
When I read one record
Then it contains: finbert_sentiment ("positive" | "neutral" | "negative"), finbert_confidence (float in [0,1]), lm_positive_count (int >= 0), lm_negative_count (int >= 0)
  And these fields are computed on the segment's text field (not the full filing)
```

### Scenario B: Readability features present in every JSONL record
```gherkin
Given a segment with word_count >= 20
When feature engineering runs as part of the batch pipeline
Then the record contains: flesch_kincaid_grade (float), gunning_fog (float), avg_sentence_length (float)
```

### Scenario C: Topic distribution present in every JSONL record
```gherkin
Given an LDA model trained on the corpus and accessible at the path specified in configs/config.yaml
When feature engineering runs
Then the record contains: topic_distribution (list of float, sum ≈ 1.0, length == n_topics), dominant_topic (int)
  And n_topics matches the value in the LDA model config
```

### Scenario D: No separate feature file is required post-batch
```gherkin
Given the batch pipeline has completed
When I run datasets.load_dataset("json", data_files="*.jsonl") on the output directory
Then every record contains all features from Scenarios A–C inline
  And no post-batch join or feature script is needed to produce a training-ready dataset
```

### Scenario E: Feature computation failure is non-blocking
```gherkin
Given a segment where FinBERT inference times out
When the feature computation raises an exception
Then the record is still written to JSONL with finbert_sentiment: null, finbert_confidence: null
  And the failure is logged to _progress.log with the segment_id and exception type
  And the pipeline does not crash or skip the filing
```

## Technical Notes

- Current state: `src/features/sentiment.py`, `src/features/readability/`, `src/features/topic_modeling/` — all implemented but called from separate `scripts/feature_engineering/` scripts
- Required change: integrate feature computation into `process_batch()` after segmentation, before JSONL serialisation
- LDA model path: configured in `configs/features/topic_modeling` section; model must be pre-trained before batch run
- Topic features require a pre-trained LDA model — if none is available, `topic_distribution: null`
- Status: ❌ Not yet unified. Existing feature scripts are correct but not wired into the primary batch pipeline.
