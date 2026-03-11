---
title: "Segment Annotator Module — JSONL Transform from SegmentedRisks to Training Record"
date: 2026-03-11
time: "17:30:00"
author: beth88.career@gmail.com
git_commit: d774bf7
branch: main
status: IMPLEMENTED — 2026-03-11; US-032 delivered. B-5 fixed, AnnotationConfig created, SegmentAnnotator + CLI shipped, 48 unit tests green. OQ-A9/C-3 (label_source namespace) resolved via ADR-015. OQ-A18 (ancestor prior) resolved as score-bonus (option c). B-5/C-1/OQ-A8 resolved. B-8/C-10 resolved (token-count truncation). Previous update 2026-03-11: §4.2–§4.6 extended with binary risk gate, section-specific hypothesis templates, ancestor context injection, section-specific confidence thresholds, and pluggable LLM backend for part1item1 / part2item7. Domain expert clarification: "81.5% noise" framing too narrow — see §10 C-11. Original validation: 2026-03-03 against classifier input formats, SASB taxonomy architecture, and LLM synthesis research.
related_prd: PRD-002_SEC_Finetune_Pipeline_v2.md
related_goals: G-04, G-12, G-15
related_stories: US-001, US-029, US-030, US-032
---

# Segment Annotator Module — Research

## 1. Problem Statement

PRD-002 §8 defines a Phase 2 target output schema — one flat JSON record per segment —
that `process_batch()` does not yet produce. The pipeline currently writes a nested JSON
per section per filing (`document_info / chunks`). The target is:

```json
{
  "index": 0,
  "text": "We face significant risks from data breaches and ransomware attacks.",
  "word_count": 45,
  "char_count": 270,
  "label": 0,
  "risk_label": "cybersecurity",
  "sasb_topic": "Data_Security",
  "sasb_industry": "Software & IT Services",
  "sic_code": "7372",
  "ticker": "AAPL",
  "cik": "0000320193",
  "filing_date": "2023-10-15",
  "confidence": 0.94,
  "label_source": "classifier"
}
```

This document establishes ground truth for what a new **`SegmentAnnotator`** module
needs to do, what infrastructure exists, what is missing, and where the module should live.

A pre-classification **ancestor-grouped merge** step is included in the annotator: short
segments that share identical `ancestors` breadcrumbs are merged into single records
targeting the 200–379 word range before the classifier is called. This gives the
zero-shot and fine-tuned models denser, more classifiable input than the raw 68-word
median segment while respecting the Option A ceiling (ADR-012).

---

## 2. Source → Target Schema Map

### 2.1 Source: `SegmentedRisks` v1.0 JSON

`save_to_json()` (`src/preprocessing/models/segmentation.py:79`) emits this structure
per `*_segmented.json` file:

```
document_info.ticker               → ticker          (direct copy)
document_info.cik                  → cik             (direct copy)
document_info.sic_code             → sic_code        (direct copy)
document_info.filed_as_of_date     → filing_date     (YYYYMMDD → YYYY-MM-DD reformat)
chunks[i].text                     → text            (direct copy)
chunks[i].word_count               → word_count      (direct copy)
chunks[i].char_count               → char_count      (direct copy)
(sequential counter)               → index           (assigned during flattening)
```

### 2.2 Fields Requiring Computation

| Target field | Source | Computation |
|---|---|---|
| `filing_date` | `document_info.filed_as_of_date` = `"20211029"` | String reformat: `YYYYMMDD → YYYY-MM-DD` |
| `index` | None | Monotonically increasing int per output file |
| `label` (int 0–8) | None | **Classifier inference** |
| `risk_label` (str) | None | **Classifier inference** |
| `confidence` (float) | None | **Classifier inference** |
| `label_source` | None | `"classifier"` if confidence ≥ threshold else `"heuristic"` |
| `sasb_industry` | None | `TaxonomyManager.get_industry_for_sic(sic_code)` — **needs `sasb_sics_mapping.json`** |
| `sasb_topic` | None | Crosswalk `(risk_label, sasb_industry)` via `archetype_to_sasb.yaml` — **file absent** |

> **Bug — `filed_as_of_date` not restored by `load_from_json` (Blocker B-5, C-1):**
> `segmentation.py:204–224` reads `document_info.filed_as_of_date` from disk but never
> passes it to the `SegmentedRisks` constructor. After `load_from_json()`,
> `segmented.filed_as_of_date` is always `None`. The `filing_date` reformat above will
> produce `None` for every record. `accession_number` has the same omission.
> **This must be patched in `segmentation.py` before the annotator can produce valid records.**

### 2.3 Archetype Integer Mapping (PRD-002 §8)

No authoritative source exists in code yet. Must be defined as a constant in the module:

```python
ARCHETYPE_LABEL_MAP = {
    "cybersecurity":  0,
    "regulatory":     1,
    "financial":      2,
    "supply_chain":   3,
    "market":         4,
    "esg":            5,
    "macro":          6,
    "human_capital":  7,
    "other":          8,
}
```

---

## 3. Existing Infrastructure Audit

### 3.1 `src/analysis/inference.py:RiskClassifier`

- Model: `facebook/bart-large-mnli` (zero-shot-classification)
- Labels: loaded from `risk_taxonomy.yaml` — **deprecated, hardcoded to Software & IT
  Services only** (`src/analysis/taxonomies/risk_taxonomy.yaml`)
- Returns string `label` (category from deprecated taxonomy), not an archetype int
- No `sasb_topic`, `sasb_industry`, `confidence`, `label_source` in output
- **Cannot be reused** — wrong taxonomy, wrong output schema
- **Char truncation is wrong gate (C-10):** `inference.py:84–86` truncates at 2,000 chars
  before calling the NLI model. BART NLI supports up to 1,024 tokens; DeBERTa supports
  512 tokens. A 2,000-char SEC paragraph is ~330–400 words but can tokenize to 420–560
  tokens under SentencePiece — above the DeBERTa limit. The annotator's
  `_classify_archetype()` must use tokenizer token-count truncation, not char-count
  truncation. The two models have different limits and neither is 2,000 chars.

### 3.2 `scripts/feature_engineering/auto_label.py`

The closest existing component. It uses `TaxonomyManager` for SASB-aware SIC routing
and produces JSONL. **Cannot be reused as-is** because:

- Reads from `ParsedFiling` pickle objects in `parsed_data_dir` — wrong input source.
  The new module must consume `*_segmented.json` (Stage 4 output), not Stage 1 output.
- Calls `segmenter.segment_risks(risk_text)` — re-segments from scratch, ignoring all
  Stage 4 output
- Output schema: `{"text", "labels": [{name, score}], "top_label", "top_score", "metadata"}`
  — does not match target
- No `label` (int), `risk_label`, `confidence`, `label_source` in required column names
- Uses SASB topics as *candidate labels* (correct for SASB topic assignment, but not
  for 9-archetype classification)
- `archetype_to_sasb.yaml` does not exist — crosswalk is absent

### 3.3 `TaxonomyManager` (`src/analysis/taxonomies/taxonomy_manager.py:118`)

- `get_industry_for_sic(sic_code)` → `str | None` ✅
- `get_topics_for_sic(sic_code)` → `Dict[str, str]` ✅
- Loads from `sasb_sics_mapping.json` — **file does not exist** (G-15 / US-030)
- Silently returns empty dict on missing file (`SASBMapping.load_from_json:103`) — safe

### 3.4 `SegmentedRisks` (`src/preprocessing/models/segmentation.py:33`)

- `save_to_json()` / `load_from_json()` exist and handle v1 and old flat schema ✅
- **No `save_to_jsonl()` method exists** — must be built in the annotator
- `RiskSegment` fields present: `chunk_id`, `parent_subsection`, `ancestors`, `text`,
  `word_count`, `char_count`
- Filing-level fields present: `ticker`, `cik`, `sic_code`, `filed_as_of_date`,
  `form_type`, `fiscal_year`

### 3.5 Missing Taxonomy Files (G-15 / US-030)

| File | Path | Status |
|---|---|---|
| `sasb_sics_mapping.json` | `src/analysis/taxonomies/sasb_sics_mapping.json` | **Does not exist** |
| `archetype_to_sasb.yaml` | `src/analysis/taxonomies/archetype_to_sasb.yaml` | **Does not exist** |

Their absence means `sasb_industry` and `sasb_topic` will be `null` in all output until
G-15 is completed. The module must handle this gracefully — null, not a crash.

---

## 4. Proposed Module Design

### 4.1 Location

**New file:** `src/analysis/segment_annotator.py`

Rationale:
- Not a script — it is a library class, consumed by `process_batch()` (Stage A
  integration) and by a standalone CLI script
- Lives in `src/analysis/` alongside `inference.py` and `taxonomies/`

### 4.2 Core Class Interface

```python
class SegmentAnnotator:
    """
    Transforms SegmentedRisks into flat JSONL records matching the PRD-002 §8
    Phase 2 target schema.

    Stage A: zero-shot classifier (facebook/bart-large-mnli)
    Stage B: fine-tuned checkpoint swap — same interface, no schema change

    Classification strategy (2026-03-11):
    - Binary risk gate filters non-risk segments before multi-class inference
    - Section-specific hypothesis templates match linguistic register of each section
    - Ancestor context injection narrows NLI candidate set using heading priors
    - Section-specific confidence thresholds reflect signal density per section
    - Pluggable LLM backend for part1item1 / part2item7 (Layer 5, optional)
    See §4.4.1–§4.4.5 for full design rationale.
    """

    ARCHETYPE_LABEL_MAP: ClassVar[Dict[str, int]]  # 9-entry constant
    ARCHETYPE_NAMES: ClassVar[List[str]]           # ordered by label int

    # Section-specific NLI hypothesis templates. {archetype} substituted at inference time.
    # Adapts to linguistic register: part1item1a = explicit; part1item1 = structural/factual;
    # part2item7 = retrospective causal. See §4.4.2.
    _HYPOTHESIS_TEMPLATES: ClassVar[Dict[str, str]] = {
        "part1item1a": "This text describes a risk related to {archetype}.",
        "part1item1c": "This text describes a risk related to {archetype}.",
        "part1item1":  ("This business description reveals a dependency, concentration, "
                        "or structural exposure related to {archetype}."),
        "part2item7":  ("This management discussion describes the financial or operational "
                        "impact of, or ongoing exposure to, {archetype}-related factors."),
        "part2item7a": ("This market risk disclosure describes quantitative exposure "
                        "to {archetype}."),
        "_default":    "This text describes a risk related to {archetype}.",
    }

    # Ancestor heading → archetype prior for candidate pruning and tie-breaking.
    # Keys are lowercase; matched against ancestors[-1].lower(). See §4.4.3.
    _ANCESTOR_ARCHETYPE_PRIOR: ClassVar[Dict[str, str]] = {
        "liquidity and capital resources": "financial",
        "market risk":                     "market",
        "competition":                     "market",
        "supply chain":                    "supply_chain",
        "cybersecurity":                   "cybersecurity",
        "regulatory":                      "regulatory",
        "human capital":                   "human_capital",
        "environmental":                   "esg",
        "climate":                         "esg",
        "critical accounting":             "financial",
    }

    # Per-section confidence thresholds. Implicit-language sections use lower values.
    # Below threshold → label_source = "heuristic". See §4.4.4.
    _SECTION_CONFIDENCE_THRESHOLDS: ClassVar[Dict[str, float]] = {
        "part1item1a": 0.70,
        "part1item1c": 0.70,
        "part2item7a": 0.65,
        "part2item7":  0.60,
        "part1item1":  0.55,
        "_default":    0.70,
    }

    def __init__(
        self,
        model_name: str,               # settings.models.zero_shot_model
        taxonomy_manager: TaxonomyManager,
        archetype_yaml_path: Optional[Path],  # archetype_to_sasb.yaml; may be None
        confidence_threshold: float = 0.7,    # overridden per section by _SECTION_CONFIDENCE_THRESHOLDS
        binary_gate_threshold: float = 0.5,   # binary risk relevance gate; see §4.4.1
        merge_lo: int = 200,           # target lower bound for merged segment (words)
        merge_hi: int = 379,           # hard ceiling; must not exceed Option A limit
        device: int = -1,
        llm_client: Optional[Any] = None,          # optional LLM backend; see §4.4.5
        use_llm_for_sections: Tuple[str, ...] = (), # e.g. ("part1item1", "part2item7")
    ) -> None: ...

    def annotate(self, segmented: SegmentedRisks) -> List[Dict[str, Any]]:
        """
        Merge short segments by ancestors, then classify each merged segment.
        Returns list of flat target-schema records.
        """

    def annotate_run_dir(
        self,
        run_dir: Path,
        output_path: Path,
        section_include: List[str] = ("part1item1a", "part2item7a", "part1item1c"),
        part2item7_subsection_filter: Optional[List[str]] = None,
    ) -> int:
        """
        Load *_segmented.json from run_dir whose section_identifier is in
        section_include, annotate, write to output_path as JSONL.

        part2item7_subsection_filter: if part2item7 is in section_include,
        only retain chunks whose ancestors[-1] matches an entry in this list
        (e.g. ["Liquidity and Capital Resources", "Critical Accounting Estimates"]).
        None = include all part2item7 chunks (not recommended).

        Returns total record count written.
        """

    @staticmethod
    def _merge_by_ancestors(
        segments: List[RiskSegment],
        merge_lo: int = 200,
        merge_hi: int = 379,
    ) -> List[RiskSegment]:
        """
        Group consecutive segments with identical ancestors and greedily merge
        them into segments targeting [merge_lo, merge_hi] words.
        See §4.6 for full algorithm.
        """

    @staticmethod
    def write_jsonl(records: List[Dict], output_path: Path) -> None:
        """Write records to JSONL, one JSON object per line."""

    @staticmethod
    def _is_risk_relevant(
        text: str,
        section_id: str,
        pipeline: Any,               # transformers zero-shot-classification pipeline
        gate_threshold: float = 0.5,
    ) -> bool:
        """
        Binary pre-classification gate. Returns True if segment contains a risk,
        vulnerability, dependency, or adverse event. Applied to part1item1 and
        part2item7 only — sections with high non-risk content density.
        part1item1a, part1item1c, part2item7a always return True (gate skipped).
        See §4.4.1.
        """

    @staticmethod
    def _build_candidate_labels(
        archetype_names: List[str],
        ancestors: List[str],
        ancestor_prior: Dict[str, str],
        top_n: int = 3,
    ) -> List[str]:
        """
        Narrow NLI candidate set using ancestor heading prior. Returns top_n archetype
        names biased toward the ancestor-implied archetype. Falls back to all
        archetype_names when no ancestor match found. See §4.4.3 and OQ-A18.
        """
```

### 4.3 `annotate()` Internal Flow

```
SegmentedRisks
    │
    ├─ filing-level:
    │     sic_code → sasb_industry = TaxonomyManager.get_industry_for_sic(sic_code)
    │     filed_as_of_date ("20211029") → filing_date ("2021-10-29")
    │     section_id = segmented.section_identifier
    │
    ├─ PRE-CLASSIFICATION MERGE:
    │     merged_segs = _merge_by_ancestors(segmented.segments, merge_lo, merge_hi)
    │     (see §4.6 for full algorithm)
    │
    └─ for chunk_i, seg in enumerate(merged_segs):
          0. BINARY RISK GATE (part1item1 and part2item7 only):
             if section_id in ("part1item1", "part2item7"):
                 if not _is_risk_relevant(seg.text, section_id, pipeline, gate_threshold):
                     continue  # excluded from JSONL; not labeled "other"
             # part1item1a, part1item1c, part2item7a: gate always True — skipped.
             # See §4.4.1.

          1. CANDIDATE NARROWING (ancestor context injection):
             candidate_labels = _build_candidate_labels(
                 ARCHETYPE_NAMES, seg.ancestors, _ANCESTOR_ARCHETYPE_PRIOR, top_n=3
             )
             # Falls back to full ARCHETYPE_NAMES when no ancestor prior matches.
             # See §4.4.3 and OQ-A18.

          2. HYPOTHESIS + THRESHOLD SELECTION (section-specific):
             template  = _HYPOTHESIS_TEMPLATES.get(section_id, _HYPOTHESIS_TEMPLATES["_default"])
             threshold = _SECTION_CONFIDENCE_THRESHOLDS.get(section_id,
                         _SECTION_CONFIDENCE_THRESHOLDS["_default"])
             # See §4.4.2 and §4.4.4.

          3. CLASSIFY:
             if section_id in use_llm_for_sections and llm_client is not None:
                 top_archetype, confidence = _classify_with_llm(
                     seg.text, section_id, seg.ancestors, llm_client
                 )
                 label_source = "llm_silver"    # OQ-A9 namespace
             else:
                 top_archetype, confidence = _classify_archetype(
                     seg.text, template, candidate_labels
                 )
                 label_source = "nli_zero_shot" if confidence ≥ threshold else "heuristic"
             # ⚠ OQ-A9: namespace must be locked before first annotation run.
             # "nli_zero_shot" = Stage A BART; "llm_silver" = LLM backend;
             # "heuristic" = keyword fallback; "classifier" = Stage B fine-tuned.

          4. label = ARCHETYPE_LABEL_MAP[top_archetype]

          5. sasb_topic = _crosswalk(top_archetype, sasb_industry)
                          or None if archetype_to_sasb.yaml absent

          6. yield {
               "index":        global_index,
               "text":         seg.text,
               "word_count":   seg.word_count,
               "char_count":   seg.char_count,
               "label":        label,
               "risk_label":   top_archetype,
               "sasb_topic":   sasb_topic,
               "sasb_industry": sasb_industry,
               "sic_code":     segmented.sic_code,
               "ticker":       segmented.ticker,
               "cik":          segmented.cik,
               "filing_date":  filing_date,
               "confidence":   round(confidence, 4),
               "label_source": label_source,
             }
```

### 4.4 Classifier Design (Stage A)

#### 4.4.1 Binary Risk Gate (Layer 1)

Before multi-class classification, a binary NLI pass filters segments that do not
contain risk-relevant content. Applied to `part1item1` and `part2item7` only —
sections with high non-risk content density. For `part1item1a`, `part1item1c`, and
`part2item7a`, all content is risk-relevant by definition; the gate is skipped.

```
Binary hypothesis:
  "This text describes a risk, vulnerability, dependency, or adverse event
   that could affect the company's operations or finances."
Threshold: 0.5  (recall-biased — false negatives lose valid risk signals permanently)
```

Segments below threshold are excluded from JSONL output entirely. They are **not**
labeled "other" and not emitted.

**Expected filter rates:**
- `part1item1`: ~40–60% of segments are non-risk (product descriptions, employee
  counts, facility lists)
- `part2item7`: ~20–30% (boilerplate disclaimers, transition sentences, table labels)

One additional BART inference call per segment. No new model required.

#### 4.4.2 Section-Specific Hypothesis Templates (Layer 2)

`part1item1` uses structural/factual language: "One customer accounted for 38% of
revenue." `part2item7` uses retrospective causal language: "Revenue declined due to
supply chain delays." Neither surface-matches "This text is about supply chain risk."
NLI entailment is weak on implicit framing.

Section-specific templates adapt the hypothesis to each section's linguistic register.
See `_HYPOTHESIS_TEMPLATES` constant in §4.2.

**Key design principle:** The `part1item1` template uses "dependency, concentration,
or structural exposure" to trigger entailment from factual language. The `part2item7`
template uses "impact of, or ongoing exposure to" to cover both retrospective
and prospective language.

#### 4.4.3 Ancestor Context Injection (Layer 3)

`ancestors[-1]` (immediate heading) is a strong prior over the likely archetype.
`_build_candidate_labels()` narrows the NLI candidate set to top 3 archetypes,
biased toward the ancestor-implied archetype. See `_ANCESTOR_ARCHETYPE_PRIOR` in §4.2.

**Two uses:**
1. **Candidate pruning:** Narrowing from 9 → 3 significantly increases per-archetype
   entailment scores (less score dilution across hypotheses).
2. **Tie-breaking:** When confidence < threshold, ancestor prior determines the
   fallback archetype rather than the keyword heuristic. `label_source = "ancestor_prior"`
   when this path fires.

**Example:** Segment from `part2item7` under `ancestors[-1] = "Liquidity and Capital
Resources"` → candidate_labels = `["financial", "macro", "market"]`. BART scores
against only these 3 hypotheses.

See OQ-A18 for the debate between candidate filtering vs. score-biasing.

#### 4.4.4 Section-Specific Confidence Thresholds (Layer 4)

Implicit-language sections require lower thresholds to avoid routing all segments to
the heuristic fallback. Below threshold → `label_source = "heuristic"`. See
`_SECTION_CONFIDENCE_THRESHOLDS` in §4.2.

**Critical:** Threshold values are initial estimates. Must be tuned after empirical
validation (50-segment labeled sample per section, see §8 SC-11 and OQ-A16).

#### 4.4.5 Pluggable LLM Backend (Layer 5)

BART zero-shot estimated Macro F1 ceiling on implicit risk language (`part1item1`,
`part2item7`): ~0.60–0.65 even with Layers 1–4. LLM-based classification (Claude
structured output) reaches estimated ~0.72–0.78 on these sections.

`_classify_archetype()` dispatches to `_classify_with_llm()` when:
- `llm_client is not None` (LLM backend configured)
- `section_id in use_llm_for_sections` (caller explicitly opts in)

LLM prompt template:
```
Classify the following text from a 10-K {section_name} into the most applicable
risk archetype, or "other" if no risk is implied.
Return JSON: {"archetype": str, "confidence": float}
Archetypes: {archetype_list}
Context: This text appears under the heading: "{ancestors[-1]}"
Text: {segment_text}
```

`label_source` values: LLM path → `"llm_silver"`; BART path → `"nli_zero_shot"`.
Output schema is identical — no downstream change.

**Cost:** ~$0.002–0.005 per segment (Claude Haiku). For ~100K `part1item1` +
`part2item7` segments after binary gate, estimated $200–500 total. Activate only
after binary gate reduces the candidate pool and BART baseline F1 is measured.
See OQ-A19.

**Recommendation:** Run BART with Layers 1–4 first. Activate LLM only if BART F1
< 0.65 on the 50-segment per-section holdout.

Two approaches for the `(risk_label, sasb_topic)` pair:

**Option A — Single inference + crosswalk lookup (preferred):**
```
classify(text, candidate_labels=ARCHETYPE_NAMES) → risk_label, confidence
sasb_topic = archetype_to_sasb_crosswalk[risk_label][sasb_industry]
```
Requires `archetype_to_sasb.yaml`. Faster (one model call per segment).
`sasb_topic` = null when the file is absent.

**Option B — Two inference calls (fallback when crosswalk absent):**
```
classify(text, ARCHETYPE_NAMES) → risk_label, confidence        # call 1
classify(text, sasb_topics_for_sic) → sasb_topic, sasb_conf    # call 2
```
Works without `archetype_to_sasb.yaml`. ~2× inference cost per segment.

**Implement Option A with Option B as fallback.** When `archetype_to_sasb.yaml` is
absent, either emit `null` for `sasb_topic` (simpler) or fall back to Option B
(richer output, higher cost). Configurable via `--sasb-inference-fallback` flag.

**Conflict — Archetype names vs. SASB topic names as NLI candidates (C-2, OQ-A10):**
Using `ARCHETYPE_NAMES` as NLI hypotheses ("This text is about cybersecurity") produces
weaker entailment signal than SASB topic names ("This text is about Data_Security").
The synthesis research silver labeling prompt (§4.1) and SASB architecture annotation
workflow (§5.1) both use industry-specific SASB topic names from
`TaxonomyManager.get_topics_for_sic()` as candidates — producing `sasb_topic` directly,
without requiring `archetype_to_sasb.yaml`. If SASB topic names are used as candidates,
the crosswalk is no longer needed for NLI inference; instead `archetype_to_sasb.yaml`
is consulted in reverse to derive `label` (int) from the winning SASB topic.
Trade-off: requires `sasb_sics_mapping.json` (G-15 blocker) to be present at
annotation time. If G-15 is not yet complete, Option A with archetype candidates is
the only available path. See OQ-A10.

**`sasb_source` provenance gap (C-9 extension, OQ-A15):**
Option A (`archetype → crosswalk → sasb_topic`) and Option B (`NLI → sasb_topic directly`)
produce `sasb_topic` values via different mechanisms. Records generated under different
option paths cannot be safely merged without a `sasb_source: "crosswalk" | "nli" | null`
field to distinguish them.

### 4.5 Heuristic Fallback (confidence < threshold)

When the classifier confidence < 0.7, fall back to keyword matching and set
`label_source = "heuristic"`. The existing `risk_taxonomy.yaml` is deprecated (Software
& IT only) and cannot be used here. A new cross-industry keyword map must be defined as
a module-level constant:

```python
_HEURISTIC_KEYWORDS: Dict[str, List[str]] = {
    "cybersecurity":  ["cybersecurity", "data breach", "ransomware", "gdpr", "unauthorized access"],
    "regulatory":     ["regulatory", "compliance", "sec", "litigation", "enforcement", "cftc"],
    "financial":      ["liquidity", "credit", "default", "interest rate", "refinancing", "debt"],
    "supply_chain":   ["supply chain", "supplier", "logistics", "procurement", "sourcing"],
    "market":         ["competition", "market share", "pricing", "demand", "commodity"],
    "esg":            ["environmental", "climate", "greenhouse", "esg", "emissions", "sustainability"],
    "macro":          ["inflation", "recession", "gdp", "federal reserve", "foreign exchange", "tariff"],
    "human_capital":  ["workforce", "talent", "retention", "labor", "union", "employee"],
    "other":          [],
}
```

Assign `label = 8` ("other") when no keywords match. This replaces the deprecated
`RiskClassifier` path entirely.

**`label_source` namespace — RESOLVED (C-3, OQ-A9) — ADR-015, 2026-03-11:**

The seven-value namespace is locked as module-level constants in `src/analysis/segment_annotator.py`.
`"classifier"` is reserved exclusively for Stage B fine-tuned inference and is **never written
by this module**. ADR-015 governs — no new value may be added without a superseding ADR.

| Constant | Value | Written by |
|---|---|---|
| `LABEL_SOURCE_NLI` | `"nli_zero_shot"` | BART Stage A, confidence ≥ section threshold |
| `LABEL_SOURCE_HEURISTIC` | `"heuristic"` | Keyword fallback, confidence < threshold, no ancestor match |
| `LABEL_SOURCE_ANCESTOR` | `"ancestor_prior"` | Confidence < threshold; ancestor heading matched prior map |
| `LABEL_SOURCE_LLM` | `"llm_silver"` | LLM backend (`llm_client` set and section in `use_llm_for_sections`) |
| `LABEL_SOURCE_CLASSIFIER` | `"classifier"` | **Not written here** — Stage B fine-tuned model only |
| `LABEL_SOURCE_HUMAN` | `"human"` | **Not written here** — IAA tool only |
| `LABEL_SOURCE_SYNTHETIC` | `"llm_synthetic"` | **Not written here** — synthesis script only |

Assignment logic in `annotate()`:
```python
if section_id in self._use_llm_for and self._llm_client is not None:
    label_source = LABEL_SOURCE_LLM
elif confidence >= section_threshold:
    label_source = LABEL_SOURCE_NLI
elif ancestor_matched:
    label_source = LABEL_SOURCE_ANCESTOR
else:
    label_source = LABEL_SOURCE_HEURISTIC
```

### 4.6 Ancestor-Grouped Pre-classification Merge

#### Motivation

The full corpus (run `20260303_160207`) has mean=68 words and median=48 words — 82%
of segments are ≤100 words. The segment strategy research
(`2026-02-23_18-30-00_segment_strategy_classifier_input.md` §2) identifies the 200–379
word range as the richest zone for classifier signal: long enough for disambiguating
context, short enough to stay under the DeBERTa 512-token ceiling.

The `ancestors` field (`RiskSegment.ancestors`, ADR-014, commit `51eb8b8`) gives each
segment an ordered heading breadcrumb (outermost → innermost). Segments sharing an
identical `ancestors` list came from the same logical node in the document tree, making
them the natural unit to merge without crossing topical boundaries.

This merge runs **in the annotator only**, not in the segmenter. It does not mutate
`*_segmented.json` files. The segmenter output is canonical; the merge is an
annotation-layer concern.

#### Relation to S2 (`_merge_short_segments`)

S2 (`src/preprocessing/segmenter.py:307–335`, commit `3ef72af`) is a greedy
forward-merge that fires **inside the segmenter** on sub-20-word segments before
the JSON is saved. It merges regardless of ancestors.

The ancestor-grouped merge here is a **separate, later-stage transform** with a
different objective: it targets the classifier input quality range (200–379 words)
for segments that are individually valid (≥20 words) but too short for reliable
classification. The two merges are not in conflict — S2 runs first (at segment
time), the ancestor merge runs second (at annotation time).

#### Algorithm

```
Input:  List[RiskSegment] — all chunks from one *_segmented.json, in order
Output: List[RiskSegment] — merged chunks, order preserved

Parameters:
    merge_lo = 200   # target lower bound (words); segments below this are candidates
    merge_hi = 379   # hard ceiling (Option A); never exceed this

Step 1 — Group consecutive segments by ancestors equality:
    A "run" = maximal consecutive sub-sequence with identical ancestors list.
    ancestors equality: list.__eq__ (order and values must match exactly).
    Segments with ancestors = [] form their own singleton runs.

Step 2 — Within each run, greedy forward accumulation:
    acc_text  = []
    acc_words = 0
    acc_chars = 0

    For each segment s in run:
        if acc_words == 0:
            # start new accumulator
            start_chunk_id    = s.chunk_id
            start_parent_sub  = s.parent_subsection
            start_ancestors   = s.ancestors

        if acc_words + s.word_count > merge_hi:
            # adding s would exceed ceiling — flush current accumulator
            if acc_words > 0:
                emit merged_segment(acc_text, acc_words, acc_chars,
                                    start_chunk_id, start_parent_sub, start_ancestors)
            # start fresh with s
            acc_text, acc_words, acc_chars = [s.text], s.word_count, s.char_count
            start_chunk_id, start_parent_sub, start_ancestors = s.chunk_id, ...
        else:
            acc_text.append(s.text)
            acc_words += s.word_count
            acc_chars += s.char_count

        if acc_words >= merge_lo:
            # target reached — emit and reset
            emit merged_segment(...)
            acc_text, acc_words, acc_chars = [], 0, 0

    # flush remaining accumulator (may be < merge_lo — emit as-is, best effort)
    if acc_words > 0:
        emit merged_segment(...)

Step 3 — Segments already ≥ merge_lo words:
    Pass through unchanged — no merge attempted.
    (A segment already at 250 words is passed directly to the classifier.)

Step 4 — Segments already > merge_hi words (670 residuals from Option A bypass):
    Pass through unchanged — no merge, no truncation.
    OQ-A4 governs whether to hard-filter these before classification.
```

#### Merged Segment Fields

| Field | Value |
|---|---|
| `chunk_id` | `"{first_id}+{last_id}"` e.g. `"1A_003+1A_007"` |
| `parent_subsection` | From first segment in merged group |
| `ancestors` | Shared ancestors list (identical by construction) |
| `text` | `" ".join(seg.text for seg in group)` |
| `word_count` | `sum(seg.word_count for seg in group)` |
| `char_count` | `sum(seg.char_count for seg in group)` |

#### Expected Distribution Impact

From corpus statistics (run `20260303_160207`, `part1item1a` only: 112,177 segments):

| Before merge | After merge (estimated) |
|---|---|
| mean=68 words | mean shifts toward 150–200 words |
| 82% ≤100 words | ≤100 bucket collapses into 101–379 range |
| p95=185 words | p95 rises; hard ceiling at 379 holds |
| 112,177 records | Fewer records (groups compress multiple → one) |

The compression ratio depends on how many consecutive ≤200-word segments share the same
ancestors. In a typical Item 1A risk factor subsection, 3–8 short sentences under a
single heading will merge into one 150–350 word record.

#### Failure Modes

| Scenario | Behaviour |
|---|---|
| Subsection has only 1 segment, word_count < 200 | Emitted as-is (best effort; no neighbour to merge with) |
| Two segments share ancestors but combined > 379 words | Flush first, emit second standalone |
| Segment has `ancestors = []` (cover-page node, ADR-014) | Singleton run; no merge |
| Boilerplate segment passes through (S5 not yet implemented) | Merged with real risk text — classification noise. S5 (Phase B) must filter before this merge for best results. |

#### Interaction with S5 (Boilerplate Filter)

The segment strategy research (§5 S5) describes expanding `_is_non_risk_content` to
filter auditor fragments, ToC navigation, and financial statement headers. S5 runs in
the segmenter; the ancestor merge runs in the annotator. If S5 is not yet deployed,
boilerplate segments will be merged with real risk text before classification, degrading
label quality. **Correct order of operations:**

```
Segmenter (S2 + S5 when deployed) → *_segmented.json → Annotator (ancestor merge) → JSONL
```

Until S5 is live, the `part2item7` selective path (subsection-level filter via
`ancestors[-1]`) is the primary guard against boilerplate contamination from MD&A.
`part2item7a` and `part1item1c` have lower dup rates (49.6% and 35.9% respectively
vs `part1item1a` at 53.5%) and do not require S5 to be safe to include.

**Revised section policy (OQ-6 reopened 2026-03-03):**

| Section | Include by default | Condition |
|---|---|---|
| `part1item1a` | ✅ Always | — |
| `part2item7a` | ✅ Always | — |
| `part1item1c` | ✅ Always | Post-2023 filings only; pre-2023 files will simply have no matching JSON |
| `part2item7` | ⚠️ Optional | Only with `part2item7_subsection_filter` set to high-signal subsection names |
| `part1item1` | ⚠️ Optional | Domain expert confirmed embedded risk signals (customer concentration, supplier dependencies, competitive exposures). Include with binary risk gate enabled (§4.4.1); gate filters ~40–60% non-risk segments. Requires `use_binary_gate=True` in `annotate_run_dir()` call. |
| `part2item8` | ❌ Never | Financial statement tables are non-classifiable for NLP. Footnotes contain risk signals (litigation contingencies, going concern, covenant violations) but cannot be separated from tables at current pipeline level. Revisit when pipeline can isolate footnotes. |
| `part1item1b` | ❌ Never | Typically a stub ("None" or "Not applicable"); negligible signal. |

---

## 5. Integration Points

### 5.1 Standalone Script (immediate)

`scripts/feature_engineering/segment_annotator_cli.py`:
```bash
# Default: includes part1item1a + part2item7a + part1item1c
python scripts/feature_engineering/segment_annotator_cli.py \
    --run-dir data/processed/20260303_160207_preprocessing_3bc89d7 \
    --output data/processed/annotation/labeled.jsonl \
    --confidence-threshold 0.7

# With selective part2item7 (high-signal MD&A subsections only)
python scripts/feature_engineering/segment_annotator_cli.py \
    --run-dir data/processed/20260303_160207_preprocessing_3bc89d7 \
    --output data/processed/annotation/labeled.jsonl \
    --include-sections part1item1a part2item7a part1item1c part2item7 \
    --part2item7-subsections "Liquidity and Capital Resources" "Critical Accounting Estimates"
```

Enables annotation corpus construction (G-16) without changing `process_batch()`.
The default section list implements the revised OQ-6 policy: `part1item1a` + `part2item7a`
+ `part1item1c`; `part1item1`, `part2item8`, `part1item1b` are hard-excluded.
`part2item7` is opt-in only, requires explicit `--part2item7-subsections` names.

### 5.2 `process_batch()` Integration (Stage A, PRD-002 §11 item 9)

`SegmentAnnotator` is instantiated once in `init_preprocessing_worker()`
(`src/utils/worker_pool.py`) via a new `init_annotator_worker()` / `get_worker_annotator()`
pair (same pattern as `init_preprocessing_worker` + `get_worker_segmenter`).

Called after `segment_extracted_section()` in `_process_filing_with_global_workers()`
(`src/preprocessing/pipeline.py:250`). Annotated records are streamed to a JSONL file
in the run directory.

**Regression risk:** Adding model loading to `init_preprocessing_worker` increases
worker startup time. The `forkserver` context (commit `3bc89d7`) already supports this
pattern. Stage A integration should be a separate story (US-029) from the standalone
CLI to isolate the risk.

### 5.3 Note on `SegmentedRisks.save_to_jsonl()`

PRD-002 §11 Group 3 item 10 proposes adding `save_to_jsonl()` to `SegmentedRisks`.
This is **wrong layering** — JSONL emission requires classifier output, and models must
not import classifiers. The correct boundary:

- `SegmentedRisks` → Pydantic model; no classifier dependency; may add `to_flat_records()`
  returning records with `null` for classifier fields
- `SegmentAnnotator.annotate()` → enriches flat records with classifier output
- `SegmentAnnotator.write_jsonl()` → writes JSONL

---

## 6. Files to Create / Modify

| File | Action | Notes |
|---|---|---|
| `src/analysis/segment_annotator.py` | **CREATE** | New `SegmentAnnotator` class |
| `src/analysis/taxonomies/archetype_to_sasb.yaml` | **CREATE** | G-15 / US-030; crosswalk enables Option A |
| `src/analysis/taxonomies/sasb_sics_mapping.json` | **CREATE** | G-15 / US-030 prerequisite |
| `scripts/feature_engineering/segment_annotator_cli.py` | **CREATE** | CLI wrapper |
| `src/utils/worker_pool.py` | **MODIFY (Stage A only)** | Add annotator worker init/getter |
| `src/preprocessing/pipeline.py` | **MODIFY (Stage A only)** | Wire annotator after `segment_extracted_section()` |

**Do NOT modify:**
- `auto_label.py` — superseded but retained; no code change
- `inference.py` — deprecated; new annotator replaces its role
- `RiskSegment` or `SegmentedRisks` model fields — no schema migration required

**Prerequisite patch (B-5):** `src/preprocessing/models/segmentation.py:load_from_json`
must be fixed to restore `filed_as_of_date` and `accession_number` before this module
is implemented. This is a one-line fix per field in the structured-schema branch
(lines 204–224). Add to the same story as the annotator or as a preceding blocker story.

---

## 7. Blockers

| Blocker | What it blocks | Resolution |
|---|---|---|
| `sasb_sics_mapping.json` absent (G-15) | `sasb_industry = null` for all records | US-030 |
| `archetype_to_sasb.yaml` absent (G-15) | `sasb_topic = null`; forces Option B or null | US-030; resolve OQ-T3 (macro default) first |
| Dispatch config contamination (OQ-PRD-1, OQ-6 reopened) | Annotation corpus quality | Default `section_include` = `[part1item1a, part2item7a, part1item1c]`; hard-exclude `[part1item1, part2item8, part1item1b]`; `part2item7` opt-in with subsection filter |
| Option A 0.11% over-380-word residual | Some segments may exceed DeBERTa 512 tokens | Investigate bypass path; annotate with warning or pre-filter |
| **B-5** ~~`filed_as_of_date` not restored in `segmentation.py:load_from_json` (lines 204–224) — `accession_number` has same omission~~ | ~~`filing_date = null` in all annotator output; every record is undated~~ | **RESOLVED 2026-03-11** — patched `load_from_json` to pass `filed_as_of_date=di.get('filed_as_of_date')` and `accession_number=di.get('accession_number')` to constructor; round-trip tests in `test_preprocessing_models_unit.py` |
| **B-6** No test set holdout mechanism | Phase 2 Macro F1 ≥ 0.72 gate is invalid — evaluating on NLI-labeled segments measures label-copying, not classification of real text | Implement filing-level `--hold-out-test` split (OQ-A11) before first corpus annotation run; holdout filings must never be passed to NLI |
| **B-7** IAA gate absent (QR-01) | Cohen's Kappa ≥ 0.80 requirement unenforceable; noisy BART labels enter training without quality verification | Define 50-sample-per-SASB-topic IAA output path (OQ-A12) |
| **B-8** ~~Char truncation in `inference.py:84–86` is not token-aware~~ | ~~Inputs >2,000 chars truncated regardless of actual token count; BART limit is 1,024 tokens, DeBERTa limit is 512 tokens — neither is 2,000 chars~~ | **RESOLVED 2026-03-11** — `_classify_archetype()` uses `self._tokenizer.encode()` for truncation; char limit removed |
| **B-9** ~~`label_source` namespace conflict with synthesis research~~ | ~~Merged corpus cannot distinguish zero-shot BART labels from fine-tuned labels from LLM silver labels~~ | **RESOLVED 2026-03-11** — 7-value locked namespace as module-level constants in `segment_annotator.py`; ADR-015 |

---

## 8. Success Criteria

| Criterion | Target |
|---|---|
| All 14 target fields present per record | `null` for SASB/classifier fields when deps absent |
| `index` monotonically increasing per output file | Verified by JSONL read-back |
| `filing_date` is ISO 8601 | `re.match(r'\d{4}-\d{2}-\d{2}', record["filing_date"])` |
| `label` in range 0–8 | `assert 0 <= record["label"] <= 8` |
| `label_source` ∈ `{"nli_zero_shot", "heuristic", "ancestor_prior", "llm_silver"}` for all BART-path output | All records: `assert record["label_source"] in {LABEL_SOURCE_NLI, LABEL_SOURCE_HEURISTIC, LABEL_SOURCE_ANCESTOR, LABEL_SOURCE_LLM}` — `"classifier"` never written by this module (ADR-015) |
| `datasets.load_dataset("json", data_files="output.jsonl")` succeeds without preprocessing | G-04 gate |
| SASB fields null-safe (no crash when taxonomy files absent) | `TaxonomyManager` already handles this |
| Default section include on run `20260303_160207`: input is 112,177 (`part1item1a`) + 39,516 (`part2item7a`) + 5,074 (`part1item1c`) = ~156,767 segments | Hard-excluded sections produce zero records; verify by grouping output by `section_identifier` |
| No merged segment exceeds 379 words | `assert record["word_count"] <= 379` for all records |
| Merged `chunk_id` format is `"{first}+{last}"` for multi-segment groups | Verified by JSONL read-back |
| `ancestors = []` segments are never merged with neighbours | Singleton run — emitted as-is |
| Merge does not cross `ancestors` boundaries | Verified: consecutive segments in each merged group have identical `ancestors` |
| `filed_as_of_date` survives `load_from_json` round-trip | `segmented.filed_as_of_date` non-null after load for any filing whose `document_info` contains `filed_as_of_date` |
| No merged segment exceeds 512 tokens (DeBERTa) | Verified via `tokenizer(text, return_length=True, truncation=False)["length"][0] <= 512` for all records in output JSONL |
| `label_source` values are from agreed namespace | All records have `label_source in {"nli_zero_shot", "classifier", "heuristic", "llm_silver", "llm_synthetic", "human", "ancestor_prior"}` |
| Test set holdout files produce zero NLI-labeled records | Holdout filing list written before `annotate_run_dir()` runs; holdout records are absent from `labeled.jsonl` entirely |
| SC-11: Binary gate recall ≥ 90% on `part1item1` and `part2item7` | 100-segment human-labeled holdout per section; `_is_risk_relevant()` must retain ≥ 90 of 100 genuine risk segments |
| SC-12: Section-specific templates improve Macro F1 vs default template | A/B comparison on 50-segment labeled sample per section; improvement ≥ 5 F1 points required to justify template complexity |
| SC-13: No segment emitted with mismatched `label_source` | All below-threshold records have `label_source in {"heuristic", "ancestor_prior"}`; all above-threshold BART records have `label_source = "nli_zero_shot"`; all LLM records have `label_source = "llm_silver"` |

---

## 9. Open Questions

| ID | Question | Blocker for |
|---|---|---|
| OQ-A1 | Single archetype inference + crosswalk (Option A), or two inference calls (Option B)? Crosswalk is faster but needs `archetype_to_sasb.yaml`. | Stage A implementation choice |
| OQ-A2 | Wire `SegmentAnnotator` into `process_batch()` in the same story as the standalone CLI, or a separate story? Coupling to `init_preprocessing_worker()` risks test regression. | US-029 scope |
| OQ-A3 | Where does `ARCHETYPE_LABEL_MAP` live? Options: (a) module constant in `segment_annotator.py`; (b) `src/config/models.py`; (c) taxonomy YAML. Option (a) is simplest for Phase 2; option (c) is more maintainable long-term. | Implementation |
| OQ-A4 | Should the 670 over-380-word residual segments be hard-filtered before JSONL emission, or annotated with a warning flag? The ancestor merge passes them through unchanged (§4.6 Step 4); the root bypass path must be found first. | `annotate()` preprocessing |
| OQ-A5 | Is `merge_lo=200` the right lower bound? The segment strategy research (§3 Tension 1) identifies 20–49 words as "ideal atomic range". Merging to 200 produces richer context but may create multi-topic segments from subsections with diverse risk statements. A lower `merge_lo=100` is safer; needs empirical validation. | `_merge_by_ancestors` tuning |
| OQ-A6 | Should singletons below `merge_lo` that have no ancestor-matching neighbours be filtered out (too short for reliable classification) or passed through as-is? Phase A showed these are 0.01% of corpus at sub-20 words; the broader < 100-word population is 82% and mostly genuine content. Pass through is safer. | `_merge_by_ancestors` edge case |
| OQ-A7 | What is the canonical allowlist of `ancestors[-1]` values for the `part2item7` subsection filter? Candidates: "Liquidity and Capital Resources", "Critical Accounting Estimates", "Market Risk". Needs a one-time audit of `ancestors` values across `part2item7` files in run `20260303_160207` to confirm exact strings before hardening the CLI default. | `--part2item7-subsections` CLI default |
| OQ-A8 | ~~`filed_as_of_date` not restored in `segmentation.py:load_from_json` lines 204–224.~~ **RESOLVED 2026-03-11** — patched `segmentation.py:load_from_json`; both `filed_as_of_date` and `accession_number` now passed to constructor. Round-trip tests added to `test_preprocessing_models_unit.py`. | ~~`annotate()` correctness, Blocker B-5~~ |
| OQ-A9 | ~~`label_source` namespace: use `"classifier"` / `"heuristic"` or adopt full synthesis research namespace?~~ **RESOLVED 2026-03-11** — adopted full 7-value namespace; locked as constants in `segment_annotator.py`; `"classifier"` reserved for Stage B only; documented in ADR-015. | ~~All JSONL output, Blocker B-9~~ |
| OQ-A10 | NLI candidate labels — use `ARCHETYPE_NAMES` (current §4.4 design) or industry-specific SASB topic names from `TaxonomyManager.get_topics_for_sic()` (synthesis research §4.1)? SASB topics as candidates: higher NLI precision, `sasb_topic` produced directly, crosswalk not needed for inference. Cost: requires `sasb_sics_mapping.json` (G-15) at annotation time; when G-15 is blocked, falls back to archetype candidates. Recommendation: use SASB topics as candidates when `sasb_sics_mapping.json` is present; archetype names otherwise. | `_classify_archetype()` interface, `archetype_to_sasb.yaml` necessity, C-2 |
| OQ-A11 | Test set holdout: implement as `--hold-out-test <fraction>` flag in `annotate_run_dir()` (filing-level split decided before NLI labeling begins), or as a separate pre-annotation script that writes a holdout filing list to disk? The holdout must be decided and locked before any NLI call runs. Recommendation: separate script — decouples the holdout decision from the annotator implementation and makes the holdout list auditable and version-controlled. | Phase 2 F1 gate validity, QR-01, Blocker B-6 |
| OQ-A12 | IAA sampling (QR-01): where does the Cohen's Kappa gate live? Options: (a) post-annotation script over `labeled.jsonl` that samples 50 records per SASB topic; (b) integrated into `annotate_run_dir()` as `--iaa-sample-output` flag; (c) separate `scripts/feature_engineering/iaa_sampler.py`. Recommendation: option (c) — keeps annotator stateless and IAA sampling independently runnable. Must output a reviewable TSV with `text`, `sasb_topic`, `label_source`, `confidence` columns for two annotators to label independently. | QR-01 compliance, training corpus sign-off, Blocker B-7 |
| OQ-A13 | Replace 2,000-char truncation in `inference.py` with token-count gate in `_classify_archetype()`. `facebook/bart-large-mnli` supports up to 1,024 tokens; DeBERTa supports 512. These are different limits for different models. `_classify_archetype()` must use the NLI model's tokenizer for truncation decisions, not DeBERTa's. The fine-tuning dataset must separately enforce DeBERTa's 512-token limit via the HuggingFace data quality checklist. | `_classify_archetype()` correctness, C-10 |
| OQ-A14 | Section priority without S5: start annotation corpus with `part2item7a` + `part1item1c` (dup rates 49.6% and 35.9%) before `part1item1a` (53.5% dup rate)? This inverts the current default section priority but produces a cleaner bootstrap corpus for IAA and initial fine-tuning. Recommendation: yes — build and validate the IAA pipeline on lower-dup sections first; add `part1item1a` after S5 ships. | Annotation corpus quality, Phase 2 training data plan |
| OQ-A15 | Add `sasb_source: "crosswalk" \| "nli" \| null` field to distinguish how `sasb_topic` was derived (Option A crosswalk vs Option B NLI vs absent taxonomy files)? Records generated under different option paths cannot be merged without this field. | Corpus reproducibility, `sasb_topic` provenance |
| OQ-A16 | Binary risk gate threshold: is 0.5 the right value for `part1item1` and `part2item7`? Lower threshold = higher recall (fewer valid risk signals dropped) but more noise passes. Empirically validate against a 100-segment human-labeled set per section before first annotation run. Recall ≥ 0.90 required (SC-11). | `_is_risk_relevant()` gate, §4.4.1 |
| OQ-A17 | Section-specific hypothesis template effectiveness: do the templates in `_HYPOTHESIS_TEMPLATES` materially improve Macro F1 on `part1item1` and `part2item7`? Requires 50-segment per-section labeled sample and A/B comparison against the default template. If improvement < 5 F1 points, simplify to one template for all sections. | `_HYPOTHESIS_TEMPLATES`, §4.4.2, SC-12 |
| OQ-A18 | ~~Ancestor candidate pruning: is top_n=3 the right narrowing depth?~~ **RESOLVED 2026-03-11** — option (c) chosen: all 9 archetype candidates always passed to NLI; ancestor prior adds a 0.05 score bonus to the matched archetype before threshold comparison. `_apply_ancestor_score_bonus()` implements this. No hard filter; correct label cannot be excluded by a wrong prior. | ~~`_build_candidate_labels()`, §4.4.3~~ |
| OQ-A19 | LLM backend activation timing: activate for `part1item1` / `part2item7` in the initial annotation run, or only after BART baseline F1 is measured on those sections? Activating LLM before baseline obscures whether Layers 1–4 alone are sufficient. Recommendation: run BART + Layers 1–4 first; measure F1 on 50-segment per-section holdout; activate LLM backend only if BART F1 < 0.65 on `part1item1` or `part2item7`. | `use_llm_for_sections`, §4.4.5, cost estimate |

---

## 10. Cross-Research Conflict Register

Conflicts identified by cross-referencing against:
- `2026-02-19_14-22-00_huggingface_classifier_input_formats.md`
- `2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md`
- `2026-02-19_14-59-17_llm_synthetic_data_per_industry_models.md`
- `src/preprocessing/models/segmentation.py` (live code, lines 173–243)
- `src/analysis/inference.py` (live code, lines 82–86)

| ID | Conflict | Severity | Location in This Doc | Resolves via |
|---|---|---|---|---|
| C-1 | ~~`filed_as_of_date` not restored by `segmentation.py:load_from_json` (lines 204–224).~~ **RESOLVED 2026-03-11** — B-5 patch applied; `filed_as_of_date` and `accession_number` both restored by `load_from_json`. | ~~**Critical**~~ **CLOSED** | §2.2, §7 B-5 | OQ-A8 RESOLVED |
| C-2 | NLI candidate labels: annotator uses abstract `ARCHETYPE_NAMES` as NLI hypotheses. Synthesis research (§4.1) and SASB architecture annotation workflow (§5.1) both use industry-specific SASB topic names — more discriminative hypotheses that produce `sasb_topic` directly and eliminate the `archetype_to_sasb.yaml` crosswalk dependency. | High | §4.4 | OQ-A10 |
| C-3 | ~~`label_source` namespace mismatch: annotator collapses all model paths into `"classifier"`.~~ **RESOLVED 2026-03-11** — 7-value locked namespace; `"classifier"` reserved Stage B only; all paths distinguished. ADR-015 governs. | ~~High~~ **CLOSED** | §4.3 step 3, §4.5 | OQ-A9 RESOLVED |
| C-4 | Silver labeling model: annotator retains `facebook/bart-large-mnli`. Synthesis research (§1) explicitly proposes replacing it with Claude/GPT-4o. BART zero-shot Macro F1 on SEC domain text is estimated ~0.55–0.60, below the frontier LLM zero-shot range (0.63–0.69) from the SASB architecture comparison table. Fine-tuning DeBERTa on BART-labeled records sets a lower accuracy ceiling. | Medium | §3.1 | OQ-A9 resolved |
| C-5 | 379-word ceiling ≠ 512-token ceiling. DeBERTa-v3 SentencePiece produces ~1.3–1.5 tokens/word on SEC prose. A 379-word merged segment can tokenize to ~490–570 tokens; upper bound exceeds 512. HuggingFace formats research (§10 data quality checklist) mandates explicit per-segment token count verification. The `assert word_count <= 379` success criterion does not catch this. | Medium | §4.6 Step 4, §7 B-5, §8 | OQ-A13 |
| C-6 | No test set holdout. Synthesis research (§3 "TEST SET") requires 10–15% of real EDGAR segments held out at filing level before any NLI labeling. Annotator has no holdout mechanism. A test split drawn from `labeled.jsonl` contains NLI-labeled records; Phase 2 Macro F1 ≥ 0.72 gate measures label-copying from BART, not real classification quality. | High | §5.1 CLI design, §8 | OQ-A11 |
| C-7 | IAA gate absent. QR-01 (Cohen's Kappa ≥ 0.80, 50 examples per SASB topic) required by HuggingFace formats research (§10 label quality checklist) and synthesis research (§3 Layer 3) before training begins. Annotator success criteria do not include a Kappa check or a sampling output path. | Medium | §8 | OQ-A12 |
| C-8 | `word_count` sum in merge may not match joined text word count. The accumulator uses `sum(seg.word_count)` but `word_count` was computed at construction time (`len(text.split())`). After `" ".join(seg.text for seg in group)`, segments with trailing/leading whitespace or unicode non-breaking spaces produce a post-join word count that differs from the sum by ±2–5 words. The `merge_hi` boundary check fires on the sum. | Low | §4.6 Algorithm Step 2 | Before `merge_hi` boundary hardened |
| C-9 | `index` non-unique in combined JSONL. Counter resets per `SegmentedRisks` (per filing), so the merged 156K-record `labeled.jsonl` contains ~309 sequences of 0–N. Synthesis research dedup (SHA-256 of text) is unaffected, but `index` cannot serve as a record identifier for downstream tools. | Low | §2.2 `index` row, §8 | Before downstream tools use `index` as key |
| C-10 | ~~Char truncation in `inference.py:84–86` uses 2,000-char limit.~~ **RESOLVED 2026-03-11** — `_classify_archetype()` in `segment_annotator.py` uses `self._tokenizer.encode()` for truncation; char limit not used. Fine-tuning pipeline enforcement (DeBERTa 512 tokens) remains a separate concern. | ~~Medium~~ **CLOSED** | §3.1, §4.4 | OQ-A13 RESOLVED |
| C-11 | Domain expert challenge to "81.5% noise" framing in gap analysis (2026-03-11). Gap analysis (YoY research doc §2.3) classified `part1item1`, `part2item7`, and `part2item8` as noise. Domain expert correctly identified that risk signals appear throughout the 10-K: `part1item1` contains structural risks (customer concentration, supplier dependency, competitive exposure); `part2item7` contains materialized and liquidity risks and is arguably the richest risk source for trailing signals; `part2item8` footnotes contain contingent liabilities, going concern notes, and covenant violations. The ✅/❌ section classification was based on structural section identity, not semantic content. **Resolution:** `part1item1` promoted to "optional with binary risk gate" in the revised section policy (§4.6). `part2item8` remains excluded only because footnotes cannot be separated from financial tables at current pipeline level. `part2item7` policy unchanged (opt-in with subsection filter). The five-layer classifier strategy (§4.4.1–§4.4.5) directly addresses classification quality on non-1A sections. | Medium | §4.4, §4.6 revised section policy | OQ-A16–OQ-A19 |
