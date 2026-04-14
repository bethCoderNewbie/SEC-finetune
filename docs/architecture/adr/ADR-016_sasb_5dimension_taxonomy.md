# ADR-016: Replace 9-Class Archetype Taxonomy with SASB 5-Dimension 6-Class Schema

**Status:** Accepted
**Date:** 2026-03-11
**Author:** bethCoderNewbie
**Supersedes:** ADR-008 (label taxonomy only — fine-tuned encoder architecture decision stands)

---

## Context

ADR-008 decided to use a fine-tuned encoder over a 9-class archetype taxonomy
(`cybersecurity`, `regulatory`, `financial`, `supply_chain`, `market`, `esg`,
`macro`, `human_capital`, `other`). Validation of that taxonomy against the
official SASB Conceptual Framework identified three structural defects:

1. **`esg` collapses 7 SASB General Issue Categories into one bucket.** The
   SASB Conceptual Framework distributes environmental topics across the
   Environment dimension (GHG, Air Quality, Energy, Water, Waste, Ecological
   Impacts) and the Business Model and Innovation dimension (Physical Impacts of
   Climate Change, Materials). A single `esg` class produces incorrect crosswalk
   outputs — an environmental compliance segment and a water-use segment receive
   the same label but should resolve to different SASB topics.

2. **`macro` and `financial` have no SASB home.** Every SASB topic belongs to
   one of the five sustainability dimensions. Macro-economic and pure financial
   risk disclosures (interest rate, credit, liquidity) are not covered by any
   SASB General Issue Category. Under the 9-class schema, these two classes
   always produce `null` `sasb_topic` — making them useless for the Layer 2
   crosswalk that is the primary output of the classification pipeline.

3. **Class names are poor NLI candidates.** BART zero-shot (the interim
   production classifier per RFC-001 Q3) reasons over natural-language
   hypotheses. Abbreviations like `esg`, `macro`, and underscore-joined strings
   like `supply_chain` produce weaker NLI hypotheses than SASB's own dimension
   labels ("business model and innovation", "leadership and governance"), which
   appear verbatim in SASB documentation.

---

## Decision

Replace the 9-class taxonomy with 6 classes aligned to SASB's five sustainability
dimensions, plus `other` for content with no SASB home.

### Label map (`ARCHETYPE_LABEL_MAP`)

| Code | Int | NLI display name | ADR-008 classes subsumed |
|:-----|:----|:-----------------|:-------------------------|
| `environment` | 0 | "environment" | `esg` (partial), `market` (partial — commodity/GHG) |
| `social_capital` | 1 | "social capital" | `cybersecurity`, `esg` (partial) |
| `human_capital` | 2 | "human capital" | `human_capital` |
| `business_model` | 3 | "business model and innovation" | `supply_chain`, `esg` (partial) |
| `governance` | 4 | "leadership and governance" | `regulatory`, `esg` (partial) |
| `other` | 5 | "other" | `macro`, `financial`, residual `market` |

### Two-name design

Snake_case codes are used in all output artefacts (`risk_label`, JSONL records,
`ARCHETYPE_LABEL_MAP` keys). Human-readable display names are passed to the BART
NLI pipeline at classification time. A module-level `_NLI_LABEL_TO_CODE` reverse
map converts BART responses back to snake_case codes before scoring.

This separation keeps output identifiers stable and machine-readable while
improving zero-shot NLI quality — the display name "leadership and governance"
is a better NLI hypothesis candidate than the output code "governance".

### Governing rules

- `ARCHETYPE_LABEL_MAP` has exactly 6 keys. Adding a new class requires a
  superseding ADR.
- `_NLI_CANDIDATE_NAMES` is always derived from `_ARCHETYPE_DISPLAY_NAMES` in
  declaration order — never edited directly.
- `_NLI_LABEL_TO_CODE` is always derived from `_ARCHETYPE_DISPLAY_NAMES` — never
  edited directly.
- `archetype_to_sasb.yaml` crosswalk uses the same snake_case codes as top-level
  keys. The `other` dimension maps to `{}` (no crosswalk; `_crosswalk_sasb()`
  returns `None`).

---

## Consequences

**Positive:**
- The `esg` catch-all bucket is eliminated. Every segment classified as
  `environment`, `social_capital`, `business_model`, or `governance` can resolve
  to a specific SASB General Issue Category via `archetype_to_sasb.yaml`.
- `_crosswalk_sasb()` now produces non-null `sasb_topic` for all five SASB
  dimensions. Only `other` returns `None`.
- NLI zero-shot quality improves. "business model and innovation" and "leadership
  and governance" are recognised phrases in ESG literature; BART's NLI prior
  aligns with them more reliably than with `esg`, `macro`, or `supply_chain`.
- `_ANCESTOR_ARCHETYPE_PRIOR` and `_HEURISTIC_KEYWORDS` are updated to use new
  codes, eliminating dead keys pointing at removed classes.

**Negative:**
- Training corpus must be rebuilt. The `4,500 = 500 × 9` target from ADR-008
  §Consequences becomes `3,000 = 500 × 6`. Existing annotated JSONL files
  carrying old archetype labels (`cybersecurity`, `regulatory`, `esg`, etc.)
  must be reclassified before they can be included in the fine-tuning corpus.
- The reduction from 9 to 6 classes may reduce the encoder's ability to
  distinguish intra-dimension subtypes (e.g., data security vs. product safety
  within `social_capital`). If this proves a problem, a Layer 1b sub-classifier
  within each dimension can be added in a future ADR without changing the schema.

---

## Supersedes

ADR-008 §Decision and §Consequences sections that reference:
- "9 archetype labels"
- "9-class archetype taxonomy"
- "softmax over fixed 9-class output"
- "4,500-example corpus (500 per class × 9 classes)"

The ADR-008 core decision — use a fine-tuned encoder (Phase 2 default:
`ProsusAI/finbert`) rather than API LLMs or local LLMs — is unchanged.

---

## References

- `src/analysis/segment_annotator.py:34` — `ARCHETYPE_LABEL_MAP` (6-class)
- `src/analysis/taxonomies/archetype_to_sasb.yaml` — crosswalk (created with this ADR)
- `thoughts/shared/research/2026-03-11_14-24-12_SASB Framework.md` — SASB Conceptual
  Framework analysis confirming the 5-dimension structure
- ADR-008 — superseded sections (label taxonomy only)
- ADR-015 — `label_source` namespace (7-value; unaffected by this change)
- PRD-002 §2.2 — feature schema (output JSONL `risk_label` field)
