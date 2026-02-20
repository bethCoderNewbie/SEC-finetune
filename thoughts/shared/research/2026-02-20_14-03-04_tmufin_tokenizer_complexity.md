---
title: "T-MuFin Tokenizer — Complexity Analysis for SEC 10-K Risk Classifier"
date: 2026-02-20
author: beth88.career@gmail.com
git_sha: 5476f84b48de41dccb2426efef07ccd143019fae
branch: main
related_prd: docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md
related_rfc: docs/architecture/rfc/RFC-003_segment_token_length_enforcement.md
related_research: thoughts/shared/research/2026-02-19_14-22-00_classifier_model_selection.md
status: RESEARCH — decision pending
decision_needed_by: Phase 2 model selection (Experiment B)
---

# T-MuFin Tokenizer — Complexity Analysis for SEC 10-K Risk Classifier

## 1. What Is T-MuFin

**Full title:** "Reducing tokenizer's tokens per word ratio in Financial domain with
T-MuFin BERT Tokenizer"
**Authors:** Braulio Blanco Lambruschini, Patricia Becerra-Sanchez, Mats Brorsson,
Maciej Zurad
**Venue:** Fifth Workshop on Financial Technology and NLP (FinNLP + Muffin),
ACL 2023, Macao, pp. 94–103
**Source:** https://aclanthology.org/2023.finnlp-1.9.pdf

T-MuFin (Term-Based Multilingual Financial BERT) modifies BERT's default WordPiece
tokenizer by injecting high-frequency financial n-gram terms as single vocabulary
entries, reducing *fertility* — the average number of sub-word tokens produced per
word. A lower fertility means more content fits within a fixed token budget (e.g. 512
tokens for FinBERT / DeBERTa-v3-base).

---

## 2. Core Mechanism

### 2.1 The Fertility Problem

Standard WordPiece tokenization fragments multi-word financial terms:

| Surface form | WordPiece tokens | Token count |
|:-------------|:-----------------|:------------|
| `collateralized` | `["col", "##later", "##alized"]` | 3 |
| `earnings per share` | `["earnings", "per", "share"]` | 3 |
| `item 1a risk factors` | `["item", "1", "##a", "risk", "factors"]` | 5 |
| `collateralized debt obligation` | `["col","##later","##alized","debt","ob","##ligation"]` | 6 |

SEC 10-K Item 1A prose is dense with exactly this class of multi-word expressions.
With FinBERT's default vocabulary, fertility for financial text is approximately
1.2–1.5 tokens/word. At 390 words, a segment reaches ~512–585 tokens — straddling
or exceeding the model's hard limit.

### 2.2 N-gram Extraction

Domain-specific terms are extracted from a financial corpus via n-gram frequency
analysis:

1. Tokenise the corpus at the word level (not sub-word).
2. Count bigram and trigram frequencies across all documents.
3. Threshold by minimum frequency (paper uses corpus-specific cutoffs).
4. Filter against a stop-list to remove generic n-grams (`"the risk"`, `"we may"`).
5. Output: a ranked list of financial multi-word terms.

For this project the extraction corpus would be `RiskSegment.text` fields from
`data/processed/**/*_segmented_risks.json`.

### 2.3 Vocabulary Injection

Extracted terms are added to the BERT tokenizer vocabulary using HuggingFace's
`add_tokens()` API:

```python
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
new_terms = ["collateralized_debt_obligation", "item_1a_risk_factors", ...]
tokenizer.add_tokens(new_terms)
model.resize_token_embeddings(len(tokenizer))
```

`resize_token_embeddings()` appends new rows to the model's token embedding matrix.
These new rows are **randomly initialised by default** — the model has no prior
signal for the new tokens until fine-tuning shapes them.

**Better practice — averaged sub-token initialisation:** Before discarding the old
tokenizer, compute the mean of each new term's constituent sub-token embeddings and
use that as the initialisation vector. Gives the model a meaningful starting point
derived from the representations it already has for the component pieces.

```python
# For each new term, average its constituent sub-token embeddings
with torch.no_grad():
    for i, term in enumerate(new_terms):
        sub_ids = old_tokenizer.encode(term, add_special_tokens=False)
        avg_emb = model.embeddings.word_embeddings.weight[sub_ids].mean(dim=0)
        new_idx = len(old_vocab) + i
        model.embeddings.word_embeddings.weight[new_idx] = avg_emb
```

---

## 3. Relationship to RFC-003 (Segment Token Length Enforcement)

T-MuFin and RFC-003 attack the same 512-token problem from opposite directions and
are **complementary, not alternatives**:

| Approach | Mechanism | When applied |
|:---------|:----------|:-------------|
| RFC-003 Option A (word-count ceiling) | Split segment before it hits the tokenizer | Preprocessing |
| RFC-003 Option B (tokenizer-aware split) | Count exact tokens at split boundary | Preprocessing |
| T-MuFin | Reduce tokens-per-word so more text fits within the limit | Tokenizer / model layer |

T-MuFin does not eliminate the need for RFC-003. A 600-word paragraph tokenised at
1.0 tokens/word (best case with aggressive n-gram injection) is still 600 tokens —
over the limit. T-MuFin makes RFC-003's ceiling more **forgiving**: if fertility
drops from 1.35 to ~1.2 tokens/word, the safe word-count ceiling rises from 380
words to approximately 425 words, reducing how aggressively long segments are split.

**Dependency order:**
RFC-003 Option A must be implemented first (no blockers, low complexity). T-MuFin
vocabulary injection is a Phase 2 enhancement layered on top once the corpus and
annotation work (G-15, G-16) are further along.

---

## 4. Complexity Breakdown

### Step 1 — N-gram extraction from EDGAR corpus

| Item | Detail |
|:-----|:-------|
| Input | `data/processed/**/*_segmented_risks.json` → `.segments[].text` |
| Method | Bigram + trigram frequency count; frequency threshold; financial stop-list |
| Output | `src/analysis/taxonomies/financial_terms.txt` (candidate list) |
| Complexity | **Medium** |
| Blocker | OQ-T1 open — current corpus is AAPL-heavy; n-gram term set will be SIC-skewed until the full stratified corpus (G-01: ≥ 30 filings, ≥ 5 SIC sectors) is assembled. Running extraction before that produces a biased vocabulary. |

### Step 2 — Vocabulary injection

| Item | Detail |
|:-----|:-------|
| Code | `tokenizer.add_tokens()` + `model.resize_token_embeddings()` + averaged sub-token init (~30 lines) |
| Complexity | **Medium** |
| Blocker | None — can be prototyped once Step 1 output exists |
| Risk | Random embedding init (if sub-token averaging is skipped) produces meaningless representations until fine-tune reshapes them. Averaged init is strongly preferred. |

### Step 3 — Continued MLM pretraining (optional)

| Item | Detail |
|:-----|:-------|
| Purpose | Give new token embeddings real distributional signal via masked language modelling on the EDGAR corpus before classifier fine-tuning |
| Complexity | **High** — requires GPU time; requires full EDGAR corpus (G-01 not yet at scale) |
| Recommendation | **Defer to Phase 3.** The annotation corpus (G-16) does not yet exist; fine-tuning signal alone is sufficient for Phase 2 classification. MLM pretraining compounds accuracy but is not a Phase 2 blocker. |

### Step 4 — Tokenizer co-versioning through the pipeline

This is the highest hidden complexity cost. The custom tokenizer must be consistent
at every point the model is used:

| Location | Change required |
|:---------|:----------------|
| `src/analysis/inference.py` | Load custom T-MuFin tokenizer instead of `ProsusAI/finbert` default |
| `scripts/training/finetune.py` | Same |
| `src/preprocessing/segmenter.py` | If RFC-003 Option B is active, segmenter's tokenizer must be the T-MuFin tokenizer |
| `src/models/registry/` (`ModelRegistry`) | Checkpoint **and** tokenizer must be co-versioned; loading a checkpoint with a mismatched tokenizer silently corrupts embedding lookups |

Complexity: **Medium**. Not high in code volume, but a co-versioning discipline
violation (old tokenizer + new checkpoint) produces silent wrong outputs with no
error. Must be enforced in `ModelRegistry`.

---

## 5. Full Complexity Summary

| Phase | Work item | Complexity | Blocked by |
|:------|:----------|:-----------|:-----------|
| Now | RFC-003 Option A word-count ceiling | **Low** | Nothing |
| Phase 2 | Corpus SIC audit (OQ-T1) | Low | — |
| Phase 2 | N-gram extraction on stratified corpus | **Medium** | OQ-T1 (corpus coverage) |
| Phase 2 | `add_tokens()` + averaged sub-token init | **Medium** | Step above |
| Phase 2 | Tokenizer co-versioning in `ModelRegistry` | **Medium** | G-12 classifier integration |
| Phase 2 | Experiment B comparison: T-MuFin vs. vanilla DeBERTa | Medium | G-16 annotation corpus |
| Phase 3 | Continued MLM pretraining on EDGAR corpus | **High** | Full corpus + GPU |

**Net assessment:** T-MuFin vocabulary injection is **Medium overall complexity** for
Phase 2 if MLM pretraining is deferred. The tokenizer coupling to `ModelRegistry` is
the principal operational risk.

---

## 6. Recommended Integration Path

1. **Now (no blockers):** Implement RFC-003 Option A (word-count ceiling, 380 words).
   Closes US-015 immediately.

2. **Phase 2, after OQ-T1 resolved:** Run n-gram frequency extraction on the
   stratified corpus. Produce `financial_terms.txt`. Review manually to cull noise
   before injection.

3. **Phase 2, Experiment B:** Fine-tune three variants on identical 80/10/10 splits:
   - B-1: `ProsusAI/finbert` (baseline)
   - B-2: `microsoft/deberta-v3-base` (model selection research recommendation)
   - B-3: FinBERT + T-MuFin vocabulary injection (averaged sub-token init)

   Report Macro F1 and P95 inference latency for each. T-MuFin adds value only if
   B-3 measurably outperforms B-1 — the fertility reduction must translate to F1
   improvement on the 9-class task to justify the co-versioning overhead.

4. **Phase 2, after winning model selected:** Enforce tokenizer co-versioning in
   `ModelRegistry`. Update RFC-003 Option B to use the T-MuFin tokenizer for exact
   token-aware splits in `RiskSegmenter`. Write ADR-008 recording the model +
   tokenizer decision with empirical results.

5. **Phase 3 (optional):** If B-3 wins Experiment B and the full EDGAR corpus is
   assembled, run continued MLM pretraining to mature the new token embeddings.
   Re-run Experiment B with the pretrained checkpoint and compare.

---

## 7. Open Questions

| # | Question | Owner | Blocks |
|:--|:---------|:------|:-------|
| OQ-TM-1 | What fertility does FinBERT achieve on the current EDGAR corpus? Run `tokenizer.encode(segment)` on all segments and compute `tokens / words`. Determines how much headroom T-MuFin actually buys. | ML Engineer | N-gram threshold selection |
| OQ-TM-2 | How many financial terms does the EDGAR corpus yield above a practical frequency threshold (e.g., ≥ 50 occurrences)? Determines vocabulary expansion size and whether the embedding matrix growth is material. | Data Eng | Step 1 |
| OQ-TM-3 | Does averaged sub-token initialisation measurably improve Macro F1 on the validation set vs. random initialisation for this vocabulary size? | ML Engineer | Experiment B |
| OQ-TM-4 | Should `financial_terms.txt` be checked into `src/analysis/taxonomies/` alongside `sasb_sics_mapping.json` and `archetype_to_sasb.yaml`? Ensures reproducibility of tokenizer construction but adds a versioned artefact dependency. | ML Engineer | ModelRegistry design |

---

## 8. References

- [T-MuFin — "Reducing tokenizer's tokens per word ratio in Financial domain", ACL FinNLP 2023](https://aclanthology.org/2023.finnlp-1.9.pdf)
- [Classifier model selection research (FinBERT vs DeBERTa vs ModernBERT)](thoughts/shared/research/2026-02-19_14-22-00_classifier_model_selection.md)
- [RFC-003 — Segment Token Length Enforcement](docs/architecture/rfc/RFC-003_segment_token_length_enforcement.md)
- [HuggingFace `add_tokens()` docs](https://huggingface.co/docs/transformers/main_classes/tokenizer)
- [PRD-002 §4.1 — Training pipeline and model selection](docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md)
