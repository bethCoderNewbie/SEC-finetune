---
id: OQ-RFC3-1
question: What fraction of current corpus segments exceed 380 words?
status: ANSWERED
answered_date: 2026-02-20
git_sha: 5476f84
branch: main
author: beth88.career@gmail.com
corpus_batch: data/processed/20260218_142659_preprocessing_0b83409
blocks: RFC-003 §Open Questions — Sizing Option A's impact
---

# OQ-RFC3-1: Segment Word Count Distribution

## Method

Ran on the latest complete batch
(`data/processed/20260218_142659_preprocessing_0b83409`, 11 filings,
3 tickers — AAPL 2021-2025, ABBV 2021-2024, ABT 2021-2022):

```bash
BATCH_DIR="data/processed/20260218_142659_preprocessing_0b83409"
jq '.segments[].word_count' "$BATCH_DIR"/*_segmented_risks.json | awk '$1>380'
```

## Result

**28 of 1,019 segments (2.75%) exceed 380 words.**

### Distribution

| Bucket | Count | % of corpus |
|:-------|------:|------------:|
| ≤100 words | 724 | 71.1% |
| 101–200 words | 195 | 19.1% |
| 201–300 words | 51 | 5.0% |
| 301–380 words | 21 | 2.1% |
| 381–420 words | 12 | 1.2% |
| 421–500 words | 9 | 0.9% |
| >500 words | 7 | 0.7% |

### Threshold summary

| Threshold | Count | % |
|:----------|------:|--:|
| >350 words (borderline zone start) | 33 | 3.24% |
| **>380 words (Option A ceiling)** | **28** | **2.75%** |
| >420 words (certain truncation at 1.35 tok/word) | 16 | 1.57% |
| >500 words (severe truncation) | 7 | 0.69% |

**Max segment:** 1,141 words (~1,540 tokens estimated — 3× the 512-token limit).
**Average segment:** 87.5 words.

### Per-filing breakdown

| Filing | Segments >380 | Total segments | Rate |
|:-------|-------------:|---------------:|-----:|
| ABBV_10K_2022 | 5 | 58 | 8.6% |
| ABBV_10K_2023 | 5 | 73 | 6.8% |
| ABBV_10K_2024 | 5 | 78 | 6.4% |
| ABBV_10K_2021 | 3 | 59 | 5.1% |
| AAPL_10K_2021 | 3 | 124 | 2.4% |
| AAPL_10K_2022 | 2 | 139 | 1.4% |
| AAPL_10K_2024 | 2 | 133 | 1.5% |
| AAPL_10K_2023 | 1 | 124 | 0.8% |
| ABT_10K_2021 | 1 | 44 | 2.3% |
| ABT_10K_2022 | 1 | 44 | 2.3% |
| AAPL_10K_2025 | 0 | — | — |

## Interpretation

### Option A impact is low but non-trivial

- **2.75% of current segments will be re-split** when Option A
  (`max_segment_words: 380`) is deployed. This is a modest but real corpus change.
- **ABBV filings are the outlier:** 5.1–8.6% of ABBV segments exceed 380 words,
  compared to 0.8–2.4% for AAPL and ABT. ABBV is a pharma company; long risk
  paragraphs citing drug trial obligations and regulatory citations are consistent
  with the RFC-003 §Context warning about dense acronym clusters driving high
  tokens/word ratios (up to 2.0 tok/word).
- The max segment at **1,141 words (~1,540 est. tokens)** is a hard truncation
  case today — the tokenizer is silently discarding roughly 1,028 tokens of text.
- **7 segments (0.69%) exceed 500 words** — these are the highest-severity silent
  truncation cases and will be split into 2+ chunks each under Option A.

### OQ-RFC3-2 pre-signal

The current >390-word rate is ~2.6% (extrapolating the 381–420 + 421–500 + >500
buckets). After Option A is deployed, this figure should drop to ~0%. The OQ-RFC3-2
trigger condition (>5% of segments exceed 390 words post-deployment) is not at risk
from this corpus, but ABBV-heavy corpora should be monitored.

### Corpus caveat

This measurement covers 11 filings across 3 tickers from a single preprocessing
run. The PRD-002 corpus target is ~200 filings (§2.1). The ABBV over-rate pattern
suggests pharma-sector filings may skew higher. Re-run this measurement after the
full corpus batch is processed before finalizing Option A's impact estimate.

## Answer to OQ-RFC3-1

> **2.75% of current corpus segments (28/1,019) exceed the 380-word Option A ceiling.**
> Option A will re-split these segments into shorter chunks.
> ABBV filings show 5–9% over-rate, consistent with pharma regulatory prose density.
> Worst observed: 1,141 words (estimated ~1,540 tokens; actively truncated today).

## Next Steps

1. **OQ-RFC3-1: CLOSED.** Record this answer in RFC-003 Open Questions table.
2. **Implement Option A** (`max_segment_words: 380`) per RFC-003 Affected Files table.
3. **After full corpus batch:** Re-run this query on all ~200 filings to validate
   the 2.75% figure holds, or update it in RFC-003 before ADR is written.
4. **OQ-RFC3-2** remains open until Option A is deployed and the full-corpus
   measurement is taken.
