---
title: "SASB GIC Enrichment — Schema Critique & Two-Stage NLI Method"
date: 2026-03-11
time: "20:27:44"
author: bethCoderNewbie
git_commit: 15655da
branch: main
repository: SEC-finetune
status: DRAFT
related_prd: PRD-002_SEC_Finetune_Pipeline_v2.md
related_stories: US-030
related_adr: ADR-016
related_research:
  - 2026-03-11_14-24-12_yoy_risk_comparison_gap_analysis.md
  - 2026-03-03_17-30-00_segment_annotator_jsonl_transform.md
---

# SASB GIC Enrichment — Schema Critique & Two-Stage NLI Method

## 1. Problem Statement

`SegmentAnnotator` currently classifies each segment to one of 6 SASB dimensions
(`environment`, `social_capital`, `human_capital`, `business_model`, `governance`, `other`).
The dimension label is too coarse for an analyst: "environment" does not distinguish
*GHG Emissions* from *Water & Wastewater Management* from *Ecological Impacts* — three
materially different risk topics that require different disclosures.

**Goal:** Enrich the `sasb_topic` output field from the current single-GIC-per-industry
crosswalk to a fully discriminated GIC label selected by NLI from the industry's actual
SASB-defined candidate set.

---

## 2. Current Architecture (Ground Truth)

### 2.1 Classification flow

```
segment.text
    → Stage 1 NLI (6 dimension display names)        → archetype (e.g. "environment")
    → _crosswalk_sasb(archetype, sasb_industry)       → sasb_topic (single string, or None)
```

`_crosswalk_sasb()` at `segment_annotator.py:721–735`:
```python
dimension_map = self._crosswalk.get(archetype, {})   # archetype_to_sasb.yaml
return dimension_map.get(sasb_industry) or dimension_map.get("default")
```

The lookup is `archetype_to_sasb.yaml` → one GIC string per (dimension, industry) pair.

### 2.2 Unused data

`TaxonomyManager` loads `sasb_sics_mapping.json` at init.
`sasb_topics` (the bulk of the file) is parsed into full Pydantic models
(`SASBTopic`, `DisclosureTopic`) at `taxonomy_manager.py:116–129`.

`get_topics_for_sic()` and `get_topics_for_industry()` exist at
`taxonomy_manager.py:205–238` but **are never called by `SegmentAnnotator`**.
The full per-industry GIC candidate sets sit loaded in memory and are never queried.

---

## 3. Schema Critique

### 3.1 `archetype_to_sasb.yaml` — lossy by design

The YAML picks exactly one "most material" GIC per (dimension, industry) pair.
This is wrong when an industry has multiple material GICs within one dimension:

| Industry | Dimension | GICs in `sasb_topics` | GICs in YAML |
|---|---|---|---|
| Construction Materials | Environment | GHG Emissions, Air Quality, Energy Management, Water & Wastewater, Waste & Hazardous Materials, Ecological Impacts | `Water_&_Wastewater_Management` (1 of 6) |
| Coal Operations | Environment | GHG Emissions, Water & Wastewater, Waste & Hazardous Materials, Ecological Impacts | `Greenhouse_Gas_Emissions` (1 of 4) |
| E-Commerce | Social Capital | Customer Privacy, Data Security | `Data_Security` (1 of 2) |

The YAML crosswalk makes the GIC pre-determined — NLI in Stage 2 has nothing to decide.

### 3.2 `archetype_to_sasb.yaml` — GIC name inconsistency

Two spellings for the same GIC (gic_code 110) exist across dimension entries:
- `"GHG_Emissions"` — used in: `environment → Air Freight & Logistics, Cruise Lines,`
  `Food Retailers & Distributors, Health Care Distributors, Marine Transportation,`
  `Rail Transportation, Waste Management`
- `"Greenhouse_Gas_Emissions"` — used in: `environment → Airlines, Chemicals,`
  `Coal Operations, Electric Utilities, Iron & Steel Producers, Meat/Poultry/Dairy,`
  `Metals & Mining, Oil & Gas (all), Road Transportation`

The canonical form from `sasb_topics` `gic_name` is `"GHG Emissions"` (gic_code=110).
All YAML entries must normalise to `"GHG_Emissions"` (underscore form of canonical name).

### 3.3 `archetype_to_sasb.yaml` — industry name mismatches vs `sic_to_sasb`

`_crosswalk_sasb()` passes the string returned by `sic_to_sasb` directly as the YAML key.
The following mismatches silently fall through to `default`:

| `sic_to_sasb` canonical name | YAML key (wrong) | Dimension | Correct GIC missed |
|---|---|---|---|
| `"Telecommunications"` (SIC 4812/4813) | `"Telecommunication Services"` | environment | `Energy_Management` |
| `"Electric Utilities"` (SIC 4911/4931) | `"Electric Utilities & Power Generators"` | social_capital, human_capital | `Access_&_Affordability`, `Employee_Health_&_Safety` |
| `"Aerospace & Defense"` (SIC 3760–3812) | `"Aerospace & Defence"` (British) | environment | `Waste_&_Hazardous_Materials_Management` |
| `"Biotechnology"` (SIC 8731) | `"Biotechnology & Pharmaceuticals"` | human_capital | `Employee_Engagement,_Diversity_&_Inclusion` |

**Fix:** all YAML keys must match the exact strings in `sic_to_sasb`. Run the audit:
```python
canonical = set(sic_to_sasb.values())
yaml_keys  = set().union(*[d.keys() for d in crosswalk.values()]) - {"default"}
print("YAML keys not in sic_to_sasb:", yaml_keys - canonical)
```

### 3.4 `sasb_topics` — `description` field quality is split

Two tiers observed:
- **`[Auto]` prefix (~80%):** boilerplate — `"GHG Emissions risks material to the
  Construction Materials industry (Environment dimension, SASB Navigator)."` — zero NLI
  signal beyond the GIC name itself.
- **Domain-written (~20%):** industry-specific risk language — Coal Operations, Water:
  `"Risks from acid mine drainage, slurry impoundment integrity, and stream buffer zone
  compliance."` — substantially better NLI hypothesis than the bare GIC name.

### 3.5 Dimension name mismatch: `ARCHETYPE_LABEL_MAP` vs `sasb_topics`

| `segment_annotator.py` key | `sasb_topics` `dimension` string |
|---|---|
| `environment` | `"Environment"` |
| `social_capital` | `"Social Capital"` |
| `human_capital` | `"Human Capital"` |
| `business_model` | `"Business Model and Innovation"` |
| `governance` | `"Leadership and Governance"` |

Any GIC index keyed by archetype code requires an explicit translation map.
Currently no such map exists in either file.

---

## 4. Proposed Method: Two-Stage NLI

### 4.1 Architecture

```
segment.text
    → Stage 1: NLI vs 6 dimension names             → archetype
    → get_gic_candidates(sasb_industry, archetype)   → [SASBTopic, ...]  (from sasb_topics)
         ├─ len > 1  → Stage 2 NLI vs GIC names      → sasb_topic (discriminated)
         ├─ len == 1 → unambiguous                    → sasb_topic (direct assign)
         └─ len == 0 → fallback to archetype_to_sasb.yaml crosswalk (existing path)
```

Stage 2 only fires when the industry has ≥2 GICs within the assigned dimension.
Single-GIC industries (most Consumer sectors) skip Stage 2 at no cost.

### 4.2 `TaxonomyManager` changes

Add translation constant and one method to `taxonomy_manager.py`:

```python
_ARCHETYPE_TO_DIMENSION: Dict[str, str] = {
    "environment":    "Environment",
    "social_capital": "Social Capital",
    "human_capital":  "Human Capital",
    "business_model": "Business Model and Innovation",
    "governance":     "Leadership and Governance",
}

def get_gic_candidates(
    self, industry: str, archetype: str
) -> List[SASBTopic]:
    """Return material GICs for (industry, archetype). Empty = no coverage."""
    dimension = _ARCHETYPE_TO_DIMENSION.get(archetype)
    if not dimension:
        return []
    return [
        t for t in self.topic_map.get(industry, [])
        if t.dimension == dimension
    ]
```

No schema changes to `SASBTopic` — `gic_name` (human-readable) and
`description` (hypothesis text) already exist.

### 4.3 NLI hypothesis template for Stage 2

**Option A — GIC name only (full coverage):**
```python
hypothesis = f"This text describes an environmental risk related to {{gic_name}}."
# e.g. "...related to Water & Wastewater Management."
```

**Option B — Domain description where available (better signal, partial coverage):**
```python
if not topic.description.startswith("[Auto]"):
    hypothesis = f"This text describes: {topic.description}"
else:
    hypothesis = f"This text describes an {archetype} risk related to {topic.gic_name}."
```

**Recommendation: Option B with Option A fallback.**
Domain-written descriptions for Coal Operations, Oil & Gas, Metals & Mining contain
site-specific risk vocabulary ("acid mine drainage", "flaring intensity", "tailings")
that BART NLI can match against segment text far more reliably than bare GIC names.

### 4.4 `SegmentAnnotator` changes

In `annotate()` at `segment_annotator.py:371`, replace the current single call:
```python
# current
sasb_topic = self._crosswalk_sasb(top_archetype, sasb_industry)
```
with:
```python
# new
gic_candidates = self._taxonomy.get_gic_candidates(sasb_industry, top_archetype)
if len(gic_candidates) > 1:
    sasb_topic = self._classify_gic(seg.text, top_archetype, gic_candidates)
elif len(gic_candidates) == 1:
    sasb_topic = gic_candidates[0].name
else:
    sasb_topic = self._crosswalk_sasb(top_archetype, sasb_industry)  # unchanged fallback
```

New private method `_classify_gic()`:
```python
def _classify_gic(
    self,
    text: str,
    archetype: str,
    candidates: List[SASBTopic],
) -> str:
    hypotheses = []
    for t in candidates:
        if not t.description.startswith("[Auto]"):
            h = f"This text describes: {t.description}"
        else:
            h = f"This text describes an {archetype} risk related to {t.gic_name}."
        hypotheses.append(h)

    # Pass text as each hypothesis, GIC name as label
    # BART NLI: text as premise, hypothesis as hypothesis
    gic_names = [t.name for t in candidates]
    result = self._pipeline(
        text,
        gic_names,
        hypothesis_template="This text describes a risk matching: {}",
        multi_label=False,
    )
    return result["labels"][0]   # top GIC name
```

> **Note on BART NLI call shape:** The standard `zero-shot-classification` pipeline
> accepts `candidate_labels` and `hypothesis_template`. For Option B (custom hypothesis
> per candidate), a direct `transformers.AutoModelForSequenceClassification` call with
> per-candidate premise-hypothesis pairs is required instead of the pipeline wrapper.
> The pipeline wrapper only supports a single shared template.

### 4.5 Output schema change

`sasb_topic` field (already present in JSONL output) changes meaning:
- **Before:** single pre-baked GIC from `archetype_to_sasb.yaml` crosswalk (or null)
- **After:** NLI-selected GIC from industry's actual candidate set (more discriminated)

No field additions needed. `sasb_industry` (already output at `segment_annotator.py:381`)
provides the context for interpreting the GIC label.

---

## 5. Data Fixes Required Before Stage 2 is Reliable

### 5.1 Normalise GIC names in `archetype_to_sasb.yaml`

Replace all `"Greenhouse_Gas_Emissions"` with `"GHG_Emissions"` (canonical per
`sasb_topics` gic_code=110). Affected industries listed in §3.2.

### 5.2 Align YAML industry key strings to `sic_to_sasb`

Fix the four mismatches in §3.3. Method: run the audit query, apply string replacements.
`archetype_to_sasb.yaml` is the follower; `sic_to_sasb` is the source of truth.

### 5.3 Verify `sasb_topics` industry coverage vs `sic_to_sasb`

`sic_to_sasb` has ~50 canonical industry strings. `sasb_topics` may not cover all of them.
Audit at load time:
```python
missing = set(self._mapping.sic_to_sasb.values()) - set(self._mapping.sasb_topics.keys())
if missing:
    logger.warning("Industries in sic_to_sasb with no sasb_topics entries: %s", missing)
```
Industries with no `sasb_topics` coverage fall through to the `archetype_to_sasb.yaml`
fallback path — this is acceptable and expected.

---

## 6. What Stays Unchanged

- `archetype_to_sasb.yaml` is retained as the fallback crosswalk for industries without
  `sasb_topics` coverage. Its structure (`dimension → industry → GIC_string`) is correct
  for this role; only the string values need fixing (§5.1, §5.2).
- `DisclosureTopic` (metric-level codes like `CG-AA-250a`) remains unused by the annotator.
  It is retained in the schema for potential future fine-tuning label lookup, not
  for NLI classification.
- Stage 1 NLI (6 dimensions) is unchanged. Stage 2 is additive.
- JSONL output schema is unchanged — `sasb_topic` is already the target field.

---

## 7. Open Questions

| ID | Question | Blocks |
|---|---|---|
| OQ-GIC-1 | Does BART zero-shot discriminate reliably between GHGs, Water, and Waste at sentence level for extractive 10-K text? Expected F1 unknown — needs evaluation on ≥50 manually labelled segments per GIC. | Stage 2 confidence calibration |
| OQ-GIC-2 | For direct `AutoModelForSequenceClassification` calls (Option B per-candidate hypothesis): what is the per-segment latency penalty of N hypotheses vs 1? At N=6 GICs for Construction Materials, throughput drops ~6×. Acceptable for a 112K-segment corpus? | `_classify_gic()` implementation |
| OQ-GIC-3 | Should `sasb_topic` store the underscore `name` (e.g. `"GHG_Emissions"`) or the space-separated `gic_name` (`"GHG Emissions"`)? Downstream YoY table display prefers the readable form; the training schema prefers a clean enum. Decide before annotating. | JSONL schema |
| OQ-GIC-4 | Coal Operations and Oil & Gas have domain-written descriptions. Which other industries have non-`[Auto]` descriptions in `sasb_topics`? A full audit determines whether Option B provides material coverage or is edge-case only. | Hypothesis template selection |
| OQ-GIC-5 | `archetype_to_sasb.yaml` `other` dimension is empty (`{}`). Segments labelled `other` by Stage 1 get `sasb_topic=None`. Is this acceptable, or should `other` segments be excluded from the output entirely? | Annotator output completeness |
