---
id: RFC-002
title: SASB Two-Layer Label Schema — Three Blocked Decisions
status: DRAFT
author: bethCoderNewbie
created: 2026-02-20
last_updated: 2026-02-20
git_sha: 5476f84
superseded_by: null
related_research: thoughts/shared/research/2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md
---

# RFC-002: SASB Two-Layer Label Schema — Three Blocked Decisions

## Status

**DRAFT** — three decisions required before ADR-009 can be written. Each section
states the options, trade-offs, and a recommendation. Once an option is chosen per
section, record the choices in ADR-009 and reference this document as context.

---

## Background

The SASB two-layer label architecture (research §1.3, Approach C) is agreed:

- **Layer 1** — 9 archetype integers (ML classifier output)
- **Layer 2** — SASB material topic string (deterministic crosswalk lookup via
  `archetype_to_sasb.yaml` + `TaxonomyManager`)

Three specific sub-decisions were left unresolved in the research document and
block ADR-009. They are independent and can be decided in any order.

---

## Decision 1: Output Schema — Single `str` vs. List for `sasb_topic`

### Context

`archetype_to_sasb.yaml` maps each `(archetype, sasb_industry)` pair to a list
of one or more SASB topics. For example, `esg` under `Oil & Gas — E&P` maps to
four topics: `Greenhouse_Gas_Emissions`, `Air_Quality`,
`Water_&_Wastewater_Management`, `Ecological_Impacts`.

The inference pseudocode (research §6) emits `sasb_topics[0]` — a single string.
OQ-T2 (research §9) says "Resolved: single str; most specific topic; first match
wins." This is internally contradictory: "most specific" implies a ranking criterion
exists, but "first in the YAML list" is editorial ordering with no stated priority
rule.

The field is written into the final output record and into training JSONL. Its type
propagates to every downstream consumer: `GROUP BY` queries, TCFD mapping, peer
comparison dashboards.

### Option A — Single string, YAML list order is the explicit priority rule

`sasb_topic: str`. The first entry in the YAML list for a given
`(archetype, sasb_industry)` pair is always emitted. The YAML list order is
formally defined as priority order: topic authors must place the most directly
applicable topic first.

```json
{ "sasb_topic": "Greenhouse_Gas_Emissions" }
```

**Pros:**
- Simple schema — one field, one string, directly joinable in SQL/pandas
- Exact-match peer comparison and portfolio aggregation work without list handling
- YAML ordering rule is enforced at review time (no code enforcement needed)

**Cons:**
- A segment about water disposal receives `Greenhouse_Gas_Emissions` (first in list)
  even though `Water_&_Wastewater_Management` is more precise for that segment —
  the model has no way to distinguish; the crosswalk is by archetype only
- YAML list order becomes a de facto policy requiring documentation and discipline

### Option B — List of strings, all matched SASB topics emitted

`sasb_topics: list[str]`. All topics for the `(archetype, sasb_industry)` pair
are emitted as a list.

```json
{ "sasb_topics": ["Greenhouse_Gas_Emissions", "Air_Quality", "Water_&_Wastewater_Management", "Ecological_Impacts"] }
```

**Pros:**
- No information loss — all material SASB topics for the risk type are present
- Downstream consumers can filter or weight by topic as needed
- No arbitrary priority ordering required in the YAML

**Cons:**
- Schema change: `GROUP BY sasb_topic` requires UNNEST/EXPLODE; exact-match
  aggregation is broken without this step
- Training JSONL must store a list — HuggingFace `ClassLabel` does not support
  multi-label lists on the `label` column; requires separate handling
- All downstream consumers (PRD-004 use cases: competitive benchmarking US-021,
  M&A due diligence US-023) must handle list semantics

### Option C — Single string primary + list as supplementary field

`sasb_topic: str` (primary, first-in-list rule) and `sasb_topics_all: list[str]`
(supplementary, full list).

**Pros:** Simple consumers use `sasb_topic`; analytical consumers use
`sasb_topics_all`.

**Cons:** Two fields encoding overlapping information; schema complexity increases;
`sasb_topic` is always a subset of `sasb_topics_all`, creating potential for
inconsistency if YAML is updated and only one field is regenerated.

### Recommendation

**Option A.** The crosswalk operates at archetype granularity — it cannot
distinguish which SASB subtopic within a pair applies to a specific segment's text.
Emitting a list implies a precision the system does not have. Option A is honest
about that constraint. The YAML ordering rule (most directly applicable topic first)
must be documented in the file header and enforced at PR review.

**Decision required:** Choose A, B, or C.

---

## Decision 2: SIC Resolution — Explicit 4-Digit Enumeration vs. Prefix Matching

### Context

`TaxonomyManager.get_industry_for_sic()` (`taxonomy_manager.py:170`) performs
**exact string match only**:

```python
return self.sic_map.get(sic_str)   # exact match; no prefix fallback
```

The research document (§3.2) claimed that "2-digit prefix matching covers most
filings" — this is factually wrong. If `sasb_sics_mapping.json` contains `"7372"`
but a filing has SIC `"7373"` (Computer Integrated Systems Design), the lookup
returns `None` and logs a warning. Both are Software & IT Services per SASB, but
`"7373"` gets no enrichment.

EDGAR uses ~1,500 distinct 4-digit SIC codes. The SASB standard maps 77 industries
to SIC major groups (first 2 digits). A complete mapping must bridge this gap.

### Option A — Explicit 4-digit enumeration in `sasb_sics_mapping.json`; no code change

Enumerate every relevant 4-digit SIC code in `sic_to_sasb`. All lookups remain
exact-match. The SIC audit (OQ-T1) identifies which codes appear in the corpus;
only those need entries.

```json
{
  "sic_to_sasb": {
    "7371": "Software & IT Services",
    "7372": "Software & IT Services",
    "7373": "Software & IT Services",
    "7374": "Software & IT Services",
    "7375": "Software & IT Services",
    "7376": "Software & IT Services",
    "7379": "Software & IT Services"
  }
}
```

**Pros:**
- Zero code change — `taxonomy_manager.py` is not modified (research §8 "No change")
- Every mapping is explicit and auditable; no implicit prefix inference
- The SIC audit (OQ-T1) naturally produces the enumeration

**Cons:**
- Maintenance burden: new SIC codes that appear in future EDGAR cohorts require
  manual JSON additions
- Approximately 50–80 additional JSON entries for full Software/Banking/O&G coverage

### Option B — Add 2-digit prefix fallback to `get_industry_for_sic()`

Modify `taxonomy_manager.py:170` to try exact match first, then 2-digit prefix:

```python
def get_industry_for_sic(self, sic_code):
    sic_str = str(sic_code).strip()
    # Exact match first
    result = self.sic_map.get(sic_str)
    if result:
        return result
    # 2-digit major group fallback
    return self.sic_map.get(sic_str[:2])
```

`sasb_sics_mapping.json` uses 2-digit keys for major groups and 4-digit keys for
overrides:

```json
{
  "sic_to_sasb": {
    "73":   "Software & IT Services",
    "7371": "Software & IT Services",
    "6020": "Commercial Banks",
    "60":   "Commercial Banks"
  }
}
```

**Pros:**
- Smaller JSON file — one 2-digit entry covers dozens of 4-digit SIC codes
- Automatic coverage of new SIC codes within a mapped major group

**Cons:**
- Code change required to `taxonomy_manager.py` (contradicts research §8 "No change")
- Major group precision is coarse: SIC major group `73` covers both pure-play SaaS
  (7372) and data processing bureaus (7374) — both map to Software & IT Services,
  which is correct here, but other major groups are heterogeneous (e.g., SIC `60`
  covers banks, savings institutions, and credit unions — different SASB industries)
- Prefix matching can produce incorrect industry assignments where a major group
  spans multiple SASB industries; must enumerate exceptions as 4-digit overrides
  regardless

### Option C — Hybrid: prefix matching in code + 4-digit override support

Same as Option B but the JSON can contain both 2-digit and 4-digit keys. The code
resolution order is: exact 4-digit → 2-digit prefix → None. Gives the compactness
of B with the precision of A for ambiguous major groups.

**Pros:** Best coverage with minimum JSON size.

**Cons:** Resolution order must be documented and tested. Code change still required.
For major groups that span multiple SASB industries, the 2-digit entry cannot exist
— must be left out and all 4-digit codes enumerated explicitly. Adds cognitive
complexity to the JSON structure (mixed key lengths with implicit semantics).

### Recommendation

**Option A** for Phase 2. The SIC audit (OQ-T1) must be run before populating the
JSON file in any case. The audit output directly produces the enumeration needed for
Option A. No code change preserves the research §8 constraint. Option B or C can be
revisited if the audit reveals that corpus SIC diversity makes enumeration
unmanageable (>200 distinct codes).

**Decision required:** Choose A, B, or C.

---

## Decision 3: `macro` Archetype SASB Mapping

### Context

The 9-class archetype taxonomy includes `macro` (integer label 6) for
macroeconomic risk: interest rate sensitivity, foreign exchange exposure,
inflationary input costs, recession demand risk.

SASB does not define a universal `macro` material topic. No SASB industry maps
macroeconomic exposure to a named disclosure topic because SASB focuses on
industry-specific operational and ESG materiality, not cross-cutting financial
conditions.

The research document is internally contradictory on this point:
- §4.2 YAML: `macro: default: ["Management_of_the_Legal_&_Regulatory_Environment"]`
  — implying the question is settled
- §9 OQ-T3: "Open — recommendation: use `"Macro_Environment"` as a project-defined
  label rather than null"

Both are wrong: `Management_of_the_Legal_&_Regulatory_Environment` is the
`regulatory` archetype default, making `macro` and `regulatory` indistinguishable
in the output. And `"Macro_Environment"` is not an SASB topic.

### Option A — Emit `null`; omit SASB enrichment for `macro` segments

`sasb_topic: null` when archetype is `macro`. `sasb_industry` is still populated.

```json
{
  "risk_label": "macro",
  "sasb_topic": null,
  "sasb_industry": "Commercial Banks"
}
```

**Pros:**
- Honest — no false SASB attribution for a risk type that SASB does not map
- Downstream consumers must handle null but the null is meaningful signal:
  "this segment was classified macro; SASB has no specific topic for it"

**Cons:**
- Null-handling complexity in every downstream aggregation
- `"14 segments have no SASB topic"` is a confusing output for non-ML users

### Option B — Use `"Macro_Environment"` as a project-defined non-SASB label

`sasb_topic: "Macro_Environment"`. Document explicitly in ADR-009 and in the
data dictionary that this is a project-defined label, not an official SASB topic.

```json
{
  "risk_label":    "macro",
  "sasb_topic":    "Macro_Environment",
  "sasb_industry": "Commercial Banks"
}
```

**Pros:**
- No nulls — downstream aggregation is uniform
- Clear and human-readable; analysts understand macroeconomic risk
- Label can be excluded from SASB-specific analysis by filtering on a known string
  rather than null-checking

**Cons:**
- Introduces a project-defined label into a field called `sasb_topic` — naming
  implies SASB provenance that does not exist; misleads downstream consumers who
  assume all `sasb_topic` values are canonical SASB
- Must be documented in data dictionary with `[project-defined, not SASB]` flag

### Option C — Dissolve the `macro` archetype; redistribute segments

Remove `macro` (label 6) from the 9-class taxonomy. Relabel macro-economic segments
as `financial` (label 2) or `regulatory` (label 1) depending on the dominant
exposure. Renumber labels to maintain 0-based integers.

- *Interest rate / FX / recession* → `financial`
- *Trade policy / tariffs / government intervention* → `regulatory`

**Pros:**
- Eliminates the unmappable category at its root
- Both `financial` and `regulatory` have well-defined SASB crosswalk entries
- 10-K Item 1A risk factors rarely use "macro" as a standalone category —
  rate sensitivity appears in financial risk sections; trade risk in regulatory

**Cons:**
- Reduces taxonomy from 9 to 8 classes — breaking change to all existing annotated
  data, training code (`NUM_LABELS = 9`), and model configs
- Requires re-annotation of any already-labeled `macro` segments
- Loses the ability to filter for pure macroeconomic exposure (e.g., "how many
  segments cite inflation as a risk factor?")
- `financial` archetype becomes broader and harder to annotate consistently

### Recommendation

**Option B.** Nulls are operationally more expensive than a documented
project-defined label. Option C dissolves signal that is genuinely distinct in
10-K disclosures (a segment about interest rate hedging is not the same as a
segment about credit default risk, even if both are `financial`). Option B
preserves `macro` as a queryable category while being explicit in the ADR and
data dictionary that `"Macro_Environment"` is not a canonical SASB topic.

**Decision required:** Choose A, B, or C.

---

## Next Steps

Once all three decisions are made:

1. Update `archetype_to_sasb.yaml` per Decision 1 (schema) and Decision 3 (macro)
2. Populate `sasb_sics_mapping.json` per Decision 2 (SIC resolution strategy)
3. If Decision 2 = Option B or C, update `taxonomy_manager.py:156–170`
4. Write **ADR-009** recording the three chosen options; reference this RFC

---

## References

- `thoughts/shared/research/2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md`
  — §1.3, §1.4, §4.2, §6, §9 (OQ-T2, OQ-T3)
- `src/analysis/taxonomies/taxonomy_manager.py:156–170` — exact-match SIC lookup
- `src/analysis/taxonomies/archetype_to_sasb.yaml` — (file to be created)
- `src/analysis/taxonomies/sasb_sics_mapping.json` — (file to be created)
