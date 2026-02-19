---
title: "SASB Materiality Map as Classifier Foundation — Architecture & Implementation"
date: 2026-02-19
time: "14:53:50"
author: bethCoderNewbie
git_sha: 2df33475511680276791484900fab90c793df5bf
branch: main
related_prd: PRD-002_SEC_Finetune_Pipeline_v2.md
related_research:
  - 2026-02-19_14-22-00_huggingface_classifier_input_formats.md
  - 2026-02-19_classifier_model_selection.md
status: FINAL
---

# SASB Materiality Map as Classifier Foundation — Architecture & Implementation

This document defines the end-to-end design for using the SASB Materiality Map as the
authoritative source for risk classification labels in the SEC 10-K pipeline. It covers
the full drill-down: company → SIC → SASB industry → material topics → training labels →
inference output enrichment.

---

## 1. Problem Statement

### 1.1 Why the current taxonomy is wrong

`src/analysis/taxonomies/risk_taxonomy.yaml` (line 1) is hardcoded to **Software & IT Services**
only. PRD-002 §8 claims a 12-class taxonomy. The classifier research specifies 9 classes.
None of these are consistent. None are grounded in the SASB standard.

The core issue: EDGAR spans **all** SIC industries. A fixed label set applied cross-industry
collapses critical signal — "Regulatory" means tax compliance for a bank, EPA permitting for
an oil company, and GDPR for a tech company. The label must carry industry context to be useful
downstream.

### 1.2 What's already built (don't rebuild)

`src/analysis/taxonomies/taxonomy_manager.py` already has the correct 3-layer architecture:

```
SIC code  →  SASB Industry name   (sic_to_sasb dict)
SASB Industry name  →  Topics list  (sasb_topics dict)
```

Both layers are loaded from `sasb_sics_mapping.json` — **which does not exist yet.**
`TaxonomyManager.get_topics_for_sic(sic_code)` is already the correct inference interface;
it just returns `{}` until the data file is created.

`SECFilingParser` already extracts `sic_code` into `ParsedFiling` and it flows through all
pipeline stages into `SegmentedRisks`. The company-to-SIC mapping is free — it arrives with
the filing.

### 1.3 The Core Problem: Industry-Specific vs. Universal Labels

SASB defines 77 industries across 11 sectors. Each industry has 4–12 material topics. An oil company's risks ("Greenhouse Gas Emissions", "Mine Safety") have nothing in common with a tech company's ("Data Security", "Managing Systemic Risks"). A single fixed label set collapses this signal.

Three design choices:

Approach: A. Semantic Archetypes
Labels: 9 universal labels
Models: 1
SASB Fidelity: Low — collapses context
Training Complexity: Low
────────────────────────────────────────
Approach: B. Per-Industry Models
Labels: SASB topics per industry
Models: 1 per industry group
SASB Fidelity: High
Training Complexity: High — need data per industry
────────────────────────────────────────
Approach: C. Hierarchical (Recommended)
Labels: 9 archetypes (ML) + SASB topic (lookup)
Models: 1
SASB Fidelity: High — preserved in output
Training Complexity: Moderate

Recommendation: Approach C. One 9-class classifier + a crosswalk layer that maps archetype → SASB topic per industry at output time. This is what your existing architecture is designed for — taxonomy_manager.py is the crosswalk lookup, it just needs the data.

---

## 2. Architecture Decision: Two-Layer Label Schema

### 2.1 The design choice

Three valid approaches exist:

| Approach | Labels | Models | SASB Fidelity | Training complexity |
|:---------|:-------|:-------|:--------------|:--------------------|
| A. Semantic Archetypes only | 9 universal integers | 1 | Low — collapses industry context | Low |
| B. Per-industry models | SASB topics per industry | 1 per industry group | High | High — need annotated data per industry |
| **C. Hierarchical (chosen)** | **9 archetypes (ML) + SASB topic (lookup)** | **1** | **High — preserved in output** | **Moderate** |

**Approach C is the right choice** because:
- One model trains on 9 archetype integers → single HuggingFace-compatible classifier
- SASB specificity is preserved in the output record via a crosswalk lookup (no ML needed for that step)
- The existing `TaxonomyManager` is already the correct crosswalk interface
- Per-industry model training becomes possible later by filtering `sasb_industry` from the training records — the schema supports it without schema changes

### 2.2 Two-layer label schema

**Layer 1 — Archetype integers** (what the ML model learns):

```python
ARCHETYPE_LABELS = [
    "cybersecurity",   # 0 — data breach, ransomware, system disruption
    "regulatory",      # 1 — compliance, legal, government action
    "financial",       # 2 — liquidity, credit, covenant, capital structure
    "supply_chain",    # 3 — vendor concentration, logistics, sourcing
    "market",          # 4 — competition, pricing pressure, market share
    "esg",             # 5 — environmental, climate, social, governance
    "macro",           # 6 — interest rates, FX, inflation, recession
    "human_capital",   # 7 — talent, key person, labor relations
    "other",           # 8 — boilerplate, uncategorizable
]
NUM_LABELS = 9
```

**Layer 2 — SASB material topics** (industry-specific; derived via lookup, not ML):

Each archetype maps to one or more SASB topic names per industry. This crosswalk lives in
`src/analysis/taxonomies/archetype_to_sasb.yaml` (new file; see §4.2).

---

## 3. Step 1: Map Company to SASB Industry

### 3.1 Data flow (already implemented in pipeline)

```
Ticker / CIK (batch CLI input)
    │
    ▼  SECFilingParser.parse()  [src/preprocessing/parser.py]
ParsedFiling.sic_code  (str, e.g. "7372")
    │
    ▼  TaxonomyManager.get_industry_for_sic(sic_code)
    │      reads: src/analysis/taxonomies/sasb_sics_mapping.json → sic_to_sasb dict
    │
"Software & IT Services"
    │
    ▼  TaxonomyManager.get_topics_for_sic(sic_code)
    │      reads: sasb_sics_mapping.json → sasb_topics dict
    │
{"Data_Security": "...", "Managing_Systemic_Risks...": "..."}
```

No code changes required to `taxonomy_manager.py`. The missing artifact is the data file.

### 3.2 SIC → SASB mapping source

The SASB SICS® codebook maps their 77 industries to SIC major groups (first 2 digits).
The crosswalk below covers the major EDGAR sectors. Not every 4-digit SIC code needs a row —
major-group (2-digit) prefix matching covers most filings. Add specific 4-digit overrides
where an industry is split inside a major group.

**Priority order to build the mapping:** Start with the SIC codes represented in your corpus.
Run `grep -h "sic_code" data/processed/**/*.json | sort | uniq -c | sort -rn` on any batch
output to get the actual distribution before hand-mapping 77 industries.

---

## 4. Step 2: Extract Class Labels

### 4.1 `sasb_sics_mapping.json` — structure and priority industries

File location: `src/analysis/taxonomies/sasb_sics_mapping.json`

Required schema (matches what `SASBMapping.load_from_json()` at
`taxonomy_manager.py:99` expects):

```json
{
  "sic_to_sasb": {
    "7372": "Software & IT Services",
    "7371": "Software & IT Services",
    "7374": "Software & IT Services",
    "7379": "Software & IT Services",
    "6020": "Commercial Banks",
    "6022": "Commercial Banks",
    "6021": "Commercial Banks",
    "6211": "Investment Banking & Brokerage",
    "6282": "Asset Management & Custody Activities",
    "6311": "Insurance",
    "6321": "Insurance",
    "2836": "Biotechnology & Pharmaceuticals",
    "2835": "Biotechnology & Pharmaceuticals",
    "2834": "Biotechnology & Pharmaceuticals",
    "8011": "Health Care Delivery",
    "1311": "Oil & Gas — Exploration & Production",
    "1381": "Oil & Gas — Services",
    "2911": "Oil & Gas — Refining & Marketing & Transportation",
    "4911": "Electric Utilities & Power Generators",
    "4931": "Electric Utilities & Power Generators",
    "3711": "Automobiles",
    "5411": "Food Retailers & Distributors",
    "2000": "Processed Foods",
    "3669": "Hardware",
    "3674": "Semiconductors",
    "4813": "Telecommunication Services"
  },
  "sasb_topics": {
    "Software & IT Services": [
      {"name": "Data_Security", "description": "Risks from unauthorized access, disclosure, or disruption of customer and company data."},
      {"name": "Data_Privacy_&_Freedom_of_Expression", "description": "Risks from collection, use, and retention of personal information; censorship or access restriction."},
      {"name": "Intellectual_Property_Protection_&_Competitive_Behavior", "description": "Risks from patent, trade secret, and IP exposure; anti-competitive conduct."},
      {"name": "Management_of_the_Legal_&_Regulatory_Environment", "description": "Risks from compliance with laws and regulations; adverse regulatory changes."},
      {"name": "Recruiting_&_Managing_a_Skilled_Workforce", "description": "Risks from failure to attract, retain, or develop talent with specialized skills."},
      {"name": "Environmental_Footprint_of_Hardware_Infrastructure", "description": "Environmental risks from energy consumption and e-waste of data centers and hardware."}
    ],
    "Commercial Banks": [
      {"name": "Systemic_Risk_Management", "description": "Risks from the bank's contribution to financial system instability; counterparty and concentration risk."},
      {"name": "Data_Security", "description": "Risks from cyberattacks, data breaches, and fraud affecting customer financial data."},
      {"name": "Financial_Inclusion_&_Capacity_Building", "description": "Risks from failure to serve underbanked populations; community reinvestment obligations."},
      {"name": "Incorporation_of_ESG_Factors_in_Credit_Analysis", "description": "Risks from not accounting for ESG factors in lending and underwriting decisions."},
      {"name": "Business_Ethics", "description": "Risks from anti-money laundering failures, bribery, corruption, and sales practice violations."},
      {"name": "Management_of_the_Legal_&_Regulatory_Environment", "description": "Risks from compliance with banking regulations (Basel, Dodd-Frank, etc.)."}
    ],
    "Oil & Gas — Exploration & Production": [
      {"name": "Greenhouse_Gas_Emissions", "description": "Regulatory and reputational risks from Scope 1 and 2 GHG emissions; methane flaring and venting."},
      {"name": "Air_Quality", "description": "Risks from NOx, SOx, and volatile organic compound emissions affecting permits and community relations."},
      {"name": "Water_&_Wastewater_Management", "description": "Risks from water consumption and produced water disposal in drilling operations."},
      {"name": "Ecological_Impacts", "description": "Risks from habitat disruption, spills, and biodiversity loss in exploration and production areas."},
      {"name": "Community_Relations", "description": "Risks from opposition by local communities and indigenous peoples to exploration activities."},
      {"name": "Management_of_the_Legal_&_Regulatory_Environment", "description": "Risks from evolving environmental and drilling regulations; permit revocations."},
      {"name": "Business_Ethics_&_Payments_Transparency", "description": "Risks from anti-bribery violations and opaque payments to host governments."},
      {"name": "Workforce_Health_&_Safety", "description": "Risks from fatalities, injuries, and process safety incidents in field operations."}
    ],
    "Biotechnology & Pharmaceuticals": [
      {"name": "Drug_Safety", "description": "Risks from adverse events, product recalls, and post-market safety obligations."},
      {"name": "Affordability_&_Pricing", "description": "Risks from pricing scrutiny, government price controls, and public backlash."},
      {"name": "Ethical_Marketing", "description": "Risks from off-label promotion, kickbacks, and relationships with healthcare providers."},
      {"name": "Employee_Health_&_Safety", "description": "Risks from exposure to hazardous materials in lab and manufacturing environments."},
      {"name": "Product_Innovation_&_Lifecycle_Management", "description": "Risks from pipeline failure, patent expiration, and generic competition."},
      {"name": "Supply_Chain_Management", "description": "Risks from API sourcing concentration, cold-chain integrity, and supplier quality."}
    ]
  }
}
```

### 4.2 `archetype_to_sasb.yaml` — crosswalk from ML output to SASB language

File location: `src/analysis/taxonomies/archetype_to_sasb.yaml`

This is a pure lookup table. At inference time, after the classifier returns an archetype label,
this file is consulted to enrich the output with the company-specific SASB topic name.

```yaml
# archetype_to_sasb.yaml
# Maps 9-class archetype labels to SASB material topic names per industry.
# "default" is used when the company's SASB industry has no specific mapping.

archetype_to_sasb:

  cybersecurity:
    "Software & IT Services":
      - "Data_Security"
      - "Managing_Systemic_Risks_from_Technology_Disruptions"
    "Commercial Banks":
      - "Data_Security"
      - "Systemic_Risk_Management"
    "Biotechnology & Pharmaceuticals":
      - "Drug_Safety"          # cyberattack on trial data / manufacturing systems
    default:
      - "Data_Security"

  regulatory:
    "Software & IT Services":
      - "Management_of_the_Legal_&_Regulatory_Environment"
      - "Data_Privacy_&_Freedom_of_Expression"
    "Commercial Banks":
      - "Management_of_the_Legal_&_Regulatory_Environment"
      - "Business_Ethics"
    "Oil & Gas — Exploration & Production":
      - "Management_of_the_Legal_&_Regulatory_Environment"
    "Biotechnology & Pharmaceuticals":
      - "Drug_Safety"
      - "Ethical_Marketing"
    default:
      - "Management_of_the_Legal_&_Regulatory_Environment"

  financial:
    "Commercial Banks":
      - "Systemic_Risk_Management"
      - "Incorporation_of_ESG_Factors_in_Credit_Analysis"
    default:
      - "Systemic_Risk_Management"

  supply_chain:
    "Biotechnology & Pharmaceuticals":
      - "Supply_Chain_Management"
    "Oil & Gas — Exploration & Production":
      - "Community_Relations"
    default:
      - "Supply_Chain_Management"

  esg:
    "Oil & Gas — Exploration & Production":
      - "Greenhouse_Gas_Emissions"
      - "Air_Quality"
      - "Water_&_Wastewater_Management"
      - "Ecological_Impacts"
    "Electric Utilities & Power Generators":
      - "Greenhouse_Gas_Emissions"
    "Software & IT Services":
      - "Environmental_Footprint_of_Hardware_Infrastructure"
    default:
      - "Environmental_Footprint_of_Hardware_Infrastructure"

  macro:
    default:
      - "Management_of_the_Legal_&_Regulatory_Environment"

  market:
    "Software & IT Services":
      - "Intellectual_Property_Protection_&_Competitive_Behavior"
    "Biotechnology & Pharmaceuticals":
      - "Affordability_&_Pricing"
      - "Product_Innovation_&_Lifecycle_Management"
    default:
      - "Intellectual_Property_Protection_&_Competitive_Behavior"

  human_capital:
    "Software & IT Services":
      - "Recruiting_&_Managing_a_Skilled_Workforce"
      - "Employee_Engagement,_Diversity_&_Inclusion"
    "Oil & Gas — Exploration & Production":
      - "Workforce_Health_&_Safety"
    default:
      - "Employee_Health_&_Safety"

  other:
    default: []
```

---

## 5. Step 3: Create a Labeled Training Dataset

### 5.1 Annotation workflow — present SASB topics, not archetypes

The annotator sees industry-familiar SASB terminology, not abstract archetype names.
The archetype integer is derived automatically via the crosswalk.

```
RiskSegment (from PRD-002 pipeline)
    │
    ├── text:         "We are subject to complex cybersecurity laws..."
    ├── sic_code:     "7372"
    ├── ticker:       "MSFT"
    └── filing_date:  "2023-10-15"
         │
         ▼  TaxonomyManager.get_topics_for_sic("7372")
         │
         Annotator label choices (industry-specific):
           ○ Data_Security
           ○ Data_Privacy_&_Freedom_of_Expression
           ○ Intellectual_Property_Protection_&_Competitive_Behavior
           ○ Management_of_the_Legal_&_Regulatory_Environment
           ○ Recruiting_&_Managing_a_Skilled_Workforce
           ○ Environmental_Footprint_of_Hardware_Infrastructure
           ○ Other_General_Risk
         │
         Annotator selects: Data_Security
         │
         ▼  archetype_to_sasb.yaml reverse lookup
         │      "Data_Security" in "Software & IT Services" → archetype 0 (cybersecurity)
         │
         JSONL record written
```

**Why this produces higher-quality labels:**
- Annotators recognize "Data_Security" from the SASB framework and SEC disclosures
- "cybersecurity" vs. "regulatory" is an abstract distinction; "Data_Security" vs.
  "Management_of_the_Legal_&_Regulatory_Environment" is a concrete one for a tech analyst
- Inter-annotator agreement (Cohen's Kappa, QR-01 target ≥ 0.80) is easier to achieve
  with industry-specific terminology

### 5.2 JSONL training record schema

One line per segment. Both label layers preserved:

```jsonl
{
  "text": "We are subject to complex and evolving cybersecurity laws...",
  "label": 0,
  "sasb_topic": "Data_Security",
  "sasb_industry": "Software & IT Services",
  "sic_code": "7372",
  "ticker": "MSFT",
  "filing_date": "2023-10-15"
}
```

| Column | Type | Required for training | Notes |
|:-------|:-----|:----------------------|:------|
| `text` | `str` | Yes — HuggingFace `text` column | Sourced from `RiskSegment.text` after PRD-003 cleanup |
| `label` | `int` (0–8) | Yes — archetype integer | Derived from annotator's SASB topic selection via crosswalk |
| `sasb_topic` | `str` | No — metadata only | The exact SASB material topic name selected |
| `sasb_industry` | `str` | No — metadata only | Enables per-industry filtering for future model training |
| `sic_code` | `str` | No — metadata only | Source SIC for traceability and re-mapping |
| `ticker` | `str` | No — metadata only | Company identifier |
| `filing_date` | `str` | No — metadata only | ISO 8601; enables temporal drift analysis |

**Critical rule:** `label` must be an integer. Never store `"cybersecurity"` in this field.
HuggingFace's `load_dataset("json")` requires `label` to be integer-typed for
`ClassLabel` casting to work (research §1.1).

### 5.3 Per-class data requirements

| Archetype | Expected SASB topics mapped (cross-industry) | Min training examples |
|:----------|:---------------------------------------------|:----------------------|
| `cybersecurity` (0) | Data_Security; Systemic_Risk_Management | ≥ 500 |
| `regulatory` (1) | Management_of_the_Legal_&_Regulatory_Environment; Ethical_Marketing | ≥ 500 |
| `financial` (2) | Systemic_Risk_Management; Affordability_&_Pricing | ≥ 500 |
| `supply_chain` (3) | Supply_Chain_Management; Community_Relations | ≥ 500 |
| `market` (4) | Intellectual_Property_Protection; Affordability_&_Pricing | ≥ 500 |
| `esg` (5) | Greenhouse_Gas_Emissions; Environmental_Footprint | ≥ 500 |
| `macro` (6) | — (cross-cutting; no dedicated SASB topic) | ≥ 500 |
| `human_capital` (7) | Recruiting_&_Managing_a_Skilled_Workforce; Workforce_Health_&_Safety | ≥ 500 |
| `other` (8) | Other_General_Risk; uncategorized boilerplate | ≥ 500 |

`other` and `regulatory` will likely over-represent in 10-K filings. Apply weighted loss
when imbalance ratio exceeds 5:1 (research §6).

### 5.4 Loading into HuggingFace Datasets

```python
from datasets import load_dataset, ClassLabel

ARCHETYPE_LABELS = [
    "cybersecurity", "regulatory", "financial", "supply_chain",
    "market", "esg", "macro", "human_capital", "other",
]

dataset = load_dataset(
    "json",
    data_files={
        "train":      "data/processed/annotation/train.jsonl",
        "validation": "data/processed/annotation/validation.jsonl",
        "test":       "data/processed/annotation/test.jsonl",
    },
)
# Cast label to ClassLabel — retains sasb_topic etc. as pass-through metadata
dataset = dataset.cast_column(
    "label",
    ClassLabel(num_classes=9, names=ARCHETYPE_LABELS),
)
```

The `sasb_topic`, `sasb_industry`, `sic_code`, `ticker`, `filing_date` columns are retained
as metadata. Remove only `text` after tokenization (via `remove_columns=["text"]`).

---

## 6. Inference Output Enrichment

At inference time, after the classifier assigns an archetype label, the output record is
enriched with the SASB layer:

```python
# Pseudocode — belongs in src/inference/classifier.py (Phase 2 new)
from src.analysis.taxonomies.taxonomy_manager import TaxonomyManager
import yaml

taxonomy  = TaxonomyManager()
crosswalk = yaml.safe_load(open("src/analysis/taxonomies/archetype_to_sasb.yaml"))["archetype_to_sasb"]

def enrich_prediction(archetype_label: str, sic_code: str) -> dict:
    industry = taxonomy.get_industry_for_sic(sic_code) or "default"
    industry_map = crosswalk.get(archetype_label, {})
    sasb_topics  = industry_map.get(industry) or industry_map.get("default", [])
    return {
        "risk_label":    archetype_label,       # e.g. "cybersecurity"
        "sasb_topic":    sasb_topics[0] if sasb_topics else None,  # e.g. "Data_Security"
        "sasb_industry": industry,
    }
```

Final output record per segment adds three new fields to what `SegmentedRisks` produces today:

```json
{
  "index": 0,
  "text": "We face significant risks from data breaches...",
  "word_count": 45,
  "char_count": 270,
  "risk_label": "cybersecurity",
  "sasb_topic": "Data_Security",
  "sasb_industry": "Software & IT Services",
  "confidence": 0.94,
  "label_source": "classifier"
}
```

---

## 7. Corrections to PRD-002

| PRD-002 location | Current text | Correct text |
|:-----------------|:-------------|:-------------|
| §2.2 `risk_label` type | "Categorical — 12-class taxonomy" | "str — one of 9 archetype labels (`cybersecurity` … `other`)" |
| §2.2 (new field needed) | — | Add `sasb_topic: str` — SASB material topic name for this company's industry |
| §8 Risk Taxonomy | 12-class list | 9 archetypes (Layer 1) + SASB topics per industry (Layer 2 via crosswalk) |
| §4.1 default_model | `ProsusAI/finbert` | `microsoft/deberta-v3-base` (research §2.2) |
| §10 OQ-3 | Open | Resolved: truncate to 512 for DeBERTa; use ModernBERT at 8,192 if >5% segments exceed 390 words |
| §10 OQ-4 | Open | Resolved: JSONL is confirmed; schema defined in this document §5.2 |

---

## 8. Files to Create / Modify

| Action | File | Notes |
|:-------|:-----|:------|
| **Create** | `src/analysis/taxonomies/sasb_sics_mapping.json` | Priority: cover SIC codes in your corpus first |
| **Create** | `src/analysis/taxonomies/archetype_to_sasb.yaml` | Crosswalk from archetype → SASB topic per industry |
| **Deprecate** | `src/analysis/taxonomies/risk_taxonomy.yaml` | Superseded by `sasb_sics_mapping.json`; keep for reference only |
| **No change** | `src/analysis/taxonomies/taxonomy_manager.py` | Already correct; loads `sasb_sics_mapping.json` at line 125 |
| **Update** | `src/config/models.py` line 21 | Change default from `ProsusAI/finbert` to `microsoft/deberta-v3-base` |
| **Update** | `docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md` §2.2, §8 | Align taxonomy description to two-layer schema |

---

## 9. Open Questions

| # | Question | Owner | Unblocks |
|:--|:---------|:------|:---------|
| OQ-T1 | What SIC codes are actually present in the target corpus? Run frequency count on batch output before completing `sasb_sics_mapping.json` | Data Eng | `sasb_sics_mapping.json` completeness |
| OQ-T2 | Should `sasb_topic` be a list (multiple SASB topics per segment) or a single best match? Current design returns `sasb_topics[0]`. | ML Engineer | Annotation UI, output schema |
| OQ-T3 | For the `macro` archetype (interest rates, FX, inflation), no SASB topic maps cleanly. Does it get mapped to `Other_General_Risk` or omitted from SASB enrichment entirely? | Data Scientist | `archetype_to_sasb.yaml` completeness |
| OQ-T4 | Should annotators be allowed to select "Other_General_Risk" per SASB, or only forced to one of the industry's named topics + the global `other` archetype? | Product | Annotation tool design |
