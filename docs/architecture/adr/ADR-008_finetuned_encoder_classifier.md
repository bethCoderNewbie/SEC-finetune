# ADR-008: Fine-Tuned Encoder as Phase 2 Classifier Architecture

**Status:** Accepted
**Date:** 2026-02-20
**Author:** bethCoderNewbie

---

## Context

The pipeline must classify each `RiskSegment` into one of 9 archetype labels
(§2.2 of the SASB taxonomy research). Three classifier architectures were
evaluated against the operational constraints of this pipeline:

| Constraint | Source |
|:-----------|:-------|
| ≤ 1,000ms per segment on CPU | PRD-002 TR-07 |
| ~450,000 segments per annual EDGAR cohort | PRD-002 §2 |
| Output must conform to a controlled SASB vocabulary | PRD-002 §2.2 |
| Air-gapped / local deployment permitted | PRD-002 §4 |
| Single-contributor project; GPU not guaranteed at inference | PRD-002 §9 |

Three architectures were evaluated:

1. **API-hosted LLMs** (GPT-4o, Claude 3.5 Sonnet, Gemini 2.5 Pro) — zero-shot
   or few-shot prompted to emit a SASB topic label
2. **Local open-weight LLMs** (Llama 3.1 8B, Mistral 7B, Phi-4) — grammar-
   constrained generation (Outlines / llama.cpp GBNF) to enforce controlled
   vocabulary output; optionally fine-tuned via QLoRA
3. **Fine-tuned encoders** (FinBERT / DeBERTa-v3-base) — supervised fine-tuning
   on the 9-class archetype taxonomy using the annotated JSONL corpus

---

## Decision

Use a **fine-tuned encoder** (Phase 2 default: `ProsusAI/finbert`) for risk
segment classification. `microsoft/deberta-v3-base` is queued as a Phase 2
comparison experiment but is not the default; `src/config/models.py` is not
changed.

This decision applies to Phase 2 core pipeline classification only. Local LLMs
with grammar constraints and QLoRA fine-tuning are the designated Phase 3
candidate for the explainability use case (US-017), where generated rationale
per segment is required and GPU availability can be assumed.

### Failure modes that eliminated API LLMs

**Schema determinism:** When prompted to emit a SASB topic, API LLMs produce
free-text that does not conform to the `archetype_to_sasb.yaml` controlled
vocabulary. The same segment receives `"Cybersecurity & Data Security"` in one
run and `"Data Protection"` in another. At 450,000 segments per cohort, a 2%
schema-mismatch rate produces 9,000 unresolvable records — `GROUP BY` on
`sasb_topic` breaks peer comparison and TCFD mapping.

**CPU latency:** API LLMs add 1,500–4,000ms of network RTT per segment on top
of inference time. PRD-002 TR-07 requires ≤ 1,000ms on CPU. At 450,000 segments,
rate limits and per-token cost (~$0.004/segment for GPT-4o) make nightly EDGAR
batch runs uneconomical (~$1,800/yr variable cost, unbounded by cohort size).

**F1 accuracy:** Fine-tuned FinBERT achieves Macro F1 = 0.83 on S&P 100 10-K
Item 1A risk factors (Vo et al., SSRN 2025, 122,000 paragraphs). API LLMs in
zero-shot mode score 0.63–0.69. The 14–20 point gap is not closeable by prompt
engineering — it reflects the supervised learning advantage on domain-specific
edge cases.

### Failure mode that eliminated local LLMs for Phase 2

**CPU latency (hard wall):** Grammar-constrained generation resolves schema
determinism and air-gap concerns for local LLMs. It does not resolve CPU latency.
Autoregressive decoding for a 7B 4-bit quantised model on CPU runs at 4–8
tokens/second. A 50-token classification output takes 6–12 seconds — 8–15× over
TR-07. This is a decoding architecture constraint; it cannot be optimised away
for a CPU-only deployment target.

GPU inference (A10G) achieves 80–300ms for a 7B local LLM — within TR-07 — but
the project currently targets CPU-only deployment at inference time. GPU inference
remains viable for Phase 3 when the explainability use case (US-017) justifies
the hardware requirement.

### Why fine-tuned encoders satisfy all four constraints

| Constraint | Result |
|:-----------|:-------|
| Schema determinism | ✅ Always deterministic — softmax over fixed 9-class output |
| CPU latency (TR-07) | ✅ FinBERT ~800ms, DeBERTa-v3-base ~600ms on CPU |
| Macro F1 | ✅ 0.83 (fine-tuned FinBERT, domain benchmark) |
| RAM / deployment | ✅ ~450MB; no GPU required; air-gapped compatible |
| Parallel inference | ✅ Encoder forward passes are embarrassingly parallel; autoregressive decoding is sequential by design |

---

## Consequences

**Positive:**
- TR-07 CPU latency constraint is satisfied without GPU hardware
- Classification output is deterministic across runs — peer comparison,
  portfolio aggregation, and TCFD mapping all rely on stable label identity
- Single model trains once on the 9-class archetype taxonomy; works across
  all EDGAR SIC industries via the Layer 2 crosswalk (RFC-002 / ADR-009)
- 8GB consumer GPU sufficient for fine-tuning; inference requires no GPU
- Encoder forward passes parallelise across the existing worker pool (ADR-003)
  without coordination overhead

**Negative:**
- No generated rationale per segment — an analyst receives a label and
  confidence score but not a natural-language explanation of why the segment
  was classified as it was (US-017 explainability is deferred to Phase 3)
- Hard 512-token context limit for FinBERT and DeBERTa-v3-base; segments
  exceeding ~390 words are truncated. If >5% of corpus segments exceed this
  threshold after PRD-003 cleanup, evaluate ModernBERT (8,192-token context)
  as a Phase 2 alternative (PRD-002 OQ-3, now resolved in research §7)
- Fine-tuning requires annotated training data — the 4,500-example corpus
  (500 per class × 9 classes) defined in the SASB research §5.3 must exist
  before fine-tuning can begin; the zero-shot path from RFC-001 Q3 is the
  interim production state
- QLoRA fine-tuning of a 7B local LLM (Phase 3) achieves an estimated 0.75–0.80
  Macro F1 — a 3–8 point deficit vs. this decision's FinBERT baseline — which
  must be accepted as a Phase 3 trade-off for generated rationale capability

## Supersedes

Zero-shot `facebook/bart-large-mnli` as the interim production classifier
(RFC-001 Q3, Option A). The encoder becomes the production classifier upon
completion of the annotated training corpus (US-031) and fine-tuning run.

## References

- `thoughts/shared/research/2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md`
  §1.4 — full three-architecture comparison with failure mode analysis
- `src/config/models.py` — `default_model = "ProsusAI/finbert"` (unchanged)
- `src/analysis/inference.py:15` — current zero-shot `bart-large-mnli` classifier
- Vo et al., *ESG Risk Classification in 10-K Filings: Benchmarking FinBERT
  and LLMs*, SSRN 2025 — domain F1 benchmark source
- PRD-002 §4.1, TR-07 — CPU latency and deployment constraints
- RFC-001 Q3 — interim zero-shot model selection
- RFC-002 — SASB two-layer schema decisions (ADR-009 pending)
