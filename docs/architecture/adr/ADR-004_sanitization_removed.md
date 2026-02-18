# ADR-004: Remove HTML Sanitization from the Hot Path

**Status:** Accepted
**Date:** 2026-02-10
**Author:** @bethCoderNewbie

---

## Context

`src/preprocessing/sanitizer.py` (`HTMLSanitizer`) was added in December 2025 to pre-clean raw HTML
before passing it to `sec-parser`. It performed entity decoding, Unicode normalization, invisible
character removal, and redundant tag flattening.

Profiling on `AAPL_10K_2021.html` showed:

- `HTMLSanitizer` achieved **1.9% HTML reduction** — negligible improvement
- `sec-parser` handles raw HTML directly and correctly without pre-cleaning
- Adding a sanitization step before a semantic parser is **redundant** — the library was designed
  for production EDGAR HTML including its quirks

The sanitizer also introduced risk: stripping EDGAR-specific tags (e.g., `<DOCUMENT>`, `<SEC-HEADER>`)
broke CIK/SIC metadata extraction by `sec-parser`, requiring guards to prevent data loss.

## Decision

**Remove `HTMLSanitizer` from the default pipeline hot path.** The 4-step pipeline is:

```
Parse → Extract → Clean → Segment
```

`HTMLSanitizer` remains in `src/preprocessing/sanitizer.py` and is available as an optional
pre-processing step for research or edge-case filings, but it is **not imported or called** by
`SECPreprocessingPipeline` or the batch CLI.

## Consequences

**Positive:**
- Eliminates one full HTML parse pass per filing (CPU + memory savings)
- Removes the risk of EDGAR header tag stripping corrupting metadata
- Pipeline code is simpler — 4 stages instead of 5

**Negative:**
- Filings with genuine encoding corruption (mojibake) will not be automatically repaired;
  they will surface as garbled text in segments or DLQ entries
- If `sec-parser` behaviour changes in a future version (post-pinned upgrade), raw HTML quirks
  may need sanitization re-enabled

## Supersedes

Supersedes the 5-step pipeline design (`Sanitize → Parse → Extract → Clean → Segment`)
from CHANGELOG 2025-12-12.

## References

- `src/preprocessing/sanitizer.py` — retained but not in default path
- `src/preprocessing/pipeline.py:69` — note on sanitization removal
- CHANGELOG: 2026-02-10 (commit `8bb512c`)
