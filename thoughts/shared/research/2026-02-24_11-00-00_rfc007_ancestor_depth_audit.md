---
title: "RFC-007 OQ-1 Audit — Ancestor Depth in Pre-Seek vs Full-Doc Parse Paths"
date: 2026-02-24
commit: 997a101
branch: main
author: bethCoderNewbie <beth88.career@gmail.com>
resolves: RFC-007 OQ-1
method: "_build_ancestor_map() prototype run against 10 production filings"
raw_data: thoughts/shared/research/rfc007_ancestor_depth_audit.json
---

# RFC-007 OQ-1 Audit: Ancestor Depth Across Parse Paths

## Sample

| File | Parse Path | Pre-seek KB | Text depth | Max depth |
|------|-----------|------------|-----------|----------|
| AAPL_10K_2021 | pre_seek_slice | 91.7 | 1..2 | 2 |
| BA_10K_2022 | pre_seek_slice | 92.3 | 1..2 | 2 |
| DIS_10K_2021 | pre_seek_slice | 79.8 | 1..3 | 3 |
| ITW_10K_2025 | pre_seek_slice | 42.3 | **2..4** | 4 |
| MMM_10K_2025 | pre_seek_slice | 59.6 | 1..2 | 2 |
| O_10K_2025 | pre_seek_slice | 133.5 | 2..2 | 2 |
| RTX_10K_2026 | pre_seek_slice | 120.8 | 1..2 | 2 |
| TRV_10K_2023 | pre_seek_slice | 950.8 | **1..5** | **5** |
| CMCSA_10K_2026 | full_doc1_fallback | — | 2..4 | 4 |
| GE_10K_2023 | full_doc1_fallback | — | **0..5** | **5** |

---

## Finding 1: Pre-seek slices are NOT flat — they ARE hierarchical

The RFC-007 draft stated (as a risk) that pre-seek HTML slices might produce
shallow 1–2 level trees vs. full-doc's 3–4 levels. The audit contradicts the
oversimplification:

- **All 8 pre-seek cases** have `TopSectionTitle` as their root node. The
  pre-seek HTML slice always begins at the Item 1A heading tag, which sec-parser
  correctly classifies as a `TopSectionTitle`.
- **Text node depth in pre-seek cases ranges from 1 to 5** — identical to the
  full-doc fallback range (0..5).
- TRV_10K_2023 is parsed via pre-seek (950.8 KB slice) and reaches depth 5.
  ITW_10K_2025 reaches depth 4 on a 42 KB pre-seek slice.

**The depth variation is driven by the internal structure of the Risk Factors
section itself, not by the parse path.** Filings that use multi-level heading
hierarchies (category → subcategory → individual risk title → paragraph)
produce deeper trees regardless of whether the full document or a pre-seek
slice was parsed.

## Finding 2: PART I ancestor is always absent in pre-seek; GE shows depth-0 edge case

The RFC's stated concern stands for a different reason:

- **Pre-seek cases**: outermost ancestor is always `"Item 1A..."`. `"PART I"` /
  `"PART II"` is never present because the HTML slice begins at Item 1A, not at
  the part boundary.
- **Full-doc cases** (CMCSA, GE): `"Part I"` appears as an ancestor (CMCSA
  depth-2 samples show `['Part I', 'Item 1: Business', ...]`).
- **GE edge case**: Two text nodes at depth 0 (empty ancestor list `[]`). These
  are `TextElement` nodes at the root level of the full document (cover page
  boilerplate before any `TopSectionTitle`). This confirms Behavioral Invariant 1:
  ancestors CAN be `[]`.

## Finding 3: Four distinct depth profiles observed in pre-seek

| Profile | Depth range | Example | Structural pattern |
|---------|------------|---------|-------------------|
| **Flat** | 1..2 | AAPL, BA, MMM, RTX | `Item 1A → [SubsectionTitle → TextElement*]` |
| **Shallow-uniform** | 2..2 | O_10K | All TextElements directly under one subsection level |
| **3-level** | 1..3 | DIS | `Item 1A → CategoryTitle → IndividualRiskTitle → TextElement` |
| **4-level** | 2..4 | ITW | `Item 1A. → Risk Factors → CategoryTitle → IndividualRiskTitle → TextElement` |
| **5-level** | 1..5 | TRV | Full 4-level heading hierarchy below Item 1A |

The **4-level ITW case** is especially revealing: ITW's pre-seek HTML begins
with `ITEM 1A.` as one `TopSectionTitle` and `Risk Factors` as a nested
`TitleElement`, then `Economic Risks` as a sub-TitleElement, then individual
risk paragraph titles as a third TitleElement level — producing an ancestor
chain `["ITEM 1A.", "Risk Factors", "Economic Risks", "Individual risk title"]`
for the deepest text nodes.

## Finding 4: \xa0 (non-breaking space) contamination in ancestor strings

Every filing shows `\xa0` characters in ancestor text (e.g., `"Item\xa01A."`,
`"Item\xa01A.\xa0\xa0\xa0\xa0Risk Factors"`). The `_build_ancestor_map()` helper
must normalize whitespace before storing:

```python
current_path.append(node.text.strip().replace('\xa0', ' '))
```

Without this, ancestor strings fail string equality checks and produce
malformed LLM prompts.

## Finding 5: id(node) mapping is stable

No `id()` collisions or node mutation was observed across the DFS pre-pass and
the subsequent flat iteration in `_extract_section_content`. OQ-2 from RFC-007
is confirmed safe.

---

## Schema Implications (updates to RFC-007)

### Confirmed invariants

1. `ancestors` MAY be `[]` (GE full-doc root-level nodes) — **confirmed**
2. Max observed depth is **5** in production across 10 filings
3. Pre-seek breadcrumbs always start from `"Item 1A..."`, never from `"Part I"`
4. Full-doc breadcrumbs may include `"Part I"` / `"Part II"` prefix

### New invariant (from audit)

5. **`ancestors[0]` in pre-seek cases is always the Item 1A heading text** (some
   variant of `"Item 1A..."`, `"ITEM\xa01A."`, `"Item 1A:\xa0Risk Factors"`).
   In full-doc fallback cases, `ancestors[0]` is `"Part I"` (when present) or a
   cover-page heading (`"Securities Registered Pursuant to..."`).

### Normalization requirement (new — not in RFC-007 draft)

`_build_ancestor_map()` MUST normalize each ancestor string:
```python
text = node.text.strip().replace('\xa0', ' ')
import re
text = re.sub(r'\s+', ' ', text)
text = text[:120]   # truncate to cap JSON size per node
```

### Depth cap for JSON safety

Max observed depth is 5. A hard cap of `ancestors[:6]` prevents pathological
nesting from bloating output in edge cases, without dropping any observed data.

---

## Updated OQ-1 Answer for RFC-007

> **OQ-1: In the pre-seek path, what is the deepest ancestor available for
> Item 1A content?**

**Answer: Up to depth 5 in production** (TRV pre-seek, 950 KB slice). The
depth is driven by the filing's own heading hierarchy, not the parse path.
The only structural difference between parse paths is:
- Pre-seek: `ancestors[0]` = Item 1A heading (PART context missing)
- Full-doc fallback: `ancestors[0]` may be `"Part I"` or a cover-page node

**Behavioral Invariant 1 stands but is now tightened:**
> `ancestors` is `[]` for root-level nodes in full-doc parses only.
> In pre-seek parses, `ancestors` is always non-empty (at minimum `["Item 1A..."]`).

The schema field `ancestors: List[str] = []` is correct. No maximum-length
constraint is needed beyond a soft cap of 6 for JSON safety.
