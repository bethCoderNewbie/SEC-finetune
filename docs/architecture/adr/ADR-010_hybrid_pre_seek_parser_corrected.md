# ADR-010: Hybrid Pre-Seek Parser Architecture with SGMLManifest (Supersedes ADR-009)

**Status:** Accepted — Implemented 2026-02-22
**Date:** 2026-02-22
**Author:** bethCoderNewbie
**Implementation git SHA:** 94d7d6e (plan) + subsequent bug-fix commits
**Bug report:** `thoughts/shared/research/2026-02-22_19-45-00_adr010_single_file_run_bugs.md`

---

## Context

ADR-009 defined a four-stage hybrid pre-seek architecture. **Stage 2 of that architecture
(pre-fragment sanitization via `bs4.Tag.decompose()` before passing the HTML slice to
sec-parser) was found to be unsafe** after auditing sec-parser v0.54.0 internals.
Additionally, ADR-009 Stage 0 was defined too narrowly: it extracted only Document 1 byte
boundaries, wasting the single sequential read of a 6–205 MB container that already passes
over all other embedded documents.

### Problem 1 — Performance

`sec-parser.Edgar10QParser.parse()` processes the **entire Document 1 iXBRL body** to
classify every element before the extractor can isolate Item 1A. Empirical timing on
`AAPL_10K_2021.html` (commit `b9fb777`):

| Step | Time | % of total |
|------|------|-----------|
| `_flatten_html_nesting` (BS4, Fix 1A) | 2.12s | 11% |
| `Edgar10QParser.parse()` | 16.30s | **87%** |
| `TreeBuilder.build()` | 0.02s | <1% |
| **Total** | **18.44s** | 100% |

The 5-second target is unachievable for 10 MB files. At corpus scale (959 files, mean
main body 5.2 MB, P95 15.3 MB), full-body parsing takes 5–16 hours per batch run.

### Problem 2 — TitleElement misclassification

Page footer text embedded in Item 1A section flow is misclassified as `TitleElement`
rather than `PageHeaderElement`. Observed in production output
(`data/interim/20260220_190317_preprocessing_b9fb777/parsed/AAPL_10K_2024_parsed.json`):

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

Root cause: in EDGAR HTML, page footers appear inline in the document flow as
`<span style="font-weight:700;...">` nodes between content paragraphs. sec-parser's
`TitleClassifier` promotes any bold node that `PageHeaderClassifier` did not claim.
`PageHeaderClassifier` is designed for top/bottom page regions, not inline
pipe-delimited footers. The misclassified `TitleElement` is serialised into `full_text`
and enters training data as if it were risk content.

### Why ADR-009 Stage 2 (BS4 decompose) is unsafe

ADR-009 attempted to fix the misclassification by removing page footer nodes from the
HTML fragment via `bs4.Tag.decompose()` before passing to sec-parser. Audit of
sec-parser v0.54.0 source reveals four independent failure modes:

| sec-parser component | Violated invariant | Silent failure |
|---|---|---|
| `TextElementMerger` (`text_element_merger.py:47`) | Batches `TextElement`s by list position. Removing a node makes non-adjacent elements adjacent. | Separate paragraphs concatenated into one `TextElement` |
| `XbrlTagCheck` (`xbrl_tag_check.py:15`) | Detects `ix:*` tags by `element.html_tag.name.startswith("ix")`. Decomposed nodes never enter the element list. | XBRL-tagged financial data treated as plain text; metadata regex at `parser.py:326` also breaks |
| `TableCheck` (`table_check.py:31`) | `has_text_outside_tags("table")` inspects sibling counts. Removing a sibling changes the boolean. | Tables misclassified as composite or standalone incorrectly |
| `TopSectionManagerFor10Q` (`core.py:46`) | Section boundary promotion depends on element sequence order. | Section boundaries promoted at wrong positions |

All four produce silent data corruption with no exception raised.

### Problem 3 — Stage 0 extracts too little from the single SGML pass

The SGML container embeds 88–684 documents (mean 152). Stage 0 already reads the
container sequentially to find Document 1. Two categories of value are discarded:

**SGML header fields (8 of 14 fields currently ignored):**

| Field | Coverage | Example |
|---|---|---|
| `accession_number` | 100% | `0000320193-21-000105` |
| `fiscal_year_end` | 100% | `0924` (MMDD) |
| `sec_file_number` | 100% | `001-36743` |
| `filed_as_of_date` | 100% | `20211029` |
| `document_count` | 100% | `88` |
| `state_of_incorporation` | 95% | `CA` |
| `ein` | 12% | `942404110` — unreliable; use DEI fallback |
| address fields | 100% | street, city, state, zip |

**Document Index (currently not built at all):**

Four high-value structured documents are embedded in every filing but are unreachable
because their byte offsets in the container are unknown:

| Document | Type | Filename | Value |
|---|---|---|---|
| XBRL instance | `XML` | `*_htm.xml` | All tagged financial facts (226–4,500+ contexts) |
| MetaLinks.json | `JSON` | `MetaLinks.json` | Full XBRL element catalogue; 633 elements, FASB definitions, calculation trees |
| FilingSummary.xml | `XML` | `FilingSummary.xml` | Maps every R*.htm sheet to human name + MenuCategory |
| iXBRL body | `10-K` | `{ticker}-{date}.htm` | Doc 1 — already extracted |

---

## Decision

### Architecture: three-stage pre-seek pipeline with SGMLManifest

```
┌──────────────────────────────────────────────────────────────┐
│ Stage 0 — SGML manifest extraction                           │
│  Input:   full SGML container (6–205 MB)                     │
│  Tool:    str.find() + line scan — no HTML parser            │
│  Output:  SGMLManifest (header + document index)             │
│  Method:  single forward pass; document content never        │
│           loaded into memory — only byte offsets recorded    │
│  Time:    < 0.3s                                             │
│                                                              │
│  Extracts:                                                   │
│   • SGMLHeader — all 14 SGML header fields                   │
│   • DocumentEntry list — type, filename, byte offsets for    │
│     all 88–684 embedded documents                            │
│   • Promotes: doc_10k, doc_metalinks, doc_filing_summary,    │
│     doc_xbrl_instance as named fields                        │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Stage 1 — Anchor-based section pre-seek                      │
│  Input:   manifest.doc_10k byte range                        │
│  Tool:    BeautifulSoup (lxml) — READ ONLY                   │
│  Output:  raw, UNMODIFIED HTML slice from Item 1A            │
│           start anchor → Item 1B/2 anchor (~50–200 KB)       │
│  Constraint: BS4 is used only to LOCATE anchors.             │
│    No node is decomposed, modified, or removed.              │
│  Time:    < 0.5s                                             │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Stage 2 — sec-parser on raw HTML fragment                    │
│  Input:   raw, unmodified ~50–200 KB HTML slice              │
│  Tool:    Edgar10QParser (unchanged)                         │
│  Output:  semantic element list                              │
│  Note:    sec-parser receives structurally intact HTML.      │
│    TextElementMerger, XbrlTagCheck, TableCheck, and          │
│    TopSectionManagerFor10Q all operate on unmodified DOM.    │
│  Time:    ~1–2s (vs 16–18s on full 5.2 MB body)              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Stage 3 — Element-level post-filter (extractor.py)           │
│  Input:   sec-parser element list                            │
│  Tool:    extractor._extract_section_content (existing)      │
│  Action:  drop elements matching PAGE_HEADER_PATTERN         │
│           from content_nodes before building full_text       │
│  This is the ONLY place noise filtering occurs.              │
└──────────────────────────────────────────────────────────────┘

Fallback: if Stage 1 finds no ToC anchors, skip to Stage 2
with full Document 1 HTML (existing Fix 1A path).
Stage 3 post-filter runs unconditionally on both paths.
```

---

### SGMLManifest schema

Implemented as Pydantic V2 `BaseModel` (per ADR-001), not `@dataclass`.
All fields are `Optional` with `None` default to match EDGAR header variability.
`SGMLManifest.container_path` is a required field (see Rule 8 and Consequences).

```python
# src/preprocessing/models/sgml.py

class DocumentEntry(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    doc_type:    str    # <TYPE> field, e.g. "10-K", "XML", "JSON", "EX-31.1"
    sequence:    int    # <SEQUENCE> field
    filename:    str    # <FILENAME> field
    description: str    # <DESCRIPTION> field (may be empty)
    byte_start:  int    # byte offset just after <TEXT>\n in container
    byte_end:    int    # byte offset of leading \n before </TEXT> in container

class SGMLHeader(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    # 6 fields previously extracted (semantics unchanged)
    company_name:    Optional[str] = None
    cik:             Optional[str] = None
    sic_code:        Optional[str] = None
    sic_name:        Optional[str] = None
    fiscal_year:     Optional[str] = None   # derived: first 4 chars of period_of_report
    period_of_report: Optional[str] = None  # YYYYMMDD from CONFORMED PERIOD OF REPORT
    # 7 newly extracted fields (ADR-010)
    accession_number:       Optional[str] = None
    fiscal_year_end:        Optional[str] = None   # MMDD e.g. "0925"
    sec_file_number:        Optional[str] = None
    filed_as_of_date:       Optional[str] = None   # YYYYMMDD
    document_count:         Optional[int] = None
    state_of_incorporation: Optional[str] = None   # ~95% coverage
    ein:                    Optional[str] = None    # ~12% SGML coverage; use DEI fallback

class SGMLManifest(BaseModel):
    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)
    header:              SGMLHeader
    documents:           List[DocumentEntry] = Field(default_factory=list)
    container_path:      Path                           # required (see Rule 8)
    doc_10k:             Optional[DocumentEntry] = None # TYPE=10-K — iXBRL body
    doc_metalinks:       Optional[DocumentEntry] = None # FILENAME=MetaLinks.json
    doc_filing_summary:  Optional[DocumentEntry] = None # FILENAME=FilingSummary.xml
    doc_xbrl_instance:   Optional[DocumentEntry] = None # TYPE=XML, filename *_htm.xml
```

**EDGAR DOCUMENT block tag syntax note:** Document metadata lines use angle-bracket tags
(`<TYPE>10-K`, `<SEQUENCE>1`, `<FILENAME>aapl.htm`, `<DESCRIPTION>...`), NOT the
`FIELD: value` colon syntax used in the `<SEC-HEADER>` block. The scanner uses distinct
patterns for each block type (`_DOC_TYPE_PAT`, `_DOC_SEQUENCE_PAT`, etc. in
`sgml_manifest.py`).

### Stage 0 scanning method

Single forward pass; document content is never loaded into memory:

```
1. Read lines until </SEC-HEADER>  →  parse into SGMLHeader
2. For each <DOCUMENT> block:
     a. Read TYPE / SEQUENCE / FILENAME / DESCRIPTION lines (~5 lines)
     b. Record byte position of <TEXT> tag  →  byte_start
     c. Scan forward for </TEXT> tag        →  byte_end
     d. Append DocumentEntry; continue to next <DOCUMENT>
3. Promote doc_10k, doc_metalinks, doc_filing_summary,
   doc_xbrl_instance by matching FILENAME / TYPE patterns
```

Memory footprint: ~80 lines of SGML header + ~6 fields × 152 docs ≈ **< 10 KB**
regardless of container size.

### Document content extraction (on-demand)

`DocumentEntry.byte_start/byte_end` allow any stage to extract a document without
re-reading the container:

```python
def extract_document(container_path: Path, entry: DocumentEntry) -> bytes:
    with open(container_path, "rb") as f:
        f.seek(entry.byte_start)
        raw = f.read(entry.byte_end - entry.byte_start)
    # Strip XBRL inner wrapper if present (<XBRL>...</XBRL> around XML/iXBRL docs)
    if raw.lstrip().startswith(b"<XBRL>"):
        raw = raw[raw.index(b">") + 1 : raw.rfind(b"</XBRL>")]
    return raw
```

Called by:
- Stage 1 using `manifest.doc_10k` (pre-seek, then fragment slice)
- Plan D metadata enrichment using `manifest.doc_10k` for DEI tag extraction
- Future XBRL extraction using `manifest.doc_xbrl_instance`
- Future MetaLinks.json parsing using `manifest.doc_metalinks`

---

### Governing rules

**Rule 1 — Never modify the HTML fragment before passing to sec-parser.**
The output of Stage 1 is always a raw, byte-for-byte slice of Document 1. No node is
decomposed, wrapped, unwrapped, or removed. BS4 in Stage 1 is a read-only navigation
tool for locating anchor boundaries. The structurally intact fragment is passed directly
to `Edgar10QParser.parse()`.

This rule exists because sec-parser's internal processors depend on four structural
invariants that BS4 decompose violates: adjacent element positions (`TextElementMerger`),
`ix:*` tag presence (`XbrlTagCheck`), sibling node counts (`TableCheck`), and element
sequence order (`TopSectionManagerFor10Q`). Violating any of these produces silent data
corruption with no exception raised.

**Rule 2 — All noise filtering operates on the element list, never on the HTML.**
Page headers and any other noise that sec-parser misclassifies are removed by filtering
the `list[AbstractSemanticElement]` that sec-parser returns. Filtering at the element
level is safe because the element list is a flat projection with no structural invariants
spanning element positions after sec-parser has completed its classification pass.

**Rule 3 — PAGE_HEADER_PATTERN is the single source of truth, applied in Stage 3.**

```python
# src/preprocessing/constants.py
# Matches any pipe-delimited string containing "Form 10-K" or "Form 10-Q".
# Handles variations: year present or absent, "Page N" or bare integer after last pipe.
PAGE_HEADER_PATTERN = re.compile(
    r'[^|]+\|[^|]*Form\s+10-[KQ][^|]*\|',
    re.IGNORECASE
)
```

The earlier pattern `r'.+\|\s*\d{4}\s+Form\s+10-[KQ]\s*\|\s*\d+'` was too rigid:
it required a 4-digit year immediately before "Form" (missed year-less footers) and
required a bare integer after the final pipe (missed "Page 21"). The implemented
pattern requires only two pipe separators enclosing "Form 10-K/Q".

Applied in `extractor._extract_section_content` after sec-parser returns:

```python
content_nodes = [
    node for node in content_nodes
    if not (
        isinstance(node.semantic_element, sp.TitleElement)
        and PAGE_HEADER_PATTERN.search(node.text)
    )
]
```

Note: the filter uses `node.semantic_element` (the sec-parser element object) and
`node.text` (the text attribute of the tree node), not bare `node` which is a
`TreeNode`. `TitleElement.text` is the fully merged output of `TextElementMerger`.
Split-span page footers are reassembled before Stage 3 sees them, making this more
reliable than the BS4 `.get_text()` approach ADR-009 Stage 2 used. Pattern updates
require corpus regression test before merge.

**Rule 4 — Metadata extraction runs in Stage 0 against full Document 1 before the anchor slice.**
`parser.py` metadata extraction uses regex against raw HTML for `ix:nonNumeric` tags
(`dei:TradingSymbol`, `dei:EntityCentralIndexKey`, etc.). These tags may not appear
inside the Item 1A slice. Metadata extraction must complete in Stage 0 using
`extract_document(path, manifest.doc_10k)`, before the anchor slice is made.

**Rule 5 — EIN sourcing: SGML header is the fast path; DEI is authoritative.**
`SGMLHeader.ein` is populated when present in the SGML header (12% of filings). The
authoritative source is `dei:EntityTaxIdentificationNumber` from the DEI `<ix:hidden>`
block (100% coverage). Callers must guard:

```python
ein = manifest.header.ein or dei_tags.get("EntityTaxIdentificationNumber")
```

**Rule 6 — Stage 0 uses string seek and line scan, never BeautifulSoup.**
SGML header and document boundary parsing uses `str.find()` and line iteration on
raw bytes. BS4 is instantiated exactly once per filing (Stage 1 Strategy A), on
Document 1 content only, using `SoupStrainer("a")` to limit parse tree size.

**Rule 7 — Fallback for anchor-less filings.**
If neither Strategy A nor Strategy B locates the target section, fall back to passing
the full Document 1 HTML to `Edgar10QParser.parse()`. Fallback preserves 100% filing
coverage. Stage 3 post-filter runs unconditionally on both the pre-seek and fallback
paths. Expected fallback rate: ~5% of corpus.

**Rule 8 — `SGMLManifest.container_path` is required and must be stable.**
`SGMLManifest` carries `container_path: Path` as a required field (no default). Byte
offsets in `DocumentEntry` are valid only for the specific container file they were
scanned from. Callers must not move, copy, or delete the container between
`extract_sgml_manifest()` and any subsequent `extract_document()` call. In multi-worker
batch pipelines, the path must point to a stable location (not a temp copy).

---

### Stage 1 anchor resolution (read-only) — two strategies

`AnchorPreSeeker.seek()` tries strategies in order and returns the first non-None result.

#### Strategy A — ToC `<a href>` → body `id=` resolution (primary)

Modern EDGAR filings include a Table of Contents where each section entry links to its
body via a named anchor:

```html
<!-- Inside ToC <table> -->
<a href="#icffec2d5c553492089e1784044e3cc53_16">Item 1A.&#160;&#160;&#160;&#160;Risk Factors</a>

<!-- Section body — NOTE: a <div id>, NOT <a id> -->
<div id="icffec2d5c553492089e1784044e3cc53_16"></div>
```

**Critical implementation detail:** Modern EDGAR iXBRL filings (including AAPL) use
`<div id="...">` as anchor targets, not `<a id="...">`. The `_find_anchor_pos()` helper
searches for `id="FRAGMENT_ID"` on **any element type**:

```python
# src/preprocessing/pre_seeker.py
def _find_anchor_pos(doc_html: str, fragment_id: str) -> int:
    pattern = re.compile(
        r'\bid\s*=\s*"' + re.escape(fragment_id) + r'"',
        re.IGNORECASE,
    )
    m = pattern.search(doc_html)
    if m is None:
        return -1
    tag_start = doc_html.rfind('<', 0, m.start())
    return tag_start if tag_start != -1 else m.start()
```

Strategy A uses `SoupStrainer("a")` so lxml ignores all non-`<a>` nodes at the C level
(< 50ms on 10 MB documents). It scans the `<a href="#...">` tags for a text match against
`SECTION_PATTERNS[section_id]`, extracts the fragment ID, then calls `_find_anchor_pos()`
to resolve the body element position. End anchor is found by the same method for the next
section in document order.

#### Strategy B — Direct regex scan of raw HTML (fallback)

If no ToC anchor matches (ToC-less filings, non-standard formatting), Strategy B scans
raw `doc_html` directly with the compiled target and end patterns:

```python
def _strategy_b(self, doc_html, target_patterns, end_patterns):
    # Find start: earliest target-pattern match in raw HTML
    start_match = None
    for pattern in target_patterns:
        m = pattern.search(doc_html)
        if m and (start_match is None or m.start() < start_match.start()):
            start_match = m
    if start_match is None:
        return None
    # Walk back to opening < of surrounding tag
    start_pos = doc_html.rfind('<', 0, start_match.start())
    if start_pos == -1:
        start_pos = start_match.start()
    # Find end: first end-pattern match after start_pos
    end_pos = len(doc_html)
    for pattern in end_patterns:
        m = pattern.search(doc_html, start_pos + 1)
        if m:
            candidate = doc_html.rfind('<', 0, m.start())
            if candidate == -1:
                candidate = m.start()
            if candidate > start_pos and candidate < end_pos:
                end_pos = candidate
    return doc_html[start_pos:end_pos]
```

**Why not SoupStrainer + `str(tag)`:** BeautifulSoup normalises HTML when stringifying
tags — `&#160;` in raw HTML becomes `\xa0` in `str(tag)`, quotes and attribute ordering
may differ. `doc_html.find(str(tag))` always returns -1. Strategy B therefore avoids the
BS4 round-trip entirely and scans raw HTML directly. EDGAR section headings are plain
ASCII, so the `SECTION_PATTERNS` regexes reliably match the raw text.

No BS4 mutations (decompose, insert, replace, wrap, unwrap) are called at any point in
Stage 1 under either strategy.

---

## Consequences

**Positive:**
- Parsing latency: 18.44s → ~5.85s per 10 MB filing (AAPL_10K_2021.html measured
  post-implementation). sec-parser processes 91.7 KB instead of 5.2 MB; all four
  internal structural invariants are intact. Stage 1 measured at 106.8 ms.
- Stage 1 pre-seek succeeds on AAPL iXBRL (which uses `<div id>` anchors); the
  fix to `_find_anchor_pos()` to match any element type was critical for this class
  of modern filing.
- Corpus throughput: 5–16 hours → ~32 minutes for 959 files (estimated from per-file
  timing; excludes sentence-transformer model load which amortises over a batch).
- `TitleElement` misclassification (`"Apple Inc. | 2024 Form 10-K | 21"`) eliminated by
  Stage 3 pattern filter. Zero page-header segments in AAPL output (verified).
- Stage 0 single pass now captures the full SGML header (7 previously-missing fields)
  and the complete Document Index at near-zero cost (10.9 ms measured).
- `accession_number`, `fiscal_year_end`, `state_of_incorporation`, `sec_file_number`,
  `filed_as_of_date` become available to all downstream stages immediately.
- MetaLinks.json, FilingSummary.xml, and XBRL instance document are addressable by
  byte offset without re-reading the container. This unblocks Plan D and future work.
- `SGMLManifest` replaces ad-hoc dict passing as the filing context carrier.
- Architecture is simpler than ADR-009: three stages vs four; no pre-sanitization stage.

**Negative:**
- Stage 0 `</TEXT>` seek step scans content bytes sequentially to record `byte_end`.
  For the 26 MB iXBRL body, this scan is explicit (previously it was implicit in the
  pass that located Document 1). Measured overhead < 11ms in practice.
- `SGMLManifest.documents` holds up to 684 `DocumentEntry` objects (~70 KB peak). Negligible
  but non-zero increase over the previous bare-bytes Stage 0 output.
- Serialised `SGMLManifest` objects must carry `container_path` alongside byte offsets —
  offsets are only valid for a specific file. Multi-worker batch pipelines must ensure the
  container path is stable (not a temp copy) for the duration of a run.
- The `<XBRL>` inner wrapper stripping in `extract_document()` relies on the wrapper
  appearing at the start of content bytes. If EDGAR changes the SGML wrapper format,
  this breaks silently. A `doc_type`-based guard must protect the strip branch.
- `PAGE_HEADER_PATTERN` is company-name-agnostic: any pipe-delimited string containing
  `Form 10-K/Q` between two pipes is dropped. A risk factor segment legitimately
  containing such a string would be incorrectly removed. Considered pathologically
  unlikely; monitor in corpus regression runs.
- Stage 1 Strategy A depends on EDGAR ToC formatting conventions. Non-standard or
  JavaScript-generated ToC patterns cause Strategy A to return None, and Strategy B
  runs a raw regex scan as secondary fallback. If both fail, the full doc1 is parsed.
- `fiscal_year_end` SGML field uses `FISCAL YEAR END:` (not `FISCAL YEAR ENDING:`).
  EDGAR header field names are not published in a machine-readable schema; mismatches
  are discovered only by running against real filings. The field name is now correct
  in `sgml_manifest.py:_HDR_PATTERNS` after post-implementation correction.

---

## Post-implementation corrections (2026-02-22)

Four issues were found during the single-file smoke test on `AAPL_10K_2021.html`
immediately after initial implementation. All were fixed before the first batch run.
Full documentation: `thoughts/shared/research/2026-02-22_19-45-00_adr010_single_file_run_bugs.md`.

| ID | Severity | Location | Issue | Fix |
|----|----------|----------|-------|-----|
| B1 | Critical | `pre_seeker.py:_find_anchor_pos` | Body anchor search was confined to `<a id="...">` tags. AAPL iXBRL (and modern EDGAR generally) uses `<div id="...">`. Zero `<a id>` anchors exist in the 5.2 MB iXBRL body; Strategy A returned None for every filing of this type. | Changed pattern to `\bid\s*=\s*"FRAGMENT_ID"` — matches any element type. |
| B2 | Critical | `pre_seeker.py:_strategy_b` | Strategy B located matches via BS4 then called `doc_html.find(str(tag))`. BS4 normalises HTML when stringifying: `&#160;` → `\xa0`, quote styles may differ. `str(tag)` never matches raw source. Strategy B silently returned None on every filing. | Rewrote `_strategy_b` to scan raw `doc_html` directly with compiled `SECTION_PATTERNS` regexes. No BS4 round-trip. |
| B3 | Minor | `sgml_manifest.py:_HDR_PATTERNS` | `fiscal_year_end` pattern matched `FISCAL YEAR ENDING:` but actual EDGAR field is `FISCAL YEAR END:` (no trailing G). Field was None on every filing. | Changed pattern to `rb'FISCAL YEAR END:\s*(\d{4})'`. |
| W1 | Warning | `parser.py:parse_filing` | `UserWarning: 10-K parsed with Edgar10QParser` fired on every 10-K via the internal `parse_from_content()` call. Non-actionable noise in batch logs. | Passed `quiet=True` on the internal call inside `parse_filing()`. |

**Post-fix verified results on AAPL_10K_2021.html:**
- Stage 0: 10.9 ms — all 10 metadata fields populated including `fiscal_year_end: "0925"`
- Stage 1: 106.8 ms — returns 91.7 KB slice (vs. full ~2 MB doc1 before fixes)
- Total end-to-end: ~5.85s (down from 18.44s baseline; model load amortises over batch)
- Segments: 136 extracted; 0 page-header segments

---

## Supersedes

Supersedes **ADR-009** (`ADR-009_hybrid_pre_seek_parser.md`).

Specifically:
- ADR-009 Stage 2 (pre-fragment sanitization via BS4 decompose) is removed entirely.
- ADR-009 Stage 0 (bare Document 1 boundary extraction) is replaced by full
  `SGMLManifest` extraction.
- ADR-009 Rule 1 ("never pass a raw HTML slice to sec-parser") is inverted: the
  correct invariant is "always pass a raw, unmodified HTML slice to sec-parser."

ADR-002's decision to use sec-parser is **unchanged**. This ADR governs the scope of HTML
passed to sec-parser, where element-level filtering occurs, and what Stage 0 extracts
from the SGML container.

---

## References

**Implementation files:**
- `src/preprocessing/models/sgml.py` — `DocumentEntry`, `SGMLHeader`, `SGMLManifest` (Pydantic V2)
- `src/preprocessing/sgml_manifest.py` — Stage 0: `extract_sgml_manifest()`, `extract_document()`
- `src/preprocessing/pre_seeker.py` — Stage 1: `AnchorPreSeeker`, `_find_anchor_pos`, `_strategy_b`
- `src/preprocessing/constants.py` — `PAGE_HEADER_PATTERN`, `SECTION_PATTERNS`, anchor patterns
- `src/preprocessing/extractor.py` — Stage 3 filter in `_extract_section_content()`
- `src/preprocessing/parser.py` — `parse_filing()` orchestration, `_extract_metadata()`

**Bug report:**
- `thoughts/shared/research/2026-02-22_19-45-00_adr010_single_file_run_bugs.md` — B1/B2/B3/W1 with evidence and fixes

**sec-parser internals (structural invariants):**
- `venv/.../sec_parser/processing_steps/text_element_merger.py:47-50` — adjacent position invariant
- `venv/.../single_element_checks/xbrl_tag_check.py:15-24` — ix:* tag name detection
- `venv/.../single_element_checks/table_check.py:31` — `has_text_outside_tags()` sibling invariant
- `venv/.../processing_engine/core.py:46-47` — `TopSectionManagerFor10Q` sequence invariant

**Research and evidence:**
- `thoughts/shared/research/2026-02-22_12-00-00_sec_html_structure_and_extraction.md` §Layer 1–4 — SGML container format, Document Index structure, MetaLinks.json and FilingSummary.xml schemas
- `thoughts/shared/research/2026-02-22_10-00-00_aapl_parser_metrics_audit.md` — empirical timing breakdown (16.30s in `Edgar10QParser`, 87% of total)
- `reports/sec_html_structure/2026-02-22_17-57-43_sec_html_structure_findings.md` §3, §7 — SGML header field coverage; 7/22 extraction gap; Document Index distribution (88–684 docs, mean 152)
- `data/interim/20260220_190317_preprocessing_b9fb777/parsed/AAPL_10K_2024_parsed.json` — production evidence of `TitleElement` misclassification

**Related decisions:**
- ADR-009 — superseded
- ADR-002 — sec-parser adoption decision (unchanged)
