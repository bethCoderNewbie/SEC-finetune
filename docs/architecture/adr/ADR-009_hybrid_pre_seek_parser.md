# ADR-009: Hybrid Pre-Seek Parser Architecture with Pre-Sanitized Fragment

**Status:** Superseded by ADR-010
**Date:** 2026-02-22
**Author:** bethCoderNewbie

---

## Context

### Performance problem

`sec-parser.Edgar10QParser.parse()` processes the **entire Document 1 iXBRL body** to
classify every element before the extractor can isolate Item 1A. Empirical timing on
`AAPL_10K_2021.html` (commit `b9fb777`):

| Step | Time | % of total |
|------|------|-----------|
| `_flatten_html_nesting` (BS4, Fix 1A) | 2.12s | 11% |
| `Edgar10QParser.parse()` | 16.30s | **87%** |
| `TreeBuilder.build()` | 0.02s | <1% |
| **Total** | **18.44s** | 100% |

The 5-second target in `plans/2026-02-18_10-00-00_parser_finetune_fixes.md` is unachievable
for 10 MB files. At corpus scale (959 files, mean main body 5.2 MB, P95 15.3 MB), full-body
parsing takes 5–16 hours for a single batch run. Fix 1A eliminated DOTALL catastrophic
backtracking but did not reduce `Edgar10QParser` time.

### Classification problem

Even when `sec-parser` completes, page header text embedded in the Item 1A section flow is
**misclassified as `TitleElement`** rather than `PageHeaderElement`. Observed in production
output (`data/interim/20260220_190317_preprocessing_b9fb777/parsed/AAPL_10K_2024_parsed.json`):

```json
{
  "type": "TextElement",
  "text": "Macroeconomic conditions, including inflation, interest rates and currency
           fluctuations, have directly and indirectly impacted..."
},
{
  "type": "TitleElement",
  "text": "Apple Inc. | 2024 Form 10-K | 21"
}
```

The page footer `"Apple Inc. | 2024 Form 10-K | 21"` is promoted to `TitleElement` because:

1. In EDGAR HTML, page footers appear **inline in the document flow** as
   `<span style="font-weight:700;...">` nodes between content paragraphs.
2. sec-parser's `TitleClassifier` runs after `PageHeaderClassifier`. If
   `PageHeaderClassifier` does not recognise the inline pattern, `TitleClassifier`
   promotes any bold/highlighted node to `TitleElement`.
3. `PageHeaderClassifier` is designed for top/bottom page regions, not for inline
   pipe-delimited footers injected between paragraphs in EDGAR's XBRL-annotated HTML.

The misclassified `TitleElement` flows into `SECSectionExtractor._extract_section_content`
(`extractor.py:459–468`), where it is included in `content_nodes` and serialised into
`full_text`. This injects `"Apple Inc. | 2024 Form 10-K | 21"` into training segments —
a category error that FinBERT will attempt to learn as risk content.

### Root cause summary

The pipeline gives sec-parser a 5.2 MB HTML body and trusts its element classification
pipeline entirely. Both failure modes (latency and classification) stem from the same
cause: **sec-parser operates on the full document body without any pre-filtering of
scope or noise.**

---

## Decision

### Architecture: four-stage pre-seek pipeline

Replace the current single-step `Edgar10QParser(full_body)` call with a four-stage
pipeline. The four stages are sequenced so that each stage reduces the surface area that
the next stage must handle.

```
┌──────────────────────────────────────────────────────────┐
│ Stage 0 — SGML document boundary extraction              │
│  Input:  full SGML container (6–205 MB)                  │
│  Tool:   string seek (no HTML parser)                    │
│  Output: raw bytes of Document 1 only (~0.8–26 MB)       │
│  Time:   < 0.1s                                          │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│ Stage 1 — Anchor-based section pre-seek                  │
│  Input:  Document 1 HTML                                 │
│  Tool:   BeautifulSoup (lxml parser)                     │
│  Output: raw HTML slice from Item 1A start → Item 1B/2   │
│          anchor (~50–200 KB)                             │
│  Method: resolve ToC href → find matching <a id="…">     │
│  Time:   < 0.5s                                          │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│ Stage 2 — Pre-fragment sanitization                      │
│  Input:  raw Item 1A HTML slice                          │
│  Tool:   BeautifulSoup (same parse pass as Stage 1)      │
│  Output: sanitized HTML with page header nodes removed   │
│  Method: remove any node whose text matches              │
│          PAGE_HEADER_PATTERN before sec-parser sees it   │
│  Time:   < 0.1s (inline with Stage 1)                   │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│ Stage 3 — sec-parser on sanitized fragment               │
│  Input:  sanitized ~50–200 KB HTML                       │
│  Tool:   Edgar10QParser (unchanged)                      │
│  Output: semantic element tree (TextElement,             │
│          TitleElement, TableElement, …)                  │
│  Time:   ~1–2s (vs 16–18s on full body)                  │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│ Stage 4 — Extractor post-filter (defense in depth)       │
│  Input:  sec-parser element tree                         │
│  Tool:   extractor.py (existing)                         │
│  Action: drop any TitleElement matching                  │
│          PAGE_HEADER_PATTERN that Stage 2 missed         │
└──────────────────────────────────────────────────────────┘
```

### Governing rules

**Rule 1 — Never pass a raw HTML slice to sec-parser.**
The output of Stage 1 is always sanitized (Stage 2) before being handed to sec-parser.
A raw, unsanitized slice exposes sec-parser to the same inline page header pattern that
causes the `TitleElement` misclassification documented above.

**Rule 2 — Pre-sanitization and post-filter both run, unconditionally.**
Stage 2 removes nodes from the HTML. Stage 4 drops elements from the tree. These are not
alternatives — both run on every filing. Stage 2 prevents sec-parser from ever classifying
the noise. Stage 4 catches cases where Stage 2 missed a variant.

**Rule 3 — The PAGE_HEADER_PATTERN is the single source of truth.**
One compiled pattern is defined in `extractor.py` and shared by both Stage 2 and Stage 4:

```python
PAGE_HEADER_PATTERN = re.compile(
    r'.+\|\s*\d{4}\s+Form\s+10-[KQ]\s*\|\s*\d+',
    re.IGNORECASE
)
```

This matches the EDGAR pipe-delimited footer format:
`CompanyName | YYYY Form 10-K | PageNumber`

If new footer formats are observed in the corpus, the pattern is updated in one place and
both stages benefit. Pattern updates require a corpus regression test before merge.

**Rule 4 — Stage 0 uses string seek, not BeautifulSoup.**
The SGML `<DOCUMENT>` boundary is located by scanning for the first
`<DOCUMENT>` / `</DOCUMENT>` tag pair using `str.find()` — no HTML parse overhead.
BS4 is only instantiated once, on Document 1 bytes.

**Rule 5 — Fallback for anchor-less filings.**
If Stage 1 finds no ToC `<a href="#...">` targeting an Item 1A identifier, the pipeline
falls back to the current full-document parse path (Fix 1A BS4 flatten → full
`Edgar10QParser.parse()`). Fallback preserves 100% filing coverage.

### Stage 1 anchor resolution

EDGAR ToC entries link to section bodies via named anchors:

```html
<!-- Inside ToC table -->
<a href="#i4bf6d0bde838478985b72eb4052bc976_19">Item 1A. Risk Factors</a>

<!-- The actual section body -->
<a id="i4bf6d0bde838478985b72eb4052bc976_19"></a>
```

Stage 1 locates the Item 1A anchor in two passes:

1. **Forward pass:** find the ToC `<a href>` whose link text matches
   `re.search(r'item\s+1a', text, re.IGNORECASE)`. Extract the fragment ID from `href`.
2. **Boundary pass:** find the matching `<a id="FRAGMENT_ID">` in the document.
   The Item 1A slice ends at the first subsequent `<a id="…">` whose sibling text
   matches `re.search(r'item\s+(1b|2)\b', text, re.IGNORECASE)`.

The raw HTML bytes between the two anchor positions form the Stage 1 output slice.

### Stage 2 sanitization (inline with Stage 1 BS4 parse)

During the same BS4 parse used for Stage 1, before extracting the slice, decompose
(remove from the parse tree) any tag whose `.get_text()` matches `PAGE_HEADER_PATTERN`.
The sanitized serialisation of the trimmed parse tree is the Stage 2 output.

This removes nodes like:

```html
<p><span style="font-size:9pt;font-weight:700;">Apple Inc. | 2024 Form 10-K | 21</span></p>
```

before sec-parser ever sees the HTML. The `font-weight:700` attribute that triggers
`TitleClassifier` is absent from the sanitized fragment.

### Stage 4 post-filter (defense in depth)

In `SECSectionExtractor._extract_section_content`, after sec-parser returns the element
tree, filter `content_nodes` before building `full_text`:

```python
content_nodes = [
    node for node in content_nodes
    if not (
        isinstance(node, TitleElement)
        and PAGE_HEADER_PATTERN.search(node.text)
    )
]
```

This catches page footer variants that Stage 2 missed (e.g., filings where the footer
text is split across multiple `<span>` tags that BS4 resolves differently during
`.get_text()` extraction).

---

## Consequences

**Positive:**
- Parsing latency: 18.44s → ~2s per 10 MB filing (≈10x improvement)
- Corpus throughput: 5–16 hours → ~32 minutes for 959 files
- `"Apple Inc. | 2024 Form 10-K | 21"`-class elements are removed before
  sec-parser classifies them; `TitleElement` misclassification eliminated for the
  documented pattern
- `PAGE_HEADER_PATTERN` is auditable, testable, and corpus-regressionable in a
  single location
- Fallback path preserves 100% filing coverage for anchor-less filings
- sec-parser's `TextElementMerger` and `TitleClassifier` are retained — the
  `<span>`-reassembly capability that justified ADR-002 is unchanged

**Negative:**
- Stage 1 anchor resolution adds a dependency on EDGAR ToC formatting. If a filing
  uses JavaScript-generated ToC or non-standard `href` patterns, it silently falls
  back to the full-parse path (slower but correct).
- Stage 2 sanitization operates on BS4's `.get_text()` representation — split-span
  page footers whose individual `<span>` elements do not match the pattern in isolation
  will not be removed by Stage 2. Stage 4 provides the fallback for these cases but
  requires that the rejoined `TitleElement.text` be intact (which `TextElementMerger`
  guarantees).
- `PAGE_HEADER_PATTERN` is company-name-agnostic (matches any text before ` | YYYY
  Form 10-K | N`). A risk factor segment that legitimately contains a pipe-delimited
  string matching this pattern would be incorrectly stripped. This is considered
  pathologically unlikely in the corpus; the pattern must be monitored in corpus
  regression runs.
- Two-stage sanitization (Stage 2 + Stage 4) requires tests for both independently.
  Omitting either stage silently degrades quality without a hard failure.

---

## Supersedes

Supersedes the single-step `Edgar10QParser(full_body)` parse path described in ADR-002
for the `extractor.py` item isolation step. ADR-002's decision to use `sec-parser`
(over custom regex) is **unchanged**; this ADR governs the scope of HTML passed to
sec-parser, not the choice of library.

---

## References

- `src/preprocessing/parser.py:412-466` — `_flatten_html_nesting` (Fix 1A, active)
- `src/preprocessing/extractor.py:459-468` — `_extract_section_content`, `content_nodes` construction
- `data/interim/20260220_190317_preprocessing_b9fb777/parsed/AAPL_10K_2024_parsed.json` — production evidence of `TitleElement` misclassification
- `thoughts/shared/research/2026-02-22_10-00-00_aapl_parser_metrics_audit.md` — empirical timing breakdown (16.30s in `Edgar10QParser`, 87% of total)
- `thoughts/shared/research/2026-02-22_18-09-02_full_pipeline_finetune_readiness.md` §4.5 — pre-seek architecture design (supersedes §4.6 of `2026-02-18_15-26-29`)
- `reports/sec_html_structure/2026-02-22_17-57-43_sec_html_structure_findings.md` §F1, §1.2 — SGML container structure; Document 1 mean 5.2 MB vs container mean 28.5 MB
- ADR-002 — original `sec-parser` adoption decision (unchanged)
