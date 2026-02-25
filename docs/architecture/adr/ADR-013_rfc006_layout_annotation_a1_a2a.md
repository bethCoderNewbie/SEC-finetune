# ADR-013: Element-Level Layout Annotations — ListItem Flag and TitleLevel Normalization (RFC-006 A1 + A2a)

**Status:** Accepted
**Date:** 2026-02-25
**Author:** bethCoderNewbie
**git SHA:** 4045f92
**Related RFC:** `docs/architecture/rfc/RFC-006_layout_analysis_model_evaluation.md`
**Supersedes:** None

---

## Context

RFC-006 identified three layout-tagging weaknesses in the Stage 3 extractor:

1. **No list item distinction.** Bulleted/numbered risk entries are classified as
   generic `TextElement`. The segmenter cannot distinguish a list entry (natural
   split point) from flowing prose (should be merged).

2. **Document-relative title level integers.** `TitleElement.level` is assigned
   by sec-parser's `TitleClassifier` in CSS-style-appearance order within a
   single filing. Level 0 is the first unique bold/large-font style seen — not a
   canonical H1. The integers are not comparable across filings.

3. **Pipe-delimited page footer leakage** (already resolved by `PAGE_HEADER_PATTERN`
   in ADR-010; not in scope here).

Two corpus audits on 2026-02-25 resolved all RFC-006 open questions and informed
the exact implementation:

**OQ-1 — Bullet format (961-file full corpus scan):**

| Format | Files | % |
|--------|------:|---|
| `<li>` / `<ul>` / `<ol>` tags | **0** | **0.0%** |
| Unicode bullet chars (`•`, `·`, `▪`, …) | 902 | 94.1% |
| Parenthetical `(N)` prefix | 262 | 27.3% |
| Flowing paragraphs only | 32 | 3.3% |

`<li>` tags are absent across all 961 files. EDGAR encodes lists as `TextElement`
nodes whose text begins with a unicode bullet character directly followed by the
entry word — **no space** between bullet and word (e.g., `•Supply chain risk`).

**OQ-2 — `TitleElement.level` semantics (50-filing sample):**

| Level | Nodes | Item/Part headings |
|-------|------:|-------------------:|
| 0 | 3,387 | 239 (7.1%) |
| 1 | 2,907 | — |
| 2–11 | 5,260 | `ITEM 1A. RISK FACTORS` at level=3 observed |

Level=0 is a **subsection heading 92.9% of the time** (e.g., `"Overview"`,
`"Competition"`, `"Results of Operations"`). Level integers are CSS-order-appearance
indices, not semantic hierarchy labels. A threshold-based mapping (RFC-006 A2b) is
not viable for this corpus. RFC-006 A2b is ruled out.

---

## Decision

Implement RFC-006 sub-options **A1** and **A2a** as post-parse annotations on the
`elements` list inside `_extract_section_content`. No changes to `ExtractedSection`
model, no new dependencies, no modification of HTML before sec-parser (Rule 1,
ADR-010).

### A1 — `is_list_item` flag

```python
# src/preprocessing/constants.py
BULLET_LIST_PAT = re.compile(
    r'^\s*[•·▪▸►‣⁃]\s*\S'  # unicode bullet + optional space + non-ws char
    r'|^\s*\(\d+\)\s+'       # (1) parenthetical prefix — 27.3% of corpus
    r'|^\s*\d+\.\s+',        # 1. numbered list
    re.UNICODE,
)
```

Every element dict receives `'is_list_item': bool(BULLET_LIST_PAT.match(text))`.
The `<li>` branch from RFC-006 draft code is absent — 0% corpus coverage.

**Governing rule:** `\s*` (not `\s+`) after the bullet character. EDGAR emits
`•word` with no separator. Using `\s+` would silently miss 94.1% of the corpus.

### A2a — `title_level` annotation via structural anchoring

```python
# src/preprocessing/constants.py
class TitleLevel(Enum):
    H1   = 1   # Part-level: TopSectionTitle ("PART I", "PART II")
    H2   = 2   # Item-level: TopSectionTitle ("ITEM 1A") or SECTION_PATTERNS match
    H3   = 3   # First-level subsection within an Item
    H4   = 4   # Second-level subsection
    H5   = 5   # Third-level subsection (rare; max observed depth=5)
    BODY = 99  # Non-title node (TextElement, TableElement, etc.)
```

`_build_title_level_map(content_nodes)` collects all unique `TitleElement.level`
integers within the section, sorts them ascending, and maps smallest→H3,
next→H4, next+→H5 (capped). This is filing-format-invariant: it uses **relative
ordering** among TitleElements in the section, not the raw CSS-order integer.

`_get_node_title_level(node, level_map)` returns:
- `H1` for `TopSectionTitle` nodes (defensive; `_is_next_section` stops these before collection)
- `H3/H4/H5` via `level_map` for `TitleElement` nodes
- `BODY` for all other nodes

Every element dict receives `'title_level': TitleLevel.name` (e.g., `"H3"`,
`"BODY"`) stored as a string for JSON readability.

**Governing rule:** H1/H2 are never assigned to `TitleElement` nodes inside a
collected section — they are reserved for `TopSectionTitle` nodes which are
already stopped at the section boundary by `_is_next_section`. This means the
practical range within `elements` is `{H3, H4, H5, BODY}`.

### Files changed

| File | Change |
|:-----|:-------|
| `src/preprocessing/constants.py` | Added `BULLET_LIST_PAT` (after line 191), `TitleLevel` enum |
| `src/preprocessing/extractor.py` | Updated constants import; added `_get_node_title_level()` module helper; added `_build_title_level_map()` method to `SECSectionExtractor`; added annotation block in `_extract_section_content` after page-header filter |
| `tests/unit/preprocessing/test_extractor_unit.py` | Added `TestBulletListDetection` (13 parametrized cases), `TestTitleLevel` (7 tests including `_build_title_level_map` at 0/1/2/4 levels); added `MagicMock` import |

---

## Consequences

### Positive

- **Segmenter-ready list boundaries.** `RiskSegmenter` can now gate on
  `is_list_item=True` as an implicit segment boundary — reducing mid-list
  sentence-boundary splits for the 94.1% of filings that use unicode bullet lists.
- **Cross-filing title hierarchy.** `title_level` is now a stable, filing-invariant
  H-label. Downstream contextual enrichment (RFC-007) and breadcrumb annotation
  can rely on `"H3"` meaning "first subsection level within the current Item"
  across all filings.
- **Backward-compatible.** `elements: List[Dict[str, Any]]` already accepted
  arbitrary keys. No schema migration needed. Existing consumers that do not
  read `is_list_item`/`title_level` are unaffected.
- **No new dependencies.** All code uses stdlib `re`, `enum`, and sec-parser
  types already in the import graph.
- **Rule 1 preserved.** Annotations are applied post-`sec-parser.parse()` in
  Stage 3. HTML is not touched.

### Negative / Watch Items

- **`is_list_item` is text-heuristic, not structural.** Bullet detection operates
  on `node.text` pattern matching applied to `TextElement` output. It correctly
  captures 94.1% of the corpus (unicode bullets) and 27.3% (parenthetical). Dash
  prefix lists (22.4% of corpus, e.g., `– Supply chain`) are **not** detected —
  dash prefixes overlap with em-dash punctuation in flowing prose (false-positive
  risk). This is a known limitation; extend `BULLET_LIST_PAT` only with corpus
  evidence.
- **H1/H2 are currently unused** in `elements` (always `BODY` or `H3–H5`). They
  are reserved in `TitleLevel` for future use if the annotation scope is extended
  to include `TopSectionTitle` nodes.
- **A3 (paragraph boundary annotation) deferred.** RFC-006 sub-option A3
  (`paragraph_count`, character-offset boundaries within `TextElement`) was
  approved as a lower-priority enhancement and is not implemented in this ADR.
  The `_is_toc_node` and page-header filter do not conflict with A3 (OQ-4
  confirmed); A3 can be added independently.

### Batch test evidence (2026-02-25, 10-file sample)

| File | Elements | `is_list_item=True` | `title_level` values seen |
|:-----|--------:|--------------------:|:--------------------------|
| COR_10K_2021.html | 64 | 0 | BODY, H3, H4 |
| DLTR_10K_2024.html | 56 | 0 | BODY, H3 |
| MCK_10K_2022.html | 83 | 0 | BODY, H3 |
| MRK_10K_2022.html | 71 | 0 | BODY, H3, H4 |
| MU_10K_2023.html | 109 | 4 (3.7%) | BODY, H3, H4 |
| SNPS_10K_2023.html | 57 | 0 | BODY, H3 |
| TSN_10K_2025.html | 69 | 0 | BODY, H3, H4 |
| WMB_10K_2021.html | 83 | 0 | BODY, H3, H4, H5 |

MU's 4 list items are genuine `•`-prefixed bullet text. WMB's H5 confirms
`_build_title_level_map` correctly resolves 3-level nesting. PG and PLD returned
`NO_SECTION` — a pre-existing `_find_section_node` gap unrelated to this ADR.

---

## Supersedes

None.

---

## References

- `docs/architecture/rfc/RFC-006_layout_analysis_model_evaluation.md` — full option analysis, OQ-1/OQ-2 audit data
- `src/preprocessing/constants.py:191–219` — `BULLET_LIST_PAT`, `TitleLevel`
- `src/preprocessing/extractor.py:29–31` — updated import
- `src/preprocessing/extractor.py:31–51` — `_get_node_title_level()` module helper
- `src/preprocessing/extractor.py:392–407` — annotation block in `_extract_section_content`
- `src/preprocessing/extractor.py:477–503` — `_build_title_level_map()` method
- `docs/architecture/adr/ADR-002_sec_parser.md` — sec-parser version pin
- `docs/architecture/adr/ADR-010_hybrid_pre_seek_parser_corrected.md` — Rule 1 (no HTML modification before sec-parser)
- `docs/architecture/adr/ADR-003_global_worker_pool.md` — CPU-only worker pool (constraint that ruled out Options B/C)
