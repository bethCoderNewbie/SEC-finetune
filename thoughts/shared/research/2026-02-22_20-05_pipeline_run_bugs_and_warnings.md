---
title: "Pipeline Run: Bugs & Warnings — AAPL_10K_2021.html"
date: "2026-02-22T20:05:46-06:00"
commit: 15670ba
branch: main
author: claude-sonnet-4-6
file_under_test: data/raw/AAPL_10K_2021.html
command: python scripts/data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K_2021.html
---

# Pipeline Run: Bugs & Warnings

## Summary

Full pipeline was run against `AAPL_10K_2021.html`. Stages 1–4 (Parse → Extract → Clean → Segment)
complete successfully. Stage 5 (Sentiment) crashes with a `FileNotFoundError`. Two additional
warnings surfaced. One pending code health concern from unstaged diffs.

---

## Bug 1 (P0 — Crash): LM Dictionary Cache Missing

**Severity:** Fatal — pipeline exits with error code 1 when sentiment is enabled (default).

**Traceback path:**
```
scripts/data_preprocessing/run_preprocessing_pipeline.py:251 → run_pipeline()
  src/features/sentiment.py:326 → extract_features_batch()
  src/features/sentiment.py:256 → extract_features()
  src/features/sentiment.py:230 → count_category_words()
  src/features/sentiment.py:189 → dict_manager (lazy property)
  src/features/dictionaries/lm_dictionary.py:103 → load_dictionary()
  FileNotFoundError: Dictionary cache not found at
    /home/beth/work/SEC-finetune/data/dictionary/lm_dictionary_cache.pkl
```

**Root cause:** The `data/dictionary/` directory exists but is empty. The Loughran-McDonald
pickle cache has never been built on this machine. `LMDictionaryManager.load_dictionary()` at
`src/features/dictionaries/lm_dictionary.py:103` raises `FileNotFoundError` when the cache is absent.

**Fix:**
```bash
python scripts/feature_engineering/utils/preprocess_lm_dict.py
```

**Workaround (immediate):** Pass `--no-sentiment` to skip Stage 5.

---

## Warning 1 (P2): Unauthenticated HuggingFace Hub Requests

**Observed:**
```
Warning: You are sending unauthenticated requests to the HF Hub.
Please set a HF_TOKEN to enable higher rate limits and faster downloads.
```
Logged at: `src/preprocessing/segmenter.py` (SentenceTransformer load path).

**Root cause:** No `HF_TOKEN` environment variable is set. The model `all-MiniLM-L6-v2` is loaded
with HEAD requests to HF resolve-cache but without auth. Rate limits may cause intermittent
failures in CI or on repeated batch runs.

**Fix:** Set `export HF_TOKEN=<token>` in `.env` or shell profile. The model loads from local
cache after first download so this is low-risk in practice.

---

## Warning 2 (P3): Unexpected BERT Weight Key

**Observed:**
```
BertModel LOAD REPORT from: sentence-transformers/all-MiniLM-L6-v2
embeddings.position_ids | UNEXPECTED
```

**Root cause:** `embeddings.position_ids` is a buffer (not a trainable parameter) registered in
newer versions of `transformers` but absent in the checkpoint. This is a known cosmetic issue with
`all-MiniLM-L6-v2` and can be safely ignored. It does not affect model output quality.

**Fix:** None required. Can suppress by pinning `transformers` version or ignoring the load report.

---

## Observation 1 (P2): Cleaning Step Makes Zero Changes

**Observed:**
```
[3/5] Cleaning extracted text...
  [OK] Cleaned text from 66,278 to 66,278 characters
```

**Context:** `TextCleaner.clean_text(text, deep_clean=False)` is called at
`scripts/data_preprocessing/run_preprocessing_pipeline.py:192`. The input/output character count
is identical, meaning no normalization, whitespace collapsing, or page-number removal occurred.

**Expected behavior:** At minimum, `remove_page_numbers=True` (from `settings.preprocessing`)
should strip page-number lines from the extracted section.

**Possible cause:** sec-parser already strips formatting artifacts during extraction, leaving
`TextCleaner` with nothing to do. OR the cleaner's patterns do not match the text format produced
by `extract_risk_factors()`. Needs investigation.

**Impact:** Downstream segment quality may be degraded if residual page headers or noise remains
in the text passed to Stage 4. However, Stage 4 produced 136 segments at 485 avg chars, which
appears reasonable.

---

## Observation 2 (P3): Parser Reports Only 1 Section

**Observed:**
```
[OK] Found 1 sections
```

**Context:** `num_sections` in `src/preprocessing/parser.py:380` counts `TopSectionTitle`
instances. Finding only 1 in a 10-K with 67 elements suggests sec-parser is not recognizing
section boundaries in this HTML structure, OR AAPL's 2021 10-K wraps the entire text under a
single top-level element.

**Impact:** None on current extraction (Item 1A was found correctly with 6 subsections), but
may affect completeness metrics and any future multi-section extraction.

---

## Code Health: Unstaged Diffs

Two files have unstaged working-tree changes (`git status`):

### `src/preprocessing/extractor.py` (M)
- **Deleted** the `extract_risk_factors_from_dict()` method from `SECSectionExtractor` (~133 lines).
- **Added** a new `elements` filter on `TitleElement` nodes matching `PAGE_HEADER_PATTERN` at line
  ~372, so the saved JSON `elements` list is also clean (defensive fix).

### `scripts/data_preprocessing/batch_extract.py` (M)
- **Added** import of `PAGE_HEADER_PATTERN, SECTION_PATTERNS` from `constants.py`.
- **Added** standalone `_extract_risk_factors_from_dict(data, extractor)` function (~124 lines),
  migrating the dict-based extraction logic out of the class.
- **Updated** `extract_single_file` and `extract_single_file_fast` to call the new module-level
  function instead of `extractor.extract_risk_factors_from_dict()`.

These changes are internally consistent. The refactoring moves dict-based extraction to
`batch_extract.py` (the only consumer), reducing the surface area of `SECSectionExtractor`.
**Neither change is committed.** Commit when confident the refactoring is complete.

---

## Stage-by-Stage Result (with --no-sentiment)

| Stage | Status | Key Metric |
|-------|--------|------------|
| 1 Parse | OK | 67 elements, CIK=0000320193, SIC=3571 |
| 2 Extract | OK | 66,278 chars, 6 subsections, 66 elements |
| 3 Clean | OK (no-op) | 66,278 → 66,278 chars |
| 4 Segment | OK | 136 segments, avg 485 chars |
| 5 Sentiment | CRASH | FileNotFoundError: lm_dictionary_cache.pkl missing |

---

## Action Items

| Priority | Item | Fix |
|----------|------|-----|
| P0 | Build LM dictionary cache | `python scripts/feature_engineering/utils/preprocess_lm_dict.py` |
| P2 | Investigate cleaner no-op | Check `TextCleaner` patterns vs sec-parser output format |
| P2 | Set HF_TOKEN | Add to `.env` or shell profile |
| P3 | Commit or discard unstaged extractor refactoring | Review and commit if correct |
