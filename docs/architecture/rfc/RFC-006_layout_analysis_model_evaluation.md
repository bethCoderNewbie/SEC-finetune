---
id: RFC-006
title: Layout Analysis Model Evaluation for SEC EDGAR Filings
status: DRAFT
author: beth88.career@gmail.com
created: 2026-02-24
last_updated: 2026-02-24
git_sha: 997a101
superseded_by: null
related_prd: docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md
related_adr: docs/architecture/adr/ADR-002_sec_parser.md
related_adr: docs/architecture/adr/ADR-010_hybrid_pre_seek_parser_corrected.md
---

# RFC-006: Layout Analysis Model Evaluation for SEC EDGAR Filings

## Status

**DRAFT** — Decision pending. See §Options and §Recommendation.

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

```python
# extractor.py (new helper, ~50 LoC)
_LIST_TAG_NAMES = frozenset({'li'})
_BULLET_PREFIX_PAT = re.compile(r'^\s*[•\-–—*]\s+|^\s*\(\d+\)\s+|^\s*\d+\.\s+')

def _is_list_item(node: sp.AbstractSemanticElement) -> bool:
    tag_name = getattr(node.html_tag, 'name', '')
    if tag_name in _LIST_TAG_NAMES:
        return True
    return bool(_BULLET_PREFIX_PAT.match(node.text or ''))
```

Elements identified as list items receive `is_list_item: True` in the `elements`
list of `ExtractedSection`. The segmenter can treat each list item as an implicit
segment boundary (subject to `min_segment_words` floor).

**SEC EDGAR HTML reality:** EDGAR filings use `<ul>/<li>` tags in roughly 60–70%
of modern iXBRL filings. Legacy plain-text-derived HTML uses bullet prefix
characters (`•`, `-`, `(1)`, `1.`). Both are detectable with zero ML overhead.

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

- **A2b (level-threshold):** Observe the corpus empirically: Level 0 is almost
  always a part/item heading; level 1 is almost always a subsection. Define a
  configurable `level_to_hlabel` mapping in `configs/config.yaml`. Works for
  the overwhelming majority of 10-K filings where EDGAR-mandated section
  structure is uniform.

Recommendation: **A2a** (structural anchoring) is filing-format-invariant.

### Sub-option A3: Paragraph boundary annotation within `TextElement`

`TextElement` may span multiple HTML `<p>` tags merged by sec-parser's
`TextElementMerger`. Adding `paragraph_count: int` and `boundaries: List[int]`
(character offsets of `</p>` boundaries) to the elements dict enables the
segmenter to break on paragraph seams before falling back to sentence splitting.

This is a BS4 pass on `node.html_tag` (~30 LoC) with no new dependencies.

### Complexity and risk

| Sub-option | LoC | New deps | GPU | Risk |
|------------|-----|----------|-----|------|
| A1 ListItem detection | ~100 | None | No | Low |
| A2a H-label normalization | ~80 | None | No | Low |
| A2b H-label (threshold) | ~30 | None | No | Low |
| A3 paragraph boundaries | ~50 | None | No | Low |
| **Total Option A** | **~260** | **None** | **No** | **Low** |

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
| Estimated LoC | ~260 | ~400 + labeling pipeline | ~800 + rendering pipeline |
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

| # | Question | Recommendation |
|---|----------|---------------|
| OQ-1 | What fraction of the 959-file corpus uses `<li>` tags vs. bullet-prefix text? | Sample 20 files; measure `<li>` tag presence via BS4 before implementing A1 |
| OQ-2 | Are there filings where `level=0` is NOT a Part/Item heading? | Audit `TitleElement(level=0)` text across 50 filings; confirm A2a structural anchoring holds |
| OQ-3 | Should `ListItem` be a new `AbstractSemanticElement` subtype (requiring monkey-patching sec-parser) or a flag in the `elements` dict? | Use `elements` dict flag (`is_list_item: bool`) to avoid sec-parser internal mutation |
| OQ-4 | Does paragraph boundary annotation conflict with `TextElementMerger`? | `TextElementMerger` runs before Stage 3; A3 operates on merged outputs, so no conflict |

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
