---
date: 2026-08-14T14:55:44-05:00
git_commit: dfdb43e
branch: main
repository: SEC-finetune
researcher: bethCoderNewbie
topic: TF-IDF Noise Reduction for SEC 10-K Keyword Extraction
status: IMPLEMENTED
---

# TF-IDF Noise Reduction for SEC 10-K Keyword Extraction

## Problem Statement

After ADR-022 added ~30 finance-domain stopwords and a numeric token filter, the
TF-IDF keyword extractor still surfaces SEC boilerplate phrases as high-scoring
keywords. Terms like "forward looking", "safe harbor", "actual results", and
"risk factors" appear in nearly every 10-K filing and carry zero discriminating
signal, yet they dominate keyword lists because (a) they are repeated across
multiple sections (safe harbor disclaimer in Item 1A, Item 7, Item 7A), and
(b) the IDF corpus is only 4-8 sections of a single filing.

## Root Cause Analysis

Four gaps identified:

### Gap 1: Missing SEC Boilerplate Phrases

The `finance_terms` stopword list (28 single words) does not cover multi-word
SEC boilerplate. Since `TfidfVectorizer` uses `ngram_range=(1,2)`, bigrams like
"forward looking" and "safe harbor" surface as high-scoring keywords.

- **Working path:** `configs/features/investment.yaml:57-92` (stopwords section)
- **Broken path:** No bigram stopwords existed. Only unigrams were filtered.

### Gap 2: No Sublinear TF Scaling

`TfidfVectorizer` defaults to raw term frequency. Boilerplate paragraphs that
repeat the same phrases get linearly inflated TF weights. Setting
`sublinear_tf=True` uses `1 + log(tf)` which compresses repeated terms.

- **Working path:** `src/features/investment/keyword_extractor.py:55-61` (fit_tfidf vectorizer)
- **Broken path:** `sublinear_tf` was not set (defaults to `False`).

### Gap 3: Small IDF Corpus

The vectorizer fits on 4-8 sections of a single filing, making IDF nearly
meaningless. A term appearing in 3/6 documents gets `log(6/3) = 0.3` — minimal
dampening. Cross-filing IDF would fix this architecturally but requires
persistent vectorizer infrastructure that doesn't exist.

- **Mitigation:** Better stopwords + sublinear TF. Cross-filing IDF is future work.

### Gap 4: Missing Loughran-McDonald-Informed Terms

The pipeline uses L-M sentiment dictionaries for ratio computation
(`sentiment_ensemble.py`) but doesn't leverage L-M stopword insights for TF-IDF.
Terms like "fiscal year ended", "annual report", "exchange commission" are generic
across all 10-Ks and should be suppressed.

## Literature References

- Loughran & McDonald (2016), "Textual Analysis in Accounting and Finance: A Survey",
  *Journal of Accounting Research* — recommends domain-specific stopword lists for
  financial text mining; generic English stopwords miss SEC-specific boilerplate.
- Loughran & McDonald (2011), "When is a Liability not a Liability?", *The Journal
  of Finance* — established that general-purpose sentiment dictionaries misclassify
  financial terms; same principle applies to stopwords.
- SRAF Master Dictionary & Stopword Lists (sraf.nd.edu) — provides curated financial
  stopword lists. Full list is ~4,000 terms; we cherry-pick the SEC-filing subset.

## Solution Implemented

### Phase 1: Expanded Stopword Lists

**Tier A — Hardcoded in `StopwordsConfig.finance_terms`** (zero ambiguity):

Added 22 terms to `configs/features/investment.yaml:57+` and
`src/config/features/investment.py:21+`:

- 14 SEC boilerplate bigrams: "forward looking", "looking statements",
  "safe harbor", "actual results", "differ materially", "risk factors",
  "annual report", "exchange commission", "securities exchange", "exchange act",
  "fiscal year", "year ended", "incorporated herein", "common stock"
- 8 SEC structural unigrams: "registrant", "exhibit", "filing", "securities",
  "commission", "annual", "report", "described"

**Tier B — Configurable extras in `tfidf_finance_stopwords`** (ambiguous terms):

Populated the previously-empty `tfidf_finance_stopwords` list in
`configs/features/investment.yaml:12` with 13 broader terms: "business",
"market", "management", "discussion", "analysis", "significant", "material",
"applicable", "including", "certain", "respect", "following", "general".

These are merged into the stopword list by existing infrastructure in
`keyword_extractor.py:45-46`.

### Phase 2: Sublinear TF Scaling

Added `sublinear_tf=True` to both `TfidfVectorizer` instantiations in
`src/features/investment/keyword_extractor.py:55-62` and `:169-176`.

Made configurable via `tfidf_sublinear_tf` field:
- `configs/features/investment.yaml` — `tfidf_sublinear_tf: true`
- `src/config/features/investment.py` — `InvestmentConfig.tfidf_sublinear_tf`

## Files Modified

| File | Change |
|------|--------|
| `configs/features/investment.yaml` | +22 stopwords to `finance_terms`, +13 configurable extras to `tfidf_finance_stopwords`, +`tfidf_sublinear_tf: true` |
| `src/config/features/investment.py` | Updated `StopwordsConfig.finance_terms` defaults, added `tfidf_sublinear_tf` field |
| `src/features/investment/keyword_extractor.py` | Added `sublinear_tf=self._config.tfidf_sublinear_tf` to both vectorizer instantiations |

## Anti-Scope

- Cross-filing IDF infrastructure (persistent vectorizer, multi-filing fitting)
- KeyBERT changes (uses its own embeddings, unaffected by TF-IDF stopwords)
- Cross-section overlap logic changes (consumes keyword output; cleaner keywords improve Jaccard naturally)
- Full L-M stopword CSV import (~4,000 terms would over-filter)
