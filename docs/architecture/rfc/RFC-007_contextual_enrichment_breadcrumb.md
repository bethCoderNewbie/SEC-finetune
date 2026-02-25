---
id: RFC-007
title: Contextual Enrichment — Full Breadcrumb Serialization and Cross-Section Linking
status: PARTIALLY_IMPLEMENTED
author: beth88.career@gmail.com
created: 2026-02-24
last_updated: 2026-02-25
git_sha: 1c24d6e
superseded_by: null
related_prd: docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md
decision_adr: docs/architecture/adr/ADR-014_rfc007_ancestors_field.md
related_adr:
  - docs/architecture/adr/ADR-010_hybrid_pre_seek_parser_corrected.md
  - docs/architecture/adr/ADR-011_preseeker_single_section_constraint.md
  - docs/architecture/adr/ADR-014_rfc007_ancestors_field.md
related_rfc:
  - docs/architecture/rfc/RFC-005_multi_section_full_document_dispatch.md
---

# RFC-007: Contextual Enrichment — Full Breadcrumb Serialization and Cross-Section Linking

## Status

**PARTIALLY IMPLEMENTED** — D1-B + D2-A implemented 2026-02-25 (ADR-014).
D3-B (explicit cross-ref extraction) and D3-C (embedding cross-section
similarity) remain deferred.

---

## Context

The gap analysis
(`thoughts/shared/research/2026-02-24_10-00-00_ingestion_normalization_gap_analysis.md`,
Step 3) identified that current contextual enrichment is limited to a 2-level
hierarchy:

```
{section_identifier} → {parent_subsection}
  e.g. "part1item1a" → "Supply Chain Risk"
```

The proposed pipeline target (Step 3) requires appending the **full parent
hierarchy** to every child node:

```
Document > Part I > Item 1A > Supply Chain Risk > [chunk text]
```

This RFC covers three decisions:

1. **D1 — Full breadcrumb serialization:** How to walk the `sp.TreeNode.parent`
   chain and serialize an `ancestors` list on every output chunk.
2. **D2 — Ancestors field in the JSON schema:** Where and how to add
   `ancestors: List[str]` to `RiskSegment` and `SegmentedRisks` without
   breaking the v2 schema contract.
3. **D3 — Cross-section linking:** Whether and how to link a risk factor chunk
   to the corresponding MD&A or Notes passage that discusses the same topic.

---

## How the Tree Works Today

### `TreeBuilder` nesting rules

`TreeBuilder.get_default_rules()` (`sec_parser/semantic_tree/tree_builder.py`)
applies three rules in order:

```python
[
    AlwaysNestAsParentRule(TopSectionStartMarker),           # Part-level markers nest everything
    AlwaysNestAsParentRule(TitleElement,                     # TitleElement nests subsequent elements
        exclude_children={TopSectionStartMarker}),
    NestSameTypeDependingOnLevelRule(),                      # Lower level = higher in hierarchy
]
```

This means for a full-document parse, the tree IS genuinely hierarchical:

```
TreeNode(TopSectionTitle "PART I")
  └── TreeNode(TopSectionTitle "ITEM 1A. RISK FACTORS")
        ├── TreeNode(TitleElement[L0] "Supply Chain Risk")
        │     └── TreeNode(TextElement "Our supply chain depends on...")
        └── TreeNode(TitleElement[L0] "Regulatory Risk")
              └── TreeNode(TextElement "Changes in regulations...")
```

Every `TreeNode` carries a `parent` property (`TreeNode | None`). The full
ancestor chain for `TextElement "Our supply chain..."` is:

```python
node.parent.text          # "Supply Chain Risk"
node.parent.parent.text   # "ITEM 1A. RISK FACTORS"
node.parent.parent.parent.text  # "PART I"
node.parent.parent.parent.parent  # None  (root)
```

### The flat-iteration problem in `_extract_section_content`

`extractor.py:_extract_section_content()` (line 302) calls:

```python
all_nodes = list(tree.nodes)         # DFS flatten of the entire SemanticTree
start_idx = all_nodes.index(section_node)
for i in range(start_idx + 1, len(all_nodes)):
    node = all_nodes[i]
    if self._is_next_section(node): break
    content_nodes.append(node)
```

`SemanticTree.nodes` yields every node in depth-first order. This means
`all_nodes` includes nodes at ALL depths — root-level `TopSectionTitle` nodes
and deeply-nested `TextElement` nodes in the same flat list. The iteration
correctly collects all descendant content, but by flattening the tree it
**discards the parent chain for each collected node**. The `parent` attribute
still exists on each node object, but is never read.

### Critical constraint: pre-seek vs. full-document parse tree depth

The parent chain depth varies, but **not primarily by parse path** — depth is
driven by each filing's own heading hierarchy. Empirical audit of 10 production
filings confirms:

| Parse path | Triggered when | Root node types | Text depth range |
|------------|---------------|----------------|-----------------|
| **Pre-seek slice** (Stage 1 hit, ~95%) | Single section, ToC anchor resolved | `TopSectionTitle` (always) | **1..5** (filing-dependent) |
| **Full Document 1** (Stage 1 miss or multi-section, ~5%) | Pre-seek failed or multi-section call | `IntroductorySectionElement`, `TopSectionTitle`, sometimes bare `TextElement` | **0..5** |

All 8 pre-seek parses produced a `TopSectionTitle` root — sec-parser correctly
classifies the Item 1A heading even inside a small HTML slice. The tree IS
hierarchical within the slice.

**The one structural difference between parse paths is `ancestors[0]`:**
- Pre-seek: `ancestors[0]` is always an "Item 1A…" heading variant. `"PART I"` is never present.
- Full-doc fallback: `ancestors[0]` may be `"Part I"` / `"Part II"`, or a cover-page node, or `[]`.

**Confirmed sample breadcrumbs (pre-seek path):**

| Filing | Depth | ancestors for a typical TextElement |
|--------|-------|-------------------------------------|
| AAPL 2021 | 2 | `["Item 1A. Risk Factors", "Macroeconomic and Industry Risks"]` |
| BA 2022 | 2 | `["Item 1A. Risk Factors", "Risks Related to Our Business…"]` |
| DIS 2021 | 3 | `["ITEM 1A. Risk Factors", "BUSINESS, ECONOMIC… RISKS", "The adverse impact…"]` |
| ITW 2025 | 4 | `["ITEM 1A.", "Risk Factors", "Economic Risks", "The Company's results…"]` |
| TRV 2023 | 5 | `["Item 1A.    RISK FACTORS", "Insurance-Related Risks", …, …, …]` |

> Note: `\xa0` (non-breaking space) appears in every filing's ancestor strings.
> Normalization is required — see §Behavioral Invariant 6.

Downstream consumers (LLM prompts, embeddings, classifiers) must not assume a
fixed breadcrumb length. Both `[]` (GE full-doc cover page) and depth-5 (TRV
pre-seek) are production-observed values.

---

## Decision 1: Full Breadcrumb Serialization

### What is needed

For each `content_node` collected in `_extract_section_content()`, walk the
`sp.TreeNode.parent` chain upward and collect the text of every
`TitleElement` or `TopSectionTitle` ancestor. Store as an ordered list from
outermost to innermost:

```python
# e.g.  ["PART I", "ITEM 1A. RISK FACTORS", "Supply Chain Risk"]
```

### Option D1-A: Walk parent chain inline in `_extract_section_content`

Extend the existing `node_subsections_list` build loop (line 393–405) to emit
`ancestors` per node:

```python
def _get_ancestors(node: sp.TreeNode) -> List[str]:
    """Collect title ancestors from outermost to innermost."""
    ancestors = []
    current = node.parent
    while current is not None:
        elem = current.semantic_element
        if isinstance(elem, (sp.TitleElement, sp.TopSectionTitle)):
            ancestors.insert(0, current.text.strip())
        current = current.parent
    return ancestors
```

Append to `node_subsections_list` as a 3-tuple:
`(node.text.strip(), current_subsection, ancestors)`.

Pros:
- Minimal change — one helper function (~20 LoC) + 3-tuple extension
- No new pass over nodes
- Parent chain is valid at point of iteration (before any node is discarded)

Cons:
- `node_subsections_list` signature changes from `List[Tuple[str, Optional[str]]]`
  to `List[Tuple[str, Optional[str], List[str]]]` — all callers must be updated
  (`segmenter.py:_resolve_subsection`, `segment_extracted_section`)
- Produces variable-length ancestor lists (pre-seek vs. full-doc inconsistency)

### Option D1-B: Separate `element_ancestors` dict built before flattening

Before the flat iteration, traverse the tree recursively and build a mapping
`{node_id: ancestors_list}` while the tree is still hierarchical:

```python
import re as _re

def _normalize_ancestor_text(raw: str) -> str:
    """Normalize EDGAR title text for ancestor storage (audit finding: \xa0 ubiquitous)."""
    text = raw.strip().replace('\xa0', ' ')
    text = _re.sub(r'\s+', ' ', text)
    return text[:120]  # cap to prevent pathological title lengths in JSON

def _build_ancestor_map(tree: sp.SemanticTree) -> Dict[int, List[str]]:
    """
    Pre-traverse the full tree to record title ancestor texts for every node.
    Returns {id(node): [outermost_title, ..., immediate_parent_title]}.

    Audit (2026-02-24, 10 filings): max observed depth = 5. Cap at [:6] for safety.
    id(node) is stable between this pass and flat iteration — no tree mutation occurs.
    """
    result: Dict[int, List[str]] = {}

    def _recurse(node: sp.TreeNode, path: List[str]) -> None:
        elem = node.semantic_element
        current_path = path.copy()
        # Record ancestors BEFORE adding this node (result = ancestors, not self+ancestors)
        result[id(node)] = path[:6]
        if isinstance(elem, (sp.TitleElement, sp.TopSectionTitle)):
            current_path.append(_normalize_ancestor_text(node.text))
        for child in node.children:
            _recurse(child, current_path)

    for root in tree:
        _recurse(root, [])
    return result
```

Called once at the top of `_extract_section_content` or in `extract_section`.
Then for any `content_node`, `ancestor_map[id(content_node)]` gives the
pre-computed ancestor list.

Pros:
- Clean separation: ancestry computation before extraction logic
- Node_subsections_list signature unchanged (3-tuple is in a separate dict)
- Can be reused across multiple section extractions from the same filing

Cons:
- Extra DFS pass over the full tree (~milliseconds, negligible)
- `id(node)` mapping is fragile if the tree is mutated (it is not, but worth noting)
- Slightly more LoC (~50)

### Option D1-C: Add `ancestors` field to `element_dict` in `elements` list

Instead of plumbing through `node_subsections_list`, add `ancestors` as a
field of each element dict already built in the element-tracking loop (line
361–371):

```python
element_dict = {
    'type':       node.semantic_element.__class__.__name__,
    'text':       _elem_text,
    'char_count': len(_elem_text),
    'level':      getattr(node.semantic_element, 'level', 0),
    'ancestors':  _get_ancestors(node),   # new field
}
```

`ancestors` is then available on every element in `ExtractedSection.elements`.
The segmenter can look it up from the element list rather than the
`node_subsections_list`.

Pros:
- Cleanest data model — ancestry is co-located with the element
- No signature changes to `node_subsections_list` or `_resolve_subsection`
- `ExtractedSection.elements` already serialized to JSON (free persistence)

Cons:
- `ancestors` must be populated BEFORE the page-header filter pass (line
  376–391). Elements filtered out later still have ancestors computed —
  wasted work, but not incorrect.
- Segmenter must look up `ancestors` from `elements` list by text
  match to resolve per-segment breadcrumb — requires a new lookup helper.

### Recommendation for D1

**Option D1-B** (pre-built ancestor map). Cleaner than D1-A (no signature
change), lower coupling than D1-C (ancestry not tangled with element
serialization). ~50 LoC. Results stored as `element_ancestors: Dict[str,
List[str]]` (keyed by `node.text[:100]` for JSON serializability) in
`ExtractedSection`.

---

## Decision 2: Ancestors Field in JSON Schema

### Current schema (v2)

```json
{
  "chunks": [
    {
      "chunk_id": "1A_001",
      "parent_subsection": "Supply Chain Risk",
      "text": "Our supply chain...",
      "word_count": 287,
      "char_count": 1850
    }
  ]
}
```

`parent_subsection` carries the single nearest ancestor title (Fix 6B,
`segmenter.py:_resolve_subsection`).

### Option D2-A: Add `ancestors` as a new list field alongside `parent_subsection`

```json
{
  "chunk_id": "1A_001",
  "parent_subsection": "Supply Chain Risk",
  "ancestors": ["PART I", "ITEM 1A. RISK FACTORS", "Supply Chain Risk"],
  "text": "Our supply chain...",
  "word_count": 287,
  "char_count": 1850
}
```

`ancestors` is the full ordered breadcrumb (outermost → innermost, inclusive
of `parent_subsection`). `parent_subsection` is kept for backward compatibility
— it equals `ancestors[-1]` when `ancestors` is non-empty.

Changes required:
- `RiskSegment`: add `ancestors: List[str] = []`
- `SegmentedRisks.save_to_json()`: add `"ancestors": seg.ancestors` in chunk
  dict (line 150-ish)
- `segmenter.py:segment_extracted_section()`: resolve `ancestors` from D1
  result and pass to `RiskSegment`
- `SegmentedRisks.load_from_json()`: backward-compatible (default `[]`)

Risk: **None.** Adding a new field with default `[]` is backward-compatible
with all existing consumers and the v2 JSON schema.

### Option D2-B: Replace `parent_subsection` with `ancestors[-1]` and deprecate

Keep only `ancestors`; remove `parent_subsection`. Existing consumers that
read `parent_subsection` must migrate to `ancestors[-1]`.

Risk: **Breaking change.** Existing JSON files in `data/interim/` and any
downstream scripts reading `parent_subsection` would break.

### Recommendation for D2

**Option D2-A.** Zero breaking changes. `ancestors[-1]` == `parent_subsection`
as an invariant. `parent_subsection` can be formally deprecated in a later ADR
once all consumers are migrated to `ancestors`.

---

## Decision 3: Cross-Section Linking

### What is needed

A risk factor chunk may reference a topic also discussed in another section
(MD&A, Notes to Financial Statements). The proposed pipeline Step 3 implies
a link from the risk chunk to the relevant passage.

Example:
```json
{
  "chunk_id": "1A_023",
  "text": "Supply chain disruptions may materially impact revenue...",
  "cross_section_refs": [
    {
      "section": "part2item7",
      "title": "Management's Discussion and Analysis",
      "passage": "Supply chain costs increased 18% year-over-year...",
      "similarity": 0.87
    }
  ]
}
```

### Constraint: ADR-011 Rule 9

ADR-011 Rule 9: pre-seek only fires for single-section extraction. Multi-section
calls (`section_id=None`) skip Stage 1 and use full Document 1 parse. To
extract BOTH Item 1A AND Item 7 from a single filing, `pipeline.py` would need
to call `extract_section()` twice (single-section, pre-seek each) OR call once
with `section_id=None` (full document, multi-section).

Neither call pattern currently returns two sections simultaneously from a
single parse. Cross-section linking would require:

1. Modify pipeline to extract both sections in one pass (or two sequential passes)
2. Embed all chunks from both sections (e.g., sentence-transformers)
3. Compute cosine similarity between risk chunks and MD&A passages
4. Store top-K links per risk chunk

### Option D3-A: Deferred — out of scope for current PRDs

Cross-section linking is not mentioned in PRD-002 or PRD-003. It requires:
- Multi-section extraction per filing (not yet standard in pipeline)
- Embedding computation (adds `sentence-transformers` as required dep, not optional)
- A similarity threshold configuration
- A new schema field `cross_section_refs` on `RiskSegment`
- Storage of MD&A segments alongside risk segments

None of these are unblocked. Estimated effort: 3-5 weeks after multi-section
extraction is stable.

### Option D3-B: Shallow annotation — only section titles, no passage matching

Skip embedding-based linking. Instead, for each risk chunk, record which OTHER
sections in the same filing the segmenter detects explicit cross-references to
(using existing `_CROSS_REF_DROP_PAT` in `segmenter.py:14-19`):

```json
{
  "chunk_id": "1A_003",
  "text": "See Item 7 for further details on supply chain impacts.",
  "explicit_xrefs": ["part2item7"]
}
```

The `_CROSS_REF_DROP_PAT` already detects "See...", "For further details",
"For additional information" patterns and **drops** the matching segments.
Instead of dropping, extract the cross-reference target and store it.

This is cheap (~80 LoC) and deterministic — no embedding required.

Cons: only captures explicit textual cross-references; misses implicit
topical overlaps.

### Option D3-C: Embedding-based cross-section similarity (full implementation)

Full implementation described above (D3-A rationale). Highest information
value, highest complexity. Blocked on multi-section extraction stability and
`sentence-transformers` upgrade from optional to required.

### Recommendation for D3

**Option D3-B** as Phase 1 (low-cost, deterministic, immediate). Implement
by extracting cross-reference targets from `_CROSS_REF_DROP_PAT` matches
instead of silently dropping those segments.

**Option D3-C** deferred to Phase D (post-G-12, post-multi-section
extraction stabilization). Requires its own RFC when the time comes.

---

## Implementation Plan (Decisions D1-B + D2-A + D3-B)

### Files Changed

| File | Change | LoC |
|------|--------|-----|
| `extractor.py` | Add `_build_ancestor_map()` helper; call before flat iteration; store result in `ExtractedSection` | ~60 |
| `models/extraction.py` | Add `element_ancestors: Dict[str, List[str]] = {}` field to `ExtractedSection` | ~5 |
| `models/segmentation.py` | Add `ancestors: List[str] = []` to `RiskSegment`; add `explicit_xrefs: List[str] = []` (D3-B) | ~10 |
| `segmenter.py` | In `segment_extracted_section()`: resolve `ancestors` from `element_ancestors` map; in `_filter_segments()`: extract xref targets instead of drop | ~70 |
| `models/segmentation.py` | Update `save_to_json()` to emit `"ancestors"` and `"explicit_xrefs"` in chunk dict | ~20 |
| **Total** | | **~165** |

### No ADR conflicts

- All changes are additive (new fields with defaults)
- No HTML modification before sec-parser (Rule 1, ADR-010)
- No change to pre-seek / full-document dispatch logic (ADR-011 Rule 9 unchanged)
- `sentence-transformers` remains optional (D3-C deferred)

### Test surface

- `test_extractor_unit.py`: add tests for `_build_ancestor_map()` with a
  mock 3-level tree (TopSectionTitle > TitleElement > TextElement)
- `test_segmenter_unit.py`: add tests for `ancestors` population in
  `segment_extracted_section()`; add tests for `explicit_xrefs` extraction
- `test_preprocessing_models_unit.py`: round-trip test for new fields in
  `RiskSegment.save_to_json()` / `load_from_json()`

---

## Behavioral Invariants (if adopted as ADR)

> Invariants 1 and 5 updated from draft based on 2026-02-24 audit
> (`thoughts/shared/research/2026-02-24_11-00-00_rfc007_ancestor_depth_audit.md`).

1. **Depth variability:** `ancestors` MAY be `[]` for root-level nodes in
   full-doc fallback parses (e.g., cover-page `TextElement` nodes with no title
   ancestor). In pre-seek parses `ancestors` is always non-empty — minimum `["Item 1A…"]`.
   Consumers MUST NOT assume a fixed minimum or maximum length.
2. **Observed max depth:** 5 levels in production across 10 sampled filings.
   A soft cap of `ancestors[:6]` is applied by `_build_ancestor_map()` for JSON
   safety without losing any observed data.
3. **Ordering:** `ancestors` is ordered outermost-to-innermost. `ancestors[-1]`
   MUST equal `parent_subsection` when `ancestors` is non-empty.
4. **`parent_subsection` preserved:** `parent_subsection` MUST remain in all
   output until a superseding ADR explicitly deprecates it.
5. **Parse-path asymmetry:** Pre-seek `ancestors[0]` is always an "Item 1A…"
   heading (PART I context absent). Full-doc fallback `ancestors[0]` may be
   `"Part I"` / `"Part II"` or a cover-page node. Consumers requiring
   `"Part I"` context MUST use the full-doc fallback path (ADR-011 Rule 9,
   multi-section dispatch).
6. **Whitespace normalization:** All ancestor strings MUST have `\xa0`
   replaced with space and consecutive whitespace collapsed before storage.
   Raw ancestor text from EDGAR frequently contains non-breaking spaces
   (confirmed in all 10 audited filings).
7. **`explicit_xrefs` scope:** Only sections in the same filing and same form
   type are referenced. Cross-filing references are out of scope.

---

## Open Questions

| # | Question | Recommendation |
|---|----------|---------------|
| OQ-1 | In the pre-seek path (HTML slice), what is the deepest ancestor available for Item 1A content? | **RESOLVED** (2026-02-24 audit, `thoughts/shared/research/2026-02-24_11-00-00_rfc007_ancestor_depth_audit.md`): depth reaches **5** in production pre-seek filings (TRV 950 KB slice). Depth is driven by the filing's own heading hierarchy, not the parse path. Pre-seek breadcrumbs always begin at "Item 1A…" (PART I context absent). Full-doc fallback may add "Part I" as `ancestors[0]`. |
| OQ-2 | Does `id(node)` remain stable between the ancestor map pass and the content-node collection loop? | **RESOLVED** (2026-02-24 audit): No collisions observed across all 10 filings. No tree mutation occurs between passes. Safe to use `id(node)` as map key. |
| OQ-3 | Should `ancestors` be included in the `ExtractedSection.elements` dict as well, or only in `RiskSegment`? | Only in `RiskSegment` (D1-B stores in `element_ancestors` on `ExtractedSection` as intermediate; not exposed in `elements` JSON to avoid redundancy). |
| OQ-4 | For D3-B explicit xrefs: should dropped cross-reference segments be kept in output with a `is_cross_ref: true` flag, or discarded? | Keep as `is_cross_ref: true` segment with empty text, so chunk_id numbering remains stable. |

---

## References

- `src/preprocessing/extractor.py:302–420` — `_extract_section_content` (flat iteration + Fix 6A)
- `src/preprocessing/extractor.py:393–405` — `node_subsections_list` build loop
- `src/preprocessing/segmenter.py:155–215` — `segment_extracted_section` (Fix 6B breadcrumb resolution)
- `src/preprocessing/segmenter.py:370–399` — `_resolve_subsection` (doc-order text position matching)
- `src/preprocessing/segmenter.py:14–19` — `_CROSS_REF_DROP_PAT` (candidates for D3-B xref extraction)
- `src/preprocessing/models/extraction.py:14–59` — `ExtractedSection` Pydantic model
- `src/preprocessing/models/segmentation.py:14–29` — `RiskSegment` Pydantic model
- `sec_parser/semantic_tree/tree_builder.py` — `TreeBuilder.get_default_rules()` (nesting rules)
- `sec_parser/semantic_tree/tree_node.py` — `TreeNode.parent` property (the chain we walk)
- `docs/architecture/adr/ADR-011_preseeker_single_section_constraint.md` — Rule 9 (pre-seek single-section only)
- `docs/architecture/rfc/RFC-005_multi_section_full_document_dispatch.md` — multi-section dispatch background
