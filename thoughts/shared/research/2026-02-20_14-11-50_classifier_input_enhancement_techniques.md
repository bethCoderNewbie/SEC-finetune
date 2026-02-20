---
title: "Classifier Input Enhancement Techniques — Complexity & Decision Analysis"
date: 2026-02-20
author: beth88.career@gmail.com
git_sha: 5476f84b48de41dccb2426efef07ccd143019fae
branch: main
related_prd: docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md
related_rfc: docs/architecture/rfc/RFC-003_segment_token_length_enforcement.md
related_research:
  - thoughts/shared/research/2026-02-19_14-22-00_classifier_model_selection.md
  - thoughts/shared/research/2026-02-20_14-03-04_tmufin_tokenizer_complexity.md
status: RESEARCH — decisions required (see §6 Open Questions)
decision_needed_by: Before finetune.py is written (Phase 2 start)
---

# Classifier Input Enhancement Techniques — Complexity & Decision Analysis

## 1. Context

Four techniques were evaluated for improving the fine-tuned risk classifier's
accuracy and robustness. The evaluation was conducted against the actual codebase
state as of `5476f84`:

**Critical baseline finding:** `scripts/training/train_model.py` is entirely
`[TODO]` stubs — `load_training_data()`, `initialize_model()`, and `train_model()`
all return `None`. There is no training pipeline to modify. `scripts/training/finetune.py`
(referenced in the model selection research) does not yet exist. All four techniques
are therefore assessed against a training pipeline that must be written from scratch,
which changes the complexity calculus: some techniques cost nothing if built in from
the start, others require architectural decisions that are premature at Phase 2 scale.

---

## 2. Technique 1 — [SEP] Contextual Input Prefix

### What it is

Prepend industry and SIC metadata to the segment text as a sentence-pair input
before tokenization:

```
Standard:    [CLS] We are subject to complex and evolving cybersecurity laws... [SEP]
Contextual:  [CLS] Industry: Software & IT Services. SIC: 7372. [SEP] We are subject... [SEP]
```

BERT-family models natively handle two-segment inputs via `token_type_ids` (segment
embeddings distinguish Part A from Part B). No architecture change required — the
tokenizer handles the format.

### Rationale

A generic term like "pipeline constraints" means infrastructure risk for Oil & Gas
(SIC 1311) but sales process risk for Software (SIC 7372). Contextual prefix gives
the model immediate disambiguation signal without changing the model architecture.

### Codebase impact

| Location | Change | Notes |
|:---------|:-------|:------|
| `finetune.py` (to be written) | Construct `prefix + [SEP] + text` in `Dataset.__getitem__` or `DataCollator` | Must be identical at training and inference time |
| `src/analysis/inference.py:84` | Replace 2000-char hard truncation with prefix-aware tokenization | Current truncation is a string slice — no tokenizer awareness |
| `src/analysis/taxonomies/sasb_sics_mapping.json` | Required to look up `sasb_industry` from `sic_code` for the prefix | **Does not exist — G-15 ❌** |

**Token budget impact:** "Industry: Software & IT Services. SIC: 7372." consumes
~15 tokens. The RFC-003 Option A word-count ceiling (380 words ≈ 513 tokens) must
drop to ~368 words when the prefix is active to keep total input ≤ 512 tokens.

**Parity risk — the principal failure mode:** If the prefix is constructed from
`TaxonomyManager.get_industry_for_sic()` at inference time but was constructed from
a hardcoded string at training time, the model sees structurally different input and
F1 degrades silently. Identical prefix construction logic must be enforced in both
paths — a unit test asserting equal output is the minimum safeguard.

### Complexity: Low-Medium (blocked by G-15)

Implement after `sasb_sics_mapping.json` exists. String formatting is trivial; the
risk is parity drift between training and inference.

---

## 3. Technique 2 — Confidence-Weighted Training

### What it is

Override `Trainer.compute_loss()` to apply per-sample loss weights derived from
`llm_confidence` and `human_verified` fields already present in the annotation
corpus schema (PRD-002 §2.1.2).

Standard cross-entropy loss treats every training label as 100% correct. When
training on LLM silver labels (confidence 0.6–0.95) and LLM synthetic records,
this is wrong. A sample where `llm_confidence = 0.61` should exert less gradient
signal than one where `human_verified = true`.

### Weight derivation

```python
def sample_weight(record: dict) -> float:
    if record["human_verified"]:
        return 1.0
    source = record["label_source"]
    confidence = record.get("llm_confidence") or 0.5
    if source == "llm_silver":
        return confidence                  # e.g. 0.91
    if source == "llm_synthetic":
        return confidence * 0.8            # synthetic discount — LLM language artifact risk
    if source == "heuristic":
        return 0.5                         # floor weight — keyword match, not verified
    return 1.0
```

The recommendation's original formulation only branches on `human_verified`. Adding
a `label_source` discount on `llm_synthetic` records is a one-line addition that
enforces the PRD-002 design constraint: "LLM-synthetic records are capped at 40% of
training data to prevent the model from learning LLM language artifacts." The weight
discount is the training-time enforcement of that intent.

### Implementation pattern (for finetune.py)

```python
class WeightedTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False):
        weights = inputs.pop("sample_weight")       # float tensor, shape [batch]
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = nn.CrossEntropyLoss(reduction='none')(outputs.logits, labels)
        weighted_loss = (loss * weights).mean()
        return (weighted_loss, outputs) if return_outputs else weighted_loss
```

The `sample_weight` tensor must survive the `DataCollator → Trainer` pipeline.
`DataCollatorWithPadding` discards unknown fields by default. A custom collator
that passes `sample_weight` through as a stacked float tensor is required (~10
lines).

### Codebase impact

| Location | Change | Notes |
|:---------|:-------|:------|
| `finetune.py` (to be written) | `WeightedTrainer(Trainer)` subclass with `compute_loss` override | ~15 lines |
| `finetune.py` | Custom `DataCollator` that passes `sample_weight` | ~10 lines |
| `finetune.py` | `Dataset.__getitem__` computes `sample_weight` from record fields | ~8 lines |
| Annotation corpus JSONL | No changes — `llm_confidence` and `human_verified` already in schema | ✅ |

### Complexity: Low

**This is the highest ROI technique in this list.** The data is already in the
schema. The technique is standard practice for noisy-label training. It costs
~35 lines of code if built into `finetune.py` from day one. It should not be added
as a later enhancement — it should be the default training loop.

No blockers. No dependency on G-15 or G-16 completion. Implement first.

---

## 4. Technique 3 — Late-Fusion Architecture

### What it is

Modify the classification head to fuse the 768-dimensional `[CLS]` text embedding
with a separate `nn.Embedding` for `sic_code`, then pass the concatenated vector
through a final linear layer:

```
[CLS] embedding (768d) ──┐
                          ├── concat → Linear(768 + D_sic, 9) → softmax
SIC embedding (D_sic) ───┘
```

This explicitly separates the mathematical representation of company/industry from
the linguistic representation of the text.

### Codebase impact

| Location | Change | Notes |
|:---------|:-------|:------|
| `finetune.py` | Custom `nn.Module` wrapping FinBERT/DeBERTa with SIC embedding layer | Cannot use `AutoModelForSequenceClassification.from_pretrained()` directly |
| `src/models/registry/` | Save/load full class definition alongside weights | `ModelRegistry` currently assumes standard HF checkpoint format |
| `finetune.py` | SIC-to-integer index mapping; `[UNK_SIC]` fallback token | ~400+ SIC codes in EDGAR universe; unseen codes at inference → `IndexError` |
| `src/analysis/inference.py` | Pass `sic_code` as tensor alongside `input_ids` | All inference callers must supply SIC |

### Structural problems with this codebase at Phase 2 scale

**Problem 1 — Data sparsity.** Phase 2 gate: ≥ 500 examples per archetype (9
non-`other` classes = ~4,500 minimum total records). Spread across ~20 SIC codes,
the SIC embedding layer has ~25 examples per `(archetype, SIC)` combination. An
embedding trained on 25 examples overfits to the specific companies in training and
fails to generalise. The technique requires a corpus 5–10× larger than Phase 2 will
produce before the SIC embeddings carry real signal.

**Problem 2 — ModelRegistry coupling.** Custom `nn.Module` subclasses cannot be
loaded via `AutoModel.from_pretrained()`. `src/models/registry/` would need to
persist and restore the full class definition. If the class definition changes
between training runs, the checkpoint is unloadable. This is a non-trivial
operational risk for a project that pins exact reproducibility.

**Problem 3 — Architectural duplication.** The SASB taxonomy layer (G-15 / US-030)
already handles industry-specificity via the `archetype_to_sasb.yaml` crosswalk —
"lookup, not ML" is the deliberate PRD-002 design decision (§8). Late fusion
duplicates that concern at the model weight level. The two mechanisms must be
reconciled before implementation, or the system has two contradictory sources of
industry-routing logic. **This requires a design decision (OQ-LF-1).**

### Complexity: High — defer to Phase 3

---

## 5. Technique 4 — Special Token Injection

### What it is

Flatten HTML structural features into special tokens injected into the text string
before tokenization:

```
[ITEM_1A] [BOLD] We rely on third-party cloud infrastructure. [/BOLD] A failure...
```

Tokens like `[BOLD]`, `[/BOLD]`, `[ITEM_1A]` are added to the tokenizer vocabulary
via `add_tokens()` so the model learns structural signals alongside semantic content.

### Hard architectural conflict with the existing pipeline

`TextCleaner.remove_html_tags()` (`cleaning.py:307–335`) strips all HTML markup.
`TextCleaner.clean_text()` (`cleaning.py:86–123`) is called on every segment before
the segmenter sees it. All structural information is discarded at Step 3 of the
pipeline (`Parse → Extract → **Clean** → Segment`). By the time a `RiskSegment`
is created, `text` contains plain prose only.

To implement this technique, the following pipeline stages must change:

| Stage | Change required |
|:------|:----------------|
| `SECSectionExtractor` | Carry structural annotations (`bold`, `heading_level`) alongside plain text through `ExtractedSection` |
| `ExtractedSection` model | Add `annotated_text: Optional[str]` field |
| `TextCleaner` | Produce annotated output mode (convert `<b>text</b>` → `[BOLD] text [/BOLD]`) alongside existing clean mode |
| `RiskSegment` model | Add `annotated_text: Optional[str]` field |
| Tokenizer | `add_tokens(["[BOLD]", "[/BOLD]", "[ITEM_1A]"])` — back to T-MuFin vocabulary expansion territory |
| `finetune.py` | Train on `annotated_text` instead of `text` |
| `inference.py` | Construct `annotated_text` at inference time |

This touches six components and partially reverses a PRD-003 explicit decision to
strip structural noise.

### Questionable return — the core problem

The benefit premise is that `[BOLD]` signals classification-relevant emphasis. In
SEC 10-K Item 1A, bold text primarily marks the **risk factor heading** — the short
topic title ("Cybersecurity Risks", "Regulatory Environment") that precedes the
body paragraph. The segmenter's `_is_non_risk_content()` (`segmenter.py:246`)
already filters segments under 200 chars that match `"risk factors"`. Most bold
text in Item 1A is therefore the header that gets filtered, not the body prose that
gets classified.

The body paragraphs — the actual segments fed to the classifier — are rarely bold.
Preserving `[BOLD]` tokens adds structural overhead for markup that appears almost
exclusively in text the segmenter discards. **The expected F1 improvement is low
relative to the six-component pipeline change required.**

A targeted study would be needed to confirm whether bold-marked body prose exists
in material volume in the EDGAR corpus (OQ-ST-1) before this technique is worth
pursuing.

### Complexity: High, with questionable return

**This technique requires a design decision before any implementation begins
(OQ-ST-1, OQ-ST-2).**

---

## 6. Open Questions Requiring Decisions

Items flagged ⚠️ are blocking or near-blocking. Items flagged 🔵 are lower priority.

### ⚠️ OQ-CW-1 — Synthetic weight discount: what multiplier?

**Technique 2.** The recommendation applies `weight = llm_confidence` for all
non-human-verified records. This research recommends applying an additional `× 0.8`
discount for `label_source == "llm_synthetic"` records to enforce PRD-002's design
constraint that "the fine-tuned model should not learn LLM language artifacts."

**Decision needed:** Is `0.8` the right synthetic discount, or should synthetic
records be excluded from training entirely (weight = 0) once sufficient real EDGAR
segments exist? The answer depends on how many synthetic records will be in the
training split and how aggressively the LLM-synthetic gap fill is used.

| Option | Weight for synthetic | Trade-off |
|:-------|:---------------------|:----------|
| A | `llm_confidence × 0.8` | Soft down-weighting; keeps synthetic records as weak signal |
| B | `0.0` (excluded) | Hard exclusion once archetype reaches ≥ 500 real examples; simpler |
| C | `llm_confidence` (no discount) | Treats synthetic = silver; highest risk of artifact learning |

**Owner:** ML Engineer. **Blocks:** `finetune.py` implementation.

---

### ⚠️ OQ-SEP-1 — Prefix format: industry name or SIC code or both?

**Technique 1.** Three format candidates:

| Format | Example | Token cost |
|:-------|:--------|:-----------|
| A — industry name only | `Industry: Software & IT Services. [SEP]` | ~8 tokens |
| B — SIC only | `SIC: 7372. [SEP]` | ~5 tokens |
| C — both (recommended) | `Industry: Software & IT Services. SIC: 7372. [SEP]` | ~15 tokens |

Format C gives both a human-readable signal and the numeric SIC that the model may
learn to associate with industry clusters. Format B alone is less interpretable.

**Decision needed:** Which format? The choice must be locked before any training run
and cannot be changed without retraining from scratch.

**Owner:** ML Engineer. **Blocks:** Technique 1 implementation. Deferred until G-15
resolves.

---

### ⚠️ OQ-SEP-2 — Training/inference parity enforcement mechanism

**Technique 1.** The prefix must be constructed identically at training time
(`finetune.py`) and inference time (`inference.py`). This is currently untested
because neither file exists.

**Decision needed:** Where does the prefix construction logic live? Options:

| Option | Location | Risk |
|:-------|:---------|:-----|
| A | Duplicated in `finetune.py` and `inference.py` | Drift if one is updated without the other |
| B | Shared utility `src/analysis/input_formatter.py` | Single source of truth; both callers import it |

Option B is strongly preferred. A unit test asserting `format_input(text, sic) ==
format_input(text, sic)` across both callers is the minimum safeguard.

**Owner:** ML Engineer. **Blocks:** Technique 1 implementation.

---

### 🔵 OQ-LF-1 — Late fusion vs. SASB crosswalk: are they compatible?

**Technique 3.** The PRD-002 architecture uses `archetype_to_sasb.yaml` as a
deterministic crosswalk for industry-specificity (Layer 2, "lookup, not ML"). Late
fusion adds a learned SIC embedding inside the model (Layer 1, inside the ML model).

These two mechanisms are architecturally redundant: both route the model's output
based on `sic_code`. Having both risks conflicting signals — the model's SIC
embedding pulls toward one classification; the crosswalk overrides it with another.

**Decision needed:** If late fusion is adopted, does the SASB crosswalk remain as
Layer 2 on top of the model output, or is it subsumed into the model? If it remains,
what is the priority rule when they conflict?

**Owner:** ML Engineer + Product. **Blocks:** Technique 3 design. Not urgent — defer
to Phase 3 planning.

---

### 🔵 OQ-LF-2 — Minimum corpus size for SIC embeddings to carry signal

**Technique 3.** At Phase 2 minimum corpus (≥ 500 examples per archetype × 9
classes = ~4,500 records), spread across ~20 SIC codes: ~22 records per
`(archetype, SIC)` combination. SIC embeddings trained on 22 examples overfit.

**Decision needed:** What is the minimum examples-per-SIC-per-archetype threshold
before late fusion is expected to improve Macro F1 vs. vanilla DeBERTa? Run a
sensitivity experiment after Phase 2 corpus exists: vary SIC embedding dimension
(4, 8, 16) and report validation F1 vs. no-fusion baseline.

**Owner:** ML Engineer. **Blocks:** Technique 3 go/no-go. Not urgent.

---

### 🔵 OQ-ST-1 — Is bold-marked body prose material in EDGAR Item 1A?

**Technique 4.** The return on special token injection depends entirely on whether
bold markup appears in classifiable body prose, not just in the risk factor headings
that the segmenter filters out.

**Decision needed:** Run a one-time audit on any batch output:

```bash
# Check how many sec-parser BoldTextElement nodes survive into RiskSegment.text
# Requires running sec-parser with structural metadata preserved (not current default)
python -c "
import json, glob
# Count segments where bold headers appear in body (> 200 chars)
# Proxy: bold phrases that appear mid-paragraph rather than as standalone headers
"
```

If < 5% of segments contain mid-paragraph emphasis, the technique's expected value
is low and it should be permanently deprioritised. If > 20%, it warrants a
prototype.

**Owner:** Data Eng. **Blocks:** Technique 4 go/no-go.

---

### 🔵 OQ-ST-2 — Does Technique 4 conflict with the PRD-003 table-stripping decision?

**Technique 4.** PRD-003 Fixes 2A and 2B explicitly strip `TableElement` and
`TableOfContentsElement` nodes. The motivation was that table content degrades
segmentation quality. Special token injection re-introduces structural metadata
into the pipeline by a different mechanism.

**Decision needed:** Is there a principled distinction between structural metadata
worth preserving (e.g., `[BOLD]` emphasis in body prose) and structural noise worth
discarding (table cells, TOC entries)? If so, that distinction needs to be encoded
in `TextCleaner`'s annotated output mode rather than treating all structure
symmetrically.

**Owner:** Data Eng + ML Engineer. **Blocks:** Technique 4 design.

---

## 7. Implementation Priority

Ordered by value-to-complexity ratio and dependency chain:

| Priority | Technique | When | Blocker |
|:---------|:----------|:-----|:--------|
| 1 | Technique 2 — Confidence-weighted training | Build into `finetune.py` from day one | OQ-CW-1 decision |
| 2 | Technique 1 — [SEP] contextual prefix | After G-15 (`sasb_sics_mapping.json`) | OQ-SEP-1, OQ-SEP-2 decisions |
| 3 | Technique 3 — Late fusion | Phase 3, after corpus ≥ 10× Phase 2 minimum | OQ-LF-1, OQ-LF-2 |
| 4 | Technique 4 — Special token injection | Only if OQ-ST-1 audit shows > 20% body bold | OQ-ST-1, OQ-ST-2 |

---

## 8. References

- [PRD-002 §2.1.2 — Annotation corpus schema with `llm_confidence` and `human_verified`](docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md)
- [PRD-002 §4.1 — Training pipeline and model selection](docs/requirements/PRD-002_SEC_Finetune_Pipeline_v2.md)
- [RFC-003 — Segment token length enforcement](docs/architecture/rfc/RFC-003_segment_token_length_enforcement.md)
- [Classifier model selection research](thoughts/shared/research/2026-02-19_14-22-00_classifier_model_selection.md)
- [T-MuFin tokenizer complexity research](thoughts/shared/research/2026-02-20_14-03-04_tmufin_tokenizer_complexity.md)
- `src/analysis/inference.py:84` — 2000-char hard truncation (to be replaced)
- `scripts/training/train_model.py` — entirely TODO stubs (finetune.py needed)
- `src/preprocessing/cleaning.py:307` — `remove_html_tags()` strips all structure
- `src/preprocessing/segmenter.py:246` — `_is_non_risk_content()` filters short bold headers
