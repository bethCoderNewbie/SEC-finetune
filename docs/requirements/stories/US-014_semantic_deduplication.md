---
id: US-014
epic: EP-3 Data Quality
priority: P1
status: Not implemented
source_prd: PRD-003
estimation: 5 points
---

# US-014: Cross-Filing Semantic Deduplication

## The Story

> **As a** `Data Scientist`,
> **I want** near-duplicate risk factor segments to be identified and excluded from the training split across filings and across years for the same company,
> **So that** the model is not overfit on boilerplate language that companies copy-paste verbatim from one annual report to the next.

## Why This Is Distinct from Fix 4 in PRD-003

PRD-003 Fix 4 (`qa_validation.py:890-908`) deduplicates segments **within a single batch run** — it prevents the same segment appearing twice in one output file. This story addresses a different, larger-scope problem: the same risk language appearing across **multiple filings from different years for the same company** (e.g., AAPL 2020, 2021, 2022, 2023 all contain an identical "macroeconomic conditions" paragraph). This cross-filing deduplication must run at the corpus level before train/val/test splitting, not per-filing.

## Acceptance Criteria

### Scenario A: Exact duplicate segments are excluded from training split
```gherkin
Given a corpus containing two filings from the same company in different years
  And both filings contain the segment text "We face risks related to global supply chain disruptions." (SHA-256 identical)
When the deduplication pass runs on the full corpus
Then only one instance of the segment is included in the training split
  And the other instance is marked deduplicated: true in its JSONL record
  And both instances remain in the JSONL files (dedup flag, not deletion)
```

### Scenario B: Near-duplicate segments are flagged
```gherkin
Given two segments with Jaccard similarity >= 0.85 (MinHash estimate) across different filings
When the deduplication pass runs
Then both segments have near_duplicate_of: "<segment_id_of_canonical>" in their JSONL record
  And the canonical record (first-seen in filing-date order) has near_duplicate_of: null
  And near-duplicate records are excluded from the training split (included in val/test only)
```

### Scenario C: Deduplication does not collapse genuinely similar but distinct risks
```gherkin
Given two segments about "cybersecurity risk" from different industry sectors (SIC 7372 and SIC 6020)
  And their Jaccard similarity is 0.60 (below the 0.85 threshold)
When the deduplication pass runs
Then both segments are retained in the training split with near_duplicate_of: null
  And no false-positive deduplication occurs
```

### Scenario D: Dedup statistics in run report
```gherkin
Given a corpus of 50,000 segments after deduplication
When batch_summary_{run_id}.json is written
Then it contains: total_segments, exact_duplicates_flagged (int), near_duplicates_flagged (int), training_eligible (int)
  And training_eligible == total_segments - exact_duplicates_flagged - near_duplicates_flagged
```

## Technical Notes

- Scope: corpus-level, not per-filing. Must operate on the full assembled JSONL corpus.
- Exact dedup: SHA-256 of `text` field, accumulated in `StateManager.segment_hashes` across all runs
- Near-dedup: MinHash LSH via `datasketch` library (Jaccard threshold: 0.85, configurable)
- Key difference from PRD-003 Fix 4: Fix 4 runs within one batch run; this story runs at corpus assembly time before splitting
- Filing-date ordering determines canonical record (earliest date wins)
- Output: JSONL records gain `deduplicated` (bool) and `near_duplicate_of` (str | null) fields
- Status: ❌ Not implemented
