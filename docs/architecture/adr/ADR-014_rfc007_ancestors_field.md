---
id: ADR-014
title: RFC-007 D1-B + D2-A — ancestors field on RiskSegment
status: Accepted
date: 2026-02-25
author: beth88.career@gmail.com
git_sha: 1c24d6e
supersedes: null
superseded_by: null
related_rfc: docs/architecture/rfc/RFC-007_contextual_enrichment_breadcrumb.md
related_adr:
  - docs/architecture/adr/ADR-013_rfc006_layout_annotation_a1_a2a.md
  - docs/architecture/adr/ADR-010_hybrid_pre_seek_parser_corrected.md
---

# ADR-014: RFC-007 D1-B + D2-A — `ancestors` Field on `RiskSegment`

## Status

**Accepted** — implemented 2026-02-25.

---

## Context

The RFC-007 gap analysis identified that `RiskSegment` carried only a single
`parent_subsection` string (one level of heading context). Downstream annotation
and BERT fine-tuning require the full heading breadcrumb — from the outermost
section title down to the immediate subsection parent — to support:

1. **Weak labeling**: `ancestors[-1]` maps directly to the 9-archetype taxonomy
   for ~40–60% of segments, cutting cold-start annotation cost.
2. **Boilerplate filter**: `len(ancestors) == 1` (preamble before first
   subsection) is a deterministic filter requiring no model inference.
3. **BERT A/B input format**: `[CLS] ancestors_text [SEP] segment_text [SEP]`
   uses BERT's paired-input pre-training alignment.

RFC-007 proposed three implementation options. D1-A (parent-pointer walk at
query time) and D1-C (per-element storage in the JSON elements array) were
considered and rejected. D1-B (build an ancestor map in the extractor, pass
through to the segmenter) was selected.

---

## Decision

Implement RFC-007 options **D1-B** (extractor-side ancestor map) and **D2-A**
(ancestors field on RiskSegment).

### Governing rules

1. `ancestors` is a `List[str]` on `RiskSegment`, default `[]`.
2. Each string is an EDGAR heading title, normalized: `\xa0` → space,
   consecutive whitespace collapsed, capped at 120 characters.
3. `ancestors` is ordered outermost → innermost.
4. `ancestors[0]` is always the section title (e.g. `"ITEM 1A. RISK FACTORS"`)
   when `ancestors` is non-empty.
5. `ancestors` may be `[]` for cover-page nodes in the full-doc fallback path.
6. Depth capped at 6 for JSON safety.
7. `ancestors[-1]` semantically corresponds to `parent_subsection` when
   `ancestors` is non-empty. String equality is NOT guaranteed: `ancestors`
   uses normalized filing text; `parent_subsection` preserves raw filing text
   (stripped only). Preamble segments additionally diverge because
   `parent_subsection` falls back to the config section title while
   `ancestors[0]` uses the actual filing heading text.
8. `parent_subsection` is NOT deprecated or removed.

### Why linear stack walk, not node.children recursion

The original RFC-007 OQ-2 design assumed shared node objects between a
`node.children` pre-traversal pass and the flat `tree.nodes` content
iteration. Empirical verification on AAPL 2023 (466 nodes) showed that all
nodes had `children=[]` when accessed via the flat traversal, because
sec-parser places subsection `TitleElement` nodes as **siblings** of the
section header (both are children of the same `TopSectionTitle`), not
descendants. The correct approach is a linear heading-stack walk over the
already-filtered `content_nodes` list (see `extractor._build_ancestor_map`).

### Why not D1-A (parent-pointer walk at query time)

D1-A would require walking `node.parent` at render time. As shown above,
subsection headings are siblings, so their parent chain omits Item 1A —
`ancestors[0]` would be missing for the most common filing structure.

### Why not D1-C (per-element storage in JSON)

RFC-007 OQ-3 resolved: redundant with the `ancestors` field on `RiskSegment`
and would bloat `_extracted_risks.json` by ~30% for no downstream benefit.
`element_ancestors` on `ExtractedSection` is an in-memory intermediate only
(excluded from `model_dump` in `save_to_json`).

---

## Consequences

### Positive

- Every `RiskSegment` in `_segmented_risks.json` now carries `"ancestors"`.
- Backward compatible: old JSON files without `"ancestors"` load with default
  `[]` via `c.get('ancestors', [])`.
- No new runtime dependencies.
- 99% of segments across 10 audited filings carry non-empty ancestors.

### Negative / Known Limitations

- String equality `ancestors[-1] == parent_subsection` does not hold for
  preamble segments (~2 per filing) or headings longer than 120 characters.
  See Governing rule 7.
- Filings where sec-parser classifies long risk-factor titles as `TitleElement`
  (e.g., some utility company 10-Ks) will show deep ancestor stacks — the
  risk factor title itself becomes `ancestors[-1]`, above which is the
  category heading. This is semantically correct behavior.

---

## References

- `src/preprocessing/extractor.py` — `_normalize_ancestor_text`,
  `_build_ancestor_map`, `_extract_section_content` (updated return tuple)
- `src/preprocessing/models/extraction.py` — `ExtractedSection.element_ancestors`
- `src/preprocessing/models/segmentation.py` — `RiskSegment.ancestors`,
  `SegmentedRisks.save_to_json`, `load_from_json`
- `src/preprocessing/segmenter.py` — `_resolve_ancestors`,
  `segment_extracted_section`
- `docs/architecture/rfc/RFC-007_contextual_enrichment_breadcrumb.md`
