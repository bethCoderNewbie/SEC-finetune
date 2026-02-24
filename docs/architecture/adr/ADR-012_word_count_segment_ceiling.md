# ADR-012: Word-Count Ceiling for Segment Splitting (RFC-003 Option A)

**Status:** Accepted
**Date:** 2026-02-24
**Author:** beth
**git SHA:** 0872eb3
**Related RFC:** `docs/architecture/rfc/RFC-003_segment_token_length_enforcement.md`
**Closes:** US-015 (token-aware truncation, Option A phase)

---

## Context

The `RiskSegmenter` enforced segment size with a **character-count ceiling**
(`max_segment_length`, default `2000`). In practice this gate was disabled
(`max_segment_length: 999999999999` in `configs/config.yaml`) because it was
over-restrictive for normal prose. No word-count or token-count ceiling existed.

The downstream classifiers — `ProsusAI/finbert` and `microsoft/deberta-v3-base`
— have a hard 512-token input limit. SEC legal and financial prose tokenises at
approximately 1.2–1.5 tokens/word (SentencePiece/WordPiece on EDGAR text). A
segment that clears the old 2,000-char gate can produce 600+ tokens and be
**silently truncated** by the tokenizer with no log entry and no output flag.

### Corpus evidence (run `20260223_182806`, 607,463 segments / 4,423 filings)

| Threshold | Count | Rate |
|-----------|-------|------|
| >350 words | 4,277 | 0.70% |
| **>380 words** | **3,266** | **0.54% — WARN** |
| >420 words | 2,251 | 0.37% |
| >500 words | 1,193 | 0.20% |

Descriptive stats: mean=68 words, median=48, p95=182, max=3,232.

The ModernBERT contingency trigger (>5% segments exceeding 390 words) is **not
met** at 0.54%. DeBERTa-v3-base remains the Phase 2 default (ADR-008).
However, 3,266 truncation events is not negligible; the gate must be deployed.

---

## Decision

### Governing rule — word-count proxy ceiling

**`max_segment_words: 380`** is the active segment-size ceiling.

A segment is split when either limit is exceeded:

```python
too_long = (
    len(segment) > self.max_length        # char gate (safety net, disabled by config)
    or len(segment.split()) > self.max_words  # word gate (active)
)
```

The split runs `_split_into_chunks()`, which accumulates sentences until the
next sentence would push the chunk over `max_words`, then flushes at that
sentence boundary. A single sentence longer than `max_words` is emitted as its
own chunk (no mid-sentence splits).

**Rationale for 380:** at 1.35 tok/word (measured average for SEC 10-K prose),
380 words ≈ 513 tokens — just at DeBERTa's 512-token hard limit. The value
provides ~1 token of headroom above the limit. `[CLS]`/`[SEP]` special tokens
are not counted here; they are added at inference time (see Consequences).

### What is NOT changing

- The char gate (`max_segment_length`) remains in config as a dormant safety
  net. Its current value (`999999999999`) means it will never fire for any
  realistic EDGAR segment.
- `_merge_short_segments` (the 20-word floor) is unaffected.
- No changes to `RiskSegmenter` sentence-splitting logic or sec-parser.

### Files changed

| File | Change |
|:-----|:-------|
| `configs/config.yaml` | Added `max_segment_words: 380` |
| `src/config/preprocessing.py` | Added `max_segment_words: int` field (default 380) |
| `src/preprocessing/segmenter.py` | Added `max_words` param to `__init__`; updated `_split_long_segments` trigger; replaced char accumulator in `_split_into_chunks` with word accumulator |
| `tests/unit/preprocessing/test_segmenter_unit.py` | Updated `TestSplitIntoChunks` (3 tests); added `TestSplitLongSegmentsWordGate` (3 tests); added `max_words` coverage to `TestSegmenterInit` |

---

## Consequences

### Positive

- Eliminates silent tokenizer truncation for ~95%+ of EDGAR segments. (Exact
  coverage for pharma/biotech filings with dense acronym clusters may be lower;
  see Watch Items.)
- Closes US-015 acceptance criteria (Scenario: long segment split at sentence
  boundary before model token limit).
- `RiskSegment.word_count` (already present in every segment) is now a reliable
  proxy for token length in corpus statistics and class balance audits.
- Segment count will increase for the 0.54% of segments that were over-limit.
  Total segments in the next full run will be marginally higher than 607,463.

### Negative / Watch Items

- **Special tokens not counted.** `[CLS]` and `[SEP]` add 2 tokens at DeBERTa
  inference time. At 380 words the true token budget is 512 − 2 = 510, leaving
  ~3 tokens of headroom. For dense pharma text at 2.0 tok/word, 380 words = 760
  tokens — well over limit. This case is handled by Option B (see below).
- **`[CLS]`/`[SEP]` not counted.** This is acceptable for Phase 2 but must be
  corrected in Option B by using `max_tokens=480` (32-token headroom).
- **Annotation corpus dependency.** Do not freeze the train/test split (G-16)
  until Option B is in place. Segments split at a 380-word boundary under
  Option A will be re-split at a different sentence boundary under Option B's
  tokenizer-exact accumulator. The annotation corpus must be rebuilt from
  Option B output before any fine-tuning run.
- **OQ-RFC3-2 now answerable.** At 0.54% over 380 words on the pre-Option-A
  baseline, the ModernBERT contingency trigger (>5% over 390 words) is
  confirmed not met. ADR-008 model selection stands.

### Open questions from RFC-003 resolved by this ADR

| OQ | Resolution |
|----|------------|
| OQ-RFC3-1 | Full-corpus baseline: 3,266 / 607,463 (0.54%) segments exceed 380 words. |
| OQ-RFC3-2 | 0.54% < 5% contingency trigger; ModernBERT not needed. |
| OQ-RFC3-3 | Deferred — tokenizer selection pending Phase 2 FinBERT vs. DeBERTa experiment (Option B). |

---

## Migration path to Option B

When the Phase 2 model selection ADR resolves the FinBERT vs. DeBERTa choice:

1. Remove `max_segment_words` from `configs/config.yaml` and `PreprocessingConfig`.
2. Add `tokenizer_model` config field (default: winning model) and `max_tokens: 480`.
3. Pass the tokenizer to `RiskSegmenter.__init__`; replace the word accumulator
   in `_split_into_chunks` with `len(tokenizer.encode(sentence, add_special_tokens=False))`.
4. Rebuild the annotation corpus from the new segmentation before G-16 test-split freeze.

Do NOT let `max_segment_words` and a tokenizer-based gate coexist — remove the
word-count proxy in the same PR as the Option B implementation.

---

## Supersedes

None. Implements the Option A phase of RFC-003.

---

## References

- `docs/architecture/rfc/RFC-003_segment_token_length_enforcement.md` — full option analysis
- `docs/requirements/stories/US-015_token_aware_truncation.md` — acceptance criteria
- `reports/word_count_dist.json` — full-corpus baseline measurement (607,463 segments)
- `thoughts/shared/research/2026-02-23_18-30-00_segment_strategy_classifier_input.md` — RQ-4 token budget analysis
- `src/preprocessing/segmenter.py` — `_split_long_segments` (trigger), `_split_into_chunks` (accumulator)
- `src/config/preprocessing.py:80-83` — `max_segment_words` field
- `configs/config.yaml:49` — `max_segment_words: 380`
