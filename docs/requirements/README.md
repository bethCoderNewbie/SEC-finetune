# Requirements

Index of product specification documents (PRDs) and user stories.

Naming convention: `PRD-{NNN}_{ShortName}.md` · `US-{NNN}_{slug}.md`

> **ADRs and RFCs** are engineering lifecycle documents. They live in and are indexed by
> [`docs/architecture/README.md`](../architecture/README.md), not here.

Status values: `DRAFT` · `IN-REVIEW` · `APPROVED` · `DEPRECATED`

---

## PRDs

| ID | Title | Status | Last Updated |
|----|-------|--------|-------------|
| [PRD-001](PRD-001_SEC_Finetune_MVP.md) | SEC 10-K Risk Factor Analyzer — MVP | APPROVED | 2026-02-18 |
| [PRD-002](PRD-002_SEC_Finetune_Pipeline_v2.md) | SEC Finetune Pipeline v2 — Current State & MLOps | APPROVED | 2026-02-18 |
| [PRD-003](PRD-003_Training_Data_Quality_Remediation.md) | SEC 10-K Training Data Quality Remediation | DRAFT | 2026-02-18 |
| [PRD-004](PRD-004_Business_Intelligence_Use_Cases.md) | SEC 10-K Business Intelligence — Multi-Stakeholder Use Cases | DRAFT | 2026-02-18 |

---

## User Stories

Stories follow the Card + Validation format:
- **Card:** `As a <Role>, I want <Action>, So that <Benefit>`
- **Validation:** Gherkin `Scenario / Given / When / Then` per acceptance criterion

Individual story files live in [`stories/`](stories/). PRD tables carry the one-line summary and link here for acceptance criteria.

### Epics

| Epic | Theme | P0 Stories | P1 Stories |
|------|-------|-----------|------------|
| **EP-1** Core Pipeline | Run, filter, and emit training-ready JSONL | US-001, US-004 | — |
| **EP-2** Resilience & Recovery | Survive crashes, bad input, and silent failures | US-002, US-003, US-010, US-020 | — |
| **EP-3** Data Quality | Produce corpus-ready, uncontaminated training text | US-009 | US-012, US-014 |
| **EP-4** Performance | Iterate on the full corpus within a work session | US-011 | — |
| **EP-5** Observability | Inspect failures, trace sources, and automate operations | US-005, US-007 | US-018, US-019 |
| **EP-6** ML Readiness | Enrich output and close the gap to a training-ready dataset | US-008 | US-006, US-013, US-015, US-016, US-017 |
| **EP-7** Business Applications | Deliver model output to non-ML stakeholders via query CLI and exports | US-021, US-023 | US-022, US-024, US-025, US-026, US-027 |

---

### EP-1 — Core Pipeline

| ID | Priority | Role | Action | Value | Status | Detail |
|:---|:---------|:-----|:-------|:------|:-------|:-------|
| [US-001](stories/US-001_batch_pipeline_execution.md) | **P0** | Data Scientist | Run full pipeline; receive JSONL output | HuggingFace-compatible dataset without format conversion | ⚠️ Batch ✅; JSONL not yet emitted | [Detail](stories/US-001_batch_pipeline_execution.md) |
| [US-004](stories/US-004_sector_filtering.md) | **P0** | Data Scientist | Filter by ticker / SIC code at the CLI before processing | Sector-specific training sets without wasting compute | ❌ CLI flag not implemented | [Detail](stories/US-004_sector_filtering.md) |

### EP-2 — Resilience & Recovery

| ID | Priority | Role | Action | Value | Status | Detail |
|:---|:---------|:-----|:-------|:------|:-------|:-------|
| [US-002](stories/US-002_pipeline_resume.md) | **P0** | ML Engineer | Resume a crashed run with `--resume` | Don't lose hours of compute | ✅ Implemented | [Detail](stories/US-002_pipeline_resume.md) |
| [US-003](stories/US-003_dead_letter_queue.md) | **P0** | ML Engineer | Route malformed filings to a Dead Letter Queue | Pipeline does not halt on bad input | ✅ Implemented | [Detail](stories/US-003_dead_letter_queue.md) |
| [US-010](stories/US-010_zero_segment_hard_fail.md) | **P0** | ML Engineer | Zero-segment filings produce a blocking QA FAIL | Silent empty training examples never reach the corpus | ❌ Not implemented (PRD-003 Phase 1) | [Detail](stories/US-010_zero_segment_hard_fail.md) |
| [US-020](stories/US-020_quality_circuit_breaker.md) | **P0** | Quality Owner | Halt the run automatically if > 5% of files fail quality checks | Don't train a model on a garbage corpus | ⚠️ Per-filing checks exist; batch halt not implemented | [Detail](stories/US-020_quality_circuit_breaker.md) |

### EP-3 — Data Quality

| ID | Priority | Role | Action | Value | Status | Detail |
|:---|:---------|:-----|:-------|:------|:-------|:-------|
| [US-009](stories/US-009_clean_training_corpus.md) | **P0** | Data Scientist | Corpus contains no ToC lines or HTML table text | Training loss decreases monotonically on clean prose | ❌ Not implemented (PRD-003 Phase 2) | [Detail](stories/US-009_clean_training_corpus.md) |
| [US-012](stories/US-012_sentence_boundary_quality.md) | **P1** | Data Scientist | Segments contain complete sentences, not split on abbreviations | Training examples express coherent risk arguments | ❌ Not implemented (PRD-003 Phase 3) | [Detail](stories/US-012_sentence_boundary_quality.md) |
| [US-014](stories/US-014_semantic_deduplication.md) | **P1** | Data Scientist | Near-duplicate segments identified and excluded from training split across filings and years | Prevent data leakage from year-over-year boilerplate copy-paste | ❌ Not implemented | [Detail](stories/US-014_semantic_deduplication.md) |

### EP-4 — Performance

| ID | Priority | Role | Action | Value | Status | Detail |
|:---|:---------|:-----|:-------|:------|:-------|:-------|
| [US-011](stories/US-011_anchor_parse_performance.md) | **P0** | Pipeline Operator | Parse filings in ≤ 3s (median) via anchor-based pre-seek | Iterate on the 887-filing corpus within a work session | ❌ Not implemented (PRD-003 Phase 4) | [Detail](stories/US-011_anchor_parse_performance.md) |

### EP-5 — Observability

| ID | Priority | Role | Action | Value | Status | Detail |
|:---|:---------|:-----|:-------|:------|:-------|:-------|
| [US-005](stories/US-005_failure_inspection.md) | **P1** | Data Scientist | Inspect which filings failed and exactly why | Improve parser/extractor logic iteratively | ✅ Implemented | [Detail](stories/US-005_failure_inspection.md) |
| [US-007](stories/US-007_yaml_config.md) | **P1** | ML Engineer | Configure all settings via YAML + env vars | Deploy to different environments without code changes | ✅ Implemented | [Detail](stories/US-007_yaml_config.md) |
| [US-018](stories/US-018_source_traceability.md) | **P1** | Audit / Compliance | Click a link on any segment to view the original sentence in the SEC filing | Verify context and accuracy without manual searching | ❌ Not implemented | [Detail](stories/US-018_source_traceability.md) |
| [US-019](stories/US-019_automated_daily_ingestion.md) | **P1** | Data Manager | System automatically checks for and processes new filings every 24 hours | Always working with up-to-date information without manual runs | ❌ Not wired | [Detail](stories/US-019_automated_daily_ingestion.md) |

### EP-6 — ML Readiness

| ID | Priority | Role | Action | Value | Status | Detail |
|:---|:---------|:-----|:-------|:------|:-------|:-------|
| [US-008](stories/US-008_nlp_features.md) | **P0** | Data Scientist | Mood (sentiment) and complexity (readability) scores inline in every JSONL record | Load one file, train immediately — no joins | ❌ Features exist separately; not unified | [Detail](stories/US-008_nlp_features.md) |
| [US-006](stories/US-006_streamlit_ui.md) | **P1** | Financial Analyst | View extracted segments in a Streamlit UI | Validate extraction quality without writing code | ⚠️ App exists; integration not confirmed | [Detail](stories/US-006_streamlit_ui.md) |
| [US-013](stories/US-013_class_balance_reporting.md) | **P1** | Data Scientist | Chart showing how many risks fall into each category after every run | Know if more examples of a specific risk type are needed | ❌ Not implemented | [Detail](stories/US-013_class_balance_reporting.md) |
| [US-015](stories/US-015_token_aware_truncation.md) | **P1** | Data Scientist | Split long paragraphs into shorter chunks at natural sentence breaks | AI model can process text within its input limits | ❌ Not implemented | [Detail](stories/US-015_token_aware_truncation.md) |
| [US-016](stories/US-016_reproducible_splitting.md) | **P1** | Data Scientist | Deterministic train/val/test split keeping each company entirely in one set | Model never sees the same company in both training and testing | ❌ Not implemented | [Detail](stories/US-016_reproducible_splitting.md) |
| [US-017](stories/US-017_model_explainability.md) | **P1** | Tools Manager | See the specific words that caused a risk classification | Understand and trust the model's logic | ❌ Not implemented | [Detail](stories/US-017_model_explainability.md) |

### EP-7 — Business Applications

| ID | Priority | Role | Action | Value | Status | Detail |
|:---|:---------|:-----|:-------|:------|:-------|:-------|
| [US-021](stories/US-021_competitive_benchmarking.md) | **P0** | Strategic Analyst | Query competitor risk profiles by category in a single CLI command | Benchmark risk posture without reading 300-page filings | ❌ Not implemented (PRD-004 Phase 3) | [Detail](stories/US-021_competitive_benchmarking.md) |
| [US-022](stories/US-022_supplier_risk_screening.md) | **P1** | Risk Manager | Query a supplier's 10-K for financial and operational risk signals | Update vendor risk register with audited, structured data | ❌ Not implemented (PRD-004 Phase 3) | [Detail](stories/US-022_supplier_risk_screening.md) |
| [US-023](stories/US-023_ma_due_diligence.md) | **P0** | Corporate Development Analyst | Get a side-by-side risk category comparison of acquisition targets as CSV | Identify material liabilities before issuing a letter of intent | ❌ Not implemented (PRD-004 Phase 3) | [Detail](stories/US-023_ma_due_diligence.md) |
| [US-024](stories/US-024_ir_peer_benchmarking.md) | **P1** | IR Manager | Benchmark risk disclosure against a SIC-code peer-group cohort | Anticipate analyst questions about risk concentration before earnings calls | ❌ Not implemented (PRD-004 Phase 4) | [Detail](stories/US-024_ir_peer_benchmarking.md) |
| [US-025](stories/US-025_sales_prospect_intelligence.md) | **P1** | Account Executive | Extract the top-N highest-confidence risk segments from a prospect's latest 10-K | Tailor sales pitch to the prospect's publicly disclosed pain points | ❌ Not implemented (PRD-004 Phase 3) | [Detail](stories/US-025_sales_prospect_intelligence.md) |
| [US-026](stories/US-026_risk_change_velocity.md) | **P1** | Risk Manager | See a change velocity score comparing current and prior-year risk language | Flag filings with major structural shifts for immediate deep review | ❌ Not implemented (PRD-004 Phase 5) | [Detail](stories/US-026_risk_change_velocity.md) |
| [US-027](stories/US-027_risk_prioritization_score.md) | **P1** | Portfolio Manager | Get a composite risk prioritization score (1–100) per company | Triage a watchlist of 50 companies in minutes, not hours | ❌ Not implemented (PRD-004 Phase 6) | [Detail](stories/US-027_risk_prioritization_score.md) |
| [US-028](stories/US-028_annotation_labeler_ui.md) | **P0** | Domain Expert / SME | Review zero-shot predictions and save corrected labels to a local JSONL file | `llm_finetuning/train.py` has human-validated training data | ❌ Not implemented (PRD-004 Phase 1, Step 1.4) | [Detail](stories/US-028_annotation_labeler_ui.md) |

---

## Other Files

| File | Purpose |
|------|---------|
| `requirements_cleaning.txt` | Python dependency list for the text-cleaning subsystem |
