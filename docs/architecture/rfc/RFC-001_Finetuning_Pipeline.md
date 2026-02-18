---
id: RFC-001
title: Fine-tuning Pipeline Architecture
status: DRAFT
author: beth88.career@gmail.com
created: 2026-02-18
last_updated: 2026-02-18
superseded_by: null
---

# RFC-001: Fine-tuning Pipeline Architecture

## Status

**DRAFT** — open for review. Once a decision is reached, write an ADR that records the choice and
references this document as context.

---

## Context

The preprocessing pipeline (`src/preprocessing/pipeline.py`) produces `SegmentedRisks` objects saved
as per-filing JSON files (`{stem}_segmented.json`). The next stage — labeling segments and producing
training data for fine-tuning — is not yet integrated into the batch pipeline.

`src/analysis/inference.py` contains a working `RiskClassifier` (zero-shot via
`facebook/bart-large-mnli`, `inference.py:15`) that can classify individual `RiskSegment` text
strings. It is currently only callable as a standalone module via `classify_risk_segments()`
(`inference.py:174`). It is not invoked by `pipeline.py:process_batch()` (`pipeline.py:559`).

Four design questions must be settled before the fine-tuning pipeline can be built:

1. **Integration pattern** — Where and how does classification get called?
2. **Output format** — JSONL or JSON for the training dataset?
3. **Model selection** — Zero-shot auto-labeling vs. pre-labeled fine-tuning?
4. **Truncation strategy** — Current 2000-char hard cut (`inference.py:84`) vs. proper token-aware
   handling for segments that exceed the model's 512-token limit.

---

## Question 1: Integration Pattern

### Option A — Post-processing stage in `process_batch()`

Extend `pipeline.py:process_batch()` to call `classify_risk_segments()` after segmentation completes.
Classification results are merged into the `SegmentedRisks` object before it is saved.

```python
# pipeline.py — process_batch() addition
from src.analysis.inference import classify_risk_segments
segmented = process_filing(...)
labeled = classify_risk_segments(segmented.segments)
segmented.label_segments(labeled)
result.save_to_json(output_path)
```

**Pros:** Single output artifact; one pass per filing; output already stamped under a run dir (ADR-007).
**Cons:** Adds GPU/CPU pressure to the batch worker pool (ADR-003); slows segmentation runs when
labeling is not needed.

### Option B — Separate labeling pipeline

Add a new entry point `src/analysis/label_pipeline.py` that reads the `_segmented.json` files
produced by the preprocessing pipeline and writes `_labeled.jsonl` training files.

**Pros:** Segmentation and labeling are independently re-runnable; no change to `process_batch()`.
**Cons:** Two pipeline runs required; output dirs diverge (must track which segmented run fed which
labeling run).

### Option C — Lazy labeling via a flag

Extend `process_batch()` with a `--label` flag. When set, calls the classifier after segmentation.
When unset, behaves as today.

**Pros:** Single codebase; opt-in overhead.
**Cons:** Flag proliferation; test matrix doubles.

**Recommendation: Option B.** Keeps segmentation fast and independently testable. The labeling
pipeline can be invoked against any historical segmented run dir. Aligns with stamped run dir
provenance (ADR-007): the labeling run dir records which segmented run it consumed.

---

## Question 2: Output Format

Current pipeline saves JSON: `{stem}_segmented.json` (`pipeline.py:249`).

Fine-tuning frameworks (Hugging Face `Trainer`, OpenAI fine-tuning API, llama.cpp) all consume
**JSONL** (one JSON object per line, one record per training example).

### Option A — JSONL directly

Each classified segment becomes one line:
```jsonl
{"text": "...", "label": "Regulatory Risk", "score": 0.91, "filing": "0001234_10-K"}
```

**Pros:** Zero conversion step; streaming-compatible; standard fine-tuning format.
**Cons:** No single-file summary per filing.

### Option B — JSON per filing, convert to JSONL at dataset build time

Keep per-filing JSON. Add a `build_dataset.py` script that flattens all filings into one JSONL file.

**Pros:** Per-filing JSON useful for inspection and debugging.
**Cons:** Extra build step; two representations of the same data.

### Option C — Both

Write `_labeled.json` (per-filing) and append to a `dataset.jsonl` (cumulative).

**Pros:** Best of both.
**Cons:** Cumulative file makes reruns non-idempotent; requires deduplication logic.

**Recommendation: Option B.** Per-filing JSON is more inspectable and debuggable during development.
A separate `build_dataset.py` that produces `dataset.jsonl` is the cleanest separation of concerns.
The cumulative JSONL in Option C creates a stateful artifact that conflicts with stamped run dirs.

---

## Question 3: Model Selection

Two models are configured (`configs/models.yaml:37-40`):

| Model | Role in config | Approach |
|-------|---------------|----------|
| `facebook/bart-large-mnli` | `zero_shot_model` | Zero-shot classification; no training data required |
| `ProsusAI/finbert` | `default_model` | Sentiment-tuned BERT; requires fine-tuning for risk taxonomy |

### Option A — Zero-shot labeling with `bart-large-mnli`, then fine-tune `finbert`

Use `bart-large-mnli` to auto-label the dataset. Use the auto-labeled dataset to fine-tune
`ProsusAI/finbert` on the project's 12-category risk taxonomy (defined in
`configs/risk_taxonomy.yaml`). The fine-tuned finbert replaces bart at inference time.

**Pros:** No manual labeling required; finbert is smaller and faster at inference.
**Cons:** Training data quality depends on bart accuracy. Noisy labels degrade fine-tuned model.
PRD-003 exists specifically to address this (data quality remediation before fine-tuning).

### Option B — Manual labeling, fine-tune `finbert` directly

Label a representative sample manually. Fine-tune finbert on clean labels.

**Pros:** Highest training data quality.
**Cons:** Labeling 1000+ segments manually is prohibitive for a single contributor.

### Option C — Zero-shot `bart-large-mnli` as production model (no fine-tuning)

Keep the zero-shot approach. Fine-tuning is out of scope.

**Pros:** No training infrastructure needed.
**Cons:** Zero-shot accuracy on domain-specific SEC taxonomy is unknown; PRD-001 KPIs require
classification F1 > 0.80 which zero-shot may not achieve.

**Recommendation: Option A.** Consistent with PRD-003 (remediate data quality, then fine-tune).
The auto-label → quality gate → fine-tune loop is the stated project strategy.

---

## Question 4: Truncation Strategy

`RiskClassifier.classify_segment()` currently truncates at **2000 characters** (`inference.py:84`):

```python
max_chars = 2000
if len(text) > max_chars:
    text = text[:max_chars] + "..."
```

`facebook/bart-large-mnli` (and all BERT-family models) have a **512-token hard limit**. A character
limit is not equivalent to a token limit (typical ratio: ~4 chars/token, so 2000 chars ≈ 500 tokens,
which is close but not exact and varies by text).

### Option A — Keep character truncation, document the approximation

Document that 2000 chars ≈ 500 tokens for SEC prose. Accept the approximation.

**Pros:** No tokenizer dependency at classification time.
**Cons:** Long hyphenated legal terms can push the ratio; occasional silent truncation at token boundary.

### Option B — Tokenizer-aware truncation

Load the model's tokenizer and truncate to 512 tokens exactly:

```python
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(self.model_name)
inputs = tokenizer(text, max_length=512, truncation=True, return_tensors="pt")
text = tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=True)
```

**Pros:** Exact; no silent truncation at wrong boundary.
**Cons:** Adds tokenizer load time; tokenizer and pipeline model must stay in sync.

### Option C — Sliding window over long segments

For segments > 512 tokens, classify each 512-token window and aggregate scores (e.g., max or mean).

**Pros:** No information loss; useful for multi-topic risk disclosures.
**Cons:** Significant complexity; multiply-classifying one segment produces multiple training records
(label assignment becomes ambiguous).

**Recommendation: Option B** for correctness. The tokenizer is already a transitive dependency
(transformers is installed). Adding `AutoTokenizer` at `RiskClassifier.__init__` is minimal overhead.
Option C is out of scope until the base pipeline is validated.

---

## Open Questions

1. What is the bart-large-mnli baseline F1 on 100 manually verified segments? (prerequisite for
   deciding if Option A/Model Question is viable)
2. Should the labeling pipeline output one JSONL per run dir, or accumulate across runs?
3. What is the minimum labeled dataset size before fine-tuning finbert? (PRD-003 OQ-1)

---

## Next Steps

Once this RFC is reviewed and questions above are resolved, write **ADR-008** recording the chosen
options for Q1–Q4. RFC-001 then becomes historical context.
