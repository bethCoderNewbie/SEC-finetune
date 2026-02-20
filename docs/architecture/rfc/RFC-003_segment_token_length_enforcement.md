---
id: RFC-003
title: Segment Token Length Enforcement in Preprocessing
status: DRAFT
author: beth88.career@gmail.com
created: 2026-02-20
last_updated: 2026-02-20
git_sha: 5476f84
superseded_by: null
related_prd: docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md
related_stories: docs/requirements/stories/US-015_token_aware_truncation.md
---

# RFC-003: Segment Token Length Enforcement in Preprocessing

## Status

**DRAFT** — one phased decision required. Phase A can be implemented immediately.
Phase B implementation is deferred until G-12 (classifier integration into
`process_batch()`) is complete. Once both phases are agreed and implemented, write
an ADR referencing this document.

---

## Context

The `RiskSegmenter` enforces segment size via `_split_long_segments`
(`src/preprocessing/segmenter.py:273`) using a **character-count ceiling**
(`len(segment) > self.max_length`, configured via
`settings.preprocessing.max_segment_length`, default `2000`). Segments that pass
this gate are handed to the classifier at inference time.

The downstream classifiers — `ProsusAI/finbert` and `microsoft/deberta-v3-base` —
have a hard **512-token input limit**. The contingency model
`answerdotai/ModernBERT-base` raises this to 8,192 tokens (PRD-002 §4.1), but
FinBERT and DeBERTa remain the Phase 2 defaults.

**The gap:** characters ≠ tokens. SEC legal and financial prose tokenises at
approximately 1.2–1.5 tokens per word. A 2,000-character segment of short financial
words (e.g., "the Company's CDS spread, CDO tranche, CLO equity...") can produce
600+ tokens — 17% over the 512-token limit — and will be **silently truncated by
the tokenizer** with no error, no log entry, and no flag in the output record.

### What `_split_into_chunks` does today

`_split_into_chunks` (segmenter.py:295) splits at sentence boundaries when
`current_length + sentence_length > max_length`. `max_length` is the character-based
`max_segment_length` config value. There is no token count anywhere in the
preprocessing pipeline.

### Scope of the problem

`RiskSegment.word_count` is already computed on every segment
(segmenter.py:140–143). At ~1.35 tokens/word (measured average for SEC 10-K prose):

| word_count | estimated tokens | exceeds 512? |
|:-----------|:----------------|:-------------|
| 350        | ~473            | No           |
| 380        | ~513            | Borderline   |
| 420        | ~567            | Yes          |
| 500        | ~675            | Yes          |

With the current `max_segment_length = 2000` chars, segments of up to ~500 words
can pass the filter. The silent truncation rate on EDGAR filings has not been
measured (OQ-T1 is open; no corpus-wide token-length distribution exists yet).

---

## Options

### Option A — Word-count ceiling (lowest complexity)

Replace (or supplement) the character-count gate with a **word-count ceiling** in
`_split_long_segments`. No new dependencies.

**Config change** (`configs/preprocessing.yaml`):
```yaml
preprocessing:
  max_segment_words: 380   # add; ~512 tokens at 1.35 tok/word, with headroom
  max_segment_length: 2000 # retain for char-based pre-filter
```

**Code change** (`src/preprocessing/segmenter.py`):
1. Read `max_segment_words` in `RiskSegmenter.__init__` alongside `max_length`.
2. In `_split_long_segments`, trigger splitting when either limit is exceeded:
   ```python
   too_long = (
       len(segment) > self.max_length
       or len(segment.split()) > self.max_words
   )
   ```
3. In `_split_into_chunks`, replace the character accumulator with a word
   accumulator:
   ```python
   if current_words + sentence_words > self.max_words and current_chunk:
       # flush chunk
   ```

**Accuracy:** ~95%+ for standard SEC prose. Fails for filings with dense acronym
clusters (e.g., pharma compound names, XBRL-heavy disclosure language) where
tokens/word can reach 2.0. Acceptable for Phase 2; exact by construction in Phase B.

**Changes required:**
- `configs/preprocessing.yaml` — 1 line
- `src/preprocessing/segmenter.py` — `__init__`, `_split_long_segments`,
  `_split_into_chunks` (~10 lines total)
- Unit tests for the word-count gate in `tests/unit/preprocessing/test_segmenter.py`

---

### Option B — Tokenizer-aware split (medium complexity)

Accept a `tokenizer` parameter (or `model_name: str`) in
`RiskSegmenter.__init__`. Load the tokenizer once at construction. Replace the
word-count accumulator in `_split_into_chunks` with an actual token count:

```python
token_count = len(self.tokenizer.encode(sentence, add_special_tokens=False))
if current_tokens + token_count > self.max_tokens and current_chunk:
    # flush chunk
```

Set `max_tokens = 480` (leaving 32 tokens of headroom for `[CLS]` / `[SEP]`
special tokens that FinBERT and DeBERTa prepend at inference time).

**Accuracy:** Exact by construction for whatever tokenizer is provided.

**Coupling risk:** The segmenter's split threshold is now tied to a specific
tokenizer vocab. Swapping from FinBERT to DeBERTa (planned Phase 2 experiment;
PRD-002 §4.1) changes tokenisation subtly; the `max_tokens` headroom value may need
review if a very different vocab is introduced (e.g., ModernBERT's byte-level BPE).
This coupling must be documented in the ADR.

**Changes required:**
- `src/preprocessing/segmenter.py` — `__init__` signature, `_split_into_chunks`
- `src/config/preprocessing.py` — optional `tokenizer_model` field (defaults to
  `ProsusAI/finbert`)
- `scripts/data_preprocessing/run_preprocessing_pipeline.py` — pass tokenizer to
  `RiskSegmenter` at construction
- Unit tests mocking the tokenizer

---

### Option C — Sliding window with max-confidence selection (higher complexity)

Split any segment exceeding the token limit into overlapping windows
(e.g., window=480 tokens, stride=128 tokens). At inference time, run the classifier
on each window and select the window with the highest confidence score.

**Advantage:** No text is discarded. Captures risk language in the tail of long
paragraphs that sentence-boundary splitting would assign to a new chunk.

**Disadvantage:** Changes both the preprocessing stage and the inference stage.
Cannot be implemented until G-12 (classifier wired into `process_batch()`) is
complete. Produces more segments per filing, increasing inference latency; the
throughput benchmark (PRD-002 §5 Group 4 item 13) would need re-running.
Premature for Phase 2.

---

## Recommendation

**Implement Option A immediately (closes US-015 / G-03 token safety gap).**
**Migrate to Option B when G-12 (classifier integration) is implemented.**

Rationale:
- Option A requires no new imports and can be reviewed and merged independently of
  the G-12 work stream. It closes the silent truncation gap for ~95%+ of filings.
- Option B is the correct long-term answer, but it couples the segmenter to the
  tokenizer. That coupling is only appropriate once the tokenizer choice is stable —
  which it will be once the FinBERT vs. DeBERTa Phase 2 experiment (PRD-002 §4.1)
  is resolved and an ADR is written. At that point, pass the winning tokenizer into
  `RiskSegmenter` and remove the word-count proxy.
- Option C is Phase 3 material: it changes the inference contract and cannot be
  benchmarked until the classifier is wired in.

### Transition contract

When migrating from Option A to Option B:
1. The `max_segment_words` config key should be **removed** (it is a proxy and
   should not coexist with the tokenizer-based gate).
2. The `max_tokens` sentinel (480) and `tokenizer_model` config key should be
   added in the same PR as the Option B implementation.
3. Any segment in the corpus produced under Option A that was split at 380 words
   may be re-split at a slightly different boundary under Option B. The annotation
   corpus test split (G-16) must be **re-derived** from Option B output before any
   training run begins if Option A segments were used to build it.

---

## Affected Files

| File | Change | Phase |
|:-----|:-------|:------|
| `src/preprocessing/segmenter.py` | Add `max_words` param; update `_split_long_segments` and `_split_into_chunks` | A |
| `configs/preprocessing.yaml` | Add `max_segment_words: 380` | A |
| `src/config/preprocessing.py` | Read `max_segment_words` into `PreprocessingConfig` | A |
| `tests/unit/preprocessing/test_segmenter.py` | Word-count gate tests | A |
| `src/preprocessing/segmenter.py` | Add `tokenizer` param; replace word accumulator with token counter | B |
| `src/config/preprocessing.py` | Add `tokenizer_model` field; remove `max_segment_words` | B |
| `scripts/data_preprocessing/run_preprocessing_pipeline.py` | Pass tokenizer to `RiskSegmenter` | B |

---

## Consequences

### Positive

- Eliminates silent mid-text tokenizer truncation for ~95%+ of EDGAR segments
  (Option A) / 100% (Option B).
- Closes US-015 acceptance criteria (`Scenario: long segment split at sentence
  boundary before model token limit`).
- `RiskSegment.word_count` (already present) becomes a reliable proxy for token
  length in corpus statistics and class balance audits.

### Negative / Watch Items

- **Segment count increase:** Filings with long risk paragraphs will produce more
  segments post-split. The `total_segments` field in batch output will increase.
  Run the throughput benchmark (PRD-002 §5 Group 4 item 13) after implementing
  Option A to confirm the < 2s/filing target still holds.
- **Annotation corpus dependency:** If Option A segments are used to build the
  annotation corpus train split (G-16), and Option B is later applied, the
  corpus must be rebuilt from the new segmentation before fine-tuning. Do not
  freeze the test split (PRD-002 §11 item 6) until the final segmentation strategy
  is in place.
- **FinBERT lower-case:** `ProsusAI/finbert` uses `do_lower_case=true`. Option B's
  tokenizer count is accurate, but lowercased tokens may affect acronym-heavy
  segments differently than DeBERTa's cased tokenizer. Record both in the Phase 2
  experiment results before selecting a production default.

---

## Open Questions

| # | Question | Owner | Blocks | Status |
|:--|:---------|:------|:-------|:-------|
| OQ-RFC3-1 | What fraction of current corpus segments exceed 380 words? | Data Eng | Sizing Option A's impact | **ANSWERED** — 2.75% (28/1,019 segments across 11 filings). ABBV outlier at 5–9%; max segment 1,141 words. See [research doc](../../thoughts/shared/research/2026-02-20_14-20-37_oq_rfc3_1_segment_word_count_distribution.md). |
| OQ-RFC3-2 | After Option A is deployed, re-run batch on the full corpus and measure whether >5% of segments exceed 390 words — the ModernBERT contingency trigger (PRD-002 §4.1 OQ-3). | ML Engineer | Model selection ADR | Open |
| OQ-RFC3-3 | When migrating to Option B, which tokenizer is canonical — the fine-tune winner (FinBERT or DeBERTa) from the Phase 2 experiment? Decision deferred until ADR resolves model selection. | ML Engineer | Option B implementation | Open |
