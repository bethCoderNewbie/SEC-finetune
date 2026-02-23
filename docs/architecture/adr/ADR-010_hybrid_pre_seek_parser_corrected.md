# ADR-010: Hybrid Pre-Seek Parser Architecture with SGMLManifest (Supersedes ADR-009)

**Status:** Accepted
**Date:** 2026-02-22
**Author:** bethCoderNewbie

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

```python
@dataclass
class DocumentEntry:
    doc_type:    str    # <TYPE> field, e.g. "10-K", "XML", "JSON", "EX-31.1"
    sequence:    int    # <SEQUENCE> field
    filename:    str    # <FILENAME> field
    description: str    # <DESCRIPTION> field (may be empty)
    byte_start:  int    # byte offset of <TEXT> content start in container
    byte_end:    int    # byte offset of </TEXT> content end in container

@dataclass
class SGMLHeader:
    # Currently extracted (unchanged)
    company_name:          str
    cik:                   str
    sic_code:              str
    sic_name:              str
    fiscal_year:           str
    period_of_report:      str
    # Newly extracted
    accession_number:      str
    fiscal_year_end:       str           # MMDD e.g. "0924"
    sec_file_number:       str
    filed_as_of_date:      str           # YYYYMMDD
    document_count:        int
    state_of_incorporation: str | None   # 95% coverage; None if absent
    ein:                   str | None    # 12% SGML coverage; prefer DEI fallback

@dataclass
class SGMLManifest:
    header:              SGMLHeader
    documents:           list[DocumentEntry]   # all embedded docs, sequence order
    # Promoted first-class accessors (None if not found)
    doc_10k:             DocumentEntry | None  # TYPE=10-K — iXBRL body
    doc_metalinks:       DocumentEntry | None  # FILENAME=MetaLinks.json
    doc_filing_summary:  DocumentEntry | None  # FILENAME=FilingSummary.xml
    doc_xbrl_instance:   DocumentEntry | None  # FILENAME=*_htm.xml or *-*.xml
```

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
PAGE_HEADER_PATTERN = re.compile(
    r'.+\|\s*\d{4}\s+Form\s+10-[KQ]\s*\|\s*\d+',
    re.IGNORECASE
)
```

Applied in `extractor._extract_section_content` after sec-parser returns:

```python
content_nodes = [
    node for node in content_nodes
    if not (
        isinstance(node, TitleElement)
        and PAGE_HEADER_PATTERN.search(node.text)
    )
]
```

`TitleElement.text` is the fully merged output of `TextElementMerger`. Split-span page
footers are reassembled before Stage 3 sees them, making this more reliable than the
BS4 `.get_text()` approach ADR-009 Stage 2 used. Pattern updates require corpus
regression test before merge.

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
SGML header and document boundary parsing uses `str.find()` and line iteration.
BS4 is instantiated exactly once (Stage 1), on Document 1 content only.

**Rule 7 — Fallback for anchor-less filings.**
If Stage 1 finds no ToC `<a href="#...">` targeting an Item 1A identifier, fall back
to the existing Fix 1A path: full `Edgar10QParser.parse()` on `extract_document(path,
manifest.doc_10k)`. Fallback preserves 100% filing coverage. Stage 3 post-filter runs
unconditionally on both paths.

---

### Stage 1 anchor resolution (read-only)

EDGAR ToC entries link to section bodies via named anchors:

```html
<!-- Inside ToC <table> -->
<a href="#i4bf6d0bde838478985b72eb4052bc976_19">Item 1A. Risk Factors</a>

<!-- Section body marker -->
<a id="i4bf6d0bde838478985b72eb4052bc976_19"></a>
```

Stage 1 locates the raw HTML byte range using two read-only BS4 lookups on
`extract_document(path, manifest.doc_10k)`:

1. **Start anchor:** find the ToC `<a href>` whose link text matches
   `re.search(r'item\s+1a', text, re.IGNORECASE)`. Extract the fragment ID from `href`.
   Find the matching `<a id="FRAGMENT_ID">` tag.
2. **End anchor:** find the next `<a id="…">` after the start anchor whose surrounding
   text matches `re.search(r'item\s+(1b|2)\b', text, re.IGNORECASE)`.

Extract the HTML substring between the two anchor byte positions. No BS4 mutations
(decompose, insert, replace, wrap, unwrap) are called at any point in Stage 1.

---

## Consequences

**Positive:**
- Parsing latency: 18.44s → ~1–2s per 10 MB filing. sec-parser processes ~50–200 KB
  instead of 5.2 MB; all four internal structural invariants are intact.
- Corpus throughput: 5–16 hours → ~32 minutes for 959 files.
- `TitleElement` misclassification (`"Apple Inc. | 2024 Form 10-K | 21"`) eliminated by
  Stage 3 pattern filter. Operates on fully-merged `TitleElement.text` — more reliable
  than the BS4 `.get_text()` approach in ADR-009.
- Stage 0 single pass now captures the full SGML header (8 currently-missing fields)
  and the complete Document Index at near-zero cost.
- `accession_number`, `fiscal_year_end`, `state_of_incorporation`, `sec_file_number`,
  `filed_as_of_date` become available to all downstream stages immediately.
- MetaLinks.json, FilingSummary.xml, and XBRL instance document are addressable by
  byte offset without re-reading the container. This unblocks Plan D (Metadata
  Enrichment) and future financial-fact extraction.
- `SGMLManifest` replaces ad-hoc dict passing as the filing context carrier.
- Architecture is simpler than ADR-009: three stages vs four; no pre-sanitization stage.

**Negative:**
- Stage 0 `</TEXT>` seek step scans content bytes sequentially to record `byte_end`.
  For the 26 MB iXBRL body, this scan is explicit (previously it was implicit in the
  pass that located Document 1). Measured overhead expected < 0.2s; confirm with profiling.
- `SGMLManifest.documents` holds up to 684 `DocumentEntry` objects (~70 KB peak). Negligible
  but non-zero increase over the previous bare-bytes Stage 0 output.
- Serialised `SGMLManifest` objects must carry `container_path` alongside byte offsets —
  offsets are only valid for a specific file. Multi-worker batch pipelines must ensure the
  container path is stable (not a temp copy) for the duration of a run.
- The `<XBRL>` inner wrapper stripping in `extract_document()` relies on the wrapper
  appearing at the start of content bytes. If EDGAR changes the SGML wrapper format,
  this breaks silently. A `doc_type`-based guard must protect the strip branch.
- `PAGE_HEADER_PATTERN` is company-name-agnostic: any pipe-delimited string containing a
  4-digit year and `Form 10-K/Q` is dropped. A risk factor segment legitimately containing
  such a string would be incorrectly removed. Considered pathologically unlikely; monitor
  in corpus regression runs.
- Stage 1 anchor resolution depends on EDGAR ToC formatting conventions. Non-standard or
  JavaScript-generated ToC patterns silently trigger the fallback (slower but correct).

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

- `venv/.../sec_parser/processing_steps/text_element_merger.py:47-50` — adjacent position invariant
- `venv/.../single_element_checks/xbrl_tag_check.py:15-24` — ix:* tag name detection
- `venv/.../single_element_checks/table_check.py:31` — `has_text_outside_tags()` sibling invariant
- `venv/.../processing_engine/core.py:46-47` — `TopSectionManagerFor10Q` sequence invariant
- `src/preprocessing/parser.py:26-46` — monkey-patch for `approx_table_metrics` (evidence sec-parser is fragile about structural assumptions)
- `src/preprocessing/parser.py:279-352` — current six-field SGML header extraction (to be replaced by full `SGMLHeader` parse)
- `src/preprocessing/parser.py:326-337` — metadata regex on raw HTML (`ix:nonNumeric` source; must run before anchor slice)
- `src/preprocessing/extractor.py:459-468` — `_extract_section_content`, target for Stage 3 filter
- `data/interim/20260220_190317_preprocessing_b9fb777/parsed/AAPL_10K_2024_parsed.json` — production evidence of `TitleElement` misclassification
- `thoughts/shared/research/2026-02-22_12-00-00_sec_html_structure_and_extraction.md` §Layer 1–4 — SGML container format, Document Index structure, MetaLinks.json and FilingSummary.xml schemas
- `thoughts/shared/research/2026-02-22_10-00-00_aapl_parser_metrics_audit.md` — empirical timing breakdown (16.30s in `Edgar10QParser`, 87% of total)
- `reports/sec_html_structure/2026-02-22_17-57-43_sec_html_structure_findings.md` §3, §7 — SGML header field coverage; 7/22 extraction gap; Document Index distribution (88–684 docs, mean 152)
- ADR-009 — superseded
- ADR-002 — sec-parser adoption decision (unchanged)
