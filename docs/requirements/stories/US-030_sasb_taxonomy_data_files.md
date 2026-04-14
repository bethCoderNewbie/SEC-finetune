---
id: US-030
epic: EP-6 ML Readiness
priority: P0
status: Not implemented
source_prd: PRD-002
estimation: 3 points
---

# US-030: Create SASB Taxonomy Data Files

## The Story

> **As a** `Data Engineer`,
> **I want** `sasb_sics_mapping.json` and `archetype_to_sasb.yaml` created covering every SIC code in the target corpus,
> **So that** `TaxonomyManager` returns a non-empty SASB topic set for every filing processed — enabling the SASB-aware classifier (US-029) to enrich every segment with industry-specific labels.

## Acceptance Criteria

### Scenario A: TaxonomyManager returns non-empty results for all corpus SIC codes
```gherkin
Given sasb_sics_mapping.json is created at src/analysis/taxonomies/sasb_sics_mapping.json
  And the target corpus SIC codes have been audited (§11 item 1)
When I call TaxonomyManager().get_topics_for_sic(sic_code) for every SIC in the corpus
Then the result is a non-empty dict for every SIC code present in the corpus
  And TaxonomyManager().get_industry_for_sic(sic_code) returns a non-empty string for every SIC code in the corpus
```

### Scenario B: sasb_sics_mapping.json structure is valid
```gherkin
Given sasb_sics_mapping.json at src/analysis/taxonomies/sasb_sics_mapping.json
When I parse it with json.load()
Then the top-level object has exactly two keys: "sic_to_sasb" and "sasb_topics"
  And "sic_to_sasb" maps SIC code strings to SASB industry name strings
  And "sasb_topics" maps industry name strings to lists of {"name": str, "description": str} objects
  And every SIC code in the corpus appears as a key in "sic_to_sasb"
  And every industry referenced in "sic_to_sasb" has a corresponding entry in "sasb_topics"
```

### Scenario C: archetype_to_sasb.yaml crosswalk covers all 6 SASB dimensions
```gherkin
Given archetype_to_sasb.yaml at src/analysis/taxonomies/archetype_to_sasb.yaml
When I parse it with yaml.safe_load()
Then it contains exactly 6 top-level keys: environment, social_capital, human_capital, business_model, governance, other
  And each dimension (except "other") has a "default" entry for unknown industries
  And the "other" dimension maps to an empty dict (no crosswalk — no SASB home)
```

### Scenario D: Crosswalk lookup produces correct SASB topic per dimension+industry pair
```gherkin
Given archetype_to_sasb.yaml is loaded
When I look up dimension="social_capital" and sasb_industry="Software & IT Services"
Then the result is "Data_Security"
When I look up dimension="environment" and sasb_industry="Oil & Gas \u2013 Exploration & Production"
Then the result is "Greenhouse_Gas_Emissions"
When I look up dimension="governance" and sasb_industry="Commercial Banks"
Then the result is "Systemic_Risk_Management"
When I look up any dimension (except "other") with sasb_industry="Unknown"
Then the result is the dimension's "default" value (not null, not empty)
```

### Scenario E: risk_taxonomy.yaml deprecated — not loaded by any active code path
```gherkin
Given src/analysis/taxonomies/risk_taxonomy.yaml exists (hardcoded to Software & IT Services only)
When I grep the active code paths for references to risk_taxonomy.yaml
Then taxonomy_manager.py does not load risk_taxonomy.yaml
  And src/analysis/inference.py does not load risk_taxonomy.yaml
  And scripts/feature_engineering/auto_label.py does not load risk_taxonomy.yaml
  And the only references are in DEPRECATED comments or test fixtures
```

## Technical Notes

- **`taxonomy_manager.py:125`** loads `sasb_sics_mapping.json` by filename. It currently returns
  `{}` (silent empty dict) for every SIC code when the file is missing — no exception is raised.
  Creating the file unblocks `TaxonomyManager.get_topics_for_sic()` and `get_industry_for_sic()`
  without any code changes to `taxonomy_manager.py`.
- **SIC audit prerequisite (§11 item 1):** Before building the mapping file, run the SIC audit
  script to identify which SIC codes appear in the target corpus. Build `sasb_sics_mapping.json`
  to cover exactly those codes (Non-Goal: full 77-industry SASB coverage).
- **Schema for `sasb_sics_mapping.json`** (matches `SASBMapping` Pydantic model in
  `src/analysis/taxonomies/taxonomy_manager.py:61`):
  ```json
  {
    "sic_to_sasb": {
      "7372": "Software & IT Services",
      "7371": "Software & IT Services"
    },
    "sasb_topics": {
      "Software & IT Services": [
        {"name": "Data_Security", "description": "..."},
        {"name": "Recruiting_&_Managing_a_Skilled_Workforce", "description": "..."}
      ]
    }
  }
  ```
- **Schema for `archetype_to_sasb.yaml`** (6-class SASB dimensions per ADR-016):
  ```yaml
  social_capital:
    default: "Data_Security"
    "Software & IT Services": "Data_Security"
    "Commercial Banks": "Data_Security"
  environment:
    default: "Greenhouse_Gas_Emissions"
    "Oil & Gas \u2013 Exploration & Production": "Greenhouse_Gas_Emissions"
  other: {}
  ```
- **`risk_taxonomy.yaml` deprecation:** Mark with a `# DEPRECATED` header comment. Do not delete
  until test fixtures that reference it are updated.
- **Blocks:** US-029 (classifier cannot produce `sasb_topic` / `sasb_industry` without these files).
- Status: ❌ Not implemented
