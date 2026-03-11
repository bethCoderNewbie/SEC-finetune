# ADR-015: Locked `label_source` Namespace for Annotation Records

**Status:** Accepted
**Date:** 2026-03-11
**Author:** beth88.career@gmail.com

---

## Context

The `SegmentAnnotator` module (US-032) produces flat JSONL training records. Multiple code paths
assign labels to the same segment: the BART zero-shot NLI pipeline (Stage A), the fine-tuned
DeBERTa checkpoint (Stage B), an optional LLM backend, a keyword heuristic fallback, an ancestor
heading prior tie-breaker, the IAA annotation tool, and the LLM synthetic data generator.

Each path has a distinct reliability profile:

| Path | Estimated Macro F1 (SEC domain) |
|---|---|
| Human annotator (IAA) | ~0.92–0.97 (gold standard) |
| Fine-tuned DeBERTa Stage B | ~0.72–0.80 (Phase 2 target) |
| LLM silver (`claude-haiku-4-5`) | ~0.72–0.78 (estimated) |
| BART zero-shot NLI Stage A | ~0.55–0.65 (estimated) |
| Ancestor prior (heading-only) | ~0.60–0.70 (estimated) |
| Keyword heuristic | ~0.40–0.55 (estimated) |

The original `SegmentAnnotator` design (from `auto_label.py` heritage) used a single
`"classifier"` value for all model paths. This creates two blocking problems:

1. **Post-hoc filtering is impossible.** Training recipes that weight records by reliability
   (e.g., down-weight heuristic labels, up-weight human labels) cannot be applied without
   knowing which path produced each record.

2. **Stage A vs Stage B ambiguity.** After the fine-tuned model is available, the corpus will
   contain a mix of Stage A BART labels and Stage B fine-tuned labels. Collapsing both into
   `"classifier"` makes it impossible to detect or replace noisy Stage A labels without a
   full re-annotation pass across 156K+ records.

Migrating a 156K-record corpus post-hoc requires re-reading, re-writing, and re-checksumming
every file. The `label_source` field must be correct at write time.

---

## Decision

Define a **locked seven-value namespace** as module-level constants in `src/analysis/segment_annotator.py`.
No new value may be added without a superseding ADR.

```python
LABEL_SOURCE_NLI        = "nli_zero_shot"   # BART Stage A; confidence >= section threshold
LABEL_SOURCE_HEURISTIC  = "heuristic"        # Keyword fallback; no ancestor match
LABEL_SOURCE_ANCESTOR   = "ancestor_prior"   # Confidence < threshold; ancestor heading match
LABEL_SOURCE_LLM        = "llm_silver"       # LLM backend (llm_client configured)
LABEL_SOURCE_CLASSIFIER = "classifier"       # Fine-tuned Stage B ONLY — never written here
LABEL_SOURCE_HUMAN      = "human"            # IAA annotator — never written here
LABEL_SOURCE_SYNTHETIC  = "llm_synthetic"    # Synthesis script — never written here
```

**Governing rules:**

1. `SegmentAnnotator` (this module) writes only `"nli_zero_shot"`, `"heuristic"`,
   `"ancestor_prior"`, and `"llm_silver"`. The other three values are reserved for other tools.
2. `"classifier"` is exclusively for the fine-tuned DeBERTa Stage B inference path.
   Writing `"classifier"` from BART zero-shot output is a bug.
3. Any consumer that receives an unrecognised `label_source` value must raise `ValueError`,
   not silently default.
4. Adding a new value without a superseding ADR is a bug.

**Label-source assignment logic in `annotate()`:**

```python
if llm_path:
    label_source = LABEL_SOURCE_LLM
elif confidence >= section_threshold:
    label_source = LABEL_SOURCE_NLI
elif ancestor_prior_matched:
    label_source = LABEL_SOURCE_ANCESTOR
else:
    label_source = LABEL_SOURCE_HEURISTIC
```

---

## Consequences

**Positive:**
- Downstream train/eval splits can filter or weight records by reliability tier without
  schema migration.
- IAA sampling (QR-01) can exclude NLI-labeled records from the human-review queue by
  filtering `label_source == "nli_zero_shot"`.
- Phase 2 F1 gate evaluation can exclude heuristic labels from the test split.
- LABEL_SOURCE_* constants are importable from `segment_annotator.py`, preventing
  typo-based namespace drift across multiple scripts.

**Negative:**
- Any corpus produced before this ADR (where `label_source == "classifier"` was written
  for BART output) requires a migration pass: set `label_source = "nli_zero_shot"` for
  all records where the fine-tuned model was not used.
- Downstream consumers must handle 7 possible values instead of 2.

---

## Supersedes

Nothing — first ADR on this topic.

## References

- `src/analysis/segment_annotator.py` — LABEL_SOURCE_* constants (implemented in US-032)
- `docs/requirements/stories/US-032_segment_annotator_jsonl_transform.md` — Scenario D
- `thoughts/shared/research/2026-03-03_17-30-00_segment_annotator_jsonl_transform.md` §4.5, OQ-A9, C-3
- PRD-002 §8 (Phase 2 target schema)
