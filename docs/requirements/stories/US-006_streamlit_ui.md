---
id: US-006
epic: EP-6 ML Readiness
priority: P1
status: Partial — app exists, integration status unknown
source_prd: PRD-001, PRD-002
estimation: 3 points
---

# US-006: Streamlit UI for Extraction Validation

## The Story

> **As a** `Financial Analyst`,
> **I want** to view extracted risk segments in a Streamlit UI,
> **So that** I can validate extraction quality without writing any code.

## Acceptance Criteria

### Scenario A: Launch and browse filings
```gherkin
Given a processed run directory with at least one {stem}_segmented_risks.json file
  And the Streamlit app is started with streamlit run src/visualization/app.py
When I navigate to the app in a browser
Then I can select a company from a dropdown populated from the processed run
  And view all extracted segments for that filing
  And see per-segment metadata: word_count, char_count, segment_index
```

### Scenario B: Filter by risk taxonomy label
```gherkin
Given a processed corpus with risk_label populated on each segment
When I apply a label filter in the UI (e.g. "Financial")
Then only segments with risk_label == "Financial" are displayed
  And the segment count updates to reflect the active filter
```

### Scenario C: Flag a segment as low-quality
```gherkin
Given I am reviewing segments in the UI
When I click "Flag as low quality" on a segment
Then that segment's ID is appended to a local review_flags.csv file
  And the flag is visible on reload (persisted, not ephemeral)
```

## Technical Notes

- Implementation: `src/visualization/app.py`
- Scenario C (flagging) is deferred — not yet scoped for implementation
- Status: ⚠️ `src/visualization/app.py` exists; integration with current pipeline output not confirmed
