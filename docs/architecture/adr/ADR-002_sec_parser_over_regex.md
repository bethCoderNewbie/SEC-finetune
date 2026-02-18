# ADR-002: Use `sec-parser` Library Over Custom Regex Parsing

**Status:** Accepted
**Date:** 2025-11-17
**Author:** @bethCoderNewbie

---

## Context

The v0.1 pipeline used a hand-written regex-based `FilingParser` to extract Item 1A from raw HTML.
This approach broke on:

- EDGAR inline XBRL filings (different tag structure than plain HTML)
- Filings where "Item 1A" appeared in the table of contents before the actual section
- Multi-column layout filings where text order in the DOM did not match reading order
- Section boundary detection for Item 7 / Item 7A (needed for future scope)

Regex maintenance cost was high — each new EDGAR format variant required bespoke pattern updates.

## Decision

Replace `FilingParser` with `SECFilingParser`, a thin wrapper around **`sec-parser==0.54.0`** (pinned).

`sec-parser` builds a **semantic tree** of SEC filing elements (`TextElement`, `TableElement`,
`TitleElement`, etc.) rather than operating on raw HTML strings. Section extraction navigates the
tree rather than matching patterns.

The version is **hard-pinned** (`==0.54.0`) in `pyproject.toml` because the library's semantic
element taxonomy changed between minor versions in 2024 and breaking changes would silently
corrupt extraction output without pinning.

## Consequences

**Positive:**
- Handles inline XBRL, multi-column, and non-standard layouts without custom code
- Semantic tree navigation makes section boundary detection robust across filing formats
- `TableElement` objects are available for future table extraction (OQ-1)
- Filing metadata (CIK, SIC, ticker) is extracted from the EDGAR header by the library

**Negative:**
- Locked to `sec-parser==0.54.0` — upgrading requires regression testing across the full corpus
- `sec-parser` is a third-party dependency with limited commercial support; if it goes unmaintained,
  the parsing layer needs to be replaced
- The library requires the full HTML file (not a streaming reader) — large filings (>150MB for
  financials/REITs) load entirely into memory

## Supersedes

Replaces regex-based `FilingParser` (removed in commit `ea45dd2` area).

## References

- `src/preprocessing/parser.py` — `SECFilingParser`
- `src/preprocessing/extractor.py` — `SECSectionExtractor`
- `pyproject.toml` — `sec-parser==0.54.0`
- CHANGELOG: 2025-11-17
