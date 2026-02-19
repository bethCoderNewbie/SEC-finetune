---
id: US-015
epic: EP-6 ML Readiness
priority: P1
status: Not implemented
source_prd: PRD-003
estimation: 3 points
---

# US-015: Token-Aware Segment Truncation/Splitting

## The Story

> **As a** `Data Scientist`,
> **I want** to configure segment truncation or splitting at the token level (e.g., 512 tokens),
> **So that** training records are natively compatible with Transformer input limits without losing material context through naive character-based truncation.

## Why Token-Level, Not Character-Level

FinBERT and other Transformer models have a hard 512-token input limit. A 1,000-word risk segment truncated at character 2,048 may cut in the middle of a material disclosure, or preserve a sentence fragment that introduces noise. Token-aware splitting:
1. Splits at sentence boundaries, never mid-sentence
2. Optionally applies sliding-window overlap to preserve context across chunks
3. Produces records that are already within model limits — no in-training truncation required

## Acceptance Criteria

### Scenario A: Segment within token limit passes through unchanged
```gherkin
Given a segment with token_count <= max_tokens (e.g., 400 tokens with max_tokens=512)
When token-aware processing runs
Then the segment is written to JSONL unchanged
  And its JSONL record contains: token_count=400, truncated=false, chunk_index=0, total_chunks=1
```

### Scenario B: Segment exceeding token limit is split at sentence boundaries
```gherkin
Given a segment with token_count == 800 and max_tokens == 512
When token-aware processing runs
Then the segment is split into 2 JSONL records at the nearest sentence boundary before token 512
  And record 1 has: chunk_index=0, total_chunks=2, parent_segment_id="seg_0001", token_count <= 512
  And record 2 has: chunk_index=1, total_chunks=2, parent_segment_id="seg_0001", token_count <= 512
  And no sentence is split across chunks
```

### Scenario C: Sliding-window overlap is applied when configured
```gherkin
Given max_tokens=512 and overlap_tokens=64 are set in configs/config.yaml
  And a segment with token_count == 900
When token-aware processing runs
Then chunk 2 begins 64 tokens before chunk 1 ends
  And all chunks have token_count <= 512
  And each chunk's JSONL record has overlap_tokens=64
```

### Scenario D: Tokenizer is configurable and matches the target model
```gherkin
Given tokenizer_name: "ProsusAI/finbert" is set in configs/config.yaml
When token-aware processing initialises
Then it loads the FinBERT tokenizer from HuggingFace (or local cache)
  And all token counts are computed using that tokenizer's vocabulary
  And using a different tokenizer_name produces different token counts for the same text
```

## Technical Notes

- Tokenizer: load via `transformers.AutoTokenizer.from_pretrained(tokenizer_name)` — reuse the global worker pool singleton (one load per worker)
- `max_tokens` default: 512; `overlap_tokens` default: 0 (no overlap). Both configurable in `configs/config.yaml` under `segmentation.token_aware`
- Output fields added to JSONL: `token_count` (int), `truncated` (bool), `chunk_index` (int), `total_chunks` (int), `parent_segment_id` (str | null — null if no split)
- Sentence boundary detection: reuse the spaCy sentencizer from US-012 (never split mid-sentence)
- Status: ❌ Not implemented (open question OQ-3 in PRD-001/002 — this story closes it)
