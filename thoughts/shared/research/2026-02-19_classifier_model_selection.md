---
title: "Classifier Model Selection — FinBERT Alternatives for 10-K Risk Factor Classification"
date: 2026-02-19
author: beth88.career@gmail.com
git_sha: 3e1075ad3bfd72060391d5f34a970b86fa70d186
branch: main
related_prd: PRD-004_Business_Intelligence_Use_Cases.md
decision_needed_by: Phase 2 start (fine-tuned classifier)
status: RESEARCH — decision pending
---

# Classifier Model Selection — FinBERT Alternatives

## 1. Problem Statement

PRD-004 §4.2 specifies FinBERT as the base model for the fine-tuned 9-class risk classifier
(`src/inference/classifier.py`, Phase 2). This research evaluates whether a better base model
exists for the specific task: **multi-class text classification of SEC 10-K Item 1A risk factor
segments into 9 mutually exclusive categories**.

**Clarification on the PRD-003 "table limitation":**
FinBERT's known difficulty with tabular text is irrelevant at inference time. PRD-003 Fixes 2A
and 2B strip all `TableElement` and `TableOfContentsElement` nodes before segmentation. By the
time any classifier sees a segment, it is clean prose. The real limitation that persists is
FinBERT's **512-token context window**.

---

## 2. Task Constraints

These constraints from PRD-004 bound the model choice:

| Constraint | Value | Source |
|:-----------|:------|:-------|
| Classification type | Single-label, 9 classes | PRD-004 §3.2 |
| Input unit | One `RiskSegment.text` string | `segmentation.py:18` |
| Expected segment length | 50–250 words (post-PRD-003 cleanup) | Observed corpus |
| CPU inference ceiling | ≤ 1,000ms per segment (TR-07) | PRD-004 §9 |
| Macro F1 minimum (Phase 2 gate) | 0.72 | PRD-004 §4.3, §5 Phase 2 |
| Macro F1 target (v0.4.0 release) | ≥ 0.80 | PRD-004 §4.3 |
| Training data | ≥ 500 human-reviewed segments per non-`other` category | PRD-004 §5 Phase 1 gate |
| Training infrastructure | Single contributor; local GPU optional | Project context |
| HuggingFace Trainer | Required — `scripts/training/finetune.py` uses it | PRD-004 §5 Phase 2 |

**512-token reality check:** At 250 words × ~1.3 tokens/word average, segments reach ~325
tokens — safely within the 512-token limit. Truncation becomes a risk only for outlier segments
> 390 words. PRD-003 does not enforce a word-count ceiling, so a small fraction of segments
may exceed 512 tokens.

---

## 3. Models Evaluated

### 3.1 FinBERT (current PRD-004 default)

- **Checkpoint:** `ProsusAI/finbert` (HuggingFace)
- **Pretraining corpus:** 4.9B tokens from Reuters TRC2, Financial PhraseBank, and SEC filings
- **Context:** 512 tokens
- **Parameters:** 110M
- **Architecture:** BERT-base

**Evidence:** 2025 SSRN study classifying ESG risks in 10-K Item 1A paragraphs from S&P 100
(122,000 paragraphs, 2012–2022, same domain as this project) — fine-tuned FinBERT achieved
**83% Macro F1**, outperforming GPT-4o (67%), Claude 3.5 Sonnet (69%), Grok 3 (64%), and
Gemini 2.5 Pro (63%). Human LLM agreement was only moderate; FinBERT was the most consistent.

**Limitation for this project:** BERT's disentangled attention is weaker than DeBERTa-v3's for
classification. Financial domain pretraining helps but does not compensate for architectural
inferiority on pure classification tasks. Fine-tuning on the annotated corpus provides domain
signal regardless of the base model.

---

### 3.2 DeBERTa-v3-base ✅ Recommended

- **Checkpoint:** `microsoft/deberta-v3-base` (HuggingFace)
- **Warm-start option:** `nickmuchi/deberta-v3-base-finetuned-finance-text-classification`
- **Context:** 512 tokens
- **Parameters:** 86M (base) / 183M (large)
- **Architecture:** DeBERTa-v3 — disentangled attention + replaced token detection objective

**Why it beats FinBERT for this task:**
- Disentangled attention separately encodes content and positional information, improving
  classification of semantically similar categories (e.g., `regulatory` vs. `financial`)
- Consistently outperforms BERT-family models on GLUE/SuperGLUE by 3–5 F1 points
- The financial warm-start checkpoint (`nickmuchi/`) reduces the cold-start gap from no
  domain pretraining

**Code impact:** One-line change in `scripts/training/finetune.py`:
```python
# Before
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert", ...)
# After
model = AutoModelForSequenceClassification.from_pretrained("microsoft/deberta-v3-base", ...)
```

**CPU inference:** DeBERTa-v3-base at 86M params is faster than FinBERT at 110M. TR-07
(≤ 1,000ms/segment CPU) is achievable.

---

### 3.3 ModernBERT-base (contingency if truncation observed)

- **Checkpoint:** `answerdotai/ModernBERT-base` (HuggingFace)
- **Released:** December 2024
- **Context:** **8,192 tokens** — eliminates truncation entirely
- **Parameters:** 149M
- **Architecture:** Flash attention 2, rotary positional embeddings, alternating local/global attention

**Why it matters here:** If post-PRD-003 corpus analysis shows a material fraction of segments
exceeding 400 words, ModernBERT removes truncation as a confound. It is 2–4× faster than
BERT-family at inference, which makes TR-07 trivially satisfied.

**Trade-off:** Released December 2024 — less community validation on financial classification
specifically. No financial domain pretraining. Treat as the contingency path, not the default.

**Trigger condition for switching:** If > 5% of corpus segments exceed 390 words after
PRD-003 cleanup, switch to ModernBERT-base.

---

### 3.4 Longformer / BigBird (rejected)

- **Context:** 4,096 tokens
- **Architecture:** Sparse attention

**Rejected because:** Designed for document-level tasks (full filing, entire contract). This
project segments filings into paragraph-level units before classification — the long-context
advantage does not apply. Adds 4× training complexity for no benefit on paragraph inputs.

---

### 3.5 BloombergGPT / FinGPT / Decoder LLMs (rejected)

**Rejected because:** Generative (decoder) architectures are inefficient for single-label
classification. Fine-tuning cost is 10–50× higher. CPU inference at ≤ 1,000ms per segment
(TR-07) is not achievable. The SSRN benchmark confirms fine-tuned encoders outperform GPT-4
class models on this exact task type at 83% vs. 59–69% Macro F1.

---

## 4. Comparison Matrix

| Model | Context | Params | Financial Pretrain | Est. F1 Lift vs. FinBERT | CPU Inference | Recommended |
|:------|:--------|:-------|:------------------|:------------------------|:--------------|:------------|
| FinBERT (current) | 512 | 110M | ✅ SEC filings | baseline | ~800ms/seg | ❌ |
| **DeBERTa-v3-base** | 512 | 86M | Warm-start available | **+3–5 F1 pts** | ~600ms/seg | ✅ Default |
| ModernBERT-base | 8,192 | 149M | ❌ | +3–5 F1 pts (estimated) | ~300ms/seg | ✅ Contingency |
| Longformer | 4,096 | 149M | ❌ | neutral | ~900ms/seg | ❌ |
| DeBERTa-v3-large | 512 | 400M | Warm-start available | +5–8 F1 pts | >1,000ms/seg | ❌ (TR-07 risk) |
| BloombergGPT | varies | 50B | ✅ | −14–24 F1 pts (benchmark) | ❌ | ❌ |

---

## 5. Experiment Plan

Before committing the Phase 2 model choice in PRD-004 and ADR, run the following experiments
after Phase 1 annotation is complete (≥ 500 segments per non-`other` category available):

### Experiment A — Truncation Audit (run first, before any training)

```bash
# Count segments exceeding 390 words in the post-PRD-003 corpus
python -c "
import json, glob
over = 0; total = 0
for f in glob.glob('data/processed/*/segmented/*.json'):
    d = json.load(open(f))
    for seg in d.get('segments', []):
        total += 1
        if seg['word_count'] > 390:
            over += 1
print(f'Over-390-word segments: {over}/{total} ({100*over/total:.1f}%)')
"
```

**Decision gate:** If > 5% → use ModernBERT-base. If ≤ 5% → use DeBERTa-v3-base.

### Experiment B — Baseline F1 Comparison (after Phase 1 annotation complete)

Train three models on identical 80/10/10 train/val/test splits. Report to
`reports/classifier_eval.json` (TR-14):

| Run | Base model | Expected outcome |
|:----|:-----------|:----------------|
| B-1 | `ProsusAI/finbert` | Macro F1 ~0.72–0.80 (PRD-004 gate reference) |
| B-2 | `microsoft/deberta-v3-base` | Macro F1 ~0.75–0.83 |
| B-3 | `nickmuchi/deberta-v3-base-finetuned-finance-text-classification` | Macro F1 ~0.77–0.85 |

Keep whichever clears 0.80 target with lowest inference time. If none clear 0.80, run B-4
with `answerdotai/ModernBERT-base`.

### Experiment C — Confidence Threshold Calibration (QR-03)

After training the winning model, calibrate the `confidence < 0.70 → other` routing rule
(QR-03, PRD-004 §4.3) on the validation set:

```python
# Sweep thresholds 0.60–0.85 in 0.05 steps
# Report: precision on 7 non-other categories vs. coverage (% routed to other)
# Target: ≥ 0.80 precision on retained predictions at the chosen threshold
```

---

## 6. Required PRD-004 Update

**File:** `docs/requirements/PRD-004_Business_Intelligence_Use_Cases.md`
**Section:** §4.2 Components table, Fine-tuned risk classifier row

Current text:
> Wrap fine-tuned FinBERT on 9-class PRD-004 taxonomy

Proposed update:
> Base model: `microsoft/deberta-v3-base` (default) or `answerdotai/ModernBERT-base`
> (contingency if > 5% of segments exceed 390 words — see Experiment A). FinBERT is
> used only for zero-shot seed predictions in Phase 1 (`src/analysis/inference.py`).

**File:** `docs/architecture/adr/` — **ADR-008 required** after Experiment B completes,
recording which model was chosen and the empirical F1 results that justified the decision.

---

## 7. Open Questions

| # | Question | Blocks | Decision By |
|:--|:---------|:-------|:------------|
| OQ-01 | What fraction of post-PRD-003 segments exceed 390 words? Determines DeBERTa-v3 vs. ModernBERT. | Experiment A | Before Phase 2 start |
| OQ-02 | Does the financial warm-start checkpoint (`nickmuchi/`) measurably improve F1 vs. `microsoft/deberta-v3-base` cold? Determines whether warm-start is worth the extra dependency. | Experiment B | Phase 2 |
| OQ-03 | At what confidence threshold does precision on retained (non-`other`) predictions reach ≥ 0.80? The 0.70 floor in QR-03 is assumed — empirical calibration may revise it. | Experiment C | Phase 2 eval |
| OQ-04 | DeBERTa-v3-base CPU inference at ≤ 1,000ms/segment on the project machine: confirm before finalising TR-07. | TR-07 compliance | Phase 2 smoke test |

---

## 8. References

- [ESG Risk Classification in 10-K Filings: Benchmarking Finbert and LLMs — Vo et al., SSRN 2025](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5387933)
- [nickmuchi/deberta-v3-base-finetuned-finance-text-classification — Hugging Face](https://huggingface.co/nickmuchi/deberta-v3-base-finetuned-finance-text-classification)
- [ModernBERT: Finally a Replacement for BERT — Hugging Face Blog, Dec 2024](https://huggingface.co/blog/modernbert)
- [Fine-tune classifier with ModernBERT in 2025 — philschmid.de](https://www.philschmid.de/fine-tune-modern-bert-in-2025)
- [FinBERT vs FinGPT vs FinLLM — Technical Comparison 2025](https://blogg.fsh.se/2025/11/17/finbert-vs-fingpt-vs-finllm-a-technical-comparison-for-2025/)
- [Long Document Classification in the Transformer Era: Survey — Wiley WIREs 2025](https://wires.onlinelibrary.wiley.com/doi/full/10.1002/widm.70019)
- [DeBERTa: Decoding-enhanced BERT with Disentangled Attention — Microsoft Research](https://github.com/microsoft/DeBERTa)
- [Towards Efficient FinBERT via Quantization and Coreset — ACL FinNLP 2025](https://aclanthology.org/2025.finnlp-2.6.pdf)
