---
id: US-017
epic: EP-6 ML Readiness
priority: P1
status: Not implemented
source_prd: PRD-003
estimation: 5 points
dod: The app highlights the specific words and phrases it used to assign a risk category to each segment.
---

# US-017: Model Explainability — Classification Clue Highlighting

## The Story

> **As a** `Tools Manager`,
> **I want** to see the specific words and phrases that caused the model to assign a particular risk category,
> **So that** I can understand and trust the model's logic before acting on its outputs.

## Definition of Done (Plain Language)

When a segment is classified as "Financial Risk," the Streamlit UI highlights (e.g., in yellow) the words like "liquidity," "covenant," and "default" that drove that decision. The analyst does not need to trust a black box.

## Acceptance Criteria

### Scenario A: Classification clues are highlighted in the UI
```gherkin
Given a risk segment classified as any of the 12 taxonomy categories
When I view that segment in the Streamlit UI
Then the words and phrases with the highest attribution score are highlighted in the displayed text
  And hovering over a highlighted word shows its attribution weight (e.g., "liquidity: +0.34")
  And at least the top-3 most influential tokens are highlighted
```

### Scenario B: Attribution method is configurable
```gherkin
Given the pipeline config specifies explainability_method: "integrated_gradients"
When explainability is computed for a segment
Then integrated gradients are used to compute token-level attributions
  And the config also supports explainability_method: "shap" as an alternative
```

### Scenario C: Explainability is optional and non-blocking
```gherkin
Given explainability_method: null in configs/config.yaml
When the batch pipeline runs
Then no attribution scores are computed
  And JSONL records do not contain an attribution_tokens field
  And pipeline throughput is not penalised
```

### Scenario D: Attribution scores stored in JSONL for offline review
```gherkin
Given explainability is enabled
When a segment is classified
Then the JSONL record contains attribution_tokens: [{"token": "liquidity", "score": 0.34}, ...]
  And the list is sorted by descending absolute score
  And the Streamlit UI reads attribution_tokens directly from the JSONL record
```

## Technical Notes

- Attribution methods: `captum` (PyTorch integrated gradients) or `shap` library
- The classifier (`src/analysis/inference.py`) must be integrated before this story is implementable (US-001 dependency)
- UI: `src/visualization/app.py` — highlight via `st.markdown` with inline HTML spans
- Config: `configs/config.yaml` under `explainability.method` (null | "integrated_gradients" | "shap")
- Status: ❌ Not implemented
