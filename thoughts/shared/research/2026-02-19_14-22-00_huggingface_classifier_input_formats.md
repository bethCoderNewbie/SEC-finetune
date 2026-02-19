---
title: "HuggingFace Classifier Input Formats — Data Requirements & Output for PRD-004 Phase 2"
date: 2026-02-19
time: "14:22:00"
author: beth88.career@gmail.com
git_sha: 3e1075ad3bfd72060391d5f34a970b86fa70d186
branch: main
related_prd: PRD-004_Business_Intelligence_Use_Cases.md
related_research: 2026-02-19_classifier_model_selection.md
status: FINAL
sources:
  - https://huggingface.co/ProsusAI/finbert
  - https://huggingface.co/microsoft/deberta-v3-base
  - https://huggingface.co/answerdotai/ModernBERT-base
  - https://huggingface.co/nickmuchi/deberta-v3-base-finetuned-finance-text-classification
  - https://huggingface.co/docs/transformers/training
  - https://huggingface.co/docs/transformers/main_classes/data_collator
  - https://huggingface.co/docs/transformers/model_doc/deberta-v2
---

# HuggingFace Classifier Input Formats — Data Requirements & Output

This document records the exact tokenizer behaviour, dataset schema, training configuration,
and inference output for the three models under evaluation in PRD-004 Phase 2. All information
is sourced directly from HuggingFace model cards and config JSON files — nothing is inferred.

Task: **9-class single-label text classification** of `RiskSegment.text` strings from the
post-PRD-003 corpus. Categories: `cybersecurity`, `regulatory`, `financial`, `supply_chain`,
`market`, `esg`, `macro`, `human_capital`, `other`.

---

## 1. Raw Dataset Schema

### 1.1 Required columns

Before tokenization, the dataset needs exactly two columns:

| Column | Type | Constraint |
|:-------|:-----|:-----------|
| `text` | `str` | Non-null, non-empty, UTF-8. Sourced from `RiskSegment.text` after PRD-003 cleanup. |
| `label` | `int` | Zero-based integer in `[0, 8]`. Never a raw string at training time. |

### 1.2 JSONL format (preferred for this project)

One JSON object per line — maps directly to `synthesized_risk_categories.jsonl` from Phase 1:

```jsonl
{"text": "We are subject to complex and evolving cybersecurity laws...", "label": 0}
{"text": "Changes in tax regulations could materially affect our business.", "label": 1}
{"text": "Covenant breaches could trigger immediate debt repayment obligations.", "label": 2}
{"text": "Supply chain disruptions could adversely affect our operations.", "label": 3}
{"text": "Increased competition may cause us to lose market share.", "label": 4}
{"text": "Climate-related regulations may increase our operational costs.", "label": 5}
{"text": "Rising interest rates increase our borrowing costs.", "label": 6}
{"text": "The loss of key executives could disrupt our strategic plans.", "label": 7}
{"text": "Our stock price may be volatile due to various factors.", "label": 8}
```

### 1.3 Label mapping for this project

```python
LABEL_NAMES = [
    "cybersecurity",   # 0
    "regulatory",      # 1
    "financial",       # 2
    "supply_chain",    # 3
    "market",          # 4
    "esg",             # 5
    "macro",           # 6
    "human_capital",   # 7
    "other",           # 8
]
NUM_LABELS = 9
id2label = {i: n for i, n in enumerate(LABEL_NAMES)}
label2id = {n: i for i, n in enumerate(LABEL_NAMES)}
```

### 1.4 Loading into HuggingFace Datasets

```python
from datasets import load_dataset, ClassLabel

dataset = load_dataset(
    "json",
    data_files={
        "train":      "data/processed/annotation/train.jsonl",
        "validation": "data/processed/annotation/validation.jsonl",
        "test":       "data/processed/annotation/test.jsonl",
    },
)

# Cast label column to ClassLabel so HuggingFace tracks class names
dataset = dataset.cast_column(
    "label",
    ClassLabel(num_classes=NUM_LABELS, names=LABEL_NAMES),
)
```

---

## 2. Model-by-Model Tokenizer Specifications

### 2.1 ProsusAI/finbert

**Source:** `tokenizer_config.json`, `config.json` — HuggingFace model card.

| Property | Value |
|:---------|:------|
| Tokenizer class | `BertTokenizerFast` |
| Subword algorithm | WordPiece |
| Vocabulary size | 30,522 |
| Case sensitive | **No** — `do_lower_case: true`. All input lowercased. |
| CLS token | `[CLS]` |
| SEP token | `[SEP]` |
| PAD token | `[PAD]` (ID 0) |
| Max position embeddings | 512 |
| Returns `token_type_ids` | **Yes** — all zeros for single-sequence classification |
| Returns `attention_mask` | Yes |
| Pre-configured `num_labels` | 3 (positive/negative/neutral) — must override for 9 classes |

**Gotcha:** FinBERT was pre-trained and fine-tuned for 3-class sentiment. Loading it as a
9-class classifier requires overriding the head. The `do_lower_case=true` behavior means
ticker symbols, company names, and ALL-CAPS acronyms (e.g., `EBITDA`, `GDPR`) are silently
lowercased before tokenization. This cannot be disabled without re-pretraining.

```python
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
# Returns: input_ids, attention_mask, token_type_ids

sample = tokenizer("GDPR compliance risk", return_tensors="pt")
# input_ids contains tokens for "gdpr compliance risk" (lowercased)
```

**Tokenized dataset columns after `map()`:**

| Column | Dtype | Notes |
|:-------|:------|:------|
| `input_ids` | `List[int]` | Max length 512 |
| `attention_mask` | `List[int]` | 1=real, 0=pad |
| `token_type_ids` | `List[int]` | All zeros; present in batch |
| `labels` | `int` | Renamed from `label` |

---

### 2.2 microsoft/deberta-v3-base ✅ Recommended default

**Source:** `tokenizer_config.json`, `config.json`, `special_tokens_map.json` — HuggingFace.

| Property | Value |
|:---------|:------|
| Tokenizer class | `DebertaV2TokenizerFast` |
| Subword algorithm | SentencePiece (Unigram) |
| Vocabulary size | 128,100 |
| Case sensitive | **Yes** — `do_lower_case: false` |
| CLS token | `[CLS]` |
| SEP token | `[SEP]` |
| PAD token | `[PAD]` (ID 0) |
| Max position embeddings | 512 |
| `type_vocab_size` in config | **0** — no type embedding matrix |
| Returns `token_type_ids` | **No** — tokenizer does not produce them |
| Returns `attention_mask` | Yes |
| `add_prefix_space` | True — SentencePiece artifact, applied automatically |
| Pre-configured `num_labels` | None (MLM head only in base checkpoint) |

**Gotcha:** `type_vocab_size=0` means the model has no segment embedding. If `token_type_ids`
are somehow present in a batch (e.g., copied from a BERT pipeline), the forward pass silently
ignores them — no error, no effect. However, switching from BERT to DeBERTa means cached
tokenized datasets cannot be reused: different vocabulary (128K vs 30K), different algorithm,
different token IDs.

```python
tokenizer = AutoTokenizer.from_pretrained("microsoft/deberta-v3-base")
sample = tokenizer("GDPR compliance risk", return_tensors="pt")
print(sample.keys())
# dict_keys(['input_ids', 'attention_mask'])
# token_type_ids is ABSENT
```

**Warm-start option — `nickmuchi/deberta-v3-base-finetuned-finance-text-classification`:**
- Already fine-tuned on financial text (Financial PhraseBank + Kaggle; 4,840 samples)
- 3-class head (negative/neutral/positive)
- Performance: accuracy=0.8913, macro F1=0.8912 on its own test set
- To use as warm-start for 9-class problem: **must pass `ignore_mismatched_sizes=True`**
  to replace the 3-class classification head with a fresh 9-class head

```python
model = AutoModelForSequenceClassification.from_pretrained(
    "nickmuchi/deberta-v3-base-finetuned-finance-text-classification",
    num_labels=9,
    id2label=id2label,
    label2id=label2id,
    ignore_mismatched_sizes=True,   # REQUIRED — replaces 3-class head with 9-class head
)
```

**Tokenized dataset columns after `map()`:**

| Column | Dtype | Notes |
|:-------|:------|:------|
| `input_ids` | `List[int]` | Max length 512 |
| `attention_mask` | `List[int]` | 1=real, 0=pad |
| `labels` | `int` | Renamed from `label` |

---

### 2.3 answerdotai/ModernBERT-base ✅ Contingency (if >5% segments exceed 390 words)

**Source:** `tokenizer_config.json`, `config.json` — HuggingFace. Released December 2024.

| Property | Value |
|:---------|:------|
| Tokenizer class | `PreTrainedTokenizerFast` (BPE, GPT-NeoX-style) |
| Subword algorithm | Byte-Pair Encoding |
| Vocabulary size | 50,368 |
| Case sensitive | Yes |
| CLS token | `[CLS]` (ID 50281) |
| SEP token | `[SEP]` (ID 50282) |
| PAD token | `[PAD]` (ID 50283) |
| Max position embeddings | **8,192** |
| `model_input_names` | `["input_ids", "attention_mask"]` only |
| Returns `token_type_ids` | **No** — and passing them causes a `TypeError` |
| Returns `attention_mask` | Yes |
| Positional encoding | Rotary (RoPE) — local theta=10000, global theta=160000 |
| Attention pattern | Local window 128 + global every 3 layers |
| Num hidden layers | 22 (vs. 12 for BERT-base) |
| Minimum transformers version | **`>=4.48.0`** — will fail silently on older versions |
| Flash Attention 2 | Supported and recommended for sequences >512 tokens |
| Pre-configured `num_labels` | None (MLM head only) |

**Critical gotcha — `token_type_ids` causes a TypeError:**

```python
# BAD — copied from BERT pipeline
inputs = tokenizer(text, return_tensors="pt")
inputs["token_type_ids"] = torch.zeros_like(inputs["input_ids"])  # DO NOT DO THIS
outputs = model(**inputs)
# TypeError: ModernBertForSequenceClassification.forward() got an unexpected
# keyword argument 'token_type_ids'

# CORRECT — tokenizer never produces token_type_ids for ModernBERT
inputs = tokenizer(text, return_tensors="pt")
print(inputs.keys())  # dict_keys(['input_ids', 'attention_mask'])
outputs = model(**inputs)  # OK
```

**Tokenized dataset columns after `map()`:**

| Column | Dtype | Notes |
|:-------|:------|:------|
| `input_ids` | `List[int]` | Max length 8,192 |
| `attention_mask` | `List[int]` | 1=real, 0=pad |
| `labels` | `int` | Renamed from `label` |

---

## 3. Side-by-Side Comparison

| Property | FinBERT | DeBERTa-v3-base | ModernBERT-base |
|:---------|:--------|:----------------|:----------------|
| Tokenizer | `BertTokenizerFast` | `DebertaV2TokenizerFast` | `PreTrainedTokenizerFast` |
| Algorithm | WordPiece | SentencePiece Unigram | BPE |
| Vocab size | 30,522 | 128,100 | 50,368 |
| Case sensitive | **No** | Yes | Yes |
| Max seq length | 512 | 512 | **8,192** |
| `token_type_ids` produced | Yes (all zeros) | No | No |
| `token_type_ids` safe to pass | Yes (ignored) | Yes (ignored) | **No — TypeError** |
| Financial pretrained | ✅ SEC filings | ❌ (warm-start available) | ❌ |
| Num layers | 12 | 12 | 22 |
| Parameters | 110M | 86M | 149M |
| Transformers min version | any | any | **>=4.48.0** |
| Flash Attention | No | No | Yes |
| Recommended for project | Zero-shot Phase 1 only | ✅ Default Phase 2 | ✅ Contingency Phase 2 |

---

## 4. Tokenization Pattern for All Three Models

```python
from transformers import AutoTokenizer

# Swap MODEL_ID to switch models — everything else is identical
MODEL_ID = "microsoft/deberta-v3-base"   # or "ProsusAI/finbert" or "answerdotai/ModernBERT-base"
MAX_LEN  = 512                           # 8192 for ModernBERT if long segments present

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

def tokenize(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=MAX_LEN,
        padding=False,  # DataCollatorWithPadding handles dynamic padding per batch
    )

tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])
tokenized = tokenized.rename_column("label", "labels")
```

---

## 5. DataCollatorWithPadding

Dynamic padding — pads each batch only to its longest sequence. Never pad at tokenization
time; this wastes ~10× compute for short-text datasets.

```python
from transformers import DataCollatorWithPadding

data_collator = DataCollatorWithPadding(
    tokenizer=tokenizer,
    padding=True,            # "longest" within each batch (default)
    pad_to_multiple_of=8,   # Tensor Core alignment for NVIDIA V100/A100
    return_tensors="pt",
)
```

`DataCollatorWithPadding` pads only the columns it recognises as tokenizer outputs
(`input_ids`, `attention_mask`, `token_type_ids` if present). The `labels` column is
collated separately as a 1D integer tensor — no action needed.

---

## 6. Handling Class Imbalance

The annotated corpus is unlikely to be balanced — `other` (boilerplate) and `regulatory`
tend to be over-represented in 10-K filings. Use weighted cross-entropy loss.

```python
import torch, torch.nn as nn
from collections import Counter
from transformers import Trainer

label_counts  = Counter(tokenized["train"]["labels"])
total         = sum(label_counts.values())
class_weights = torch.tensor(
    [total / (NUM_LABELS * label_counts[i]) for i in range(NUM_LABELS)],
    dtype=torch.float,
)
# e.g. if "other" appears 3× more than "human_capital":
# weight[human_capital] ≈ 3×, weight[other] ≈ 0.33×

class WeightedLossTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels  = inputs.pop("labels")
        outputs = model(**inputs)
        loss    = nn.CrossEntropyLoss(
            weight=class_weights.to(outputs.logits.device)
        )(outputs.logits, labels)
        return (loss, outputs) if return_outputs else loss
```

Apply when imbalance ratio (majority class / minority class count) exceeds 5:1. With
≥500 examples per category enforced by the Phase 1 gate, this threshold is unlikely
to be crossed — but verify after annotation completes.

---

## 7. TrainingArguments — Critical Fields

```python
from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="./checkpoints/sec-risk-classifier",

    # Evaluation & checkpoint selection
    eval_strategy          = "epoch",      # evaluate after every epoch
    save_strategy          = "epoch",      # MUST match eval_strategy for load_best_model_at_end
    load_best_model_at_end = True,
    metric_for_best_model  = "f1",         # key returned by compute_metrics (no "eval_" prefix)
    greater_is_better      = True,         # True for F1/accuracy; False for loss

    # Batch sizes
    per_device_train_batch_size = 16,
    per_device_eval_batch_size  = 32,

    # Optimisation
    num_train_epochs            = 5,
    learning_rate               = 2e-5,
    weight_decay                = 0.01,
    warmup_ratio                = 0.06,
    lr_scheduler_type           = "linear",
    gradient_accumulation_steps = 2,       # effective batch = 16 × 2 = 32

    # Precision
    fp16                        = True,    # or bf16=True on Ampere+ GPUs

    # Logging & reproducibility
    logging_steps               = 50,
    seed                        = 42,
    report_to                   = "none", # switch to "wandb" when tracking experiments
)
```

**Critical interdependency:** `load_best_model_at_end=True` requires `save_strategy` to
match `eval_strategy` exactly. Mismatching them raises a `ValueError` at `trainer.train()`.

---

## 8. compute_metrics — Macro F1 for PRD-004

```python
import numpy as np
import evaluate
from sklearn.metrics import classification_report

f1_metric  = evaluate.load("f1")
acc_metric = evaluate.load("accuracy")

def compute_metrics(eval_pred):
    logits, labels = eval_pred           # logits: (N, 9), labels: (N,)
    preds = np.argmax(logits, axis=-1)

    macro_f1 = f1_metric.compute(
        predictions=preds,
        references=labels,
        average="macro",                 # equal weight per class — penalises ignoring minority
    )["f1"]

    accuracy = acc_metric.compute(
        predictions=preds,
        references=labels,
    )["accuracy"]

    # Per-class F1 (written to reports/classifier_eval.json per TR-14)
    report = classification_report(
        labels, preds,
        target_names=LABEL_NAMES,
        output_dict=True,
        zero_division=0,
    )

    result = {"f1": macro_f1, "accuracy": accuracy}
    for name in LABEL_NAMES:
        result[f"f1_{name}"] = report[name]["f1-score"]

    return result  # metric_for_best_model="f1" selects on macro_f1
```

The PRD-004 Phase 2 gate (Macro F1 ≥ 0.72) and v0.4.0 release target (≥ 0.80) both refer
to the `"f1"` key returned here — the unweighted macro average across all 8 non-`other`
categories plus `other` itself.

---

## 9. Inference Output — Shape and Softmax

All three models return `SequenceClassifierOutput`. The logit-to-probability conversion is
identical regardless of base model.

```python
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# Load the trained model from checkpoint
MODEL_PATH = "./checkpoints/sec-risk-classifier"
tokenizer  = AutoTokenizer.from_pretrained(MODEL_PATH)
model      = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
model.eval()

# Example segments from the 309-filing corpus
segments = [
    "We face significant risks from data breaches and ransomware attacks.",
    "Pending litigation and regulatory proceedings may result in material penalties.",
    "Our stock price may be volatile due to various factors.",  # expected: other
]

inputs = tokenizer(
    segments,
    return_tensors="pt",
    truncation=True,
    padding=True,
    max_length=512,
)
# For ModernBERT: inputs will not contain token_type_ids (safe to pass as-is)

with torch.no_grad():
    outputs = model(**inputs)

logits = outputs.logits
# Shape: torch.Size([3, 9])   — (batch_size=3, num_labels=9)

probs = F.softmax(logits, dim=-1)
# Shape: torch.Size([3, 9])

predicted_ids    = logits.argmax(dim=-1)          # shape: (3,)
predicted_labels = [model.config.id2label[i.item()] for i in predicted_ids]
confidence       = probs.max(dim=-1).values        # shape: (3,)
```

**Example output for the three segments above:**

```
Segment 0: "We face significant risks from data breaches..."
  predicted_label : cybersecurity
  confidence      : 0.94
  probs           : [0.94, 0.02, 0.01, 0.01, 0.01, 0.00, 0.00, 0.00, 0.01]
  QR-03 route     : RETAIN (0.94 >= 0.70)

Segment 1: "Pending litigation and regulatory proceedings..."
  predicted_label : regulatory
  confidence      : 0.87
  probs           : [0.01, 0.87, 0.04, 0.02, 0.02, 0.01, 0.01, 0.01, 0.01]
  QR-03 route     : RETAIN (0.87 >= 0.70)

Segment 2: "Our stock price may be volatile..."
  predicted_label : other
  confidence      : 0.61
  probs           : [0.05, 0.04, 0.07, 0.03, 0.09, 0.02, 0.06, 0.03, 0.61]
  QR-03 route     : ROUTE TO other (0.61 < 0.70, boilerplate correctly flagged)
```

**Applying QR-03 confidence routing (PRD-004 §4.3):**

```python
CONFIDENCE_THRESHOLD = 0.70   # QR-03: segments below this → "other"
OTHER_CLASS_ID       = label2id["other"]   # 8

final_labels = []
for i in range(len(segments)):
    if confidence[i].item() < CONFIDENCE_THRESHOLD:
        final_labels.append("other")
    else:
        final_labels.append(predicted_labels[i])
```

---

## 10. Data Quality Checklist

Run these checks before any training run. Write failures to `reports/data_quality.json`.

### Schema

- [ ] Every row has `text` (str, non-null, non-empty) and `label` (int, 0–8)
- [ ] `label` values cover all 9 classes with no gaps or values outside `[0, 8]`
- [ ] `label` is integer — not a string like `"cybersecurity"`
- [ ] No duplicate rows in train (dedup by SHA-256 of `text`)
- [ ] Train, validation, test splits are disjoint — no text appears in more than one split

### Text quality

- [ ] All text is UTF-8 (no mojibake from latin-1 / cp1252 conversion)
- [ ] No whitespace-only strings (`text.strip() != ""`)
- [ ] Minimum segment word count ≥ 20 (segments below this will almost always route to `other` via QR-03)
- [ ] Maximum token count ≤ `MAX_LEN` — verify with:

```python
lengths = tokenizer(texts, return_length=True, truncation=False)["length"]
over_limit = sum(1 for l in lengths if l > MAX_LEN)
print(f"Segments exceeding {MAX_LEN} tokens: {over_limit}/{len(texts)}")
```

### Label quality

- [ ] Each non-`other` class has ≥ 500 examples in train (PRD-004 Phase 1 gate)
- [ ] Inter-annotator Cohen's Kappa ≥ 0.80 recorded before training begins (QR-01)
- [ ] `corrected_category` field is non-null in every row of `synthesized_risk_categories.jsonl`
- [ ] Class imbalance ratio (max_count / min_count) is documented

### Tokenisation safety

- [ ] Cached tokenized datasets deleted and re-generated when switching model (vocabulary differs)
- [ ] For ModernBERT: `transformers>=4.48.0` installed (`pip show transformers | grep Version`)
- [ ] For ModernBERT: `token_type_ids` absent from tokenized output — confirm with `print(sample.keys())`
- [ ] For DeBERTa-v3: `token_type_ids` absent from tokenized output — confirm same check

### Training configuration

- [ ] `id2label` and `label2id` set on `model.config` before `trainer.train()`
- [ ] `num_labels=9` passed to `from_pretrained`
- [ ] `save_strategy` matches `eval_strategy` (required for `load_best_model_at_end=True`)
- [ ] `metric_for_best_model="f1"` matches key returned by `compute_metrics`
- [ ] `greater_is_better=True` (F1 is maximised, not minimised)
- [ ] Weighted loss applied if imbalance ratio > 5:1

### Output artefacts (TR-14)

- [ ] `reports/classifier_eval.json` written after training with per-category Precision, Recall, F1
- [ ] Model checkpoint saved to `./checkpoints/sec-risk-classifier/` with `tokenizer.save_pretrained()`
- [ ] `model.config.model_version` set to `"finbert-sec-risk-v1"` (PRD-004 §4.1) before saving

---

## 11. Relationship to Project Files

| Research item | Implemented in |
|:--------------|:---------------|
| Tokenization function | `scripts/training/finetune.py` (Phase 2 new) |
| WeightedLossTrainer | `scripts/training/finetune.py` |
| `compute_metrics` (Macro F1 + per-class) | `scripts/training/finetune.py` |
| QR-03 confidence routing | `src/inference/classifier.py` (Phase 2 new) |
| Eval report writer | `src/inference/classifier.py` → `reports/classifier_eval.json` (TR-14) |
| JSONL annotation output | `data/processed/synthesized_risk_categories.jsonl` (Phase 1) |
| Train/val/test split | `data/processed/annotation/{train,validation,test}.jsonl` |
