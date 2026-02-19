---
id: US-012
epic: EP-3 Data Quality
priority: P1
status: Not implemented — targeted by PRD-003 Phase 3
source_prd: PRD-003
estimation: 3 points
---

# US-012: Sentence Boundary Quality (No Abbreviation Splits)

## The Story

> **As a** `Data Scientist`,
> **I want** risk segments to contain complete sentences not split on financial abbreviations,
> **So that** training examples express coherent risk arguments rather than truncated fragments.

## Acceptance Criteria

### Scenario A: Financial abbreviations are not treated as sentence boundaries
```gherkin
Given a risk segment containing "The U.S. economy faces significant headwinds."
When the segmenter splits the text into sentences
Then "U.S." is not treated as an end-of-sentence marker
  And the full sentence "The U.S. economy faces significant headwinds." remains intact
  And the same holds for: Inc., Corp., Ltd., i.e., e.g., Jan., Feb., Mar., Apr., Jun., Jul., Aug., Sep., Oct., Nov., Dec.
```

### Scenario B: Genuine sentence boundaries are correctly detected
```gherkin
Given a risk segment containing "This risk is material. A new risk was identified."
When the segmenter splits the text into sentences
Then the two sentences are correctly separated at the period followed by a capitalised word
```

### Scenario C: Readability baseline is maintained on re-processed corpus
```gherkin
Given the 20-file spot-check corpus re-processed after the sentencizer fix
When Gunning Fog index is computed for each segment
Then the median Gunning Fog score is >= 10.0 across the spot-check set
  And no segment contains a sentence fragment shorter than 5 words (unless it is the first/last of a paragraph)
```

### Scenario D: Sentencizer reuses the worker-pool instance
```gherkin
Given the pipeline is running with 8 workers
When multiple filings are processed concurrently
Then the spaCy sentencizer model is loaded once per worker process (via the global worker pool)
  And memory usage does not increase linearly with concurrent filings
```

## Technical Notes

- Fix target: `src/preprocessing/segmenter.py:307` (`_split_into_chunks`) and `:349` (`_segment_by_semantic_breaks`)
- Replace bare regex `re.split(r'(?<=[.!?])\s+', text)` with spaCy `sentencizer` component
- spaCy is already a declared dependency (`>=3.7.0`); no new package needed
- Model: `en_core_web_sm` (Scenario D uses the global worker pool singleton)
- Test: `tests/test_segmenter.py` — "U.S. economy" not split; paragraph boundary correctly split
- See PRD-003 §4.4 for fix specification
