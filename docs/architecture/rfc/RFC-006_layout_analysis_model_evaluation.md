---
id: RFC-006
title: Layout Analysis Model Evaluation for SEC EDGAR Filings
status: IMPLEMENTED
author: beth88.career@gmail.com
created: 2026-02-24
last_updated: 2026-02-25
git_sha: 4045f92
superseded_by: null
related_prd: docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md
related_adr: docs/architecture/adr/ADR-002_sec_parser.md
related_adr: docs/architecture/adr/ADR-010_hybrid_pre_seek_parser_corrected.md
decision_adr: docs/architecture/adr/ADR-013_rfc006_layout_annotation_a1_a2a.md
---

# RFC-006: Layout Analysis Model Evaluation for SEC EDGAR Filings

## Status

**IMPLEMENTED** — A1 and A2a adopted. See ADR-013. A3 (paragraph boundaries) deferred.

---

## Context

The gap analysis in
`thoughts/shared/research/2026-02-24_10-00-00_ingestion_normalization_gap_analysis.md`
identified three weaknesses in the current layout tagging layer (Step 2 of the
proposed 5-step pipeline):

1. **No `ListItemElement` type.** Bulleted and numbered risk entries inside Item
   1A are classified as generic `TextElement`. The segmenter therefore cannot
   distinguish "this `TextElement` is a list entry that deserves its own segment
   boundary" from "this `TextElement` is a flowing paragraph to be merged."

2. **Document-relative title levels.** `TitleElement.level` is an integer
   assigned by `TitleClassifier` based on **order of unique CSS style
   appearance** within a single filing (`sec_parser/processing_steps/
   title_classifier.py`, `_unique_styles_by_order`). Level 0 is the first
   unique bold/large-font style encountered — not a canonical H1. This means:
   - Level integers are not comparable across filings.
   - The same section heading may be `level=0` in one filing and `level=1` in
     another (if a bolder title appears earlier in a different filing).

3. **`PageHeaderClassifier` failure for inline footers.** The classifier uses a
   repetition-count heuristic; it correctly identifies boilerplate repeated
   across pages but fails for pipe-delimited inline footer patterns
   `CompanyName | Year Form 10-K | Page N` (documented in ADR-009, resolved by
   `PAGE_HEADER_PATTERN` regex in Stage 3 of ADR-010).

The question raised is: **should a model-based layout analysis step —
LayoutLM, DocLayNet, or Detectron2 — replace or augment the current
rule-based sec-parser classifiers?**

---

## How sec-parser's Layout Analysis Works Today

Understanding the internals is essential to evaluate whether a model is needed.

### Title level assignment (`TitleClassifier`)

```
HTML block element
  → compute_text_styles_metrics(tag)  [bs4 style traversal, inline CSS]
  → HighlightedTextClassifier: if unique CSS style found → HighlightedTextElement
  → TitleClassifier: maintains _unique_styles_by_order tuple
       level = index of element.style in _unique_styles_by_order
       (i.e. first unique bold style seen = level 0, next unique bold size = level 1)
  → TitleElement(level=N)
```

The signal is **inline CSS properties** (`font-weight`, `font-size`, `text-decoration`)
extracted by traversing the BS4 parent chain. This is the *same* signal a human
would use when reading the HTML source. For HTML-native documents, inline CSS is
precise and explicit.

### Failures actually observed

| Failure | Root cause | Already fixed? |
|---------|-----------|----------------|
| Pipe-delimited page footer not detected as `PageHeaderElement` | `PageHeaderClassifier` counts repetitions; inline pipe patterns are not repeated verbatim | Yes — `PAGE_HEADER_PATTERN` regex in Stage 3 (ADR-010) |
| `<li>` items as `TextElement` | No `ListClassifier` in sec-parser's processing pipeline | No |
| Level integers not comparable across filings | By-design: levels are document-relative | No — not yet normalized |
| ToC lines leaking into section content | `TableOfContentsClassifier` uses `html_tag.is_table_of_content()` heuristic, misses some formats | Partially — 7-pattern `TOC_PATTERNS_COMPILED` added in Stage 3 |

---

## Option A: Rule-based Post-processing Enhancements (No New Model)

**Description:** Extend the Stage 3 element-level post-filter
(`extractor.py:_extract_section_content`) and add a new post-processor module
that operates on `sec-parser`'s element list before segmentation.

### Sub-option A1: `ListItem` detection

> **Updated 2026-02-25 based on OQ-1 corpus audit.** `<li>` tags are absent from all 961 corpus files (0%). The `_LIST_TAG_NAMES` branch is removed. The bullet-prefix pattern is corrected to match EDGAR's `•word` format (no space after bullet).

```python
# extractor.py (new helper, ~40 LoC)
# NOTE: <li>/<ul>/<ol> tags have 0% corpus coverage — omitted.
# EDGAR uses inline unicode bullet chars with NO space before the next word.
_BULLET_PREFIX_PAT = re.compile(
    r'^\s*[•·▪▸►‣⁃]\s*\S'   # unicode bullet + optional space + non-whitespace
    r'|^\s*\(\d+\)\s+'        # (1) parenthetical  — 27.3% of corpus
    r'|^\s*\d+\.\s+',         # 1. numbered list
)

def _is_list_item(node: sp.AbstractSemanticElement) -> bool:
    return bool(_BULLET_PREFIX_PAT.match(node.text or ''))
```

Elements identified as list items receive `is_list_item: True` in the `elements`
list of `ExtractedSection`. The segmenter can treat each list item as an implicit
segment boundary (subject to `min_segment_words` floor).

**SEC EDGAR HTML reality (corpus audit, 2026-02-25):** EDGAR filings in this corpus do
**not** use `<ul>/<li>` tags (0/961 files). Lists are encoded as `TextElement` nodes
whose text begins with a unicode bullet character (`•`, `·`, `▪`) immediately followed
by the entry text — no whitespace separator. 94.1% of filings use this format; 27.3%
additionally use `(N)` parenthetical prefixes; 3.3% use only flowing paragraphs.

### Sub-option A2: H-label normalization

```python
# constants.py — new enum
class TitleLevel(enum.Enum):
    H1 = 0   # Part-level: "PART I", "PART II"
    H2 = 1   # Item-level: "ITEM 1A"
    H3 = 2   # Subsection: "Supply Chain Risk"
    H4 = 3   # Sub-subsection (rare)
    BODY = 99  # Not a title
```

The `TitleClassifier.level` integer (document-relative 0..N) cannot be
mechanically mapped to H-labels without a reference point. Two strategies:

- **A2a (structural):** Anchor H1 to `TopSectionTitle` nodes (PART I, PART II,
  etc. — already identified by sec-parser's `top_section_title_check`). Any
  `TitleElement` that matches the `SECTION_PATTERNS` for Item-level headings
  → H2. Any other `TitleElement` → H3/H4 by `level` increment. This is
  deterministic and filing-independent.

- **A2b (level-threshold):** ~~Observe the corpus empirically: Level 0 is almost
  always a part/item heading~~ **INVALIDATED by OQ-2 audit (2026-02-25): level=0
  is a subsection heading in 92.9% of occurrences across 50 sampled filings.**
  Level integers are CSS-order-appearance indices, not semantic hierarchy levels.
  A2b is not viable for this corpus.

Recommendation: **A2a only** (structural anchoring). A2b is ruled out by audit.

### Sub-option A3: Paragraph boundary annotation within `TextElement`

`TextElement` may span multiple HTML `<p>` tags merged by sec-parser's
`TextElementMerger`. Adding `paragraph_count: int` and `boundaries: List[int]`
(character offsets of `</p>` boundaries) to the elements dict enables the
segmenter to break on paragraph seams before falling back to sentence splitting.

This is a BS4 pass on `node.html_tag` (~30 LoC) with no new dependencies.

### Complexity and risk

| Sub-option | LoC | New deps | GPU | Risk | Status |
|------------|-----|----------|-----|------|--------|
| A1 ListItem detection | ~40 | None | No | Low | Revised — `<li>` branch removed (0% corpus), pattern corrected for `•word` format |
| A2a H-label normalization | ~80 | None | No | Low | Confirmed viable |
| A2b H-label (threshold) | — | — | — | — | **Ruled out** — level=0 is 92.9% non-Item headings (OQ-2 audit) |
| A3 paragraph boundaries | ~50 | None | No | Low | Confirmed no conflict with TextElementMerger (OQ-4) |
| **Total Option A (A1+A2a+A3)** | **~170** | **None** | **No** | **Low** | |

Conflicts with existing architecture: **None.** Option A operates on the
sec-parser output element list after Stage 2 — it does not touch HTML before
sec-parser (Rule 1, ADR-010) and does not require any ADR to be superseded.

---

## Option B: Fine-tuned Text Classifier on sec-parser Outputs

**Description:** Train a small BERT-style classifier (DistilBERT or similar) to
re-classify sec-parser `AbstractSemanticElement` outputs using text content +
a few structural signals (tag name, CSS class, parent depth).

**Input features:**
- Element text (truncated to 128 tokens)
- `html_tag.name` (div, p, li, span, td, …)
- Boolean flags: `is_bold`, `is_large_font` (from inline CSS)
- `depth` in sec-parser tree

**Output labels:** `{Title_H1, Title_H2, Title_H3, ListItem, Paragraph,
TableCaption, FootNote, PageHeader, ToC}`

**Why this would work for HTML-native filings:**
The input features already capture the same signals as the rule-based
classifiers. The marginal gain over Option A is robustness to unusual CSS
(e.g., a filing that bolds all text, making `HighlightedTextClassifier` fire
on everything).

**Why this is over-engineered for the current problem:**

1. **Training data does not exist.** We would need to hand-label element-level
   annotations across ~100 filings (thousands of elements). This is a
   significant human-labeling effort.

2. **CSS signal is already exact.** For HTML-native EDGAR filings, inline CSS
   is a deterministic signal for title vs. non-title. ML would add variance,
   not accuracy.

3. **Adds a GPU inference requirement.** Even DistilBERT at inference requires
   ~500 MB RAM and optional CUDA. This conflicts with the CPU-only preprocessing
   worker pool (ADR-003).

4. **Fragile to sec-parser changes.** If sec-parser v0.55+ changes element
   types, the classifier's input distribution shifts silently.

**Verdict:** Not recommended until Option A is implemented and measured failures
are documented that rule-based approaches cannot fix.

---

## Option C: Visual Layout Models — LayoutLM, DocLayNet, Detectron2

**Description:** Apply a multimodal visual layout model to classify document
regions from rendered page images.

- **LayoutLMv3** (`microsoft/layoutlmv3-base`, 125 M params): Jointly attends
  to text, layout (bounding boxes), and pixel features. Trained on IIT-CDIP,
  DocVQA, PubLayNet.
- **DocLayNet** (`ds4sd/DocLayNet`): IBM Research. 11 label types (Text,
  Title, List, Table, Figure, Caption, Footnote, Formula, Page-footer,
  Page-header, Section-header). 80,863 manually annotated pages from PDFs.
- **Detectron2** (Facebook): General object-detection framework. Used as
  backbone for DocLayNet, PubLayNet, and similar layout-detection datasets.

### Why these models are architecturally mismatched to EDGAR HTML filings

#### 1. Input modality mismatch

All three models operate on **rendered page images** (pixels) with bounding
box coordinates in the (x, y, width, height) space of a rendered page. EDGAR
filings are **HTML-native documents** — they have no pixel representation
unless explicitly rendered.

To use LayoutLM on an EDGAR 10-K:

```
SGML container (5–200 MB HTML)
    ↓ extract Document 1 HTML
    ↓ render to PDF (headless Chrome / wkhtmltopdf) — 10–60 seconds per filing
    ↓ rasterize PDF pages to images — 1–3 seconds per page, ~50–150 pages
    ↓ OCR or pdfplumber bounding box extraction
    ↓ LayoutLM inference — ~0.5s per page on GPU
    ↓ map predicted bounding boxes back to HTML elements (fragile)
```

This pipeline:
- Adds **20–120 minutes** of rendering time per 959-file corpus run
- Requires headless Chrome or wkhtmltopdf (environment dependency)
- Requires a GPU (LayoutLMv3 is not practical on CPU at this scale)
- Produces **pixel-space bounding boxes** that must be re-mapped to HTML
  elements — a lossy, error-prone step with no guaranteed alignment

#### 2. CSS provides superior signals for HTML-native documents

`TitleClassifier` extracts **exact inline CSS** (`font-weight: bold`,
`font-size: 16pt`, etc.) from the HTML source. This is the *ground truth* of
what a browser would render. LayoutLM, by contrast, infers these properties
by looking at rendered pixels — which introduces rendering noise, font
substitution artifacts, and anti-aliasing blur.

For HTML-native documents, rule-based CSS analysis is strictly more accurate
than pixel inference.

#### 3. Training distribution mismatch

LayoutLMv3 and DocLayNet are trained on **general document corpora** (financial
PDFs, scientific papers, forms). Their label taxonomy (`Text`, `Title`, `List`,
`Table`, `Figure`) does not map cleanly to EDGAR-specific elements
(`TopSectionTitle`, `TableOfContentsElement`, `PageHeaderElement`). Fine-tuning
on EDGAR would require the same hand-labeling effort as Option B, plus the
rendering infrastructure.

#### 4. When visual layout models would be appropriate

Visual layout models are the correct choice **only if**:

- The source format is PDF (not HTML), or
- HTML-to-PDF conversion has already been performed and the HTML is not
  available, or
- Scanned/image-based filings are in scope (e.g., pre-2000 EDGAR filings
  submitted as TIFF/GIF images)

For the current corpus (post-2000 iXBRL/HTML filings), none of these
conditions hold. EDGAR has mandated inline XBRL (iXBRL) HTML since 2018 for
large accelerated filers. The entire processing corpus is HTML-native.

### Complexity and risk

| Dimension | Cost |
|-----------|------|
| Rendering infrastructure | headless Chrome + wkhtmltopdf, OS-level deps |
| Compute per filing | 30–120 seconds rendering + 25–75 seconds inference (GPU) |
| GPU requirement | Yes — LayoutLMv3 inference on CPU: ~90 seconds/page |
| Training data | 100+ manually annotated EDGAR filings (thousands of pages) |
| Bounding-box → HTML mapping | Fragile heuristic, ~15–25% alignment error expected |
| ADR conflicts | ADR-002 (sec-parser pinned), ADR-003 (CPU-only worker pool), ADR-010 Rule 1 |
| **Risk** | **Very High** |

---

## Comparative Summary

| Dimension | Option A (Rules) | Option B (Text ML) | Option C (Visual ML) |
|-----------|-----------------|-------------------|---------------------|
| Modality match | ✅ HTML-native | ✅ HTML-native | ❌ Requires image rendering |
| Adds `ListItem` type | ✅ Yes (`<li>` + prefix regex) | ✅ Yes (if labeled) | ⚠️ Indirect (bounding box mapping) |
| H1/H2/H3 normalization | ✅ Structural anchoring | ✅ Yes (if labeled) | ⚠️ Maps to coarse label |
| Paragraph boundaries | ✅ `<p>` tag detection | ⚠️ Requires feature | ❌ Not available |
| New dependencies | None | `transformers`, labeling tool | Headless Chrome, GPU, `detectron2` |
| Estimated LoC | ~170 (A2b ruled out; A1 revised) | ~400 + labeling pipeline | ~800 + rendering pipeline |
| GPU required | No | Optional (CPU viable) | Yes |
| Training data needed | None | ~100 labeled filings | ~100+ labeled filings |
| Latency impact | < 1 ms | ~50 ms/filing (CPU) | 30–120 s/filing |
| ADR conflicts | None | ADR-003 (worker pool) | ADR-002, ADR-003, ADR-010 Rule 1 |
| Risk | Low | Medium | Very High |

---

## Recommendation

**Adopt Option A.** Rule-based post-processing enhancements are the correct
architectural fit for HTML-native EDGAR filings. Implement in three sub-options
in priority order:

1. **A1 (ListItem)** — highest immediate impact on segmentation quality. Allows
   `RiskSegmenter` to use list item boundaries as natural split points, reducing
   the frequency of mid-list sentence-boundary splits.

2. **A2a (H-label normalization)** — enables cross-filing comparisons and
   contextual enrichment (Step 3 of the proposed pipeline). Anchors to
   `TopSectionTitle` nodes (already classified by sec-parser) for
   filing-format-invariant mapping.

3. **A3 (paragraph boundaries)** — tertiary improvement to segmentation; lower
   priority than A1/A2.

**Do not adopt Option C** for any filings in the current corpus. Visual layout
models are architecturally mismatched to HTML-native documents and would add
infrastructure complexity (rendering, GPU, bounding box re-mapping) that
provides strictly less accuracy than inline CSS analysis.

**Defer Option B** until: (a) Option A is implemented and production failures
are documented that rule-based post-processing cannot address, and (b) a
labeled dataset of EDGAR elements is available from the annotation corpus
effort (PRD-002 G-16).

### Scope of this RFC

This RFC covers **layout analysis of in-scope EDGAR HTML filings only**
(post-2000 10-K/10-Q iXBRL HTML). Out of scope:

- Pre-2000 scanned/image EDGAR filings (would require Option C)
- 8-K filings (non-goal per PRD-002/PRD-004)
- PDF-sourced conversions (not present in current corpus)
- Full document tree serialization (covered by the contextual enrichment
  gap — separate implementation task)

---

## Open Questions

> All four OQs resolved by corpus audit on 2026-02-25.
> See `thoughts/shared/research/2026-02-24_10-00-00_ingestion_normalization_gap_analysis.md` §Step 2.

| # | Question | Status | Finding |
|---|----------|--------|---------|
| OQ-1 | What fraction of the 959-file corpus uses `<li>` tags vs. bullet-prefix text? | **RESOLVED** | See below |
| OQ-2 | Are there filings where `level=0` is NOT a Part/Item heading? | **RESOLVED** | See below |
| OQ-3 | Should `ListItem` be a new `AbstractSemanticElement` subtype or a flag in the `elements` dict? | **RESOLVED** | Elements dict flag confirmed |
| OQ-4 | Does paragraph boundary annotation conflict with `TextElementMerger`? | **RESOLVED** | No conflict confirmed |

### OQ-1 — Corpus-wide bullet format audit (961 files)

Full corpus scan (all 961 files via `extract_document` + regex, 2026-02-25):

| Format | Files | % |
|--------|------:|---|
| `<li>` / `<ul>` / `<ol>` tags | **0** | **0.0%** |
| Unicode bullet chars (`•`, `·`, `▪`, `&#8226;`) | 902 | 94.1% |
| Parenthetical `(N)` prefix in `<p>`/`<div>` | 262 | 27.3% |
| Dash/en-dash prefix (`-`, `–`, `—`) in tag | 215 | 22.4% |
| None of the above (pure flowing paragraphs) | 32 | 3.3% |

**Key finding: `<li>` tags do not appear in any filing in this corpus (0/961).** The RFC-006 A1 sample code's `_LIST_TAG_NAMES = frozenset({'li'})` check is a no-op for this corpus and should be removed.

The dominant pattern (94.1%) is a unicode bullet character (`•`) embedded directly as the first character of a `TextElement`'s text node — with **no space** between the bullet and the word that follows (e.g., `•our future financial performance...`, `•Cybersecurity`, `•Supply chain disruption`). This means the current `_BULLET_PREFIX_PAT` in the RFC must be updated: the `\s+` after the bullet character must become `\s*` to match the corpus-actual format.

**Corrected A1 pattern:**
```python
# Remove the <li> branch entirely — 0% corpus coverage.
# \s* (not \s+) after bullet — EDGAR emits •word with no space.
_BULLET_PREFIX_PAT = re.compile(
    r'^\s*[•·▪▸►‣⁃]\s*\S'   # unicode bullet + optional space + non-whitespace
    r'|^\s*\(\d+\)\s+'        # (1) parenthetical
    r'|^\s*\d+\.\s+'          # 1. numbered
)
```

### OQ-2 — `TitleElement(level=0)` audit across 50 filings

Full `iter_elements` walk over `Edgar10QParser` output for 50 randomly sampled filings (2026-02-25):

| Level | Node count | Item/Part match (OQ-2 check) |
|-------|------------|-------------------------------|
| 0 | 3,387 | 239 (7.1%) |
| 1 | 2,907 | — |
| 2 | 1,806 | — |
| 3 | 1,514 | — (but `ITEM 1A. RISK FACTORS` observed at level=3 in one filing) |
| 4–11 | 1,940 | — |

**Key finding: `level=0` is NOT reliably an Item/Part heading — 92.9% of level=0 nodes are subsection headings** such as `"Overview"`, `"Competition"`, `"Results of Operations"`, `"Basis for Opinion"`. The assumption underlying RFC-006 A2b ("level 0 is almost always a part/item heading") is **empirically false**.

**Consequence for A2a vs A2b:**

- **A2b (level-threshold mapping) is NOT viable.** Level integers are purely order-of-CSS-appearance indices, and level=0 is the most common heading level in the corpus (~68 occurrences per filing on average), not a reliable proxy for Part/Item structure.
- **A2a (structural anchoring via `TopSectionTitle`) remains correct.** It anchors H1/H2 to nodes already classified by sec-parser's `top_section_title_check`, which operates on EDGAR's mandated section identifiers — not on CSS order. TitleElement level integers should only be used for *relative* ordering among TitleElement siblings under the same TopSectionTitle parent, not as absolute H-labels.

`ITEM 1A. RISK FACTORS` appearing at `level=3` in one audited filing further confirms that level integers cannot be used as absolute hierarchy indicators across filings.

### OQ-3 — `is_list_item` flag vs. new `AbstractSemanticElement` subtype

**Confirmed: elements dict flag is the correct choice** (`is_list_item: bool` in the `element_dict`). Reasons:

1. Bullet detection (OQ-1) operates on `node.text` pattern matching — a post-hoc classification applied to `TextElement` output. There is no hook point in sec-parser's processing pipeline to inject a new element type without forking the library.
2. A new subtype would need to be inserted before `TextElementMerger` (which runs during parse) — not possible without monkey-patching sec-parser internals and would break on sec-parser version upgrades (ADR-002 pin).
3. `<li>` has 0% corpus coverage, removing the only structural signal that could cleanly justify a new type. Bullet detection is text-heuristic, not structural, making a flag the right representation.

### OQ-4 — Paragraph boundary annotation vs. `TextElementMerger`

**Confirmed: no conflict.** `TextElementMerger` runs during sec-parser's `parse()` call (Stage 2), assembling `<span>`-fragmented inline text into `TextElement` nodes. By the time Stage 3 (`extractor.py:_extract_section_content`) runs, the merged `TextElement` carries its `html_tag` (a BS4 tag). A3's BS4 pass on `node.html_tag` to record `<p>` boundary offsets operates entirely on the already-merged output — it does not re-enter the sec-parser processing pipeline.

---

## References

- `src/preprocessing/extractor.py:302–420` — `_extract_section_content`, where post-filter runs
- `src/preprocessing/constants.py:177–191` — `TEXT_ELEMENT_TYPES`, `TITLE_ELEMENT_TYPES`, `TABLE_ELEMENT_TYPES`
- `sec_parser/processing_steps/title_classifier.py` — `_unique_styles_by_order` level assignment
- `sec_parser/utils/bs4_/text_styles_metrics.py` — `compute_text_styles_metrics`, CSS feature extraction
- `docs/architecture/adr/ADR-002_sec_parser.md` — sec-parser version pin and invariants
- `docs/architecture/adr/ADR-010_hybrid_pre_seek_parser_corrected.md` — Rule 1 (no HTML modification before sec-parser)
- `docs/architecture/adr/ADR-003_global_worker_pool.md` — CPU-only worker pool constraint
- `thoughts/shared/research/2026-02-24_10-00-00_ingestion_normalization_gap_analysis.md` — gap analysis that prompted this RFC
