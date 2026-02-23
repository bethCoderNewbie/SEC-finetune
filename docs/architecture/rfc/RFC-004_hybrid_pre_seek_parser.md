---
id: RFC-004
title: Hybrid Pre-Seek Parser with SGMLManifest (ADR-010 Implementation)
status: ACCEPTED
author: bethCoderNewbie
created: 2026-02-22
last_updated: 2026-02-22
git_sha: 94d7d6e
superseded_by: null
related_prd: docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md
related_adr: docs/architecture/adr/ADR-010_hybrid_pre_seek_parser_corrected.md
---

# RFC-004: Hybrid Pre-Seek Parser with SGMLManifest

## Status

**ACCEPTED** — Architecture decided in ADR-010. This RFC documents implementation
strategy for that decision. No unresolved design choices remain.

---

## Context

`SECFilingParser.parse_filing()` currently passes the full SGML container (~11 MB)
to `Edgar10QParser.parse()`. Empirical timing on `AAPL_10K_2021.html` (commit `b9fb777`):

| Step | Time | % of total |
|------|------|-----------|
| `_flatten_html_nesting` | 2.12s | 11% |
| `Edgar10QParser.parse()` | 16.30s | **87%** |
| Total | 18.44s | 100% |

At 959-file corpus scale this is 5–16 hours per batch run. The 5-second per-file target
is unachievable.

Two additional problems:
1. Page footer text (`"Apple Inc. | 2024 Form 10-K | 21"`) is misclassified as
   `TitleElement` and enters `full_text` as risk content.
2. Only 6 of 14 SGML header fields are extracted; document byte offsets are never built.

ADR-010 resolves all three with a 3-stage pre-seek architecture. This RFC specifies
the implementation approach.

---

## Proposed Design

### New modules

**`src/preprocessing/sgml_manifest.py`** (Stage 0)

Pydantic V2 `BaseModel`s (per ADR-001): `DocumentEntry`, `SGMLHeader`, `SGMLManifest`.

`extract_sgml_manifest(container_path: Path) -> SGMLManifest`:
- Opens file in binary mode; scans line-by-line tracking byte position
- Never loads document bodies into Python memory — only records byte offsets
- Finds `<SEC-HEADER>` … `</SEC-HEADER>` → builds `SGMLHeader` (14 fields)
- For each `<DOCUMENT>` block: reads TYPE/SEQUENCE/FILENAME/DESCRIPTION lines;
  scans forward in 64 KB chunks for `\n</TEXT>` to record `byte_end`
- Promotes `doc_10k`, `doc_metalinks`, `doc_filing_summary`, `doc_xbrl_instance`
- Memory footprint: < 10 KB regardless of container size (no content bytes held)

`extract_document(container_path: Path, entry: DocumentEntry) -> bytes`:
- `f.seek(entry.byte_start)` + `f.read(byte_end - byte_start)`
- Strips `<XBRL>…</XBRL>` wrapper if present (guarded by `doc_type`)

Note: Raw files in `data/raw/` have an HTML wrapper (`<!DOCTYPE html>...<body><pre>`)
before the SGML content. The scanner locates `<SEC-HEADER>` by byte search,
not by assuming file offset 0.

**`src/preprocessing/pre_seeker.py`** (Stage 1)

`AnchorPreSeeker.seek(container_path: Path, manifest: SGMLManifest) -> Optional[str]`:
- Calls `extract_document()` on `manifest.doc_10k` → full iXBRL HTML bytes
- Decodes with UTF-8 → windows-1252 → latin-1 fallback chain (windows-1252 before
  latin-1 to avoid mojibake in 0x80–0x9F range common in older EDGAR filings)
- **SoupStrainer** used in both strategies to avoid building full 5–10 MB parse trees:
  Strategy A uses `SoupStrainer("a")` — lxml ignores all non-`<a>` nodes at C level;
  Strategy B uses `SoupStrainer(["span","div","p"])` — for text-proximity scan when
  ToC anchor resolution fails
- End anchor: regex on original string using `ITEM_1B_OR_2_ANCHOR_PATTERN`
- Returns `doc_html[start_pos:end_pos]` — raw, unmodified substring
- Returns `None` if both strategies fail → Rule 7 fallback (full doc1 to Stage 2)

### Changes to existing modules

**`src/preprocessing/parser.py`**

`parse_filing()` new flow:
1. Stage 0: `extract_sgml_manifest()` (catch `ValueError` → legacy fallback)
2. `extract_document(path, manifest.doc_10k)` → `full_doc1_html` (for DEI metadata)
3. Stage 1: `AnchorPreSeeker().seek()` → `fragment` (or None → use `full_doc1_html`)
4. `parse_from_content(fragment or full_doc1_html, flatten_html=False)`
5. `_extract_metadata(elements, full_doc1_html, sgml_manifest=manifest)` — uses
   manifest header fields; still runs DEI regex on `full_doc1_html` for ticker

New private helper `_decode_bytes(raw: bytes) -> str`: UTF-8 → latin-1 fallback.

`_extract_metadata()` gets optional `sgml_manifest` parameter:
- If provided: read header fields from manifest instead of regex
- Emit new keys: `accession_number`, `filed_as_of_date`, `fiscal_year_end`,
  `sec_file_number`, `document_count`, `state_of_incorporation`, `ein`

`_flatten_html_nesting` / `_flatten_html_nesting_bs4`: methods kept for
`parse_from_content()` callers; NOT called on the new `parse_filing()` path
(Rule 1: never modify HTML before sec-parser).

**`src/preprocessing/extractor.py`**

In `_extract_section_content()`, after `content_nodes` list is fully built, add
Stage 3 filter before `full_text` assembly:

```python
content_nodes = [
    node for node in content_nodes
    if not (
        isinstance(node.semantic_element, sp.TitleElement)
        and PAGE_HEADER_PATTERN.search(node.text)
    )
]
```

Also change existing subsection filter from `.match()` to `.search()` (line 475).

**`src/preprocessing/constants.py`**

Update pattern to ADR-010 spec (`\d+-[KQ]` → `10-[KQ]`):
```python
PAGE_HEADER_PATTERN = re.compile(
    r'[^|]+\|[^|]*Form\s+10-[KQ][^|]*\|',
    re.IGNORECASE
)
```

### Rejected alternatives

**A. Pre-sanitize with BS4 `decompose()` (ADR-009 Stage 2)**
Rejected. Audit of sec-parser v0.54.0 revealed four silent failure modes
(TextElementMerger, XbrlTagCheck, TableCheck, TopSectionManagerFor10Q). No exception
is raised; output is silently corrupted.

**B. Full BS4 parse tree for Stage 1**
Rejected. `BeautifulSoup(lxml)` without `SoupStrainer` on a 5–10 MB document
costs 0.5–1.5s and creates a large heap allocation — negating a significant fraction
of the pre-seek performance benefit. `SoupStrainer` forces lxml to skip non-target
nodes at the C level, keeping Stage 1 under 0.2s for both strategies.

**C. Caching the full parsed filing and filtering post-hoc**
Rejected. This does not address the 16s parse time — it still processes the full body.

---

## Consequences

- Parsing latency: 18.44s → ~1–2s per 10 MB filing
- Corpus throughput: 5–16 hours → ~32 minutes for 959 files
- `TitleElement` page-header misclassification eliminated by Stage 3 filter
- 8 new metadata fields emitted per filing (accession_number, filed_as_of_date, etc.)
- `parse_from_content()` public API is unchanged (backward compatible)
- `SGMLManifest.documents` byte index unblocks future XBRL / MetaLinks extraction

---

## Verification

```bash
# Unit tests — no real data required
pytest tests/unit/preprocessing/test_sgml_manifest.py
pytest tests/unit/preprocessing/test_pre_seeker.py

# Regression — all existing tests must pass
pytest tests/unit/preprocessing/ -v

# Smoke test — single real filing, measure elapsed time
time python -m src.preprocessing data/raw/AAPL_10K_2021.html 10-K
```

Expected: elapsed < 5s; output JSON contains `accession_number` key;
no `"Apple Inc. | 2024 Form 10-K | 21"` entries in segment text.
