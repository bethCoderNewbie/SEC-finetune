---
id: US-018
epic: EP-5 Observability
priority: P1
status: Not implemented
source_prd: PRD-003
estimation: 3 points
dod: Every result links directly back to the original sentence in the SEC filing on EDGAR.
---

# US-018: Source Traceability — Link to Original SEC Filing

## The Story

> **As an** `Audit / Compliance` reviewer,
> **I want** to click a link on any extracted risk segment and see the original sentence in the raw SEC filing,
> **So that** I can verify the context and accuracy of the extraction for myself without searching manually.

## Definition of Done (Plain Language)

Every risk segment shown in the UI has a "View Source" link. Clicking it opens the original EDGAR filing page at the exact location where that sentence appears.

## Acceptance Criteria

### Scenario A: Every JSONL record carries its EDGAR source URL
```gherkin
Given a segment extracted from AAPL's 10-K filing (CIK: 0000320193, accession number known)
When the extractor processes the filing
Then the JSONL record contains edgar_url: "https://www.sec.gov/Archives/edgar/data/320193/..."
  And edgar_url resolves to the filing's HTML index page on EDGAR
  And the record also contains: source_file (local filename), source_section ("Item 1A"), segment_index (int)
```

### Scenario B: Streamlit UI shows a clickable "View Source" button per segment
```gherkin
Given a segment with edgar_url populated
When I view that segment in the Streamlit UI
Then a "View Source ↗" button is visible below the segment text
  And clicking it opens the EDGAR filing URL in a new browser tab
```

### Scenario C: Accession number is derived from the filename or HTML metadata
```gherkin
Given a filing filename of the form AAPL_10K_2021.html
  And the HTML header contains the EDGAR accession number (e.g. <accession-number>0000320193-21-000105</accession-number>)
When the parser processes the file
Then the accession number is extracted and stored in ParsedFiling.accession_number
  And edgar_url is constructed as: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&dateb=&owner=include&count=40
```

### Scenario D: Missing accession number degrades gracefully
```gherkin
Given a filing whose HTML header does not contain an accession number
When the extractor processes it
Then edgar_url is set to null in the JSONL record
  And the "View Source" button in the UI is disabled (greyed out) with tooltip: "Source URL not available"
  And no error is raised
```

## Technical Notes

- Accession number extraction: add to `SECFilingParser` (`src/preprocessing/parser.py`), store in `ParsedFiling`
- EDGAR URL pattern: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number_no_dashes}/{filename}`
- New JSONL fields: `edgar_url` (str | null), `accession_number` (str | null)
- Depends on `ParsedFiling` carrying `accession_number` through the pipeline to `SegmentedRisks`
- Status: ❌ Not implemented
