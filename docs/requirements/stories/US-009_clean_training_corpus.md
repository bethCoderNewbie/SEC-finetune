---
id: US-009
epic: EP-3 Data Quality
priority: P0
status: Not implemented — targeted by PRD-003
source_prd: PRD-003
estimation: 8 points
---

# US-009: Clean Training Corpus (No ToC or Table Contamination)

## The Story

> **As a** `Data Scientist`,
> **I want** the extracted corpus to contain no Table of Contents lines or HTML table text,
> **So that** training loss decreases monotonically on clean risk factor prose rather than plateauing on boilerplate.

## Acceptance Criteria

### Scenario A: HTML ToC table nodes are filtered at extraction time
```gherkin
Given an EDGAR filing containing a hyperlinked Table of Contents rendered as an HTML <table>
When SECSectionExtractor._extract_section_content processes the filing
Then TableOfContentsElement nodes are excluded before full_text is assembled
  And the output segment text contains no lines matching "Item \d+[A-Z]?\." followed by a page number
```

### Scenario B: Text-line ToC entries are filtered at node level
```gherkin
Given a filing whose ToC is rendered as plain text lines ("Item 1A. Risk Factors..... 25")
When the extractor processes the filing
Then text-line ToC patterns (TOC_PATTERNS_COMPILED) are applied per TextElement node before aggregation
  And no ToC-pattern lines appear in any segment
```

### Scenario C: HTML table numeric rows are excluded
```gherkin
Given a filing containing financial summary tables inside the Risk Factors section
When SECSectionExtractor processes the section
Then TableElement nodes are excluded from full_text assembly
  And segments contain only TextElement and TitleElement derived prose
```

### Scenario D: Batch validation confirms zero contamination
```gherkin
Given the full 309-filing corpus re-processed after Fixes 2A and 2B
When check_extractor_batch.py runs
Then _check_toc_contamination reports 0 violations across all 309 files
  And Key Item Recall remains 309/309 (100%)
```

## Technical Notes

- Fix 2A: Filter `TableOfContentsElement` + `TableElement` in `extractor.py:459-468`
- Fix 2B: Apply `cleaning.py`'s `TOC_PATTERNS_COMPILED` per TextElement node in `extractor.py`
- See PRD-003 §4.2 and §4.3 for exact code changes
- Test location: `tests/test_extractor.py` — fixture with known ToC HTML
- Defect scale: 175 / 309 files (56.6%) currently contaminated
