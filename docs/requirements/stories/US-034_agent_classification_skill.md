---
id: US-034
epic: EP-8
priority: P0
status: Not implemented
source_prd: PRD-005
estimation: M (3–5 days)
---

# US-034: Agent Classification Skill

## The Story

As an **ML Engineer**, I want an agent skill that classifies all risk segments in a filing by SASB
archetype and topic in a single tool call, so that every analysis report is grounded in the SASB
taxonomy without requiring manual labeling and without losing ancestor-prior context.

## Acceptance Criteria

### Scenario: Filing classified with known SIC code

```gherkin
Given a SegmentedRisks JSON for ticker "TEST" with SIC code "3571" (Electronic Computers)
And the file is present in the run directory at the expected path
When the classify_filing skill is invoked with ticker="TEST", fiscal_year="2024", run_dir=<path>
Then the result is a list of ClassificationResult objects with length > 0
And each ClassificationResult contains a field "risk_label" with one of: environment, social_capital, human_capital, business_model, governance, other
And each ClassificationResult contains a field "confidence" that is a float between 0.0 and 1.0
And each ClassificationResult contains a field "label_source" with one of: "nli_zero_shot", "heuristic", "ancestor_prior"
And each ClassificationResult contains a field "sasb_industry" that is a non-empty string
```

### Scenario: Skill is independently unit-testable with mocked annotator

```gherkin
Given SegmentAnnotator is mocked to return [{"risk_label": "business_model", "confidence": 0.91, "label_source": "nli_zero_shot", ...}]
And load_filing is mocked to return a SegmentedRisks with 1 segment
When classify_filing is called with ticker="MOCK", fiscal_year="2024", run_dir=<path>
Then the skill returns a list containing one ClassificationResult with risk_label="business_model" and confidence=0.91
And no actual NLI model is loaded during the test
```

### Scenario: Skill registered as Claude tool

```gherkin
Given the AnalysisOrchestrator is initialized with TOOLS list
When the TOOLS list is passed to anthropic.messages.create()
Then the tool named "classify_filing" is present in the tools list
And its input_schema requires fields "ticker" (string), "fiscal_year" (string)
And "run_dir" (string) is an optional field with default null
```

### Scenario: All segments in a filing are classified in one analysis run

```gherkin
Given a SegmentedRisks JSON with 161 segments for ticker AAPL
When the AnalysisOrchestrator completes the analyze company workflow
Then report.json["summary"]["risk_label_distribution"] sums to 161 across all six archetype keys
And every cluster entry in report.json["clusters"] contains a non-empty "archetype" field
And classify_filing was invoked exactly once (not once per segment)
```

### Scenario: Unknown SIC code returns "other" with low confidence

```gherkin
Given a SegmentedRisks with any segments
And the filing SIC code is "9999" (not in sasb_sics_mapping.json)
When classify_filing is invoked
Then every result has risk_label="other"
And every confidence is less than 0.5
And every label_source equals "heuristic"
```

### Scenario: Ancestor-prior classification preserved

```gherkin
Given a SegmentedRisks with two consecutive segments sharing ancestor "Cybersecurity Risks"
And the first segment is classified as "governance" by NLI with confidence >= 0.6
When classify_filing is invoked
Then the second segment's label_source equals "ancestor_prior"
And the second segment's risk_label equals "governance"
```

## Technical Notes

- **Skill module:** `src/analysis/skills/classifier.py`
- **Skill function name:** `classify_filing` (not `classify_segment` — operates at filing granularity)
- **Wraps:** `src/analysis/segment_annotator.py` (`SegmentAnnotator.annotate(segmented)`)
- **Why filing-level:** `SegmentAnnotator.annotate()` requires a full `SegmentedRisks` object to
  resolve ancestor-prior labels across adjacent segments. A per-text wrapper would silently drop
  the `"ancestor_prior"` label_source path (3rd of 5 classification layers). See critique §1.
- **Input to Claude tool-use:** `ticker`, `fiscal_year`, `run_dir` (all simple strings — serializable
  in Claude's `tool_use` JSON block without passing large segment arrays).
- **Internal flow:** `classify_filing` calls `load_filing(ticker, fiscal_year, run_dir)` to get
  `SegmentedRisks`, then calls `SegmentAnnotator(config).annotate(segmented)`.
- **Return type:** `List[ClassificationResult]` (Pydantic V2 model in `src/analysis/models/analysis.py`)
- **SASB taxonomy lookup:** `TaxonomyManager` in `src/analysis/taxonomies/taxonomy_manager.py`
- **Precondition:** `sasb_sics_mapping.json` and `archetype_to_sasb.yaml` must exist (US-030)
  — if missing, skill falls back to archetype-only output with `sasb_topic=None`
- **ADR-001:** `ClassificationResult` uses `model_config = ConfigDict(validate_assignment=True, extra="forbid")`
