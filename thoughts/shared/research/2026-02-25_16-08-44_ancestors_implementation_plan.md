---
title: "Implementation Plan — RFC-007 Ancestors Field (D1-B + D2-A)"
date: 2026-02-25
timestamp: 2026-02-25_16-08-44
git_commit: 4045f92
branch: main
author: bethCoderNewbie
type: plan
related_rfc: docs/architecture/rfc/RFC-007_contextual_enrichment_breadcrumb.md
related_research: thoughts/shared/research/2026-02-24_10-00-00_ingestion_normalization_gap_analysis.md
prerequisite_adr: docs/architecture/adr/ADR-013_rfc006_layout_annotation_a1_a2a.md
---

# Plan: RFC-007 D1-B + D2-A — `ancestors` Field on `RiskSegment`

## Desired End State

After this implementation every `RiskSegment` in the segmented JSON output will
carry an `ancestors` list — the full heading breadcrumb from the outermost
section title down to the immediate subsection parent:

```json
{
  "chunk_id": "1A_003",
  "parent_subsection": "Supply Chain Risk",
  "ancestors": ["ITEM 1A. RISK FACTORS", "Supply Chain Risk", "Procurement Disruption"],
  "text": "Our reliance on third-party manufacturers...",
  "word_count": 87,
  "char_count": 553
}
```

Downstream consumers (annotation corpus, BERT fine-tuning input construction,
LLM prompts) can read `ancestors[-1]` as the immediate-parent weak label and
`ancestors[:-1]` as broader structural context.

---

## Anti-Scope — What We Are NOT Doing

| Item | Why excluded |
|:-----|:-------------|
| D3-B explicit cross-ref extraction | Separate concern; requires `_CROSS_REF_DROP_PAT` refactor; lower ROI vs. ancestors |
| D3-C embedding cross-section similarity | Needs multi-section extraction stability and `sentence-transformers` as required dep |
| Deprecating `parent_subsection` | `parent_subsection` stays; `ancestors[-1] == parent_subsection` is the invariant |
| Exposing `ancestors` on element dicts (D1-C) | RFC-007 OQ-3 resolved: ancestors only in `RiskSegment`, not redundantly in elements |
| Modifying pre-seek / full-doc dispatch logic | No change to ADR-011 Rule 9 |
| A3 paragraph boundary annotation | Separate RFC-006 sub-option; not in this plan |

---

## Background: Why This Unblocks BERT Fine-Tuning

From the evaluation (2026-02-25):

1. **Weak labeling for annotation corpus** (highest impact): `ancestors[-1]`
   maps directly to the 9 archetype taxonomy for a large fraction of filings.
   Filing authors write subsection headings like `"Cybersecurity Risks"`,
   `"Supply Chain Risk"` — free high-confidence weak labels for G-16 annotation.
   Estimated 40–60% of segments can be auto-labeled, cutting cold-start annotation
   effort significantly.

2. **Boilerplate filter** (deterministic, no model needed): Segments with
   `len(ancestors) == 1` are intro/transition text preceding the first subsection.
   A single filter rule removes them from the training set without any annotation.

3. **BERT A/B input format**: `[CLS] ancestors_text [SEP] segment_text [SEP]`
   uses BERT's paired-input pre-training alignment. Breadcrumb in segment A
   reduces semantic ambiguity for archetype classification in segment B.

---

## Behavioral Invariants (from RFC-007 §Behavioral Invariants)

These must hold after implementation:

| # | Invariant |
|---|:----------|
| 1 | `ancestors` MAY be `[]` for root-level nodes in full-doc fallback (cover-page nodes). In pre-seek parses it is always non-empty. |
| 2 | Max observed depth is 5. `ancestors` capped at `[:6]` for JSON safety. |
| 3 | `ancestors` is ordered outermost→innermost. |
| 4 | `ancestors[-1] == parent_subsection` when `ancestors` is non-empty. `parent_subsection` is NOT removed. |
| 5 | Pre-seek `ancestors[0]` is always "Item 1A…" (PART I absent). Full-doc may include "Part I". |
| 6 | All ancestor strings normalized: `\xa0` → space, consecutive whitespace collapsed, capped at 120 chars. |

---

## Files to Modify

| File | Change | ~LoC |
|:-----|:-------|-----:|
| `src/preprocessing/extractor.py` | Add module-level `_normalize_ancestor_text()`; add method `_build_ancestor_map(content_nodes, section_node, level_map)`; call in `_extract_section_content`; populate `ExtractedSection.element_ancestors` | ~65 |
| `src/preprocessing/models/extraction.py` | Add `element_ancestors: Dict[str, List[str]] = {}` field to `ExtractedSection` | ~5 |
| `src/preprocessing/models/segmentation.py` | Add `ancestors: List[str] = []` to `RiskSegment`; update `save_to_json` + `load_from_json` | ~25 |
| `src/preprocessing/segmenter.py` | Add `_resolve_ancestors()` helper; call in `segment_extracted_section()` | ~35 |
| `tests/unit/preprocessing/test_extractor_unit.py` | Add `TestBuildAncestorMap` class (3 tests) | ~50 |
| `tests/unit/preprocessing/test_segmenter_unit.py` | Add `TestResolveAncestors` + `TestAncestorsInSegmentedOutput` classes | ~60 |
| `tests/unit/preprocessing/test_preprocessing_models_unit.py` | Add round-trip test for `ancestors` in `save_to_json / load_from_json` | ~20 |
| **Total** | | **~260** |

---

## Phase 1 — Ancestor Map in Extractor

### 1a. `models/extraction.py` — add `element_ancestors` field

After `node_subsections` field (line 44), add:

```python
# D1-B: filing-relative ancestor map (node_text[:100] → ancestors list).
# Intermediate field: used by segmenter to resolve RiskSegment.ancestors.
# Not exposed in elements JSON (RFC-007 OQ-3).
element_ancestors: Dict[str, List[str]] = {}
```

No change to `save_to_json` or `load_from_json` — `element_ancestors` is an
in-memory intermediate and is excluded by the existing `k not in ('version', 'stats')`
filter in `load_from_json`. Add it to that exclusion set to be explicit.

**Wait — Pydantic V2 `model_dump()` is called in `save_to_json` which will
include `element_ancestors` in the dict.** Use `model_dump(exclude={'element_ancestors'})`
in `save_to_json`.

`save_to_json:112–122` uses `**self.model_dump()` which serializes ALL fields.
`node_subsections` is already serialized and must remain so — removing it would
break any load-then-segment workflow since `load_from_json` round-trips it via
`model_validate`. Only `element_ancestors` (in-memory intermediate) is excluded.

### 1b. `extractor.py` — add helpers and wire into `_extract_section_content`

**Architecture note (verified 2026-02-25):** sec-parser places subsection
`TitleElement` nodes as **siblings** of the Item 1A node (both children of the
same `TopSectionTitle`), not as descendants of it. `node.children` recursion
from Item 1A never reaches content nodes. The original RFC-007 OQ-2 assumption
(shared node objects across children and flat traversal) is correct *in
principle*, but the ancestor map must be built from the **flat `content_nodes`
list** using a heading-level stack, not a recursive descent.

Insert one helper **at module level** (after `_get_node_title_level`):

```python
def _normalize_ancestor_text(raw: str) -> str:
    """Normalize EDGAR title text for ancestor storage.
    \xa0 is ubiquitous in EDGAR heading text (confirmed all 10 audited filings).
    Cap at 120 chars to prevent pathological title lengths in JSON.
    """
    text = raw.strip().replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text)   # re already imported at module level
    return text[:120]
```

Insert one helper as a **method on `SECSectionExtractor`** (after
`_build_title_level_map`):

```python
def _build_ancestor_map(
    self,
    content_nodes: list,
    section_node,
    level_map: dict,
) -> dict:
    """
    Build ancestor map for content nodes using a linear heading-stack walk.

    sec-parser places subsection TitleElements as siblings of the section
    node (not descendants), so node.children recursion never reaches them.
    This method walks content_nodes in document order, maintains a heading
    stack, and records the current stack for each node.

    Returns {id(node): [outermost_title, ..., immediate_parent_title]}.
    Stack is seeded with the section title (e.g. "ITEM 1A. RISK FACTORS")
    so ancestors[0] always names the containing section (Invariant 5).

    Observed max depth = 5; capped at [:6] for JSON safety (Invariant 2).
    """
    if sp is None:
        return {}

    # Level index: H3=0 (shallowest subsection), H4=1, H5=2 (deepest)
    _H_IDX = {TitleLevel.H3: 0, TitleLevel.H4: 1, TitleLevel.H5: 2}

    section_title = _normalize_ancestor_text(section_node.text)
    heading_stack: list = [section_title]   # index 0 — never popped
    result: dict = {}

    for node in content_nodes:
        if isinstance(node.semantic_element, sp.TitleElement):
            level = _get_node_title_level(node, level_map)
            level_idx = _H_IDX.get(level, 0)
            # Trim stack: keep section title + all headings shallower than this one
            del heading_stack[1 + level_idx:]
            heading_stack.append(_normalize_ancestor_text(node.text))
        result[id(node)] = heading_stack[:6]

    return result
```

**Wire into `_extract_section_content`** — insert after `_level_map` and the
A1/A2a annotation block (after line ~431, the `zip(elements, content_nodes)`
loop) and before the Fix 6A sequential scan:

```python
# D1-B: build ancestor map from flat content_nodes using heading-level stack.
# Must run after page-header filter and _level_map are ready.
_ancestor_map = self._build_ancestor_map(content_nodes, section_node, _level_map)
```

Then build `element_ancestors` immediately after (before the Fix 6A scan):

```python
# D1-B: key by normalized node.text[:100] for segmenter lookup.
element_ancestors: Dict[str, List[str]] = {
    _normalize_ancestor_text(_node.text)[:100]: _ancestor_map.get(id(_node), [])
    for _node in content_nodes
}
```

Return `element_ancestors` from `_extract_section_content` by adding it to
the return tuple. Current signature returns `(str, List[str], List[Dict], List[tuple])`.
New: `(str, List[str], List[Dict], List[tuple], Dict[str, List[str]])`.

Update `extract_section()` (line 100) to unpack the fifth element and pass it
to `ExtractedSection(element_ancestors=element_ancestors, ...)`.

**Also update the fallback early return** at `extractor.py:358–360` — this path
fires when `section_node` is not found in `all_nodes`. It currently returns a
4-tuple and must be updated to match the new arity:

```python
# extractor.py ~line 358-360 — fallback path
subsections = self._extract_subsections(section_node)
elements = self._extract_elements(section_node)
return section_node.text, subsections, elements, [], {}  # added trailing {}
```

Omitting this update causes `ValueError: not enough values to unpack` at the
call site whenever the fallback fires.

---

## Phase 2 — `RiskSegment` Field + Segmenter Resolution

### 2a. `models/segmentation.py` — add `ancestors` to `RiskSegment`

After `parent_subsection` (line 19):

```python
ancestors: List[str] = []   # D2-A: outermost→innermost title breadcrumb
```

No `__init__` change needed — Pydantic handles the default.

### 2b. `segmenter.py` — add `_resolve_ancestors` helper

```python
def _resolve_ancestors(
    self,
    chunk_text: str,
    full_text: str,
    element_ancestors: dict,
) -> List[str]:
    """
    Resolve the ancestors breadcrumb for a chunk using doc-order position walk.

    element_ancestors maps normalized node_text[:100] → List[str] ancestors,
    populated in document order by extractor._extract_section_content (D1-B).

    Uses the same text-position approach as _resolve_subsection (Fix 6B):
    walks element_ancestors in insertion order (Python 3.7+ dict), finds the
    entry whose node text precedes the chunk's position in full_text, returns
    its ancestors list.

    Returns [] if element_ancestors is empty or no match found.
    """
    if not element_ancestors:
        return []
    key = chunk_text[:50]
    chunk_start = full_text.find(key)
    if chunk_start == -1:
        # Fallback: return last entry's ancestors
        return list(element_ancestors.values())[-1]
    current: List[str] = []
    for node_key, ancestors in element_ancestors.items():
        node_start = full_text.find(node_key[:50])
        if node_start == -1:
            continue
        if node_start <= chunk_start:
            current = ancestors
        else:
            break
    return current
```

### 2c. `segmenter.py` — wire into `segment_extracted_section`

Add after the `node_subsections` / `section_title` reads (line 179–180):

```python
element_ancestors = getattr(extracted_section, 'element_ancestors', {})
```

Update the `RiskSegment` construction (line 181–191) to pass `ancestors`:

```python
segments = [
    RiskSegment(
        chunk_id=f"1A_{i+1:03d}",
        parent_subsection=(
            self._resolve_subsection(text, text_to_segment, node_subsections)
            or section_title
        ),
        ancestors=self._resolve_ancestors(text, text_to_segment, element_ancestors),
        text=text,
    )
    for i, text in enumerate(segment_texts)
]
```

---

## Phase 3 — JSON Serialization

### 3a. `save_to_json` — emit `ancestors` in chunks block

In `SegmentedRisks.save_to_json`, update the chunk dict (line 155–162):

```python
'chunks': [
    {
        'chunk_id':         seg.chunk_id,
        'parent_subsection': seg.parent_subsection,
        'ancestors':         seg.ancestors,          # new
        'text':              seg.text,
        'word_count':        seg.word_count,
        'char_count':        seg.char_count,
    }
    for seg in self.segments
],
```

### 3b. `load_from_json` — backward-compatible read

In the structured schema branch (line 191–200), update `RiskSegment` construction:

```python
segments = [
    RiskSegment(
        chunk_id=c.get('chunk_id', f"1A_{i+1:03d}"),
        parent_subsection=c.get('parent_subsection'),
        ancestors=c.get('ancestors', []),   # new — default [] for old files
        text=c.get('text', ''),
        word_count=c.get('word_count', 0),
        char_count=c.get('char_count', 0),
    )
    for i, c in enumerate(raw_chunks)
]
```

**Backward compatibility:** `c.get('ancestors', [])` returns `[]` for all
existing JSON files that predate this change. No migration needed.

---

## Phase 4 — Tests

### `test_extractor_unit.py` — `TestBuildAncestorMap`

`_build_ancestor_map` is now a method on `SECSectionExtractor`. Tests pass a
flat `content_nodes` list (reflecting actual sec-parser sibling structure) plus
a mock `section_node` and a `level_map`.

```python
class TestBuildAncestorMap:
    """D1-B: _build_ancestor_map linear heading-stack walk."""

    @pytest.fixture
    def extractor(self):
        return SECSectionExtractor()

    @pytest.fixture
    def section_node(self):
        node = MagicMock()
        node.text = "ITEM 1A. RISK FACTORS"
        return node

    def test_empty_content_returns_empty(self, extractor, section_node):
        result = extractor._build_ancestor_map([], section_node, {})
        assert result == {}

    def test_body_node_before_any_title_gets_section_only(self, extractor, section_node):
        try:
            import sec_parser as sp
        except ImportError:
            pytest.skip("sec_parser not installed")

        body = MagicMock()
        body.semantic_element = MagicMock(spec=sp.TextElement)
        body.text = "Preamble text."

        result = extractor._build_ancestor_map([body], section_node, {})
        assert result[id(body)] == ["ITEM 1A. RISK FACTORS"]

    def test_title_then_body_assigns_correct_ancestors(self, extractor, section_node):
        try:
            import sec_parser as sp
        except ImportError:
            pytest.skip("sec_parser not installed")
        from src.preprocessing.constants import TitleLevel

        title = MagicMock()
        title.semantic_element = MagicMock(spec=sp.TitleElement)
        title.text = "Supply Chain Risk"

        body = MagicMock()
        body.semantic_element = MagicMock(spec=sp.TextElement)
        body.text = "Our reliance on suppliers..."

        level_map = {getattr(title.semantic_element, 'level', 0): TitleLevel.H3}
        result = extractor._build_ancestor_map([title, body], section_node, level_map)

        assert result[id(title)] == ["ITEM 1A. RISK FACTORS"]          # title records stack BEFORE appending itself
        assert result[id(body)] == ["ITEM 1A. RISK FACTORS", "Supply Chain Risk"]

    def test_normalization_strips_xa0(self, extractor):
        node = MagicMock()
        node.text = "ITEM\xa01A.\xa0RISK FACTORS"
        from src.preprocessing.extractor import _normalize_ancestor_text
        assert _normalize_ancestor_text(node.text) == "ITEM 1A. RISK FACTORS"
```

### `test_segmenter_unit.py` — `TestResolveAncestors`

```python
class TestResolveAncestors:
    """D2-A: _resolve_ancestors doc-order position walk."""

    @pytest.fixture
    def segmenter(self):
        return RiskSegmenter()

    def test_empty_map_returns_empty_list(self, segmenter):
        result = segmenter._resolve_ancestors("chunk text", "full text here", {})
        assert result == []

    def test_returns_ancestors_for_matching_node(self, segmenter):
        full_text = "Supply chain heading\n\nBody paragraph about supply chain risk."
        element_ancestors = {
            "Supply chain heading": ["ITEM 1A", "Supply Chain Risk"],
        }
        result = segmenter._resolve_ancestors(
            "Body paragraph about supply chain risk.",
            full_text,
            element_ancestors,
        )
        assert result == ["ITEM 1A", "Supply Chain Risk"]

    def test_picks_most_recent_ancestor_before_chunk(self, segmenter):
        full_text = "Section A heading\n\nSection A body.\n\nSection B heading\n\nSection B body."
        element_ancestors = {
            "Section A heading": ["ITEM 1A", "Section A"],
            "Section B heading": ["ITEM 1A", "Section B"],
        }
        result = segmenter._resolve_ancestors("Section B body.", full_text, element_ancestors)
        assert result == ["ITEM 1A", "Section B"]


class TestAncestorsInSegmentedOutput:
    """Integration: ancestors emitted in RiskSegment and JSON output."""

    def test_risk_segment_ancestors_default_empty(self):
        seg = RiskSegment(chunk_id="1A_001", text="Sample risk text here.")
        assert seg.ancestors == []

    def test_risk_segment_accepts_ancestors(self):
        seg = RiskSegment(
            chunk_id="1A_001",
            text="Sample risk text here.",
            ancestors=["ITEM 1A", "Supply Chain Risk"],
        )
        assert seg.ancestors == ["ITEM 1A", "Supply Chain Risk"]
```

### `test_preprocessing_models_unit.py` — round-trip test

```python
def test_ancestors_round_trip_save_load(tmp_path):
    """ancestors field survives save_to_json / load_from_json round-trip."""
    seg = RiskSegment(
        chunk_id="1A_001",
        text="Our supply chain depends on third parties.",
        ancestors=["ITEM 1A. RISK FACTORS", "Supply Chain Risk"],
    )
    sr = SegmentedRisks(segments=[seg], company_name="ACME", form_type="10-K")
    out = sr.save_to_json(tmp_path / "test.json", overwrite=True)
    loaded = SegmentedRisks.load_from_json(out)
    assert loaded.segments[0].ancestors == ["ITEM 1A. RISK FACTORS", "Supply Chain Risk"]

def test_ancestors_backward_compat_old_json(tmp_path):
    """Old JSON files without ancestors key load with default []."""
    import json
    old_data = {
        "version": "1.0",
        "document_info": {"company_name": "ACME"},
        "section_metadata": {"title": "Risk Factors", "identifier": "part1item1a", "stats": {}},
        "chunks": [{"chunk_id": "1A_001", "text": "Some risk.", "word_count": 2, "char_count": 9}],
    }
    path = tmp_path / "old.json"
    path.write_text(json.dumps(old_data))
    loaded = SegmentedRisks.load_from_json(path)
    assert loaded.segments[0].ancestors == []
```

---

## Phase 5 — Documentation

### 5a. Write ADR-014

`docs/architecture/adr/ADR-014_rfc007_ancestors_field.md`

Document the decision to implement D1-B + D2-A (not D1-A, not D1-C), the
behavioral invariants (all 6), the backward-compat guarantee, and the BERT
fine-tuning rationale (weak labeling + boilerplate filter + A/B input format).

### 5b. Update RFC-007

Change `status: DRAFT` → `IMPLEMENTED` (D1-B + D2-A). Note D3-B/D3-C remain
deferred. Add `decision_adr: docs/architecture/adr/ADR-014_rfc007_ancestors_field.md`.

### 5c. Update data dictionary

`docs/architecture/data_dictionary.md` — add `ancestors` row to `RiskSegment`
table. Source/logic: `segmenter.py:_resolve_ancestors`. Nullable: No (empty list
for pre-section nodes). Constraints: `ancestors[-1] == parent_subsection` when
non-empty; capped at 6 levels; strings normalized (no `\xa0`, max 120 chars each).

---

## Success Criteria

### Automated

```bash
# 1. All existing + new unit tests pass
python -m pytest tests/unit/preprocessing/test_extractor_unit.py \
                 tests/unit/preprocessing/test_segmenter_unit.py \
                 tests/unit/preprocessing/test_preprocessing_models_unit.py -v

# 2. Invariant 4: ancestors[-1] == parent_subsection for non-empty ancestors
python -c "
from pathlib import Path
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import SECSectionExtractor
from src.preprocessing.segmenter import RiskSegmenter

parser = SECFilingParser()
extractor = SECSectionExtractor()
segmenter = RiskSegmenter()

files = list(Path('data/raw').glob('*.html'))[:10]
violations = []
for f in files:
    try:
        filing = parser.parse_filing(f)
        section = extractor.extract_risk_factors(filing)
        if section is None: continue
        result = segmenter.segment_extracted_section(section)
        for seg in result.segments:
            if seg.ancestors and seg.ancestors[-1] != seg.parent_subsection:
                violations.append((f.name, seg.chunk_id, seg.ancestors, seg.parent_subsection))
    except Exception: pass
print(f'Invariant 4 violations: {len(violations)}')
for v in violations[:5]: print(v)
"

# 3. Spot-check: ancestors present and non-empty on real filings
python -c "
from pathlib import Path
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import SECSectionExtractor
from src.preprocessing.segmenter import RiskSegmenter

parser = SECFilingParser()
extractor = SECSectionExtractor()
segmenter = RiskSegmenter()

filing = parser.parse_filing(Path('data/raw/AAPL_10K_2024.html'))
section = extractor.extract_risk_factors(filing)
result = segmenter.segment_extracted_section(section)

print(f'Total segments: {len(result.segments)}')
print(f'Segments with ancestors: {sum(1 for s in result.segments if s.ancestors)}')
print(f'Max depth: {max(len(s.ancestors) for s in result.segments)}')
print()
for seg in result.segments[:5]:
    print(f'  [{seg.chunk_id}] ancestors={seg.ancestors}')
    print(f'           parent_subsection={seg.parent_subsection!r}')
    print()
"

# 4. Backward compat: old JSON loads with ancestors=[]
python -c "
from src.preprocessing.models.segmentation import SegmentedRisks
import pathlib
old_files = list(pathlib.Path('data/interim').rglob('*_segmented_risks.json'))[:3]
for f in old_files:
    sr = SegmentedRisks.load_from_json(f)
    bad = [s for s in sr.segments if s.ancestors != []]
    print(f'{f.name}: {len(sr.segments)} segs, bad={len(bad)}')
"
```

### Manual

1. Open a saved `_segmented_risks.json` for any 10-K — verify `"ancestors"` key
   present in every chunk dict, value is a list of strings (may be `[]` for
   preamble segments).
2. Check that `ancestors[-1] == parent_subsection` for any chunk with non-empty
   ancestors.
3. Confirm `element_ancestors` is **not** in `_extracted_risks.json` output
   (it is an in-memory intermediate only).

---

## Risks

| Risk | Mitigation |
|:-----|:-----------|
| `id(node)` collision between stack build and element_ancestors lookup | `id(node)` is stable within a single parse — no tree mutation between `_build_ancestor_map` and the `element_ancestors` dict comprehension that follows immediately after |
| `node.children` recursion (original RFC-007 OQ-2 design) | **Invalidated 2026-02-25.** sec-parser places subsection TitleElements as siblings of Item 1A, not descendants. Parent of "Macroeconomic and Industry Risks" is `TopSectionTitle`, not `TitleElement`. Replaced with linear heading-stack walk over `content_nodes`. |
| Text-key collision in `element_ancestors` (two nodes with identical first 100 chars) | Rare in practice; last-write wins (same doc-order) — acceptable for lookup |
| `extract_section()` return tuple arity change breaks callers | Only one internal caller (`extract_section → _extract_section_content`); update both in same commit |
| Token budget: breadcrumb adds ~20–30 tokens to BERT input | Document in ADR-014; downstream consumers must account for it; do not enforce here |
| Pre-seek slices: `ancestors[0]` is never "PART I" | Invariant 5; documented in ADR-014; consumers must handle both parse paths |

---

## Implementation Order

```
Phase 1 (extractor)  →  Phase 2 (segmenter)  →  Phase 3 (JSON)  →  Phase 4 (tests)  →  Phase 5 (docs)
```

Phases 1 and 3 can be coded sequentially in a single session. Phase 4 should
be run after each Phase to catch regressions early. Phase 5 (docs) last.

Total estimated LoC: ~260. No new dependencies.
