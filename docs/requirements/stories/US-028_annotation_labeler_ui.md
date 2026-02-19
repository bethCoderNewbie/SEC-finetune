---
id: US-028
epic: EP-7
priority: P0
status: not_started
source_prd: PRD-004
estimation: 3d
---

## The Story

As a **Domain Expert / SME**, I want to review a zero-shot model's predicted risk category
for each segment and save my corrections to a local JSONL file, so that
`llm_finetuning/train.py` has a high-quality human-validated dataset to train on.

---

## Acceptance Criteria

### Scenario: CIK input triggers live fetch and displays first segment

```gherkin
Given the labeler app is running locally via `streamlit run src/visualization/labeler_app.py`
  And the zero-shot model (`src/analysis/inference.py`) is loaded
When the user enters CIK "0001318605" and clicks "Load Filing"
Then the app fetches the most recent 10-K for that CIK via edgar_client.py
  And the app runs the full pipeline (Parse → Extract → Clean → Segment → Zero-Shot Analysis) in memory
  And the UI displays the first segment text in a read-only text area
  And the UI shows a dropdown pre-selected to the zero-shot predicted category
  And a progress indicator shows "Segment 1 of N"
  And the "Save to File" button is disabled until all segments are reviewed
```

### Scenario: Human corrects a prediction and advances to the next segment

```gherkin
Given the UI is displaying segment 1 with zero-shot prediction "supply_chain"
When the user selects "regulatory" from the category dropdown
  And clicks "Next"
Then the segment is stored in the in-memory list with corrected_category = "regulatory"
  And label_source = "human_corrected"
  And the UI advances to display segment 2
  And the progress indicator updates to "Segment 2 of N"
```

### Scenario: Human accepts a prediction without changing the dropdown

```gherkin
Given the UI is displaying a segment with zero-shot prediction "cybersecurity"
When the user clicks "Next" without changing the dropdown
Then the segment is stored with corrected_category = "cybersecurity"
  And label_source = "human_accepted"
```

### Scenario: Save button appends all reviewed segments to the JSONL file

```gherkin
Given all N segments for the filing have been reviewed and are held in the in-memory list
When the user clicks "Save to File"
Then N records are appended to data/processed/synthesized_risk_categories.jsonl
  And each record contains: cik, company_name, filing_date, segment_id, text,
      zero_shot_prediction, zero_shot_confidence, corrected_category, label_source, labeled_at
  And labeled_at is an ISO 8601 UTC timestamp
  And the app displays: "Saved N records to synthesized_risk_categories.jsonl"
  And the in-memory list is cleared
  And the CIK input field is reset for the next session
```

### Scenario: Stateless append — second session does not overwrite prior work

```gherkin
Given synthesized_risk_categories.jsonl already contains 120 records from a prior session
When a new labeling session of 35 segments completes and the user clicks "Save to File"
Then the file contains 155 records total
  And the first 120 records are byte-for-byte unchanged
  And no deduplication is performed (stateless append)
```

### Scenario: Taxonomy dropdown is populated from risk_taxonomy.yaml, not hardcoded

```gherkin
Given configs/risk_taxonomy.yaml defines 8 categories
When the labeler app loads
Then the dropdown contains exactly the 8 category IDs from risk_taxonomy.yaml
  And adding a new category to risk_taxonomy.yaml causes it to appear in the dropdown
      on the next app restart without any code change
```

---

## Technical Notes

- **App entrypoint:** `src/visualization/labeler_app.py` — launched via `streamlit run`; runs locally only
- **Data source:** Live EDGAR fetch via `edgar_client.py` — one filing at a time per session
- **Pipeline reuse:** `src/acquisition/`, `src/preprocessing/pipeline.py`, `src/analysis/inference.py` (zero-shot model, `facebook/bart-large-mnli`)
- **Taxonomy source:** `configs/risk_taxonomy.yaml` (PRD-004 Phase 1 Step 1.1) — dropdown reads category IDs at startup
- **Output file:** `data/processed/synthesized_risk_categories.jsonl` — append-only; `data/` is in `.gitignore`; DVC versioning is a manual post-session step (`dvc add`, `dvc push`)
- **Operationalizes:** `llm_finetuning/synthesize_dataset.py` (existing concept script) — the labeler replaces the static script with an interactive workflow
- **Unblocks:** `llm_finetuning/train.py` — currently blocked; requires `synthesized_risk_categories.jsonl` as input
- **Resolves:** PRD-002 OQ-12 — "RLHF Loop: How will analysts correct misclassifications in the Streamlit UI?"
- **State:** Application is intentionally stateless — no progress saving, no user tracking, no duplicate prevention; a half-labeled session is discarded by closing the browser tab before clicking "Save"
- **Out of scope for this story:** Database storage, authentication, multi-user collaboration, DVC automation, model fine-tuning
- **Current status:** Not implemented; `llm_finetuning/synthesize_dataset.py` exists as a non-interactive proof-of-concept
