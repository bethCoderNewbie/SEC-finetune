---
git_sha: 94d7d6e
branch: main
date: 2026-02-22
researcher: bethCoderNewbie
subject: ADR-010 single-file run — bugs and warnings (AAPL_10K_2021.html)
---

# ADR-010 Single-File Run — Bug & Warning Report

**File tested:** `data/raw/AAPL_10K_2021.html`
**Form type:** 10-K
**Run command:** `SECPreprocessingPipeline().process_risk_factors(...)` with `quiet=False`
**Elapsed:** 2.55 s (baseline was 18.44 s — Stage 0 intact, but Stage 1 fell back)

---

## Summary

| # | Severity | Module | Description |
|---|----------|--------|-------------|
| B1 | **Bug — critical** | `pre_seeker.py:_find_anchor_pos` | Body anchor search is limited to `<a id>` tags; AAPL (and most iXBRL) uses `<div id>` |
| B2 | **Bug — critical** | `pre_seeker.py:_strategy_b` | `doc_html.find(str(tag))` always returns -1 (BS4 normalises HTML; stringified tag never matches raw source) |
| B3 | **Bug — minor** | `sgml_manifest.py:_HDR_PATTERNS` | `fiscal_year_end` pattern matches `FISCAL YEAR ENDING:` but EDGAR uses `FISCAL YEAR END:` |
| W1 | **Warning** | `parser.py:parse_from_content` | `UserWarning: 10-K parsed with Edgar10QParser` fires on every 10-K; noisy in production |

---

## Bug B1 — Body anchor confined to `<a id>` (critical)

### What should happen
Strategy A in `AnchorPreSeeker.seek()` resolves the ToC `href="#fragment_id"` to the
body position. The body position is found by `_find_anchor_pos()`.

### What actually happens
`_find_anchor_pos()` (`pre_seeker.py`) searches with:
```python
pattern = re.compile(
    r'<a\s[^>]*(?:id|name)\s*=\s*["\']?' + re.escape(fragment_id) + ...,
    re.IGNORECASE,
)
```
This only finds `<a id="fragment_id">` or `<a name="fragment_id">`.

Modern EDGAR iXBRL filings (including AAPL) use **`<div id="fragment_id">`** as the anchor:
```html
<!-- AAPL 2021, pos 264975 -->
<div id="icffec2d5c553492089e1784044e3cc53_16"></div>
<hr style="page-break-after:always"/>
...
<span>Item 1A.&#160;&#160;&#160;&#160;Risk Factors</span>
```

The `<a>` anchor pattern matches 0 times on this filing. `_find_anchor_pos` returns -1.
Strategy A returns `None`. Strategy B then runs (and also fails — see B2).

### Fix
Change `_find_anchor_pos` to search for `id="fragment_id"` on **any** tag:
```python
# pre_seeker.py
pattern = re.compile(
    r'\bid\s*=\s"' + re.escape(fragment_id) + r'"',
    re.IGNORECASE,
)
```
This matches `<div id="...">`, `<span id="...">`, `<a id="...">`, etc.

### Verified
```
Total <a id/name> anchors in full AAPL_10K_2021 doc: 0
Elements with id="icffec2d5c553492089e1784044e3cc53_16" (div): 1  at pos 264975
```

---

## Bug B2 — Strategy B `str(tag)` never matches raw HTML (critical)

### What should happen
Strategy B scans `BeautifulSoup(lxml, SoupStrainer(["span","div","p"]))` elements,
and for each match finds the element's position in the original HTML via
`doc_html.find(str(tag))`.

### What actually happens
BeautifulSoup normalises HTML when stringifying tags:
- Escaping: `\'Helvetica\'` in raw HTML → `'Helvetica'` in `str(tag)`
- Entities: `&#160;` in raw HTML → `\xa0` in `str(tag)` (non-breaking space decoded)
- Self-closing tags and attribute ordering can also differ

Because `str(tag)` is never byte-for-byte identical to the original source, `doc_html.find(str(tag))`
always returns -1. Strategy B silently finds no position and returns `None`.

### Evidence
```
Raw source at pos 265348:
  <span style="...font-weight:700...">Item 1A.&#160;&#160;&#160;&#160;Risk Factors</span>
```
After BS4 round-trip, `str(span)` would contain `\xa0\xa0\xa0\xa0` (decoded non-breaking spaces),
not `&#160;&#160;&#160;&#160;`. `doc_html.find(str(span))` → -1.

### Fix
Replace `doc_html.find(str(tag))` with a regex search on the tag's plain text content:
```python
# Instead of:
outer = str(tag)
pos = doc_html.find(outer)

# Use: find the text content in the raw HTML
text_content = tag.get_text(strip=True)
if text_content:
    # Escape for regex; allow whitespace/entity variants
    escaped = re.escape(text_content)
    m = re.search(escaped, doc_html, re.IGNORECASE)
    pos = m.start() if m else -1
```
Or better: search for the fragment ID from the parent element's id attribute,
then walk forward to find the tag by text proximity.

---

## Bug B3 — `fiscal_year_end` field name mismatch (minor)

### What should happen
`_HDR_PATTERNS` in `sgml_manifest.py` extracts `FISCAL YEAR END` from the SGML header.

### What actually happens
Pattern uses `FISCAL YEAR ENDING:` but EDGAR uses `FISCAL YEAR END:` (no trailing G):
```python
# sgml_manifest.py line ~36
('fiscal_year_end', re.compile(rb'FISCAL YEAR ENDING:\s*(\d{4})', re.IGNORECASE)),
```

Actual EDGAR header for AAPL_10K_2021:
```
FISCAL YEAR END:			0925
```

Result: `manifest.header.fiscal_year_end` is `None` for all filings.

### Fix
```python
('fiscal_year_end', re.compile(rb'FISCAL YEAR END:\s*(\d{4})', re.IGNORECASE)),
```

---

## Warning W1 — UserWarning fires on every 10-K (noisy)

### Observed
```
WARNING  py.warnings: parser.py:175: UserWarning: 10-K parsed with Edgar10QParser
  (no dedicated 10-K parser available). Section identifier matching falls back
  to regex patterns.
```

### Root cause
`parse_from_content()` emits this warning whenever `form_type == "10-K"` and
`quiet=False` (the default). The new `parse_filing()` path (ADR-010) calls
`parse_from_content(..., quiet=quiet)` where `quiet` defaults to `False`.
This warning fires on every 10-K filing in any batch run.

The warning is accurate but not actionable — regex fallback is the expected and only mode
for 10-K sections. Firing on every file pollutes batch logs.

### Fix options
a) Pass `quiet=True` from `parse_filing()` internal call to `parse_from_content()` (suppresses always).
b) Promote warning to one-time `warnings.warn(..., stacklevel=2)` with `once` filter.
c) Leave as-is and filter in log handlers. (Lowest effort, least clean.)

---

## Outcome: Stage 1 fallback rate for this filing

Because both B1 and B2 are unresolved, Stage 1 returns `None` for AAPL_10K_2021.
The pipeline falls back to parsing the full 2 MB doc1 HTML with sec-parser.

**Impact on timing:**
- Stage 0 elapsed: **10.9 ms** ✓
- Stage 1 elapsed: **284.9 ms** (including failed strategies + fallback)
- Total elapsed:   **2.55 s** (down from 18.44 s baseline — improvement from Stage 0 + no SGML container overhead)
- Expected with Stage 1 working: **< 0.5 s** (only ~50–200 KB fed to sec-parser)

The 7× speedup already achieved (18.44 s → 2.55 s) comes from:
1. Stage 0 extracting doc1 byte range → no SGML container HTML passed to sec-parser
2. `flatten_html=False` on the new path (2.12 s of flatten eliminated)

Remaining speedup (to target < 0.5 s) requires fixing B1 + B2 so Stage 1 actually slices.

---

## New metadata correctly populated

Despite the fallback, Stage 0 populated all fields correctly:

| Field | Value |
|-------|-------|
| `accession_number` | `0000320193-21-000105` ✓ |
| `filed_as_of_date` | `20211029` ✓ |
| `fiscal_year_end` | `None` ✗ (Bug B3) |
| `sec_file_number` | `001-36743` ✓ |
| `document_count` | `88` ✓ |
| `state_of_incorporation` | `CA` ✓ |
| `ein` | `942404110` ✓ |

---

## Action items

| Priority | Fix | File | Line |
|----------|-----|------|------|
| P0 | Fix `_find_anchor_pos` to match any element `id=` | `pre_seeker.py` | `_find_anchor_pos()` |
| P0 | Fix Strategy B to use text-content regex instead of `str(tag)` | `pre_seeker.py` | `_strategy_b()` |
| P1 | Fix `fiscal_year_end` field name pattern | `sgml_manifest.py` | `_HDR_PATTERNS` line ~36 |
| P2 | Suppress or demote `10-K parsed with Edgar10QParser` warning | `parser.py` | `parse_from_content()` |
