---
id: PRD-002
title: SEC 10-K Risk Factor Analyzer — Pipeline v2 (Current State)
status: DRAFT
author: beth88.career@gmail.com
created: 2026-02-18
last_updated: 2026-02-24
last_revised: 2026-02-24
version: 0.4.0
supersedes: PRD-001
git_sha: 96801e6
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
- Test suite grown from 186 → 715 collected tests

### What changed since initial PRD-002 (2026-02-19 taxonomy revision)

- **Taxonomy:** 12-class flat list replaced with 9-archetype + SASB topic two-layer schema
- **Default fine-tune model:** `ProsusAI/finbert` retained; `microsoft/deberta-v3-base`
  queued for Phase 2 comparison experiment (see research `2026-02-19_classifier_model_selection.md`)
- **Output column names:** `input_text` → `text` (required by HuggingFace `load_dataset`)
- **New output fields:** `sasb_topic`, `sasb_industry`, `label_source` added to segment schema
- **OQ-3 resolved:** truncation strategy defined (512 tokens DeBERTa; 8,192 ModernBERT contingency)
- **OQ-4 resolved:** JSONL output confirmed as target format with full schema defined
- **`transformers` version floor raised** from `>=4.35.0` to `>=4.48.0` (ModernBERT requirement)

### What changed 2026-02-24 (Phase A corpus quality / section contamination)

- **RFC-003 Option A DEPLOYED** (`max_segment_words: 380`, commit `0872eb3`): G-03 token
  safety gap is closed. `_split_long_segments` + `_split_into_chunks` enforce the 380-word
  ceiling. ADR-012 documents the decision. US-015 is now **implemented**.
- **Full-corpus token profile measured** (607,463 segments, run `20260223_182806`):
  p50=58 tokens · p95=**226 tokens** · p99=399 tokens · max=3,886 tokens.
  p95 ≤ 400 gate: **PASS**. Over-512 (silent truncation): 2,713 segments (0.45%).
  Danger zone 360–512 tokens: 5,736 (0.94%). ModernBERT contingency NOT triggered.
  See `reports/token_profile.json`.
- **Section contamination finding (OQ-PRD-1):** Phase A diagnostic analysis of run
  `20260223_182806` reveals **81.5% of 607,463 segments (495,290) are non-target-section
  content**. The pipeline dispatches across 7 section types; only `part1item1a` (112,173
  segments, 18.5%) is Item 1A Risk Factors. The remaining 81.5% are MD&A (`part2item7`,
  142,142), Financial Statements + Auditor Reports (`part2item8`, 198,860), Business
  Description (`part1item1`, 108,056), and others. See `reports/short_segment_analysis.json`
  and `thoughts/shared/research/2026-02-23_18-30-00_segment_strategy_classifier_input.md` §5 S5.
- **Boilerplate frame shift (OQ-PRD-1 revised, 2026-02-24):** `analyse_short_segments.py`
  shows the 52.7% text-preview duplication rate in the ≤100-word population has **two
  distinct causes**: (a) **dispatch contamination** — non-`part1item1a` sections should not
  be in the run (fix: dispatch config filter); and (b) **within-Item-1A boilerplate** —
  `_is_non_risk_content` (`segmenter.py:337-368`) only filters 5 surface patterns and misses
  auditor opinion language (655 repeats), "Table of Contents" navigation, financial statement
  headers ("Notes to Consolidated Financial Statements", 73-93 repeats/variant), and
  "REPORT OF MANAGEMENT RESPONSIBILITIES" (5,241 segments, 13.3% unique). Both causes must
  be addressed independently. Problem frame revised: the S1–S4 short-segment length strategy
  is obsolete (0.01% of corpus is sub-20-word at full scale); the operative problem is
  **boilerplate content contamination**.
- **Diagnostic scripts added:** `scripts/validation/data_quality/diagnose_short_segments.py`
  (Tasks 1, 2, 3: bracket sampling, fill rate, section contamination),
  `scripts/validation/data_quality/token_profile.py` (DeBERTa token profiling),
  `scripts/validation/data_quality/analyse_short_segments.py` (dedup / pattern / subsection
  analysis). `sentencepiece>=0.1.99` added to `pyproject.toml` (required by
  `DebertaV2TokenizerFast`).
- **`parent_subsection` fill rate:** 100% across all 607,463 segments. OQ-S3 (from
  segment strategy research) closed; S3 context prefix injection is viable for the full corpus.

### What changed 2026-02-24 (`char_count` alias fix + G-02 loss measurement)

- **`segments[].char_count` key corrected** — `_build_output_data` was emitting `'length'`
  (wrong key); now emits `'char_count'` (matching the field name in `RiskSegment`).
  `load_from_json` old-schema fallback extended to read `char_count or length` so all
  v2.1 files already on disk load with correct values (not 0).
  `HealthCheckValidator._check_substance` updated from `seg.get("length", …)` to
  `seg.get("char_count", …)` (3-file change: `run_preprocessing_pipeline.py`,
  `segmentation.py`, `qa_validation.py`).
- **G-02 loss formula now self-contained in `*_segmented.json`** — two new fields added
  to `section_metadata.stats`: `raw_section_char_count` (len of extracted text
  pre-TextCleaner) and `cleaned_section_char_count` (len post-TextCleaner). Previously
  the G-02 denominator required joining to the `extracted/` directory;
  it is now computable from the segmented file alone:
  `pipeline_loss = (raw − Σ segment.char_count) / raw`. Implemented in all three
  serialisation paths: `pipeline.py` (worker), single-file CLI path, batch CLI path,
  plus `save_to_json` / `load_from_json` round-trip in `segmentation.py`.
  Measured on AAPL 10-K 2021 part1item1a: `raw=66,278`, `cleaned=66,278`,
  `Σ segment.char_count=66,085`, `pipeline_loss=0.29%` — well below the 5% gate.
- **`metadata.text_char_count` added to `_parsed.json`** — sum of element text chars
  after `sec-parser` strips HTML markup. AAPL 2021: `text_char_count=211,751` vs
  `html_size=2,051,191` (89.7% was markup). Enables detection of filings where
  sec-parser under-extracted.
- **`char_count` added to each element in `_extracted.json` / `_cleaned.json`** — one
  new field per element dict in the extractor serialisation loop (`extractor.py`).
  Enables per-element cleaning impact measurement and outlier-length detection without
  re-reading the `text` field. All 66 elements in AAPL 2021 part1item1a verified
  correct (`char_count == len(text)` for every element).

### What changed 2026-02-20 (token safety / RFC-003)

- **OQ-RFC3-1 answered:** 2.75% of current corpus segments (28 / 1,019) exceed the 380-word
  Option A ceiling (~513 tokens at 1.35 tok/word). ABBV pharma filings are the outlier at 5–9%;
  max observed segment is 1,141 words (~1,540 estimated tokens). See research
  `thoughts/shared/research/2026-02-20_14-20-37_oq_rfc3_1_segment_word_count_distribution.md`.
- **`over_limit_word_rate` gatekeeper check live:** `HealthCheckValidator._check_substance` now
  measures and reports the fraction of segments exceeding 380 words. Threshold in
  `configs/qa_validation/health_check.yaml`: WARN > 0%, FAIL > 5% (ModernBERT trigger).
  Pre-Option-A batches will WARN; post-Option-A batches should PASS.
- **Distribution script added:** `scripts/validation/data_quality/check_word_count_distribution.py`
  — standalone bucket histogram, per-filing breakdown, `--fail-above` CI enforcement flag.
- **RFC-003 drafted:** `docs/architecture/rfc/RFC-003_segment_token_length_enforcement.md`
  defines Option A (word-count ceiling, implementable now) and Option B (tokenizer-aware split,
  after G-12). Option A is the spec for US-015.

---

## 2. Goals & Non-Goals

### Goals

> **G-07 removed.** "Parsing success rate KPI in run summary" is an observability mechanism, not an independent goal. Its requirement (parse success rate visible in `RUN_REPORT.md` and `batch_summary_{run_id}.json`) is captured in G-01's measurement spec and §4.3 Observability. US-005 re-linked to G-01.

| ID | Priority | Since | Goal | Status | Stories |
|:---|:---------|:------|:-----|:-------|:--------|
| G-01 | P0 | PRD-001 | Parse ≥95% of EDGAR HTML 10-K/10-Q filings — success rate `(total_submitted − dlq_size) / total_submitted ≥ 0.95` reported in `RUN_REPORT.md` and `batch_summary_{run_id}.json`, on a stratified random sample of ≥30 filings spanning ≥5 SIC sectors and filing years 2019–2024 | ❌ **Measured (run `20260223_182806`, 959 filings, 88 SIC codes): (816+45)/959 = 89.8% — BELOW ≥95% KPI gate.** Breakdown: success=816, warning=45, error=98 (DLQ). Run report states 85.1% (816/959 strict). Scale and sector requirements met (959 >> 30 filings; 88 SIC codes >> 5 required). Root cause: 98 DLQ failures all tagged "unknown" — concentrated in CAH, COP, C tickers. OQ-7-adjacent: DLQ drain + root-cause investigation needed before KPI can be cleared. | US-005 |
| G-02 | P0 | PRD-001 | Extract Item 1A with < 5% character loss — `(raw_section_char_count − Σ segment.char_count) / raw_section_char_count < 0.05`, using `RiskSegment.char_count` fields in `*_segmented.json`, on the same ≥30-filing stratified sample as G-01 | ✅ **Measured (run `20260223_182806`, 783 `part1item1a` filings): 100% pass. Median=0.44% · P95=1.62% · max=3.59% (GD tickers) — all below 5% gate.** Schema gap CLOSED (2026-02-24): `segments[].char_count` key corrected (was `length`); `raw_section_char_count` / `cleaned_section_char_count` added to `section_metadata.stats` — G-02 formula computable from `*_segmented.json` directly, no join to `extracted/` required. | — |
| G-03 | P1 | PRD-001 | Segment risk text into atomic, classifiable statements — every output segment must satisfy `50 ≤ char_count ≤ 2000` and `word_count ≥ 20` (configurable via `preprocessing.min/max_segment_length`; raised from 10 to align with classifier training quality gate); every processed filing must produce ≥ 1 segment | ✅ **RFC-003 Option A deployed** (commit `0872eb3`, ADR-012): `max_segment_words: 380` enforced in `_split_long_segments`; `over_limit_word_rate` gate live. Full-corpus token p95=226 (§9.3 gate PASS). **Remaining gap: 81.5% of corpus is non-target-section content** (see OQ-PRD-1) — training data must be filtered to `part1item1a` before annotation | US-015 |
| G-04 | P0 | PRD-001 | Output JSONL compatible with HuggingFace `datasets.load_dataset("json", ...)` — each record must have `text` (str, column name exact) and `label` (int 0–8); full schema defined in §2.1.2 | ❌ Currently outputs JSON, not JSONL; column is named `text` in schema but pipeline emits nested `segments[].text` — conversion not yet implemented | US-001 |
| G-05 | P0 | PRD-001 | Pipeline must be resumable — crashed runs continue from checkpoint | ✅ `CheckpointManager` + `ResumeFilter` + `--resume` flag | US-002 |
| G-06 | P1 | PRD-001 | Batch CLI: 10,000 filings < 2 hours on 32-core node | ❌ Not benchmarked | — |
| G-08 | P1 | PRD-002 | Memory-aware adaptive timeout per file size category | ✅ `MemorySemaphore` + `FileCategory` (Small/Medium/Large) | — |
| G-09 | P0 | PRD-002 | Dead Letter Queue for malformed filings with drain on final run | ✅ `DeadLetterQueue` | US-003 |
| G-10 | P2 | PRD-002 | Stamped run directories with full provenance | ✅ `{YYYYMMDD_HHMMSS}_preprocessing_{git_sha}/` | — |
| G-11 | P1 | PRD-002 | Inline QA validation / quarantine pattern | ✅ `HealthCheckValidator` + `process_and_validate()` | — |
| G-12 | P0 | PRD-002 | SASB-aware risk classifier integrated into `process_batch()` — every output segment carries `risk_label` (archetype str), `sasb_topic` (SASB material topic for this company's industry), `sasb_industry`, `confidence`, and `label_source`; segments with confidence < 0.7 fall back to heuristic | ❌ `src/analysis/inference.py` (zero-shot, single label) and `scripts/feature_engineering/auto_label.py` (SASB-aware zero-shot) both exist but neither is wired into `process_batch()`; two-layer output not yet implemented | US-029 |
| G-15 | P0 | PRD-002 | Create SASB taxonomy data files: `src/analysis/taxonomies/sasb_sics_mapping.json` (SIC → SASB industry → material topics) and `src/analysis/taxonomies/archetype_to_sasb.yaml` (archetype → SASB topic crosswalk per industry) — hard dependency for G-12; `TaxonomyManager` returns `{}` without them | ❌ Neither file exists; `taxonomy_manager.py` loads them at line 125 but silently returns empty on missing file | US-030 |
| G-16 | P0 | PRD-002 | Build labeled annotation corpus (`data/processed/annotation/{train,validation,test}.jsonl`) meeting §2.1.2 quality gates: ≥ 500 examples per non-`other` archetype in train, test set from real EDGAR segments only, Cohen's Kappa ≥ 0.80, SHA-256 dedup across splits | ❌ No annotation corpus exists; `data/processed/synthesized_risk_categories.jsonl` referenced in OQ-12 does not yet exist | US-031 |
| G-13 | P0 | PRD-002 | CLI sector filter (`--sic` / `--ticker`) for targeted dataset builds | ❌ Not implemented | US-004 |
| G-14 | P0 | PRD-002 | NLP features (sentiment, readability, topic) inline in primary output record | ❌ Features exist in separate scripts; not unified | US-008 |

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
  `answerdotai/ModernBERT-base` (max 8,192 tokens) if >5% of corpus segments exceed 390 words
  after Option A deployment; requires `transformers>=4.48.0`. **Option A deployed 2026-02-24
  (commit `0872eb3`, ADR-012). Full-corpus token profile (607K segments): p95=226 tokens —
  ModernBERT contingency NOT triggered. DeBERTa-v3-base confirmed as production model.**
  Runs on local GPU or cloud node (not yet specified).
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
| **Test regression** | Any of 715 collected tests fail in CI | [CI not yet configured] |

---

## 5. Phase-Gate Delivery Plan

We do not proceed to the next phase without meeting the Exit Criteria.

### Phase 1 — Discovery & Feasibility (Complete)

**Focus:** EDA, data cleaning, baseline modeling, pipeline infrastructure.

**Deliverables:** `src/preprocessing/` pipeline, 715-test suite, `RUN_REPORT.md`, `StateManager`.

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
- [ ] Fix 2 test collection errors (`test_pipeline_global_workers.py`, `test_validator_fix.py`); all 715 tests pass
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
> Next available story ID: US-032.

| ID | Priority | As a… | I want to… | So that… | Status | Goal | Detail |
|:---|:---------|:------|:-----------|:---------|:-------|:-----|:-------|
| US-001 | **P0** | Data Scientist | Run the full pipeline on a directory of HTML filings and receive **JSONL** output with `text`, `risk_label`, `sasb_topic`, `sasb_industry`, `confidence`, and `label_source` per segment | I get a HuggingFace-compatible dataset without format conversion or post-processing | ⚠️ Batch mode ✅; output is JSON not JSONL; two-layer fields absent — story scenario B outdated, needs update for new schema | G-04, G-12 | [→](stories/US-001_batch_pipeline_execution.md) |
| US-002 | **P0** | ML Engineer | Resume a crashed pipeline run | I don't lose hours of compute | ✅ `--resume` + `CheckpointManager` | G-05 | [→](stories/US-002_pipeline_resume.md) |
| US-003 | **P0** | ML Engineer | Route malformed filings to a Dead Letter Queue | Pipeline does not halt on bad input | ✅ `DeadLetterQueue` | G-09 | [→](stories/US-003_dead_letter_queue.md) |
| US-004 | **P0** | Data Scientist | Filter filings by ticker or SIC code **at the CLI before processing** | Build sector-specific sets without wasting compute on irrelevant filings | ❌ CLI flag not implemented | G-13 | [→](stories/US-004_sector_filtering.md) |
| US-005 | **P1** | Data Scientist | Inspect which filings failed and why | I can improve parser/extractor logic | ✅ `RUN_REPORT.md`, DLQ log, `_progress.log` | G-01 | [→](stories/US-005_failure_inspection.md) |
| US-006 | **P1** | Financial Analyst | View extracted risk segments in Streamlit UI | I can validate quality without writing code | ⚠️ `src/visualization/app.py` exists; integration status unknown | — | [→](stories/US-006_streamlit_ui.md) |
| US-007 | **P1** | ML Engineer | Configure all pipeline settings via YAML + env vars | I can deploy to different environments | ✅ 16-module config system; Pydantic V2 + env-prefix | — | [→](stories/US-007_yaml_config.md) |
| US-008 | **P0** | Data Scientist | Get sentiment, readability, and topic features **inline in the primary JSONL record** | Load one file and train immediately without complex joins | ❌ Features exist in separate scripts; not unified | G-14 | [→](stories/US-008_nlp_features.md) |
| US-013 | **P1** | Data Scientist | See a class distribution report after every annotation run showing example counts per archetype | Know which archetypes are below the ≥ 500 minimum before training begins | ❌ Not implemented | G-16 | [→](stories/US-013_class_balance_reporting.md) |
| US-015 | **P1** | Data Scientist | Have long segments split at natural sentence breaks to fit within the model token limit | No segment is silently truncated mid-sentence by the tokenizer | ✅ **Implemented** (commit `0872eb3`): `max_segment_words: 380` in `_split_long_segments` + `_split_into_chunks`; full-corpus token p95=226; over-512 rate=0.45% (2,713 segments). ADR-012 documents the decision. | G-03 | [→](stories/US-015_token_aware_truncation.md) |
| US-016 | **P1** | Data Scientist | Get a deterministic train / validation / test split that keeps each company entirely in one set | The model never sees the same company in both training and evaluation | ❌ Not implemented | G-16 | [→](stories/US-016_reproducible_splitting.md) |
| US-028 | **P0** | Domain Expert | Review zero-shot predictions and save corrected labels to the annotation JSONL | The annotation corpus has human-verified labels before training begins | ❌ Not implemented (sourced from PRD-004; required by G-16 quality gate / QR-01) | G-16 | [→](stories/US-028_annotation_labeler_ui.md) |
| US-029 | **P0** | ML Engineer | Have `process_batch()` emit `risk_label`, `sasb_topic`, `sasb_industry`, `confidence`, and `label_source` on every segment using a SASB-aware classifier | Every filing in the batch is labeled with industry-specific SASB context, not just a generic category | ❌ Not implemented | G-12 | [→](stories/US-029_sasb_aware_classifier_integration.md) |
| US-030 | **P0** | Data Engineer | Create `sasb_sics_mapping.json` and `archetype_to_sasb.yaml` covering every SIC code in the target corpus | `TaxonomyManager` returns a non-empty topic set for every filing; the SASB crosswalk is available at inference time | ❌ Not implemented | G-15 | [→](stories/US-030_sasb_taxonomy_data_files.md) |
| US-031 | **P0** | ML Engineer | Build a labeled annotation corpus with ≥ 500 examples per archetype, a contamination-free test split, and Cohen's Kappa ≥ 0.80 documented | The fine-tune training run has a quality-gated dataset and a valid evaluation baseline | ❌ Not implemented | G-16 | [→](stories/US-031_annotation_corpus_build.md) |

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

### Inputs

Two distinct datasets flow through this pipeline. See §2.1 for full specifications.

| Dataset | Source | Location | Owner |
|:--------|:-------|:---------|:------|
| **Raw EDGAR filings** (§2.1.1) | EDGAR HTML 10-K / 10-Q via `sec-downloader` | `data/raw/` — HTML, UTF-8 (latin-1 fallback) | Data Eng |
| **Annotation corpus** (§2.1.2) | EDGAR segments + LLM silver labels + LLM synthetic gap-fill | `data/processed/annotation/{train,validation,test}.jsonl` | ML Engineer |

The annotation corpus does not yet exist (G-16). The raw EDGAR corpus is present and processable today.

### Batch Pipeline Output — Current (v2.1)

What `_build_output_data()` actually emits today (one JSON file per section per filing,
written to `{run_dir}/{stem}_{section}_segmented.json`):

```json
{
  "version": "2.1",
  "filing_name": "AAPL_10K_2021.html",
  "document_info": {
    "company_name": "Apple Inc.",
    "ticker": "AAPL",
    "cik": "0000320193",
    "sic_code": "3571",
    "sic_name": "ELECTRONIC COMPUTERS",
    "form_type": "10-K",
    "fiscal_year": "2021",
    "accession_number": "0000320193-21-000105",
    "filed_as_of_date": "20211029",
    "amendment_flag": false,
    "entity_filer_category": "Large Accelerated Filer",
    "ein": "94-2404110",
    "dei": {}
  },
  "processing_metadata": {
    "parser_version": "1.0",
    "finbert_model": "ProsusAI/finbert",
    "chunking_strategy": "sentence_level",
    "max_tokens_per_chunk": 512
  },
  "section_metadata": {
    "identifier": "part1item1a",
    "title": "Item 1A. Risk Factors",
    "cleaning_settings": {
      "removed_html_tags": true,
      "normalized_whitespace": true,
      "removed_page_numbers": true,
      "discarded_tables": true
    },
    "stats": {
      "total_chunks": 118,
      "num_tables": 0,
      "raw_section_char_count": 66278,
      "cleaned_section_char_count": 66278
    }
  },
  "num_segments": 118,
  "sentiment_analysis_enabled": false,
  "segments": [
    {
      "id": "1A_001",
      "parent_subsection": "Macroeconomic and Industry Risks",
      "text": "...",
      "char_count": 499,
      "word_count": 85
    }
  ]
}
```

> **Gap vs PRD-001:** PRD-001 specified flat JSONL output. Actual code emits nested JSON
> (`version: "2.1"`). Flat JSONL conversion not yet implemented (G-04 / US-001).
>
> **OQ-8:** The `save_to_json()` path in `SegmentedRisks` emits `"version": "1.0"` in a
> different nested schema (`document_info / chunks`). Both serialisers write correct
> `char_count` as of 2026-02-24; schema version alignment is tracked in §11 Group 3 item 11.

### Batch Pipeline Output — Phase 2 Target (per-segment inference JSONL)

What `process_batch()` must emit after classifier integration (G-12, US-029). One flat JSON object per segment, loadable via `datasets.load_dataset("json", ...)`:

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

**`label_source` enum — inference output** (two values only):

| Value | Meaning |
|:------|:--------|
| `"classifier"` | Fine-tuned or zero-shot ML model assigned the label; confidence ≥ configured threshold (default 0.7) |
| `"heuristic"` | Keyword heuristic (§3.1 baseline) assigned the label; confidence < threshold or model unavailable |

> **Note:** The training annotation corpus uses a different `label_source` enum (`"human"` | `"llm_silver"` | `"llm_synthetic"` | `"heuristic"`) to record data provenance — see §2.1.2. These are distinct schemas sharing the same field name; do not conflate them.

### Annotation Corpus Schema (Training Data)

Full JSONL schema and quality gates are defined in **§2.1.2**. One record per segment:

```jsonl
{"text": "...", "label": 0, "sasb_topic": "Data_Security", "sasb_industry": "Software & IT Services",
 "sic_code": "7372", "ticker": "MSFT", "filing_date": "2023-10-15",
 "label_source": "llm_silver", "llm_confidence": 0.91, "human_verified": false}
```

`label_source` values in training corpus: `"human"` | `"llm_silver"` | `"llm_synthetic"` | `"heuristic"`

### Risk Taxonomy — Two-Layer Schema

The taxonomy uses a hierarchical two-layer design grounded in the SASB Materiality Map.
See research `2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md` §2 for full rationale.

**Layer 1 — Archetype labels** (what the ML classifier trains on; 9 classes):

`cybersecurity` (0) · `regulatory` (1) · `financial` (2) · `supply_chain` (3) · `market` (4) · `esg` (5) · `macro` (6) · `human_capital` (7) · `other` (8)

Stored as integer `label` (0–8) in training JSONL. Stored as string `risk_label` in inference output.

**Layer 2 — SASB material topics** (industry-specific; derived via lookup, not ML):

- Authoritative data: `src/analysis/taxonomies/sasb_sics_mapping.json` — maps SIC codes to SASB industries and material topics. Loaded by `TaxonomyManager` at `taxonomy_manager.py:125`. **File does not yet exist (G-15 / US-030).**
- Crosswalk: `src/analysis/taxonomies/archetype_to_sasb.yaml` — maps each archetype + SASB industry → SASB topic name. **File does not yet exist (G-15 / US-030).**
- At inference time: `TaxonomyManager.get_topics_for_sic(sic_code)` → `sasb_industry`; crosswalk maps archetype → `sasb_topic`.

| Archetype | Software & IT Services | Commercial Banks | Oil & Gas E&P |
|:----------|:-----------------------|:-----------------|:--------------|
| `cybersecurity` | `Data_Security` | `Data_Security` | `Data_Security` |
| `regulatory` | `Managing_Systemic_Risks_from_Technology_Disruption` | `Systemic_Risk_Management` | `Management_of_the_Legal_&_Regulatory_Environment` |
| `financial` | `Competitive_Behavior` | `Financial_Inclusion_&_Capacity_Building` | `Reserves_Valuation_&_Capital_Expenditures` |
| `esg` | `Environmental_Footprint_of_Hardware_Infrastructure` | `Environmental_Risk_to_Mortgaged_Properties` | `Greenhouse_Gas_Emissions` |
| `human_capital` | `Recruiting_&_Managing_a_Skilled_Workforce` | `Employee_Incentives_&_Risk_Taking` | `Workforce_Health_&_Safety` |

> **Deprecated:** `src/analysis/taxonomies/risk_taxonomy.yaml` was hardcoded to Software & IT
> Services only and is superseded by `sasb_sics_mapping.json`. Retained for reference only; not loaded by any active code path.

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
| **Testability** | ≥ 715 unit tests; 2 collection errors | ⚠️ Fix 2 collection errors |
| **Provenance** | Stamped run dirs with git SHA | ✅ `{YYYYMMDD_HHMMSS}_preprocessing_{sha}/` |

### Runtime Dependencies

```toml
sec-parser==0.54.0              # PINNED — semantic filing parser
sec-downloader>=0.10.0
transformers>=4.35.0            # DeBERTa-v3-base; >=4.48.0 if ModernBERT contingency triggered
sentencepiece>=0.1.99           # Required by DebertaV2TokenizerFast (token_profile.py)
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
| OQ-1 | Should HTML tables be extracted as markdown or discarded? | Data Eng | **Resolved** — PRD-003 Fixes 2A and 2B strip all `TableElement` and `TableOfContentsElement` nodes before segmentation. Tables are discarded; no table text reaches the classifier. See PRD-003 §4. |
| OQ-2 | Acceptable text-loss threshold for inline XBRL filings? | Data Scientist | **Resolved** — G-02 sets the threshold at < 5% character loss: `(raw_item1a_char_count − Σ segment.char_count) / raw_item1a_char_count < 0.05`. `sec-parser==0.54.0` handles inline XBRL variants; the same threshold applies. |
| OQ-3 | Fine-tuning: full segment text or truncate to 512 tokens? | ML Engineer | **Resolved** — truncate to 512 for FinBERT / DeBERTa-v3-base. RFC-003 Option A deployed (ADR-012). **Full-corpus measurement 2026-02-24 (607,463 segments, run `20260223_182806`):** p50=58 · p95=**226** · p99=399 · max=3,886 tokens. Over-512: 2,713 (0.45%). Danger zone 360–512: 5,736 (0.94%). ModernBERT contingency NOT triggered (p95 ≪ 400 gate). `reports/token_profile.json`. See also `2026-02-20_14-20-37_oq_rfc3_1_segment_word_count_distribution.md`. |
| OQ-4 | Output format: convert to JSONL for HuggingFace `datasets`? | ML Engineer | **Resolved** — JSONL confirmed; full schema (`text`, `label`, `sasb_topic`, `sasb_industry`, `label_source`, etc.) defined in §2.1.2 and §8. Tracked as G-04 / US-001. |
| OQ-5 | Batch throughput: is 10K filings / 2 hrs achievable with transformer inference active? | ML Engineer | Open — cannot measure until classifier is wired in (G-12). Tracked in §11 Group 4 item 13 (throughput benchmark on ≥ 100 filings). Phase 3 hard requirement (G-06). |
| OQ-6 | Integrate zero-shot / fine-tuned classifier into batch pipeline? | ML Engineer | **Resolved** — tracked as G-12 / US-029. Integration point is `scripts/feature_engineering/auto_label.py` (SASB-aware zero-shot, Stage A); fine-tuned model swap is Stage B (PRD-004). See §11 Group 2 item 9. |
| OQ-7 | Fix 2 test collection errors (`test_pipeline_global_workers.py`, `test_validator_fix.py`) | Eng | Open — `ZeroDivisionError` in `test_pipeline_global_workers.py`; import error in `test_validator_fix.py`. Tracked in §11 Group 4 item 14. Blocking the "715 tests pass" coverage claim. |
| OQ-8 | Schema version: align code output (`"version": "1.0"`) with CHANGELOG claim (`"2.0"`). | Eng | Open — tracked in §11 Group 3 item 11. Resolve before Phase 2 exit. |
| OQ-9 | Which experiment tracking system: MLflow or W&B? | ML Engineer | Open — blocks Phase 2 exit gate (model checkpoint logging required). Decision needed before first fine-tune training run. |
| OQ-10 | Which orchestration system: Airflow or Dagster for scheduled retraining? | Eng Lead | Open — blocks Phase 3. Not required for Phase 2. |
| OQ-11 | **Materiality Audit:** How do we verify 0% loss for critical "Black Swan" triggers (e.g., "Default", "GDPR", "Litigation") through `TextCleaner`? | Data Eng | Open — tracked in §11 Group 1 item 5. Must complete before test holdout (item 6) — a hard prerequisite, not optional. |
| OQ-12 | **HITL Loop:** How will analysts correct misclassifications? | Product | **Resolved** — PRD-004 G-09 and US-028 define the HITL labeler UI (`src/visualization/labeler_app.py`); corrected labels are appended to `data/processed/annotation/train.jsonl` (annotation corpus, §2.1.2) with `"label_source": "human"`, `"human_verified": true`. |
| OQ-13 | **Unit Cost:** What is the per-filing cost for GPU inference vs. business value? | FinOps | Open — depends on final model choice (FinBERT vs DeBERTa vs ModernBERT) and hosting strategy. Revisit after Phase 2 model selection. |
| OQ-T1 | What SIC codes are present in the target corpus? Determines which industries `sasb_sics_mapping.json` must cover. Run: `grep -h "sic_code" data/processed/**/*.json \| sort \| uniq -c \| sort -rn` | Data Eng | Open — prerequisite to building `sasb_sics_mapping.json`. Tracked in §11 Group 1 item 1. |
| OQ-T2 | Should `sasb_topic` in the output record be a single string or a list? | ML Engineer | **Resolved** — single `str`. The `archetype_to_sasb.yaml` crosswalk returns the most specific SASB topic for the `(archetype, sasb_industry)` pair; first match wins. Defined in §8 Phase 2 target schema. |
| OQ-T3 | The `macro` archetype (interest rates, FX, inflation) has no single clean SASB topic. Should `sasb_topic` be `"Other_General_Risk"` or `null` for `macro`? | Data Scientist | Open — blocks `archetype_to_sasb.yaml` default entry for `macro`. Recommendation: use `"Macro_Environment"` as a project-defined label (not official SASB) rather than `null`, to prevent downstream null-handling complexity. Decision needed in US-030. |
| OQ-T4 | Should the annotation UI (US-028) present only the industry's SASB topics as label options, or also allow `"Other_General_Risk"` as a fallback? | Product | Open — blocks annotation UI design in US-028. Suggested: show industry SASB topics + `"other"` archetype as escape hatch; do not expose `"Other_General_Risk"` as a separate choice to avoid label proliferation. |
| OQ-PRD-1 | **Section contamination + within-Item-1A boilerplate (two-cause problem).** Phase A (2026-02-24) found two distinct boilerplate causes in the ≤100-word population (52.7% duplicate rate): **(a) Dispatch contamination** — 81.5% of corpus is non-`part1item1a` content: `part2item8` (198,860 segs), `part2item7` (142,142), `part1item1` (108,056), `part2item7a` (37,957), `part1item1c` (5,296), `part1item1b` (2,979). Fix: dispatch config filter to `part1item1a` only. **(b) Within-Item-1A boilerplate** — `_is_non_risk_content` (`segmenter.py:337-368`) has only 5 surface patterns and misses auditor opinion text (655 repeats), ToC navigation, financial statement headers, and "REPORT OF MANAGEMENT RESPONSIBILITIES" (5,241 segs, 13.3% unique). Fix: strengthen `_is_non_risk_content` heuristics or add upstream boundary correction. **Decision needed for (a):** configurable dispatch list vs. single-section enforcement for annotation runs. Both (a) and (b) must be addressed before annotation corpus construction. S1–S4 length-based strategies are obsolete (sub-20-word segments = 0.01% of full corpus). See `reports/short_segment_analysis.json`, `reports/short_segment_patterns.tsv`, and segment strategy research §5 S5. | Data Eng / Eng Lead |

---

## 11. Work Remaining for Fine-Tune Readiness

The following gaps must close before the pipeline can produce a HuggingFace-ready fine-tune dataset.
Items are ordered by dependency — each group unblocks the next.

### Group 1 — Taxonomy & Data (unblocks Group 2)

1. **Corpus SIC audit** (OQ-T1) — run `grep -h "sic_code" data/processed/**/*.json | sort | uniq -c | sort -rn` on any batch output to get the actual SIC distribution before building the mapping. Prevents over-engineering coverage for industries absent from the corpus.

2. **`sasb_sics_mapping.json`** (G-15) — create `src/analysis/taxonomies/sasb_sics_mapping.json` covering all SIC codes found in step 1. Schema and priority-industry content defined in research `2026-02-19_14-53-50_sasb_materiality_taxonomy_architecture.md` §4.1. `taxonomy_manager.py:125` requires no code changes — it already loads this file.

3. **`archetype_to_sasb.yaml`** (G-15) — create `src/analysis/taxonomies/archetype_to_sasb.yaml` with per-industry mappings and a `default` entry for every archetype. Resolve OQ-T3 (`macro` archetype mapping) before finalising. Schema defined in research §4.2.

4. **Section contamination fix — filter to `part1item1a` only** (OQ-PRD-1, new prerequisite)
   — the current run `20260223_182806` contains 81.5% non-target-section content (MD&A,
   Financial Statements, Business Description). Before items 5–8 can proceed, a clean
   `part1item1a`-only corpus must be produced. Two implementation options:
   - **(a) Config-level dispatch filter** — add a `section_filter: [part1item1a]` option to
     the pipeline dispatch config so future runs only process Item 1A files. Re-run the batch.
   - **(b) Post-hoc filter script** — add a script that copies only `*_part1item1a_segmented.json`
     files from the existing run into a new target directory. Faster but doesn't fix the
     pipeline for future runs.
   Option (a) is preferred; the re-run must complete before item 5 (materiality audit).
   **True Item 1A corpus: 112,173 segments across 4,423 filings** (from run `20260223_182806`
   `part1item1a` files). This is the baseline for all annotation corpus sizing calculations.

4a. **Segmenter word-count floor** (G-03) — `min_segment_words` is already present in
   `PreprocessingConfig` and `_merge_short_segments` is live. RFC-003 Option A
   (`max_segment_words: 380`) is **deployed** (commit `0872eb3`, ADR-012). No additional
   floor config changes needed. After the item 4 section filter re-run, verify
   `over_limit_word_rate = 0.0` via `check_word_count_distribution.py --fail-above 0.0`.

5. **Materiality retention audit** — run a "Keyword Survival" check confirming that critical risk terms (e.g., "Default", "Litigation", "GDPR", "Ransomware") survive `TextCleaner` in the fresh batch output from item 4. If any term is silently stripped, fix `TextCleaner` and re-run before proceeding. **Must complete before item 6** — contaminated segments in the test split cannot be recovered after freezing.

6. **Hold out test split** (G-16 prerequisite) — extract and freeze `data/processed/annotation/test.jsonl` from real EDGAR segments produced in item 4. Human-verify labels via US-028. This is a one-way gate: once LLM labeling starts on the remaining pool, test set contamination cannot be undone.

7. **Build annotation corpus** (G-16) — run the hybrid LLM pipeline (`scripts/feature_engineering/auto_label.py`, upgraded to Claude / GPT-4o LLM backend per research `2026-02-19_14-59-17_llm_synthetic_data_per_industry_models.md` §3) on the non-test segment pool: real segments + LLM silver labels (confidence ≥ 0.80) + synthetic gap-fill for archetypes with < 300 real examples (capped at 40% of train split). Produce `data/processed/annotation/{train,validation}.jsonl`.

8. **Annotation quality gate** (G-16 / QR-01) — sample 50 examples per SASB topic; two domain experts label independently; compute Cohen's Kappa. Must reach ≥ 0.80 before training begins. Document class imbalance ratio; apply weighted cross-entropy loss if ratio > 5:1.

### Group 2 — Classifier Integration (unblocks Group 3)

9. **SASB-aware classifier wired into `process_batch()`** (G-12 / US-029) — two stages:
   - **Stage A (zero-shot, immediate):** Wire `scripts/feature_engineering/auto_label.py` (SASB-aware, SIC-routed, `facebook/bart-large-mnli`) into `process_batch()`. Proves integration end-to-end; enables annotation review in item 7. `label_source: "classifier"` for confidence ≥ 0.7; `"heuristic"` below threshold.
   - **Stage B (fine-tuned, after PRD-004 training):** Swap `facebook/bart-large-mnli` for the fine-tuned FinBERT / DeBERTa checkpoint produced by `scripts/training/finetune.py` (PRD-004). Stage B does not change the integration contract — same fields, same fallback logic, higher F1.

   Both stages must satisfy: every output segment carries `risk_label`, `sasb_topic`, `sasb_industry`, `confidence`, `label_source`; confidence < 0.7 → heuristic fallback. Verify P95 latency ≤ 500ms.

### Group 3 — Output Format (G-04)

10. **JSONL flat output** (G-04) — add `save_to_jsonl()` to `SegmentedRisks` or convert in the batch CLI. Output must be flat per-segment records (not nested under `"segments": [...]`) with `text` as the exact column name and `label` as integer 0–8. Loadable via `datasets.load_dataset("json", ...)` without pre-processing. Schema: §8 "Batch Pipeline Output — Phase 2 Target" (not §2.1.2, which is the training corpus schema).

11. **Schema version** — resolve `"1.0"` vs `"2.0"` discrepancy between code output (`"version": "1.0"` in `SegmentedRisks`) and CHANGELOG claim (`"2.0"`). Align in code and document the resolution in CHANGELOG.

### Group 4 — Pipeline & Quality (independent)

12. **CLI filter flag** (G-13) — implement `--sic` / `--ticker` filter on `run_preprocessing_pipeline.py` for sector-specific dataset builds (US-004).

12a. ~~**Token safety — RFC-003 Option A**~~ ✅ **DONE** (commit `0872eb3`, ADR-012):
   `max_segment_words: 380` implemented in `_split_long_segments` + `_split_into_chunks`.
   Full-corpus token profile: p95=226 · p99=399 · over-512=0.45%. ModernBERT contingency
   not triggered. `check_word_count_distribution.py --fail-above 0.0` should pass on a
   fresh `part1item1a`-only run (pending item 4 section filter). No further action on
   RFC-003 Option A required.

13. **Throughput benchmark** — run end-to-end on ≥ 100 filings with Stage A classifier active; confirm < 2s/filing. Required before Phase 3 (G-06 / 10K filings in < 2 hrs).

14. **Fix 2 test collection errors** — resolve `ZeroDivisionError` in `test_pipeline_global_workers.py` and import error in `test_validator_fix.py`; all 715 tests pass.

15. **Line coverage** — unit test coverage > 80%; new taxonomy, annotation pipeline, and classifier integration code included.

### Best Practice Recommendations

16. **Human-in-the-Loop labeler UI** — enable label correction in the Streamlit dashboard (`src/visualization/labeler_app.py`, per OQ-12 / US-028) so analysts can correct misclassifications and append corrected records to `data/processed/annotation/train.jsonl` with `"label_source": "human"`, `"human_verified": true`.

17. **Recall-weighted evaluation** — update `scripts/evaluation/evaluate_model.py` to report $F_{\beta}$ ($\beta=2$) alongside Macro F1, penalising false negatives more heavily. Material risk misses are costlier than false alarms in a compliance context.

---

## 12. Business Impact (ROI)

The SEC Risk Factor Analyzer transforms a manual, high-latency research process into an automated, high-scale strategic asset. The two-layer output — universal archetype labels + industry-specific SASB material topics — is the core differentiation over generic risk classifiers.

### 12.1 Efficiency & Cost Reduction

| Metric | Manual Baseline | Automated (Phase 2 target) |
|:-------|:----------------|:---------------------------|
| Time per 10-K | 30–45 min (senior analyst reads, extracts, categorises Item 1A) | < 2s filing parse + ~500ms P95 per segment for classifier inference |
| Coverage | ~200–500 filings/year per analyst | 10,000 filings per annual EDGAR cohort |
| Consistency | Varies by analyst; no cross-industry label standard | Consistent 9-archetype taxonomy; SASB material topic per segment |

**Labor displacement estimate** (conservative): 10,000 filings × 37 min/filing ÷ 60 = ~6,200 analyst-hours.
At $100/hr (blended senior analyst rate), this is **~$620k in avoided research labor per annual cohort**.
The $50/hr floor scenario ($310k) applies if work is delegated to junior associates; the $200/hr ceiling ($1.24M) applies for portfolio manager-level review time.

### 12.2 Portfolio Risk Alpha

- **Universal coverage:** Enables 100% coverage of the SEC EDGAR universe — supply chain shifts, ESG liabilities, and macro regime changes detected across entire sectors, not just S&P 500 names.
- **Early warning signal:** Automated daily ingestion (US-019) targets T+24h freshness after EDGAR publication, providing a structural edge over analysts whose read cycle is weekly or quarterly.
- **Cross-industry comparability:** A single archetype label (`esg`, `cybersecurity`, `regulatory`, etc.) allows portfolio managers to compare risk concentration across SIC sectors that have no natural common vocabulary. SASB topics add industry-specific precision within each sector.

### 12.3 Strategic Value (Audit & Compliance)

- **SASB-grounded standardisation:** Output labels are derived from the SASB Materiality Map — the same standard used by institutional ESG ratings agencies. `sasb_topic` values (e.g., `Greenhouse_Gas_Emissions`, `Data_Security`) are directly mappable to SASB disclosure frameworks without manual translation.
- **Source traceability:** US-018 links every segment back to its original sentence in the SEC filing, reducing compliance audit overhead and enabling human review of any model output.
- **Explainability:** US-017 surfaces the specific tokens driving each classification, satisfying model governance requirements for ML-assisted investment decisions.
- **Human verification chain:** The HITL correction loop (US-028) appends domain-expert reviewed labels to the annotation corpus with `"human_verified": true`, creating an auditable record of label quality decisions.

### 12.4 Downstream Business Intelligence (PRD-004)

The pipeline output is consumed by PRD-004 business intelligence use cases that deliver value to non-ML stakeholders:

| Use Case | Story | Value |
|:---------|:------|:------|
| Competitive risk benchmarking | US-021 | Benchmark risk posture vs. peers without reading filings |
| M&A due diligence | US-023 | Side-by-side risk category comparison of acquisition targets as CSV |
| Supplier risk screening | US-022 | Update vendor risk register with structured, audited data |
| IR peer benchmarking | US-024 | Anticipate analyst questions before earnings calls |
| Risk change velocity | US-026 | Flag filings with major year-over-year structural shifts for immediate review |

These use cases are gated on Phase 2 delivery: they require the two-layer classifier output (`risk_label` + `sasb_topic`) that process_batch() does not yet produce.

### 12.5 MLOps Sustainability

- **Compounding accuracy:** The HITL annotation loop (US-028) appends corrected labels to `data/processed/annotation/train.jsonl`. Each correction cycle produces higher-quality training data for the next fine-tune run, compounding model accuracy without additional labeling cost.
- **Proprietary data moat:** The human-verified annotation corpus — real EDGAR segments labeled against the SASB taxonomy — is a dataset that cannot be replicated by zero-shot prompting. It represents the firm's unique IP in applying SASB materiality to SEC disclosure classification.
- **Reproducibility:** `RANDOM_SEED=42`, pinned `sec-parser==0.54.0`, and stamped run directories ensure any training run can be exactly reproduced from the same inputs.
