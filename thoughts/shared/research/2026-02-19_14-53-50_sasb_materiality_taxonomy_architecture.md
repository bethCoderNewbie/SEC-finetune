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
status: FINAL — updated 2026-02-19 with value proposition findings (§1.4) and stale correction fixes (§7, §8, §9)
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

| Approach | Labels | Models | SASB Fidelity | Training Complexity |
|:---------|:-------|:-------|:--------------|:--------------------|
| A. Semantic Archetypes only | 9 universal integers | 1 | Low — collapses industry context | Low |
| B. Per-industry models | SASB topics per industry | 1 per industry group | High | High — need annotated data per industry |
| **C. Hierarchical (chosen)** | **9 archetypes (ML) + SASB topic (lookup)** | **1** | **High — preserved in output** | **Moderate** |

Recommendation: Approach C. One 9-class classifier + a crosswalk layer that maps archetype → SASB topic per industry at output time. This is what your existing architecture is designed for — taxonomy_manager.py is the crosswalk lookup, it just needs the data.

---

### 1.4 Why SASB Material Topics vs. Generic Classifiers — Value Proposition

#### The Label Collapse Problem

Generic open-source classifiers apply the same label regardless of industry. The result is that the same surface label covers entirely different financial exposures with different regulatory frameworks, capital implications, and investor materiality:

| Archetype label | Oil & Gas E&P | Software & IT Services | Commercial Bank |
|:----------------|:--------------|:-----------------------|:----------------|
| `esg` | **Greenhouse_Gas_Emissions** — Scope 1/2 GHG, methane flaring; direct regulatory liability under EPA and SEC climate rules | **Environmental_Footprint_of_Hardware_Infrastructure** — data centre energy efficiency; largely immaterial to earnings at current disclosure thresholds | **Environmental_Risk_to_Mortgaged_Properties** — physical climate risk embedded in the loan book; increasingly a Basel capital adequacy concern |
| `regulatory` | **Management_of_the_Legal_&_Regulatory_Environment** — EPA drilling permits, NEPA review, federal lease rights | **Data_Privacy_&_Freedom_of_Expression** — GDPR, AI Act, CFAA; cross-border data sovereignty obligations | **Systemic_Risk_Management** — Basel III capital ratios, DFAST stress test obligations, Reg W affiliate limits |
| `financial` | **Reserves_Valuation_&_Capital_Expenditures** — SEC-regulated proved reserves estimation; commodity price impact on DD&A | **Competitive_Behavior** — pricing power, customer concentration, SaaS renewal rates | **Financial_Inclusion_&_Capacity_Building** — CRA obligations, underbanked market exposure, credit loss provisioning |

**Every row above is labeled identically by a generic classifier. Every row above is a structurally different financial exposure** requiring different analyst frameworks, different regulatory capital treatments, and different investor responses. A generic `esg` label is the beginning of analysis, not the output of it — an analyst receiving it must still read every segment to determine whether they are looking at GHG liability or data centre power consumption.

#### What SASB Materiality Adds

SASB conducted industry-by-industry empirical research to answer: *which specific topics have historically been financially material to investors in each industry?* The result is ~420 topic-industry pairs across 77 industries — derived from SEC disclosures, investor engagement records, and materiality litigation, not invented by a taxonomy designer.

Using the SASB Materiality Map as Layer 2 converts a generic classification into an **industry-grounded materiality signal** — the same standard used by institutional ESG rating agencies (MSCI, Sustainalytics) and referenced in TCFD alignment frameworks.

#### Analyst Workflow Difference

```
Generic classifier output:
  "Company X has 14 ESG risk segments"
  → Analyst must read all 14 to understand the composition

SASB-aware output:
  "Company X: 8 × Greenhouse_Gas_Emissions, 4 × Water_&_Wastewater_Management, 2 × Ecological_Impacts"
  → Analyst immediately knows the composition; can filter and prioritize
  → Labels map directly to TCFD physical/transition risk categories
  → Peer comparison within same SIC sector is valid without translation
```

#### The Crosswalk as the Key Architectural Innovation

Training one model per SASB industry (Approach B) would require annotated corpora for each of 77 industries — infeasible for a single contributor. The crosswalk avoids this entirely:

```
Segment text
    │
    ▼  One 9-class archetype classifier (trains once, works across all industries)
archetype = "esg"
    │
    ▼  TaxonomyManager.get_industry_for_sic(sic_code)   ← deterministic lookup, no ML
sasb_industry = "Oil & Gas — E&P"
    │
    ▼  archetype_to_sasb.yaml                            ← table lookup, no ML
sasb_topic = "Greenhouse_Gas_Emissions"
```

Layer 1 captures the *type* of risk (a signal that generalises across industries). The crosswalk translates that signal into the specific SASB topic that is material for *this company's* industry. Neither layer does the other's job — and the crosswalk adds SASB precision without requiring 77 separate training campaigns.

#### Architecture Selection: Fine-Tuned Encoders vs. Generative LLMs

Three architectures can map risk-factor text to a controlled SASB vocabulary: API-hosted LLMs (GPT-4o, Claude 3.5), local open-weight LLMs (Llama 3.1 8B, Mistral 7B, Phi-4), and fine-tuned encoders (FinBERT, DeBERTa-v3-base). This section evaluates all three against the operational constraints of this pipeline — including the strongest case *for* local LLMs.

**Master comparison**

| Dimension | API LLM | Local LLM | Fine-tuned encoder |
|:----------|:--------|:----------|:------------------|
| Schema determinism | ❌ Free-text, non-deterministic | ✅ Grammar-constrained generation (Outlines / llama.cpp GBNF) | ✅ Always deterministic |
| Air-gapped / local deployment | ❌ API only | ✅ Fully local | ✅ Fully local |
| TR-07: ≤ 1,000ms per segment on CPU | ❌ 1,500–4,000ms + RTT | ❌ 8–30s (7B, 4-bit quant) | ✅ 600–800ms |
| TR-07 on GPU (A10G) | ❌ API only | ✅ 80–300ms (7B, 4-bit quant) | ✅ 50–150ms |
| Marginal cost (450K segments/yr) | ❌ ~$1,800 (~$0.004/seg) | ✅ $0 after model download | ✅ $0 after fine-tuning |
| RAM footprint | ❌ API only | ⚠️ 5–8GB (7B 4-bit) | ✅ ~450MB (FinBERT) |
| Fine-tuning GPU requirement | N/A | ⚠️ 16GB+ (A10G) | ✅ 8GB consumer GPU |
| Macro F1 — zero-shot | 0.63–0.69 (frontier) | ~0.55–0.65 (est., 7B) | — |
| Macro F1 — fine-tuned | N/A at scale | ~0.75–0.80 (QLoRA on 7B) | **0.83** (SSRN 2025) |

---

**Failure mode 1 — Schema inconsistency**

When prompted to assign a SASB topic, LLMs produce free-text that does not conform to the `archetype_to_sasb.yaml` controlled vocabulary:

| Input segment | GPT-4o run 1 | GPT-4o run 2 | Fine-tuned encoder |
|:-------------|:------------|:------------|:------------------|
| "We face data breach risk from third-party vendors accessing our cloud environment." | `"Cybersecurity & Data Security"` | `"Data Protection"` | `"Data_Security"` (deterministic) |
| "Methane flaring obligations under EPA Rule 40 CFR Part 60 could increase operating costs." | `"Greenhouse Gas Emissions Risk"` | `"Environmental Compliance"` | `"Greenhouse_Gas_Emissions"` (deterministic) |

At 450,000 segments per annual cohort, a 2% schema-mismatch rate produces 9,000 unresolvable records. `"Data Protection"` and `"Data_Security"` appear as two distinct categories in any downstream `GROUP BY` — peer comparison, portfolio aggregation, and TCFD mapping all fail on exact label matching.

*Counter-argument — resolved by local LLMs:* Grammar-constrained generation (`outlines` library or llama.cpp GBNF grammar mode) forces a local LLM's output token sequence to only produce strings from the `archetype_to_sasb.yaml` vocabulary. This fully and deterministically resolves schema inconsistency — no post-processing required. A local LLM with grammar constraints is as deterministic as an encoder on this dimension.

---

**Failure mode 2 — CPU latency (the hard wall)**

PRD-002 TR-07: ≤ 1,000ms per segment on CPU. Annual cohort: ~450,000 segments.

| Model | Architecture | CPU latency / segment | Annual cohort | TR-07 |
|:------|:------------|:----------------------|:-------------|:------|
| FinBERT | Encoder, 110M params | ~800ms | ~100 hrs | ✅ |
| DeBERTa-v3-base | Encoder, 86M params | ~600ms | ~75 hrs | ✅ |
| Local LLM (7B, 4-bit, CPU) | Autoregressive decoder | 8–30s | 1,000–3,750 hrs | ❌ |
| GPT-4o | API decoder | 1,500–4,000ms + RTT | 190–500 hrs (rate-limited) | ❌ |

CPU latency for a local LLM is determined by autoregressive decoding speed (~4–8 tokens/sec for a 7B 4-bit model on CPU). A 50-token classification output takes 6–12 seconds — 8–15× slower than FinBERT. Grammar constraints do not help here: the decode rate is set by model size and hardware, not by output vocabulary size.

*Counter-argument — partially resolved on GPU:* On an A10G, a 7B local LLM achieves 80–300ms per segment — within TR-07. This is a viable path if GPU hardware is available at inference time. The project currently targets CPU-only deployment; GPU inference is a Phase 3 option.

---

**Failure mode 3 — Accuracy on domain**

Source: *ESG Risk Classification in 10-K Filings: Benchmarking FinBERT and LLMs* — Vo et al., SSRN 2025. Domain: S&P 100 10-K Item 1A, 122,000 paragraphs, 2012–2022.

| Model | Type | Macro F1 |
|:------|:-----|:---------|
| **Fine-tuned FinBERT** | Encoder, fine-tuned | **0.83** |
| Claude 3.5 Sonnet | Decoder, zero-shot | 0.69 |
| GPT-4o | Decoder, zero-shot | 0.67 |
| Grok 3 | Decoder, zero-shot | 0.64 |
| Gemini 2.5 Pro | Decoder, zero-shot | 0.63 |

The 14–20 F1-point gap is not a prompt engineering problem. Supervised fine-tuning on domain-labelled examples learns the exact distribution and edge cases of the 9-class taxonomy. FinBERT also shows the lowest run-to-run variance — relevant because peer comparison and portfolio reports require reproducible output.

*Counter-argument — partially closed by QLoRA:* A 7B local LLM fine-tuned with QLoRA on the same 4,500-example annotation corpus is estimated at 0.75–0.80 Macro F1 — a 3–8 point deficit vs. FinBERT at 63× the parameter count and 2× the VRAM. For use cases that require a generated rationale *alongside* the classification label (e.g., US-017 explainability), this tradeoff may be acceptable in Phase 3.

---

**Use case impact of each failure mode**

| Use case | Schema inconsistency | CPU latency | F1 gap |
|:---------|:---------------------|:------------|:-------|
| Competitive benchmarking (US-021): compare cybersecurity risk across FAANG | ❌ Fatal — mismatched labels aggregate as separate categories | — | ⚠️ High FP rate distorts comparison |
| M&A due diligence (US-023): CSV of target's top risk categories | ❌ Fatal — dealroom requires reproducible structured output | ⚠️ 8–30s/seg × 200 segs = 27–100 min per target | ⚠️ Missed material risks appear as lower exposure |
| Portfolio ESG screen: filter holdings with >10 GHG segments | ❌ Fatal — free-text GHG synonyms cannot be counted reliably | — | ⚠️ Under-counts exposure; screen fails |
| Offline / air-gapped annotation review | — | ❌ No API access (API LLM only) | ✅ Irrelevant |
| Nightly batch of new EDGAR filings (US-019) | ⚠️ Recoverable with post-processing | ❌ Rate limits + cost make nightly uneconomical | ⚠️ 16-point gap accumulates across 10K filings |

---

**Decision rule**

Use a local LLM (grammar-constrained + QLoRA fine-tuned) when **all** of the following are true:
1. A GPU is available at inference time — negates the CPU latency failure
2. The use case requires a generated rationale alongside the label (e.g., US-017 explainability)
3. A 3–8% F1 reduction vs. the fine-tuned encoder is acceptable

Use the fine-tuned encoder (this project's Phase 2 choice) when:
1. CPU-only deployment is required (TR-07 compliance)
2. Pure classification — no generation output needed
3. Maximum F1 and minimum RAM are priorities
4. Parallel multi-worker inference is needed (encoder forward passes are embarrassingly parallel; autoregressive decoding is sequential by design)

**Synthesis:** API LLMs fail on three structural dimensions simultaneously: schema determinism, CPU latency, and accuracy — with compounding cost and governance problems at scale. Local LLMs genuinely resolve schema inconsistency (grammar constraints) and governance (air-gapped), but remain blocked on CPU latency — a fundamental decoding architecture constraint that engineering cannot optimise away. Fine-tuned encoders satisfy all four constraints for a pure classification task.

The local LLM path is not the wrong choice — it is the correct Phase 3 candidate for the explainability use case (US-017), where a generated rationale per segment adds analyst value that an encoder cannot produce. For Phase 2 core pipeline classification, the fine-tuned encoder is the correct choice.

#### Downstream Integration Value

`sasb_topic` output values connect directly to institutional workflows without a translation layer:
- **ESG ratings:** MSCI and Sustainalytics score companies on SASB material topics; this pipeline produces the same vocabulary
- **SEC climate disclosure:** Reg S-K Item 1C references TCFD; SASB topics map to TCFD physical and transition risk categories
- **PRD-004 use cases:** Competitive benchmarking (US-021), M&A due diligence (US-023), and supplier risk screening (US-022) all require industry-specific label granularity — a generic `esg` label cannot support peer comparison across SIC sectors

---

## 2. Architecture Decision: Two-Layer Label Schema

### 2.1 The design choice

Three valid approaches exist — see §1.3 comparison table and §1.4 for full rationale. Approach C is chosen because:
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

| PRD-002 location | Status | Correction applied |
|:-----------------|:-------|:-------------------|
| §2.2 `risk_label` type | ✅ Applied | "str — one of 9 archetype labels (`cybersecurity` … `other`)" |
| §2.2 (new field needed) | ✅ Applied | `sasb_topic: str`, `sasb_industry: str`, `label_source: str` added to feature schema |
| §8 Risk Taxonomy | ✅ Applied | 12-class list replaced with two-layer schema; per-industry crosswalk table added |
| §4.1 default_model | ✅ Intentionally retained as `ProsusAI/finbert` | User decision: keep FinBERT as default; `microsoft/deberta-v3-base` queued as Phase 2 comparison experiment only. Do **not** change `src/config/models.py`. |
| §10 OQ-3 | ✅ Applied | Resolved: truncate to 512 for FinBERT / DeBERTa; use ModernBERT at 8,192 if >5% segments exceed 390 words |
| §10 OQ-4 | ✅ Applied | Resolved: JSONL confirmed; full schema in PRD-002 §2.1.2 and §8 |

---

## 8. Files to Create / Modify

| Action | File | Notes |
|:-------|:-----|:------|
| **Create** | `src/analysis/taxonomies/sasb_sics_mapping.json` | Priority: cover SIC codes in your corpus first (run SIC audit per §11 item 1) |
| **Create** | `src/analysis/taxonomies/archetype_to_sasb.yaml` | Crosswalk from archetype → SASB topic per industry; resolve OQ-T3 (`macro` mapping) before finalising |
| **Deprecate** | `src/analysis/taxonomies/risk_taxonomy.yaml` | Superseded by `sasb_sics_mapping.json`; add `# DEPRECATED` header; retain for reference only |
| **No change** | `src/analysis/taxonomies/taxonomy_manager.py` | Already correct; loads `sasb_sics_mapping.json` at line 125 |
| **No change** | `src/config/models.py` | `default_model = "ProsusAI/finbert"` retained by user decision. `microsoft/deberta-v3-base` is a Phase 2 comparison experiment, not the default. |
| **Updated** | `docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md` | All corrections applied: §1, §2.1.2, §2.2, §4.1, §5, §6, §8, §10, §11, §12 |

---

## 9. Open Questions

| # | Question | Owner | Unblocks |
|:--|:---------|:------|:---------|
| OQ-T1 | What SIC codes are actually present in the target corpus? Run frequency count on batch output before completing `sasb_sics_mapping.json` | Data Eng | `sasb_sics_mapping.json` completeness |
| OQ-T2 | Should `sasb_topic` be a list (multiple SASB topics per segment) or a single best match? Current design returns `sasb_topics[0]`. | ML Engineer | **Resolved** — single `str`; crosswalk returns most specific topic for the `(archetype, sasb_industry)` pair; first match wins. Defined in PRD-002 §8 Phase 2 target schema. |
| OQ-T3 | For the `macro` archetype (interest rates, FX, inflation), no SASB topic maps cleanly. Does it get mapped to `Other_General_Risk` or omitted from SASB enrichment entirely? | Data Scientist | Open — recommendation: use `"Macro_Environment"` as a project-defined label (not official SASB) rather than `null`, to prevent downstream null-handling complexity. Decision needed before finalising `archetype_to_sasb.yaml`. |
| OQ-T4 | Should annotators be allowed to select "Other_General_Risk" per SASB, or only forced to one of the industry's named topics + the global `other` archetype? | Product | Open — recommendation: show industry SASB topics + `"other"` archetype as escape hatch; do not expose `"Other_General_Risk"` as a separate choice to avoid label proliferation. |
