---
id: US-011
epic: EP-4 Performance
priority: P0
status: Not implemented — targeted by PRD-003 Phase 4
source_prd: PRD-003
estimation: 5 points
---

# US-011: Anchor-Based Parse Performance (≤ 3s per Filing)

## The Story

> **As a** `Pipeline Operator`,
> **I want** filing parsing to complete in ≤ 3 seconds per file (median),
> **So that** I can iterate on segmenter parameters on the full 887-filing corpus within a single work session instead of waiting 8+ hours.

## Acceptance Criteria

### Scenario A: Filing with EDGAR named anchors takes the fast path
```gherkin
Given COST_10K_2023.html (6.35 MB) with EDGAR-standard hyperlink anchors in its ToC
When SECSectionExtractor processes the file
Then it uses BeautifulSoup to locate the Item 1A anchor in < 0.5s
  And passes only the ~50–200 KB Item 1A HTML fragment to sec-parser (not the full 6.35 MB)
  And total parse time is ≤ 3.0 seconds
  And output metadata contains extraction_method: "anchor_seek_v2"
```

### Scenario B: Filing without EDGAR anchors falls back gracefully
```gherkin
Given a filing with no named anchor links in its ToC
When the anchor seek finds no matching anchors
Then it falls back to the existing full-document parse path
  And the output is identical to the current behaviour
  And output metadata contains extraction_method: "full_parse_fallback"
```

### Scenario C: Key Item Recall is maintained after the change
```gherkin
Given the 309-filing corpus re-processed with anchor seek enabled
When check_extractor_batch.py runs
Then Key Item Recall is 309/309 (100%)
  And no regressions in extraction text quality
```

### Scenario D: Large-file BS4 flatten path (> 10 MB)
```gherkin
Given a filing where len(html_content) > 10_000_000 bytes
When _flatten_html_nesting is called
Then it uses the BeautifulSoup tree-walk path (not the DOTALL regex path)
  And completes without catastrophic backtracking
  And parse time is within the ≤ 3s target
```

## Technical Notes

- New method: `_anchor_seek_section` in `src/preprocessing/extractor.py`
- BS4 large-file path: `src/preprocessing/parser.py:412-466`
- Baseline: COST_10K_2023.html takes 34.52s on the full-parse path
- See PRD-003 §4.5 and §4.6 for anchor HTML patterns and code sketches
- Test: `tests/test_extractor.py` — anchor path taken; parse time ≤ 3s
