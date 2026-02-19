---
id: PRD-002
title: SEC 10-K Risk Factor Analyzer — Pipeline v2 (Current State)
status: DRAFT
author: beth88.career@gmail.com
created: 2026-02-18
last_updated: 2026-02-19
last_revised: 2026-02-19
version: 0.2.0
supersedes: PRD-001
git_sha: 1af473b
---

# PRD-002: SEC 10-K Risk Factor Analyzer — Pipeline v2

## 1. Context & Problem Statement

This document reflects the **current implemented state** of the pipeline as of commit `1af473b`
(2026-02-18), updated with taxonomy architecture decisions as of 2026-02-19. It supersedes
PRD-001 by recording what has been built, what has changed from the original MVP spec, and
what remains to be done.

### Problem

SEC 10-K filings contain Item 1A (Risk Factors) — the most decision-relevant section for
institutional investors, credit analysts, and compliance officers. Reading and categorizing
these disclosures manually is untenable at scale: a senior analyst spends 30–45 minutes per
filing, and the EDGAR universe spans ~10,000 filings per annual cohort across dozens of
industries. Existing open-source classifiers use fixed, generic label sets that ignore the
fact that material risks differ fundamentally by industry — an oil company's risks
("Greenhouse Gas Emissions", "Mine Safety") are structurally different from a bank's
("Systemic Risk Management", "Business Ethics") or a tech company's ("Data Security",
"Intellectual Property").

### Solution

A four-step extraction pipeline (`Parse → Extract → Clean → Segment`) produces atomic,
classifiable risk statements from raw EDGAR HTML. A fine-tuned classifier then assigns each
statement two label layers:

1. **Archetype label** (9 classes, single ML model) — a universal semantic category
   (`cybersecurity`, `regulatory`, `financial`, etc.) that works across all industries.
2. **SASB material topic** (lookup, not ML) — the industry-specific SASB disclosure topic
   for that company's SIC sector (e.g., `Data_Security` for Software & IT, `Greenhouse_Gas_Emissions`
   for Oil & Gas E&P), derived via `TaxonomyManager` from `sasb_sics_mapping.json`.

This two-layer design gives downstream consumers both cross-industry comparability (via
archetypes) and SASB-grounded specificity (via material topics) in a single output record.

### What changed since PRD-001

- Sanitization removed from the hot path (sec-parser handles raw HTML directly)
- Pipeline is now 4 steps, not 5: `Parse → Extract → Clean → Segment`
- Full `src/utils/` suite integrated into the batch CLI
- Stamped run output directories with git SHA and timestamps
- State manifest for cross-run hash tracking (`data/processed/.manifest.json`)
- QA validation and quarantine pattern implemented
- Test suite grown from 186 → 660 collected tests

### What changed since initial PRD-002 (2026-02-19 taxonomy revision)

- **Taxonomy:** 12-class flat list replaced with 9-archetype + SASB topic two-layer schema
- **Default fine-tune model:** `ProsusAI/finbert` retained; `microsoft/deberta-v3-base`
  queued for Phase 2 comparison experiment (see research `2026-02-19_classifier_model_selection.md`)
- **Output column names:** `input_text` → `text` (required by HuggingFace `load_dataset`)
- **New output fields:** `sasb_topic`, `sasb_industry`, `label_source` added to segment schema
- **OQ-3 resolved:** truncation strategy defined (512 tokens DeBERTa; 8,192 ModernBERT contingency)
- **OQ-4 resolved:** JSONL output confirmed as target format with full schema defined
- **`transformers` version floor raised** from `>=4.35.0` to `>=4.48.0` (ModernBERT requirement)

---

## 2. Goals & Non-Goals

### Goals

> **G-07 removed.** "Parsing success rate KPI in run summary" is an observability mechanism, not an independent goal. Its requirement (parse success rate visible in `RUN_REPORT.md` and `batch_summary_{run_id}.json`) is captured in G-01's measurement spec and §4.3 Observability. US-005 re-linked to G-01.

| ID | Priority | Since | Goal | Status | Stories |
|:---|:---------|:------|:-----|:-------|:--------|
| G-01 | P0 | PRD-001 | Parse ≥95% of EDGAR HTML 10-K/10-Q filings — success rate `(total_submitted − dlq_size) / total_submitted ≥ 0.95` reported in `RUN_REPORT.md` and `batch_summary_{run_id}.json`, on a stratified random sample of ≥30 filings spanning ≥5 SIC sectors and filing years 2019–2024 | ⚠️ DLQ implemented; ≥95% KPI not yet measured — requires corpus of ≥30 filings | US-005 |
| G-02 | P0 | PRD-001 | Extract Item 1A with < 5% character loss — `(raw_item1a_char_count − Σ segment.char_count) / raw_item1a_char_count < 0.05`, using `RiskSegment.char_count` fields in output JSON, on the same ≥30-filing stratified sample as G-01 | ❌ Not validated — tested on AAPL_10K_2021 only | — |
| G-03 | P1 | PRD-001 | Segment risk text into atomic, classifiable statements — every output segment must satisfy `50 ≤ char_count ≤ 2000` and `word_count ≥ 20` (configurable via `preprocessing.min/max_segment_length`; raised from 10 to align with classifier training quality gate); every processed filing must produce ≥ 1 segment | ✅ `RiskSegmenter`; bounds enforced by `_filter_segments` and `_split_long_segments` — **threshold config update pending** | — |
| G-04 | P0 | PRD-001 | Output JSONL compatible with HuggingFace `datasets.load_dataset("json", ...)` — each record must have `text` (str, column name exact) and `label` (int 0–8); full schema defined in §2.1.2 | ❌ Currently outputs JSON, not JSONL; column is named `text` in schema but pipeline emits nested `segments[].text` — conversion not yet implemented | US-001 |
| G-05 | P0 | PRD-001 | Pipeline must be resumable — crashed runs continue from checkpoint | ✅ `CheckpointManager` + `ResumeFilter` + `--resume` flag | US-002 |
| G-06 | P1 | PRD-001 | Batch CLI: 10,000 filings < 2 hours on 32-core node | ❌ Not benchmarked | US-021 *(pending)* |
| G-08 | P1 | PRD-002 | Memory-aware adaptive timeout per file size category | ✅ `MemorySemaphore` + `FileCategory` (Small/Medium/Large) | — |
| G-09 | P0 | PRD-002 | Dead Letter Queue for malformed filings with drain on final run | ✅ `DeadLetterQueue` | US-003 |
| G-10 | P2 | PRD-002 | Stamped run directories with full provenance | ✅ `{YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/` | — |
| G-11 | P1 | PRD-002 | Inline QA validation / quarantine pattern | ✅ `HealthCheckValidator` + `process_and_validate()` | — |
| G-12 | P0 | PRD-002 | SASB-aware risk classifier integrated into `process_batch()` — every output segment carries `risk_label` (archetype str), `sasb_topic` (SASB material topic for this company's industry), `sasb_industry`, `confidence`, and `label_source`; segments with confidence < 0.7 fall back to heuristic | ❌ `src/analysis/inference.py` (zero-shot, single label) and `scripts/feature_engineering/auto_label.py` (SASB-aware zero-shot) both exist but neither is wired into `process_batch()`; two-layer output not yet implemented | US-022 *(pending)* |
| G-13 | P0 | PRD-002 | CLI sector filter (`--sic` / `--ticker`) for targeted dataset builds | ❌ Not implemented | US-004 |
| G-14 | P0 | PRD-002 | NLP features (sentiment, readability, topic) inline in primary output record | ❌ Features exist in separate scripts; not unified | US-008 |
| G-15 | P0 | PRD-002 | Create SASB taxonomy data files: `src/analysis/taxonomies/sasb_sics_mapping.json` (SIC → SASB industry → material topics) and `src/analysis/taxonomies/archetype_to_sasb.yaml` (archetype → SASB topic crosswalk per industry) — hard dependency for G-12; `TaxonomyManager` returns `{}` without them | ❌ Neither file exists; `taxonomy_manager.py` loads them at line 125 but silently returns empty on missing file | — |
| G-16 | P0 | PRD-002 | Build labeled annotation corpus (`data/processed/annotation/{train,validation,test}.jsonl`) meeting §2.1.2 quality gates: ≥ 500 examples per non-`other` archetype in train, test set from real EDGAR segments only, Cohen's Kappa ≥ 0.80, SHA-256 dedup across splits | ❌ No annotation corpus exists; `data/processed/synthesized_risk_categories.jsonl` referenced in OQ-12 does not yet exist | — |

### Non-Goals

- Real-time streaming ingestion
- Production UI deployment — a Streamlit prototype exists at `src/visualization/app.py`; hardening, hosting, and auth are out of scope for Phase 2
- Database storage — deferred to a future PRD; not in scope for PRD-002 or PRD-003
- Public REST API
- Comparative / trend analysis across companies / years
- Non-SEC financial documents
- **Per-industry SASB classifiers (Approach B)** — training one model per SASB industry group is out of scope for Phase 2. Phase 2 delivers a single 9-class archetype classifier (Approach C). Per-industry models are a Phase 3 candidate once the annotation corpus exists and per-industry data sufficiency can be verified.
- **Full SASB coverage (77 industries)** — `sasb_sics_mapping.json` need only cover SIC codes present in the target corpus. Building the complete SASB SICS® crosswalk for all 77 industries before the corpus SIC distribution is known is premature and out of scope.

> **Design constraint:** Sentiment features (in `src/features/sentiment.py`) are pipeline outputs, not classifier inputs. They are not used as signals for risk taxonomy classification.
>
> **Design constraint:** LLM-synthetic records must never appear in the test split of the annotation corpus. The test set must consist exclusively of real EDGAR segments with human-verified labels (§2.1.2). Violating this makes the Macro F1 ≥ 0.72 gate meaningless.
>
> **Design constraint:** LLM-synthetic records are capped at 40% of the training split to prevent the fine-tuned model from learning LLM language artifacts rather than real SEC disclosure patterns.

---

### 2.1 Dataset Definition

Two distinct datasets exist in this pipeline: the raw EDGAR input corpus and the labeled
annotation corpus used for classifier training. They have different sources, schemas, quality
requirements, and owners.

---

#### 2.1.1 Raw Input Dataset (EDGAR HTML)

| Attribute | Specification | Owner |
|:----------|:--------------|:------|
| **Source System** | EDGAR HTML filings fetched via `sec-downloader`; pre-downloaded files in `data/raw/` | Data Eng |
| **Freshness SLA** | Data must be available T+24 hours after EDGAR publication (batch; not real-time). | Data Eng |
| **History** | Minimum 5 years of 10-K/10-Q backfill required for training corpus. | Data Eng |
| **PII / Compliance** | SEC filings are public documents; no SSN or personal data expected. Verify before ingesting any exhibit attachments or proxy statements. | Security |
| **Volume estimate** | ~10,000 filings per annual cohort; ~50,000 filings for a 5-year backfill. | Data Eng |
| **Format** | HTML (UTF-8; latin-1 fallback). EDGAR inline XBRL variants supported by `sec-parser==0.54.0`. | Data Eng |
| **Retention** | Raw HTML retained in `data/raw/`; processed JSONL retained in `data/processed/` indefinitely (versioned by run dir). | Data Eng |

---

#### 2.1.2 Training Dataset (Annotation Corpus)

The labeled corpus used to fine-tune the risk classifier. Produced by a hybrid pipeline
combining real EDGAR segments with LLM-assigned labels and LLM-generated synthetic examples.
See research `2026-02-19_14-59-17_llm_synthetic_data_per_industry_models.md` §3 for the
full hybrid pipeline design. See `2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md`
§5 for the annotation workflow and JSONL schema.

| Attribute | Specification | Owner |
|:----------|:--------------|:------|
| **Source — Real segments** | `RiskSegment.text` objects extracted from EDGAR filings by the PRD-002 pipeline. Provide authentic SEC language and must form the entire test set and at least 60% of training data. | Data Eng |
| **Source — LLM silver labels** | Real EDGAR segments labeled by LLM (Claude / GPT-4o) using industry-specific SASB topics as candidate labels. Confidence threshold ≥ 0.80. Flagged `"label_source": "llm_silver"`. | ML Engineer |
| **Source — LLM synthetic** | LLM-generated risk disclosure sentences for SASB topic / industry pairs where real segment count < 300. Style-anchored with real 10-K excerpts in the generation prompt. Flagged `"label_source": "llm_synthetic"`. Capped at 40% of total training data to prevent model collapse. **Never used in test set.** | ML Engineer |
| **File format** | JSONL — one JSON object per line. Required by `datasets.load_dataset("json", ...)`. See schema below. | ML Engineer |
| **File locations** | `data/processed/annotation/train.jsonl`, `data/processed/annotation/validation.jsonl`, `data/processed/annotation/test.jsonl` | ML Engineer |
| **Split ratios** | 80 / 10 / 10 (train / validation / test). Splits must be disjoint — no `text` value may appear in more than one split (verify by SHA-256 dedup). | ML Engineer |
| **Test set constraint** | Real EDGAR segments only — never LLM-labeled or LLM-generated. Human-verified labels. Test set must be held out **before** any LLM labeling runs to prevent eval contamination. | ML Engineer |
| **Minimum class size** | ≥ 500 examples per non-`other` archetype in train split. Verified before training begins (Phase 1 gate). | ML Engineer |
| **Class imbalance** | Imbalance ratio (max class count / min class count) must be documented. If ratio > 5:1, apply weighted cross-entropy loss during training. | ML Engineer |
| **Inter-annotator agreement** | Cohen's Kappa ≥ 0.80 on a 50-example sample per SASB topic, verified by two domain experts before training begins (QR-01). | Data Scientist |
| **Text quality gates** | Min word count ≥ 20; max token count ≤ `MAX_LEN` (512 for FinBERT / DeBERTa; 8,192 for ModernBERT); no whitespace-only strings; UTF-8 only (no mojibake). | ML Engineer |
| **Deduplication** | Exact-match dedup by SHA-256 of `text` within each split and across splits. | ML Engineer |
| **PII / Compliance** | Source text is public EDGAR data. LLM-generated text must not be seeded with non-public company information. | Security |
| **Retention** | JSONL splits versioned under `data/processed/annotation/` indefinitely. Raw LLM API responses stored in `data/processed/annotation/llm_responses/` for audit. | Data Eng |

**JSONL record schema** (one line per segment; both label layers preserved):

```jsonl
{
  "text": "We are subject to complex and evolving cybersecurity laws...",
  "label": 0,
  "sasb_topic": "Data_Security",
  "sasb_industry": "Software & IT Services",
  "sic_code": "7372",
  "ticker": "MSFT",
  "filing_date": "2023-10-15",
  "label_source": "llm_silver",
  "llm_confidence": 0.91,
  "human_verified": false
}
```

| Column | Type | Required for training | Notes |
|:-------|:-----|:----------------------|:------|
| `text` | `str` | ✅ Yes | Non-null, non-empty, UTF-8. `load_dataset("json")` requires this exact column name. |
| `label` | `int` (0–8) | ✅ Yes | Zero-based archetype integer. Must be cast to `ClassLabel` before training. Never store the string `"cybersecurity"` here. |
| `sasb_topic` | `str` | No — metadata | SASB material topic selected by annotator or derived via crosswalk. E.g. `"Data_Security"`. |
| `sasb_industry` | `str` | No — metadata | SASB industry from `TaxonomyManager.get_industry_for_sic()`. Enables per-industry filtering. |
| `sic_code` | `str` | No — metadata | Source SIC code for traceability and re-mapping. |
| `ticker` | `str` | No — metadata | Company identifier. Null for LLM-synthetic records. |
| `filing_date` | `str` (ISO 8601) | No — metadata | Enables temporal drift analysis. Null for LLM-synthetic records. |
| `label_source` | `str` | No — metadata | Provenance: `"human"` \| `"llm_silver"` \| `"llm_synthetic"` \| `"heuristic"` |
| `llm_confidence` | `float` or `null` | No — metadata | LLM self-reported confidence (0–1). Null for human and heuristic records. |
| `human_verified` | `bool` | No — metadata | `true` if a domain expert reviewed and confirmed the label. |

### 2.2 Feature Requirements (Schema)

Before model training begins, these features must be present in every output record. **Phase 2 Gate** indicates whether absence of the field blocks the Phase 2 exit criteria.

| Feature | Type | Notes | Phase 2 Gate |
|:--------|:-----|:------|:-------------|
| `text` | `str` — truncate to 512 tokens (DeBERTa default); 8,192 if >5% of segments exceed 390 words (ModernBERT contingency) — OQ-3 resolved | Raw cleaned risk segment text (post-`TextCleaner`). Must use this exact column name — `load_dataset("json")` requires `text` for HuggingFace compatibility. | ✅ Blocking |
| `filing_date` | ISO 8601 timestamp | Extracted from EDGAR filing metadata via `sec-downloader`. See data dictionary for null-handling behavior. | ❌ Non-blocking |
| `sector_code` | Categorical — SIC code (str) | Extracted by `SECFilingParser`; flows as `sic_code` through all pipeline stages. | ✅ Blocking |
| `risk_label` | `str` — one of 9 archetype labels: `cybersecurity`, `regulatory`, `financial`, `supply_chain`, `market`, `esg`, `macro`, `human_capital`, `other` | Assigned by classifier. At training time stored as integer `label` (0–8); never store the string in the `label` column. **Not yet in batch output — blocks Phase 2.** | ✅ Blocking |
| `sasb_topic` | `str` — SASB material topic name for this company's industry | Derived via `archetype_to_sasb.yaml` crosswalk using company `sic_code`. E.g. `"Data_Security"` for Software & IT Services, `"Greenhouse_Gas_Emissions"` for Oil & Gas E&P. **Not yet in batch output — blocks Phase 2.** | ✅ Blocking |
| `sasb_industry` | `str` — SASB industry name | Derived from `sic_code` via `TaxonomyManager.get_industry_for_sic()`. E.g. `"Software & IT Services"`. **Not yet in batch output — blocks Phase 2.** | ✅ Blocking |
| `confidence` | `float` [0, 1] | Classifier confidence score. Segments below threshold 0.7 are labeled `"other"` and flagged `"label_source": "heuristic"`. **Not yet in batch output — blocks Phase 2.** | ✅ Blocking |
| `word_count` | `int` | Segment word count. Present in `RiskSegment` today. | ✅ Blocking |
| `char_count` | `int` | Segment char count. Present in `RiskSegment` today. | ✅ Blocking |
| `ticker` | `str` | Company ticker symbol. Present in `SegmentedRisks` today. | ✅ Blocking |
| `cik` | `str` | EDGAR Central Index Key. Present in `SegmentedRisks` today. | ✅ Blocking |

---

## 3. Model Specifications (Science Requirements)

### 3.1 The Baseline ("Dumb" Model)

We must beat this to justify fine-tuning complexity.

- **Heuristic:** Keyword matching against `src/analysis/taxonomies/risk_taxonomy.yaml`
  (e.g., if segment contains "bankruptcy", "default", "liquidity" → label `Financial`).
- **Baseline Performance:** F1-Score: **0.45** (estimated; requires validation on held-out set).

Any proposed model must exceed baseline F1 by > 10 percentage points to proceed through Gate 1.

### 3.2 Success Metrics (KPIs)

Define success mathematically. "Make it better" is not an acceptance criterion.

| Metric | Acceptance Threshold (MVP) | Gold Standard (Production) |
|:-------|:--------------------------|:--------------------------|
| **Precision** | > 0.70 — do not flood downstream consumers with false alarms | > 0.85 |
| **Recall** | > 0.80 — do not miss material risk disclosures | > 0.90 |
| **Macro F1** | > 0.72 across all 9 archetype classes (`cybersecurity` … `other`) — unweighted macro average | > 0.87 |
| **Latency (P95)** | < 500ms per segment (batch inference) | < 200ms |
| **Text-loss rate** | < 5% vs. raw filing character count | < 2% |
| **Parse success rate** | ≥ 95% of input filings produce at least one segment | ≥ 98% |

---

## 4. Engineering & MLOps Requirements

### 4.1 Pipeline Architecture

- **Training pipeline:** Python / PyTorch. Fine-tune `ProsusAI/finbert` (configured as
  `default_model` in `src/config/models.py`) or use `facebook/bart-large-mnli` for zero-shot
  baseline (`zero_shot_model`). `microsoft/deberta-v3-base` is queued as a Phase 2 comparison
  experiment — see research `2026-02-19_classifier_model_selection.md` for trade-offs (note:
  FinBERT's `do_lower_case=true` lowercases acronyms like `GDPR` and `EBITDA`; record results
  against DeBERTa before deciding on the production default). Contingency model:
  `answerdotai/ModernBERT-base` (max 8,192 tokens) if >5% of corpus segments exceed 390 words;
  requires `transformers>=4.48.0`. Runs on local GPU or cloud node (not yet specified).
- **Orchestration:** [Airflow / Dagster — not yet selected]. Scheduled nightly retraining
  triggered when new EDGAR filings are available. No experiments run without scheduling.
- **Experiment Tracking:** [MLflow / Weights & Biases — not yet selected]. All training runs
  must be logged with: dataset version, model checkpoint, hyperparameters, and evaluation metrics.
  `RANDOM_SEED=42` must be recorded in every run.
- **Preprocessing entry point:** `scripts/data_preprocessing/run_preprocessing_pipeline.py`
  (batch CLI, `--resume`, `--workers`, `--chunk-size` flags).
- **Cross-run state manifest:** `StateManager` writes `data/processed/.manifest.json` with atomic
  file ops. Tracks per-file content hashes across runs (DVC-lite pattern). ✅ Implemented.

### 4.2 Serving Strategy

- **Pattern:** Batch (daily). The pipeline processes a directory of HTML filings and writes
  labeled JSONL to `data/processed/`. Real-time inference is out of scope for MVP.
- **Fallback:** If the classifier fails or `confidence < 0.7` (configurable threshold in
  `configs/config.yaml`), the segment is labeled via the keyword-matching heuristic
  (§3.1 baseline) and flagged `"label_source": "heuristic"` in the output record.
- **Model versioning:** Model artifacts stored in `models/registry/` via `ModelRegistry`
  (`src/models/registry/`). Production model pinned by registry ID; rollback by re-pinning.

### 4.3 Observability (The Dashboard)

| Signal | Alert Condition | Mechanism |
|:-------|:----------------|:----------|
| **Data drift** | Input `text` token-length distribution shifts (KL divergence > 0.1 vs. training baseline) | [TBD — no monitoring infra yet] |
| **Concept drift** | Output `risk_label` class distribution changes > 15% week-over-week | [TBD] |
| **Parse failure rate** | DLQ size > 5% of input batch | `RUN_REPORT.md` surfaced today; alerting not wired |
| **System health** | RAM usage (`ResourceTracker`), worker timeout rate, DLQ drain count | Per-run: `batch_summary_{run_id}.json` |
| **Test regression** | Any of 660 collected tests fail in CI | [CI not yet configured] |

---

## 5. Phase-Gate Delivery Plan

We do not proceed to the next phase without meeting the Exit Criteria.

### Phase 1 — Discovery & Feasibility (Complete)

**Focus:** EDA, data cleaning, baseline modeling, pipeline infrastructure.

**Deliverables:** `src/preprocessing/` pipeline, 660-test suite, `RUN_REPORT.md`, `StateManager`.

**Exit Criteria:**

- [x] Training data accessible: EDGAR HTML filings parseable via `sec-parser==0.54.0`
- [x] Pipeline runs end-to-end on AAPL_10K_2021 without crash
- [x] Extraction text loss < 5% validated on reference filing
- [x] Resumable batch CLI with DLQ, checkpoint, and progress logging
- [ ] Model outperforms baseline heuristic by > 10% F1 — **not yet measured**
- [ ] GO / NO-GO Decision: [Eng Lead]

### Phase 2 — Engineering MVP (In Progress)

**Focus:** SASB taxonomy data, annotation corpus construction, SASB-aware classifier integration, JSONL output, HuggingFace dataset compatibility, throughput benchmark.

**Deliverables:** SASB taxonomy data files + labeled annotation corpus (§2.1.2) + SASB-aware batch classifier producing two-layer output per segment.

**Exit Criteria:**

> Criteria are grouped by dependency. Taxonomy files (G-15) must exist before classifier
> integration (G-12) can be verified. Annotation corpus (G-16) must exist before the
> fine-tune KPI gate (§3.2 Macro F1 ≥ 0.72) is measurable.

**Taxonomy & Data (G-15, G-16)**
- [ ] `src/analysis/taxonomies/sasb_sics_mapping.json` created — covers all SIC codes present in target corpus; `TaxonomyManager.get_topics_for_sic()` returns non-empty results for every filing in the batch (G-15)
- [ ] `src/analysis/taxonomies/archetype_to_sasb.yaml` created — every archetype label has a `default` mapping and industry-specific entries for all industries in `sasb_sics_mapping.json` (G-15)
- [ ] Annotation corpus train split: ≥ 500 examples per non-`other` archetype; class imbalance ratio documented; dedup by SHA-256 confirmed (G-16)
- [ ] Annotation corpus test split: real EDGAR segments only — zero LLM-silver or LLM-synthetic records; labels human-verified; held out before any LLM labeling ran (G-16)
- [ ] Inter-annotator Cohen's Kappa ≥ 0.80 documented on 50-example sample per SASB topic (G-16 / QR-01)

**Classifier Integration (G-12)**
- [ ] SASB-aware classifier wired into `process_batch()` — every output segment carries `risk_label`, `sasb_topic`, `sasb_industry`, `confidence`, and `label_source`; segments with confidence < 0.7 fall back to heuristic and set `"label_source": "heuristic"` (G-12)
- [ ] Inference latency ≤ 500ms P95 per segment (§3.2)

**Output Format (G-04)**
- [ ] Per-segment JSONL output: flat records with `text` column (exact name), `label` as integer 0–8, `sasb_topic`, `sasb_industry`, `risk_label`, `confidence`, `label_source` — loadable via `datasets.load_dataset("json", ...)` without pre-processing (G-04)
- [ ] Schema version aligned: `"1.0"` vs `"2.0"` discrepancy resolved in code and CHANGELOG

**Pipeline & Quality (G-13, testing)**
- [ ] `--sic` / `--ticker` CLI filter flag implemented (G-13 / US-004)
- [ ] Throughput benchmark: ≥ 100 filings processed end-to-end; < 2s/filing confirmed
- [ ] Fix 2 test collection errors (`test_pipeline_global_workers.py`, `test_validator_fix.py`); all 660 tests pass
- [ ] Code unit-tested at > 80% line coverage

- [ ] GO / NO-GO Decision: [Eng Lead]

### Phase 3 — Production & Scale (Not Started)

**Focus:** CI/CD, monitoring, canary deployment, 10K-filing throughput.

**Deliverables:** Live batch system processing real EDGAR filings nightly.

**Exit Criteria:**

- [ ] Monitoring dashboards live: data drift + system metrics (§4.3)
- [ ] Shadow mode running silently alongside current manual process; outputs match expectations
- [ ] Batch throughput: 10,000 filings < 2 hours on 32-core node (G-06)
- [ ] On-call rotation established with runbook
- [ ] GO / NO-GO Decision: [Product Owner]

---

## 6. User Stories (Functional Requirements)

> Acceptance criteria (Gherkin Given/When/Then) are in individual story files linked below.

| ID | Priority | As a… | I want to… | So that… | Status | Goal | Detail |
|:---|:---------|:------|:-----------|:---------|:-------|:-----|:-------|
| US-001 | **P0** | Data Scientist | Run the full pipeline on a directory of HTML filings and receive **JSONL** output | I get a HuggingFace-compatible dataset without format conversion | ⚠️ Batch mode ✅; output is JSON not JSONL (gap) | G-04 | [→](stories/US-001_batch_pipeline_execution.md) |
| US-002 | **P0** | ML Engineer | Resume a crashed pipeline run | I don't lose hours of compute | ✅ `--resume` + `CheckpointManager` | G-05 | [→](stories/US-002_pipeline_resume.md) |
| US-003 | **P0** | ML Engineer | Route malformed filings to a Dead Letter Queue | Pipeline does not halt on bad input | ✅ `DeadLetterQueue` | G-09 | [→](stories/US-003_dead_letter_queue.md) |
| US-004 | **P0** | Data Scientist | Filter filings by ticker or SIC code **at the CLI before processing** | Build sector-specific sets without wasting compute on irrelevant filings | ❌ CLI flag not implemented (P0 gap) | G-13 | [→](stories/US-004_sector_filtering.md) |
| US-005 | **P1** | Data Scientist | Inspect which filings failed and why | I can improve parser/extractor logic | ✅ `RUN_REPORT.md`, DLQ log, `_progress.log` | G-01 | [→](stories/US-005_failure_inspection.md) |
| US-006 | **P1** | Financial Analyst | View extracted risk segments in Streamlit UI | I can validate quality without writing code | ⚠️ `src/visualization/app.py` exists; integration status unknown | — | [→](stories/US-006_streamlit_ui.md) |
| US-007 | **P1** | ML Engineer | Configure all pipeline settings via YAML + env vars | I can deploy to different environments | ✅ 16-module config system; Pydantic V2 + env-prefix | — | [→](stories/US-007_yaml_config.md) |
| US-008 | **P0** | Data Scientist | Get sentiment, readability, and topic features **inline in the primary JSONL record** | Load one file and train immediately without complex joins | ❌ Features exist in separate scripts; not unified (P0 gap) | G-14 | [→](stories/US-008_nlp_features.md) |

---

## 7. Architecture — Current Implementation

### 7.1 Pipeline Flow

```
HTML filing (data/raw/)
    │
    ▼ Step 1: SECFilingParser (sec-parser==0.54.0)
ParsedFiling  ← sic_code, sic_name, cik, ticker, company_name, form_type
    │
    ▼ Step 2: SECSectionExtractor
ExtractedSection  ← metadata flows through
    │
    ▼ Step 3: TextCleaner
cleaned_text (str)
    │
    ▼ Step 4: RiskSegmenter (all-MiniLM-L6-v2, cosine threshold=0.5)
SegmentedRisks → saved as JSON to stamped run dir
```

**Sanitization was removed** (commit `8bb512c`). `sec-parser` processes raw HTML directly.

### 7.2 Batch CLI Architecture (`scripts/data_preprocessing/run_preprocessing_pipeline.py`)

```
Batch run
├── ResumeFilter         — skip already-processed files
├── MemorySemaphore      — classify Small/Medium/Large; set adaptive timeout
├── ParallelProcessor    — multiprocessing pool (init_preprocessing_worker once per worker)
│   ├── ResourceTracker  — per-file CPU/memory/elapsed tracking
│   ├── DeadLetterQueue  — capture failures; drain on exit
│   └── ProgressLogger   — persistent _progress.log
├── CheckpointManager    — crash recovery (_checkpoint.json, deleted on success)
├── StateManager         — .manifest.json (atomic writes, cross-run hash tracking)
└── MarkdownReportGenerator → RUN_REPORT.md + batch_summary_{run_id}.json
```

### 7.3 Output Layout

```
data/processed/
├── .manifest.json                            # cross-run hash tracking (StateManager)
└── {YYYYMMDD_HHMMSS}_preprocessing_{sha}/
    ├── _progress.log                         # ProgressLogger output
    ├── _checkpoint.json                      # deleted on successful completion
    ├── RUN_REPORT.md                         # MarkdownReportGenerator
    ├── batch_summary_{run_id}_{ts}.json      # naming.py convention
    └── {stem}_segmented_risks.json           # per-filing output
```

### 7.4 Source Tree

```
src/
├── analysis/
│   ├── inference.py           # zero-shot risk classifier (not yet integrated to batch)
│   └── taxonomies/
│       ├── sasb_sics_mapping.json  # SIC → SASB industry → material topics (authoritative; to be created)
│       ├── archetype_to_sasb.yaml  # crosswalk: 9 archetype labels → SASB topic per industry (to be created)
│       ├── risk_taxonomy.yaml      # DEPRECATED — hardcoded to Software & IT Services only
│       └── taxonomy_manager.py
├── config/                    # 16 modular configs (Pydantic V2 + pydantic-settings)
│   ├── __init__.py            # Settings class + global instance
│   ├── _loader.py             # single cached YAML loader
│   ├── paths.py, models.py, preprocessing.py, extraction.py
│   ├── sec_parser.py, sec_sections.py, run_context.py, naming.py
│   ├── qa_validation.py       # HealthCheckValidator
│   └── features/              # sentiment, topic_modeling, readability, risk_analysis
├── features/
│   ├── sentiment.py           # LM dictionary + FinBERT sentiment
│   ├── readability/           # Flesch-Kincaid, Gunning Fog, etc.
│   ├── topic_modeling/        # LDA via gensim
│   └── dictionaries/          # Loughran-McDonald dictionary
├── models/registry/           # ModelRegistry for versioned model artifacts
├── preprocessing/
│   ├── pipeline.py            # SECPreprocessingPipeline + PipelineConfig
│   ├── parser.py              # SECFilingParser (sec-parser wrapper)
│   ├── extractor.py           # SECSectionExtractor
│   ├── cleaning.py            # TextCleaner
│   ├── segmenter.py           # RiskSegmenter (semantic + rule-based)
│   ├── sanitizer.py           # HTMLSanitizer (not in hot path; available optionally)
│   └── models/                # ParsedFiling, ExtractedSection, SegmentedRisks, RiskSegment
├── utils/
│   ├── checkpoint.py          # CheckpointManager
│   ├── dead_letter_queue.py   # DeadLetterQueue
│   ├── memory_semaphore.py    # MemorySemaphore + FileCategory
│   ├── metadata.py            # RunMetadata
│   ├── naming.py              # file naming conventions
│   ├── parallel.py            # ParallelProcessor
│   ├── progress_logger.py     # ProgressLogger
│   ├── reporting.py           # MarkdownReportGenerator
│   ├── resource_tracker.py    # ResourceTracker
│   ├── resume.py              # ResumeFilter
│   ├── state_manager.py       # StateManager (.manifest.json, atomic writes)
│   └── worker_pool.py         # global worker init + getters
└── validation/
    └── schema_validator.py
```

---

## 8. Data & Metrics

### Input

- Source: EDGAR HTML filings (10-K and 10-Q)
- Location: `data/raw/`
- Format: HTML (UTF-8; latin-1 fallback)

### Output Schema (v1.0 — actual code)

```json
{
  "version": "1.0",
  "filing_name": "AAPL_10K_2021",
  "sic_code": "3571",
  "sic_name": "ELECTRONIC COMPUTERS",
  "cik": "0000320193",
  "ticker": "AAPL",
  "company_name": "APPLE INC",
  "form_type": "10-K",
  "section_title": "Item 1A. Risk Factors",
  "total_segments": 45,
  "segments": [
    {"index": 0, "text": "...", "word_count": 150, "char_count": 890}
  ],
  "metadata": {},
  "num_segments": 45
}
```

> **Gap vs PRD-001:** PRD-001 specified `"version": "2.0"` and HuggingFace JSONL output.
> Actual code emits `"version": "1.0"` JSON. JSONL conversion not yet implemented.

**Phase 2 target output per segment** (after classifier integration):

```json
{
  "index": 0,
  "text": "We face significant risks from data breaches and ransomware attacks.",
  "word_count": 45,
  "char_count": 270,
  "risk_label": "cybersecurity",
  "sasb_topic": "Data_Security",
  "sasb_industry": "Software & IT Services",
  "confidence": 0.94,
  "label_source": "classifier"
}
```

`label_source` values: `"classifier"` | `"heuristic"` (confidence < 0.7 fallback) | `"llm_silver"` | `"human"`

### Risk Taxonomy — Two-Layer Schema

The taxonomy uses a hierarchical two-layer design grounded in the SASB Materiality Map.
See research `2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md` §2 for full rationale.

**Layer 1 — Archetype labels** (what the ML classifier trains on; 9 classes):

`cybersecurity` (0) · `regulatory` (1) · `financial` (2) · `supply_chain` (3) · `market` (4) · `esg` (5) · `macro` (6) · `human_capital` (7) · `other` (8)

Stored as integer `label` (0–8) in training JSONL. Stored as string `risk_label` in inference output.

**Layer 2 — SASB material topics** (industry-specific; derived via lookup, not ML):

- Authoritative data: `src/analysis/taxonomies/sasb_sics_mapping.json` — maps SIC codes to SASB industries and defines the material topics per industry. Loaded by `TaxonomyManager` at `taxonomy_manager.py:125`.
- Crosswalk: `src/analysis/taxonomies/archetype_to_sasb.yaml` — maps each archetype label to the corresponding SASB topic name(s) per industry.
- At inference time: `TaxonomyManager.get_topics_for_sic(sic_code)` returns the correct topic set for the company; the crosswalk then maps the archetype prediction to the SASB topic name.

| Archetype | Example SASB topic (Software & IT) | Example SASB topic (Oil & Gas E&P) |
|:----------|:-----------------------------------|:------------------------------------|
| `cybersecurity` | `Data_Security` | `Data_Security` |
| `regulatory` | `Management_of_the_Legal_&_Regulatory_Environment` | `Management_of_the_Legal_&_Regulatory_Environment` |
| `esg` | `Environmental_Footprint_of_Hardware_Infrastructure` | `Greenhouse_Gas_Emissions`, `Air_Quality` |
| `human_capital` | `Recruiting_&_Managing_a_Skilled_Workforce` | `Workforce_Health_&_Safety` |

> **Deprecated:** `src/analysis/taxonomies/risk_taxonomy.yaml` was hardcoded to Software & IT
> Services only and is superseded by `sasb_sics_mapping.json`. Retained for reference.

---

## 9. Technical Requirements (Non-Functional)

| Category | Requirement | Status |
|----------|-------------|--------|
| **Scalability** | 10,000 filings < 2 hrs on 32-core node | ❌ Not benchmarked |
| **Reliability** | No crash on malformed HTML; DLQ for failures | ✅ DLQ integrated |
| **Resumability** | Checkpoint + ResumeFilter; `--resume` flag | ✅ Implemented |
| **Reproducibility** | `sec-parser==0.54.0` pinned; `RANDOM_SEED=42`; Python ≥ 3.10 | ✅ |
| **Security** | No secrets in plaintext; `.env` only | ✅ `.env.example` provided |
| **Config** | YAML + env vars; Pydantic V2 validation | ✅ 16-module config system |
| **Memory** | Memory-aware worker pool; adaptive timeout | ✅ `MemorySemaphore` |
| **Testability** | ≥ 660 unit tests; 2 collection errors | ⚠️ Fix 2 collection errors |
| **Provenance** | Stamped run dirs with git SHA | ✅ `{YYYYMMDD_HHMMSS}_preprocessing_{sha}/` |

### Runtime Dependencies

```toml
sec-parser==0.54.0              # PINNED — semantic filing parser
sec-downloader>=0.10.0
transformers>=4.48.0            # ModernBERT contingency requires >=4.48.0; also safe for DeBERTa-v3-base
torch>=2.0.0
sentence-transformers>=2.0.0    # all-MiniLM-L6-v2 for semantic segmentation
spacy>=3.7.0                    # + en_core_web_sm download required
gensim>=4.0.0
pydantic>=2.12.4                # V2 enforced
pydantic-settings>=2.0.0
pandas>=2.0.0
streamlit>=1.28.0
```

---

## 10. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| OQ-1 | Should HTML tables be extracted as markdown or discarded? | Data Eng | Open |
| OQ-2 | Acceptable text-loss threshold for inline XBRL filings? | Data Scientist | Open |
| OQ-3 | Fine-tuning: full segment text or truncate to 512 tokens? | ML Engineer | **Resolved** — truncate to 512 for DeBERTa-v3-base default; use ModernBERT-base (8,192 max) if >5% of corpus segments exceed 390 words. See research `2026-02-19_14-22-00_huggingface_classifier_input_formats.md` §2.3. |
| OQ-4 | Output format: convert to JSONL for HuggingFace `datasets`? | ML Engineer | **Resolved** — JSONL confirmed; full schema (with `text`, `label`, `sasb_topic`, `sasb_industry` columns) defined in research `2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md` §5.2. |
| OQ-5 | Batch throughput: is 10K filings / 2 hrs achievable with transformer inference? | ML Engineer | Open |
| OQ-6 | Integrate zero-shot classifier (`src/analysis/inference.py`) into batch pipeline? | ML Engineer | **New** |
| OQ-7 | Fix 2 test collection errors (`test_pipeline_global_workers.py`, `test_validator_fix.py`) | Eng | **New — blocking test coverage claim** |
| OQ-8 | Schema version: align code (`"1.0"`) with CHANGELOG claim (`"2.0"`)? | Eng | **New** |
| OQ-9 | Which experiment tracking system: MLflow or W&B? | ML Engineer | **New — blocks Phase 2 Gate** |
| OQ-10 | Which orchestration system: Airflow or Dagster for scheduled retraining? | Eng Lead | **New — blocks Phase 3** |
| OQ-11 | **Materiality Audit:** How do we verify 0% loss for critical "Black Swan" triggers? | Data Eng | **New** |
| OQ-12 | **RLHF Loop:** How will analysts correct misclassifications in the Streamlit UI? | Product | **Resolved** — PRD-004 G-09 and US-028 define the HITL labeler (`src/visualization/labeler_app.py`); corrected labels are appended to `data/processed/synthesized_risk_categories.jsonl` |
| OQ-13 | **Unit Cost:** What is the per-filing cost for GPU inference vs. business value? | FinOps | **New** |
| OQ-T1 | What SIC codes are present in the target corpus? Run `grep -h "sic_code" data/processed/**/*.json \| sort \| uniq -c \| sort -rn` on batch output before completing `sasb_sics_mapping.json`. | Data Eng | **New — blocks taxonomy data file** |
| OQ-T2 | Should `sasb_topic` in the output record be a single best match (`sasb_topics[0]`) or a list? Current crosswalk design returns the first match. | ML Engineer | **New — blocks output schema finalization** |
| OQ-T3 | The `macro` archetype (interest rates, FX, inflation) has no clean SASB topic mapping. Does it get `Other_General_Risk` or is `sasb_topic` left null? | Data Scientist | **New — blocks `archetype_to_sasb.yaml`** |
| OQ-T4 | Should the annotation tool present annotators with only the industry's named SASB topics, or also allow `Other_General_Risk` as a fallback choice? | Product | **New — blocks annotation UI design** |

---

## 11. Work Remaining for Fine-Tune Readiness

The following gaps must close before the pipeline can produce a HuggingFace-ready fine-tune dataset:

### Required Engineering (Phase 2)
1. **JSONL output** — convert `SegmentedRisks.save_to_json()` or add `save_to_jsonl()` method. Output column must be named `text` (not `input_text`) for HuggingFace compatibility.
2. **Classifier integration** — wire `src/analysis/inference.py` into `process_batch()`; output `risk_label`, `sasb_topic`, `sasb_industry`, `confidence`, `label_source` on every segment.
3. **SASB taxonomy data files** — create `src/analysis/taxonomies/sasb_sics_mapping.json` and `src/analysis/taxonomies/archetype_to_sasb.yaml`. Start with SIC codes present in the target corpus (OQ-T1). `taxonomy_manager.py` requires no code changes — it already loads `sasb_sics_mapping.json`.
4. **Throughput benchmark** — run on ≥100 filings; confirm < 2s/filing estimate.
5. **Fix 2 test errors** — resolve `ZeroDivisionError` and global worker import errors.
6. **CLI filter flag** — `--sic` / `--ticker` filter for sector-specific dataset builds.

### Best Practice Recommendations (New)
6. **Materiality Retention Audit** — Run a "Keyword Survival" check to ensure critical risk terms (e.g., "Default", "Litigation") are never lost during cleaning.
7. **Silver Standard Baseline** — Evaluate zero-shot performance of an LLM (Claude/GPT) on 100 segments to establish a realistic performance ceiling before fine-tuning.
8. **Human-in-the-Loop (RLHF) UI** — Enable "Label Correction" in the Streamlit dashboard to collect high-quality ground truth from analysts.
9. **Recall-Weighted Evaluation** — Update evaluation scripts to use $F_{\beta}$ where $\beta=2$, penalizing false negatives more heavily than false positives.

---

## 12. Business Impact (ROI)

The adoption of the SEC Risk Factor Analyzer transforms a manual, high-latency research process into an automated, high-scale strategic asset.

### 12.1 Efficiency & Cost Reduction
- **Manual Baseline:** A senior analyst takes ~30-45 minutes to manually read, extract, and categorize Item 1A from a single 10-K.
- **Automated Performance:** The pipeline processes a filing in < 2 seconds (excluding model training).
- **ROI Metric:** For a universe of 10,000 filings, automation replaces ~6,000 hours of manual labor ($300k+ in estimated labor value assuming $50/hr).

### 12.2 Portfolio Risk Alpha
- **Universal Coverage:** Enables 100% coverage of the SEC EDGAR universe, allowing for the detection of emerging risks (e.g., supply chain shifts, ESG liabilities) across entire sectors, not just S&P 500 tickers.
- **Early Warning:** 24-hour freshness (US-11) provides a "first-mover" advantage in identifying material risk changes before they are fully reflected in market pricing or analyst reports.

### 12.3 Strategic Value (Audit & Compliance)
- **Standardization:** Replaces inconsistent human labeling with a validated SASB-aligned taxonomy, ensuring cross-company comparability and trend analysis.
- **Auditability:** Direct lineage (US-10) and evidence highlighting (US-09) reduce the overhead of compliance audits and institutional due diligence reporting.

### 12.4 MLOps Sustainability
- **Moat Creation:** The RLHF correction loop (US-06) ensures that the proprietary model becomes more accurate with every use, creating a "moat" of high-quality, human-validated financial data unique to the firm.
