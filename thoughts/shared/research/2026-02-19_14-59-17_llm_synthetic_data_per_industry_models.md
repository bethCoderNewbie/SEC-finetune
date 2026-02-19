---
title: "LLM Synthetic Data Generation for Per-Industry SASB Classifiers (Approach B)"
date: 2026-02-19
time: "14:59:17"
author: bethCoderNewbie
git_sha: 2df33475511680276791484900fab90c793df5bf
branch: main
related_prd: PRD-002_SEC_Finetune_Pipeline_v2.md
related_research:
  - 2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md
  - 2026-02-19_14-22-00_huggingface_classifier_input_formats.md
status: FINAL
---

# LLM Synthetic Data Generation for Per-Industry SASB Classifiers

The "High Training Complexity" barrier in Approach B (per-industry SASB models) is that each
industry model needs ≥ 500 labeled examples per SASB topic, and a 10-K corpus may have only
a handful of filings per SIC group initially. LLMs can bridge this gap — but only if used
correctly. Used naïvely, they produce model collapse and eval contamination.

---

## 1. What Already Exists in This Codebase

`scripts/feature_engineering/auto_label.py` is already the zero-shot teacher pipeline:

- Line 157: `taxonomy_manager = TaxonomyManager()` — retrieves industry-specific SASB topics
- Line 200–207: `get_topics_for_sic(sic_code)` → `candidate_labels` list — already SASB-aware
- Line 174: runs `facebook/bart-large-mnli` via HuggingFace `zero-shot-classification`
- Line 189: writes output to `sasb_labeled_risks.jsonl` — same schema as training target

**The structural work is done.** The question is whether to replace `facebook/bart-large-mnli`
with Claude API calls, and whether to add a fully-synthetic generation pass for thin industries.

---

## 2. Two Distinct Synthesis Strategies

### Strategy A — Real text + LLM labels ("Silver Labels")

Take real `RiskSegment.text` objects from the existing EDGAR pipeline and pass them to
an LLM with the company's SASB topics as candidate labels. The LLM assigns a label; the
human or a second LLM verifies.

```
Real 10-K segment (authentic SEC language)
    + Company SIC code → SASB industry → candidate topic list
    │
    ▼  Claude API (Anthropic)  or  GPT-4o
    │
Assigned SASB topic + confidence + one-sentence rationale
    │  (filtered at confidence ≥ 0.80)
    ▼
Silver-labeled JSONL record:
  {"text": "<real 10-K text>", "label": 3, "sasb_topic": "Data_Security",
   "label_source": "llm_silver", "llm_confidence": 0.93, "sic_code": "7372"}
```

**Properties:**
- Text distribution = real EDGAR language ✅
- Labels = LLM-assigned (not ground truth) ⚠️ — need IAA verification on a sample
- Throughput = high (batch API calls)
- Coverage = limited by how many real filings you have per industry

### Strategy B — LLM-generated text + LLM labels ("Fully Synthetic")

Prompt the LLM to write N risk disclosure sentences in the style of a 10-K Item 1A,
for a specific SASB topic in a specific industry. The label is known by construction.

```
Prompt:
  "You are a corporate attorney drafting SEC 10-K Item 1A risk disclosures for
   a Commercial Bank. Write 10 distinct, realistic risk factor sentences that
   would be labeled 'Systemic_Risk_Management' under the SASB framework.
   Use the formal, hedged language of an actual 10-K filing.
   Base your style on this example: [real 10-K excerpt]"

Output:
  {"text": "Adverse macroeconomic conditions could cause credit losses to exceed...",
   "label": 2, "sasb_topic": "Systemic_Risk_Management",
   "label_source": "llm_synthetic", "sasb_industry": "Commercial Banks"}
```

**Properties:**
- Text distribution = LLM-mimicking SEC language ⚠️ — distribution shift risk
- Labels = known by construction ✅ (prompt specifies the class)
- Throughput = very high
- Coverage = unlimited — can generate any volume for any industry/topic pair
- **Critical risk:** model trained entirely on synthetic text learns LLM artifacts, not real disclosures

---

## 3. The Hybrid Pipeline (Best Practice)

Neither strategy alone is sufficient. The correct approach is a layered pipeline:

```
LAYER 1 — Real + Silver labels (Strategy A)
  Real EDGAR corpus → existing auto_label.py pipeline (upgraded to LLM)
  Filter: keep segments with llm_confidence ≥ 0.80
  Deduplicate by SHA-256 of text
  Target: ≥ 300 examples per SASB topic from real text

LAYER 2 — Gap fill with synthetic (Strategy B)
  For each (industry, sasb_topic) pair where real count < 300:
    Generate (500 - real_count) synthetic examples
  Style grounding: include 3–5 real EDGAR examples in the few-shot prompt
  Deduplicate against Layer 1 to prevent contamination

LAYER 3 — Human verification (IAA gate)
  Sample 50 examples per SASB topic from Layer 1 + Layer 2 combined
  Two domain experts label independently
  Compute Cohen's Kappa; require ≥ 0.80 before training begins (QR-01)
  Correct any mismatches; propagate corrections to full dataset

TEST SET — Real text only (never LLM-labeled)
  Hold out 10–15% of real EDGAR segments BEFORE Layer 1 runs
  Human-labeled or verified-only labels
  Synthetic examples NEVER appear in test set
```

**Why the test set must be real and human-labeled:**
If the LLM generates both training and test data, the eval measures "how well the model
learned LLM style" not "how well the model classifies real 10-K disclosures". The Phase 2
gate (Macro F1 ≥ 0.72) is meaningless unless the test set is clean.

---

## 4. Prompt Design — The Critical Variable

Label quality is entirely determined by prompt quality. The LLM must receive:

1. **Role context** — the specific SASB industry
2. **Task definition** — the exact topic list with descriptions (from `sasb_sics_mapping.json`)
3. **Exclusive choice constraint** — force single best label, not multi-label
4. **Rationale request** — a one-sentence explanation that can be reviewed for errors
5. **Confidence request** — calibrated 0.0–1.0 self-assessment
6. **Style examples** (for Strategy B) — 3–5 real 10-K excerpts to anchor language

### 4.1 Silver labeling prompt (Strategy A)

```python
SILVER_LABEL_PROMPT = """You are an expert in SEC 10-K filings and the SASB (Sustainability
Accounting Standards Board) framework.

Company industry: {sasb_industry}
SASB material topics for this industry:
{topic_list}

Classify the following 10-K risk disclosure sentence into exactly ONE of the topics above.
If it does not clearly fit any topic, classify it as "Other_General_Risk".

Risk disclosure:
"{segment_text}"

Respond in JSON only:
{{
  "sasb_topic": "<topic name exactly as listed>",
  "confidence": <float 0.0-1.0>,
  "rationale": "<one sentence explaining why>"
}}"""

def format_topic_list(topics: dict) -> str:
    return "\n".join(
        f"- {name}: {description}"
        for name, description in topics.items()
    )
```

### 4.2 Synthetic generation prompt (Strategy B)

```python
SYNTHETIC_GEN_PROMPT = """You are a corporate attorney drafting Item 1A (Risk Factors)
disclosures for a 10-K filing. The company operates in the {sasb_industry} industry.

Write exactly {n_examples} distinct, realistic risk factor sentences that belong to the
SASB topic: "{sasb_topic}"

Definition: {topic_description}

Rules:
- Each sentence must be self-contained (50–200 words)
- Use formal SEC filing language: hedged, specific, and material
- Do NOT copy the example below — paraphrase the underlying risk
- Each sentence must be meaningfully distinct from the others
- Do NOT use generic language that could apply to any industry

Style example from a real 10-K:
"{style_anchor}"

Respond as a JSON array of strings (the sentences only, no labels or metadata):
["...", "...", ...]"""
```

---

## 5. Quality Filters Before Training

Every LLM-labeled or LLM-generated record must pass these filters before entering training:

### 5.1 Schema validation
```python
def validate_record(record: dict) -> bool:
    if not record.get("text") or not record["text"].strip():
        return False
    if record.get("label") not in range(9):          # archetype integer 0-8
        return False
    if not record.get("sasb_topic"):
        return False
    if record.get("llm_confidence", 1.0) < 0.80:     # silver threshold
        return False
    return True
```

### 5.2 Text quality
```python
import hashlib

def text_quality_checks(text: str, min_words: int = 20, max_words: int = 400) -> bool:
    words = text.split()
    if len(words) < min_words or len(words) > max_words:
        return False
    if text.strip() != text.strip().encode("utf-8").decode("utf-8"):
        return False  # encoding artifact
    return True

# Dedup across all records
seen_hashes = set()
def is_duplicate(text: str) -> bool:
    h = hashlib.sha256(text.encode()).hexdigest()
    if h in seen_hashes:
        return True
    seen_hashes.add(h)
    return False
```

### 5.3 Per-industry class balance check
```python
from collections import Counter

def check_balance(records: list, industry: str) -> dict:
    topic_counts = Counter(r["sasb_topic"] for r in records if r["sasb_industry"] == industry)
    min_count = min(topic_counts.values())
    max_count = max(topic_counts.values())
    imbalance_ratio = max_count / min_count if min_count > 0 else float("inf")
    return {
        "industry": industry,
        "topic_counts": dict(topic_counts),
        "imbalance_ratio": imbalance_ratio,
        "needs_synthetic_fill": [t for t, c in topic_counts.items() if c < 500],
    }
```

---

## 6. Output Schema — Training Records

Every record carries both label layers plus provenance:

```jsonl
{
  "text": "Adverse regulatory changes could restrict our ability to collect and process...",
  "label": 1,
  "sasb_topic": "Data_Privacy_&_Freedom_of_Expression",
  "sasb_industry": "Software & IT Services",
  "sic_code": "7372",
  "ticker": "MSFT",
  "filing_date": "2023-10-15",
  "label_source": "llm_silver",
  "llm_confidence": 0.91,
  "human_verified": false
}
```

```jsonl
{
  "text": "A significant increase in non-performing loans could impair our capital ratios...",
  "label": 2,
  "sasb_topic": "Systemic_Risk_Management",
  "sasb_industry": "Commercial Banks",
  "sic_code": "6020",
  "ticker": null,
  "filing_date": null,
  "label_source": "llm_synthetic",
  "llm_confidence": null,
  "human_verified": false
}
```

`label_source` values: `"llm_silver"` | `"llm_synthetic"` | `"human"` | `"heuristic"`

---

## 7. Per-Industry Model Training

Once the training data exists, each industry model is a standard DeBERTa fine-tune —
but with fewer classes and industry-specific labels:

```python
# Software & IT Services model: 6 classes (SASB topics) + "other"
INDUSTRY_LABEL_MAP = {
    "Software & IT Services": [
        "Data_Security",
        "Data_Privacy_&_Freedom_of_Expression",
        "Intellectual_Property_Protection_&_Competitive_Behavior",
        "Management_of_the_Legal_&_Regulatory_Environment",
        "Recruiting_&_Managing_a_Skilled_Workforce",
        "Environmental_Footprint_of_Hardware_Infrastructure",
        "Other_General_Risk",
    ],
    "Commercial Banks": [
        "Systemic_Risk_Management",
        "Data_Security",
        "Financial_Inclusion_&_Capacity_Building",
        "Incorporation_of_ESG_Factors_in_Credit_Analysis",
        "Business_Ethics",
        "Management_of_the_Legal_&_Regulatory_Environment",
        "Other_General_Risk",
    ],
}

# Per-industry training: filter records, then standard HuggingFace Trainer loop
industry = "Software & IT Services"
industry_records = [r for r in all_records if r["sasb_industry"] == industry]
label_names = INDUSTRY_LABEL_MAP[industry]
label2id    = {n: i for i, n in enumerate(label_names)}

# Re-map sasb_topic to integer for this industry
for r in industry_records:
    r["label"] = label2id.get(r["sasb_topic"], label2id["Other_General_Risk"])
```

**Inference routing** (replaces the single 9-class archetype model):

```
Segment arrives
    │  sic_code already in SegmentedRisks
    ▼  TaxonomyManager.get_industry_for_sic(sic_code)
Industry = "Software & IT Services"
    ▼  load model: checkpoints/sec-risk-classifier-software-it/
SASB topic prediction (direct — no archetype crosswalk needed)
    ▼  output: {"sasb_topic": "Data_Security", "confidence": 0.94}
```

Under Approach B, `archetype_to_sasb.yaml` is no longer needed — the model outputs
SASB labels directly. The archetype crosswalk is only needed for the Approach C hybrid.

---

## 8. Risks and Mitigations

| Risk | Severity | Mitigation |
|:-----|:---------|:-----------|
| **Model collapse** — student learns LLM style, not real SEC language | High | Cap synthetic at 40% of training data; test set must be real EDGAR text only |
| **Eval contamination** — LLM labels test segments, inflating measured F1 | Critical | Hold out test split BEFORE any LLM labeling; never run silver labeling on test set |
| **LLM label noise** — LLM misclassifies ambiguous segments | Medium | Confidence threshold ≥ 0.80; human IAA check on sampled 50 per topic |
| **Distribution shift** — synthetic text too clean / formulaic | Medium | Few-shot style anchoring with real 10-K excerpts in generation prompt |
| **Topic confusion at industry boundary** — "Data_Security" exists in both Software and Banks | Low | Per-industry models eliminate cross-industry label collision entirely |
| **Cost** — Claude API calls for 10K segments × N industries | Medium | Silver labeling is cheap (classification only); generate synthetic only for thin topics |
| **Data contamination across industries** — a segment from a bank filing appears in a tech model's training set | Medium | Filter strictly by `sasb_industry`; do not mix cross-industry in per-industry models |

---

## 9. Comparison: Upgraded Approach B vs. Current Approach C

| Dimension | Approach C (Archetype + crosswalk) | Approach B (Per-industry, LLM synthesis) |
|:----------|:-----------------------------------|:-----------------------------------------|
| Models to train | 1 (9 archetypes) | 1 per industry (e.g., 5–10 initially) |
| Output label | Generic archetype ("cybersecurity") | Exact SASB topic ("Data_Security") |
| SASB fidelity | Medium — crosswalk adds SASB but not precise | High — model directly outputs SASB topic |
| Training data needed | ~4,500 examples (500 × 9 archetypes) | ~3,500 per industry (500 × ~7 topics) |
| LLM synthesis feasibility | Yes — can synthesize archetypes | Yes — **easier**, because topics are industry-specific and less ambiguous |
| Inference complexity | 1 model + crosswalk lookup | Route to industry model → direct output |
| Evaluation | Macro F1 across 9 classes | Macro F1 per industry (separate eval per model) |
| Recommended for | Phase 2 (faster to ship) | Phase 3 (higher fidelity, more infra) |

**Recommendation: Start with Approach C (one 9-class model) for Phase 2, using LLM silver
labeling to accelerate annotation. Build Approach B per-industry models in Phase 3 using the
same synthesis pipeline — the data schema supports both without changes.**

The `label_source` field in the output records is the migration path: Phase 2 filters
for `archetype` labels; Phase 3 filters for `sasb_topic` labels per industry.

---

## 10. New Files Required

| File | Purpose |
|:-----|:--------|
| `scripts/feature_engineering/synthesize_training_data.py` | LLM silver labeling + synthetic generation pipeline |
| `configs/prompts/silver_label_prompt.txt` | Strategy A prompt template |
| `configs/prompts/synthetic_gen_prompt.txt` | Strategy B prompt template |
| `configs/synthesis.yaml` | Per-industry target counts, confidence thresholds, model choice |
| `data/processed/annotation/{industry_slug}/train.jsonl` | Per-industry training splits |
| `data/processed/annotation/{industry_slug}/validation.jsonl` | Per-industry validation splits |
| `data/processed/annotation/test.jsonl` | Shared test set — real EDGAR text + human labels ONLY |

**Existing file to upgrade (not replace):**
`scripts/feature_engineering/auto_label.py` — currently uses `bart-large-mnli` zero-shot.
Add a `--backend [nli|claude|openai]` flag to swap in the LLM silver labeling path.
The existing SIC → industry → candidate labels flow (lines 200–207) is correct and reusable.

---

## 11. Open Questions

| # | Question | Blocks |
|:--|:---------|:-------|
| OQ-S1 | Which LLM backend for silver labeling: Claude (Anthropic API), GPT-4o, or local Llama-3? Cost vs. quality trade-off to be measured on 100-segment pilot. | `synthesize_training_data.py` design |
| OQ-S2 | What silver confidence threshold: 0.80 or 0.85? Lower = more data, more noise. Run calibration study on 200 human-reviewed examples. | Training data quality |
| OQ-S3 | What is the maximum synthetic fraction before model collapse? Literature suggests 30–50%. Empirically validate on held-out test. | Training recipe |
| OQ-S4 | Should `auto_label.py` be refactored into `synthesize_training_data.py`, or kept separate for the zero-shot teacher workflow? | Code organization |
| OQ-S5 | Per-industry eval: report per-industry Macro F1 separately, or a weighted average across industries weighted by EDGAR filing volume? | PRD-004 KPI definition |
