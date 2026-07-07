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
| [PRD-002](PRD-002_SEC_Finetune_Pipeline_v2.md) | SEC Finetune Pipeline v2 — Current State & MLOps | DRAFT | 2026-02-19 |
| [PRD-003](PRD-003_Training_Data_Quality_Remediation.md) | SEC 10-K Training Data Quality Remediation | DRAFT | 2026-02-18 |
| [PRD-004](PRD-004_Business_Intelligence_Use_Cases.md) | SEC 10-K Business Intelligence — Multi-Stakeholder Use Cases | DRAFT | 2026-02-18 |
| [PRD-005](PRD-005_Agentic_Analysis_Workflow.md) | SEC 10-K Agentic Analysis Workflow — Agents, Skills & Commands | DRAFT | 2026-07-07 |

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
| **EP-6** ML Readiness | Enrich output and close the gap to a training-ready dataset | US-008, US-029, US-030, US-031, US-032 | US-006, US-013, US-015, US-016, US-017 |
| **EP-7** Business Applications | Deliver model output to non-ML stakeholders via query CLI and exports | US-021, US-023 | US-022, US-024, US-025, US-026, US-027 |
| **EP-8** Agentic Analysis | Analyze parsed 10-K output with agents, skills, and CLI commands to produce structured reports | US-033, US-034, US-035 | US-036, US-037, US-038, US-039, US-040, US-041 |

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
| [US-029](stories/US-029_sasb_aware_classifier_integration.md) | **P0** | ML Engineer | Wire SASB-aware classifier into `process_batch()` emitting two-layer output per segment | Every batch filing is labeled with archetype + SASB topic without post-processing | ❌ Not implemented | [Detail](stories/US-029_sasb_aware_classifier_integration.md) |
| [US-030](stories/US-030_sasb_taxonomy_data_files.md) | **P0** | Data Engineer | Create `sasb_sics_mapping.json` and `archetype_to_sasb.yaml` for all corpus SIC codes | `TaxonomyManager` returns non-empty SASB topics for every filing | ❌ Not implemented | [Detail](stories/US-030_sasb_taxonomy_data_files.md) |
| [US-031](stories/US-031_annotation_corpus_build.md) | **P0** | ML Engineer | Build quality-gated annotation corpus with ≥ 500 examples per archetype and clean test split | Fine-tune training has a valid dataset and the Macro F1 gate is measurable | ❌ Not implemented | [Detail](stories/US-031_annotation_corpus_build.md) |
| [US-032](stories/US-032_segment_annotator_jsonl_transform.md) | **P0** | ML Engineer | Run `SegmentAnnotator` to transform `*_segmented.json` into flat JSONL with all 14 required training fields | Annotation corpus build (US-031) has a reproducible, quality-gated input source | ❌ Not implemented | [Detail](stories/US-032_segment_annotator_jsonl_transform.md) |

### EP-7 — Business Applications

> **EP-7 / EP-8 supersession note:** US-021, US-023, US-026, and US-027 overlap directly with
> EP-8 stories that implement the same capabilities via the agentic analysis layer (PRD-005).
> Those four stories are marked **DEPRECATED** below; their EP-8 successors are the authoritative
> implementations. US-022, US-024, US-025, US-028 remain active (no EP-8 equivalent yet).

| ID | Priority | Role | Action | Value | Status | Detail |
|:---|:---------|:-----|:-------|:------|:-------|:-------|
| [US-021](stories/US-021_competitive_benchmarking.md) | **P0** | Strategic Analyst | Query competitor risk profiles by category in a single CLI command | Benchmark risk posture without reading 300-page filings | ~~❌ Not implemented~~ **DEPRECATED** — superseded by [US-038](stories/US-038_analyze_sector_command.md) (EP-8) | [Detail](stories/US-021_competitive_benchmarking.md) |
| [US-022](stories/US-022_supplier_risk_screening.md) | **P1** | Risk Manager | Query a supplier's 10-K for financial and operational risk signals | Update vendor risk register with audited, structured data | ❌ Not implemented (PRD-004 Phase 3) | [Detail](stories/US-022_supplier_risk_screening.md) |
| [US-023](stories/US-023_ma_due_diligence.md) | **P0** | Corporate Development Analyst | Get a side-by-side risk category comparison of acquisition targets as CSV | Identify material liabilities before issuing a letter of intent | ~~❌ Not implemented~~ **DEPRECATED** — superseded by [US-036](stories/US-036_compare_companies.md) (EP-8) | [Detail](stories/US-023_ma_due_diligence.md) |
| [US-024](stories/US-024_ir_peer_benchmarking.md) | **P1** | IR Manager | Benchmark risk disclosure against a SIC-code peer-group cohort | Anticipate analyst questions about risk concentration before earnings calls | ❌ Not implemented (PRD-004 Phase 4) | [Detail](stories/US-024_ir_peer_benchmarking.md) |
| [US-025](stories/US-025_sales_prospect_intelligence.md) | **P1** | Account Executive | Extract the top-N highest-confidence risk segments from a prospect's latest 10-K | Tailor sales pitch to the prospect's publicly disclosed pain points | ❌ Not implemented (PRD-004 Phase 3) | [Detail](stories/US-025_sales_prospect_intelligence.md) |
| [US-026](stories/US-026_risk_change_velocity.md) | **P1** | Risk Manager | See a change velocity score comparing current and prior-year risk language | Flag filings with major structural shifts for immediate deep review | ~~❌ Not implemented~~ **DEPRECATED** — superseded by [US-037](stories/US-037_yoy_trend_analysis.md) (EP-8) | [Detail](stories/US-026_risk_change_velocity.md) |
| [US-027](stories/US-027_risk_prioritization_score.md) | **P1** | Portfolio Manager | Get a composite risk prioritization score (1–100) per company | Triage a watchlist of 50 companies in minutes, not hours | ~~❌ Not implemented~~ **DEPRECATED** — superseded by [US-040](stories/US-040_composite_risk_score.md) (EP-8) | [Detail](stories/US-027_risk_prioritization_score.md) |
| [US-028](stories/US-028_annotation_labeler_ui.md) | **P0** | Domain Expert / SME | Review zero-shot predictions and save corrected labels to a local JSONL file | `llm_finetuning/train.py` has human-validated training data | ❌ Not implemented (PRD-004 Phase 1, Step 1.4) | [Detail](stories/US-028_annotation_labeler_ui.md) |

### EP-8 — Agentic Analysis

| ID | Priority | Role | Action | Value | Status | Detail |
|:---|:---------|:-----|:-------|:------|:-------|:-------|
| [US-033](stories/US-033_analyze_company_command.md) | **P0** | Financial Analyst | Run `analyze company <ticker>` and receive a structured risk report | Analyze a company's risk posture without writing custom code | ❌ Not implemented (PRD-005 Phase A) | [Detail](stories/US-033_analyze_company_command.md) |
| [US-034](stories/US-034_agent_classification_skill.md) | **P0** | ML Engineer | Have an agent skill classify each segment by SASB archetype and topic | Every report is grounded in the SASB taxonomy without manual labeling | ❌ Not implemented (PRD-005 Phase B) | [Detail](stories/US-034_agent_classification_skill.md) |
| [US-035](stories/US-035_multi_format_report_export.md) | **P0** | Data Scientist | Export analysis reports as Markdown, JSON, or CSV using `--format` | Integrate analysis results into downstream tools without format conversion | ❌ Not implemented (PRD-005 Phase A) | [Detail](stories/US-035_multi_format_report_export.md) |
| [US-036](stories/US-036_compare_companies.md) | **P1** | Corporate Development Analyst | Run `compare <ticker1> <ticker2>` and get a side-by-side risk comparison | Identify divergent risk exposures between acquisition targets | ❌ Not implemented (PRD-005 Phase D) | [Detail](stories/US-036_compare_companies.md) |
| [US-037](stories/US-037_yoy_trend_analysis.md) | **P1** | Risk Manager | Run `trend <ticker> --years N` and see which risk clusters grew or shrank | Detect emerging or receding risk themes without reading multiple filings | ❌ Not implemented (PRD-005 Phase E) | [Detail](stories/US-037_yoy_trend_analysis.md) |
| [US-038](stories/US-038_analyze_sector_command.md) | **P1** | Strategic Analyst | Run `analyze sector <sic>` and get aggregated risk themes across a peer cohort | Benchmark a company's risk profile against industry norms | ❌ Not implemented (PRD-005 Phase D) | [Detail](stories/US-038_analyze_sector_command.md) |
| [US-039](stories/US-039_agent_trace_logging.md) | **P1** | ML Engineer | Find a structured `agent_trace.jsonl` in every analysis run directory | Debug agent reasoning, audit LLM decisions, and improve skill logic | ❌ Not implemented (PRD-005 Phase C) | [Detail](stories/US-039_agent_trace_logging.md) |
| [US-040](stories/US-040_composite_risk_score.md) | **P1** | Portfolio Manager | Get a composite risk score (1–100) per company in the analysis report | Triage a watchlist of companies in minutes, not hours | ❌ Not implemented (PRD-005 Phase D) | [Detail](stories/US-040_composite_risk_score.md) |
| [US-041](stories/US-041_report_command_alias.md) | **P2** | Financial Analyst | Run `report <ticker>` as a shorthand alias for `analyze company <ticker>` | Generate a risk report without remembering the full subcommand syntax | ❌ Not implemented (PRD-005 Phase F) | [Detail](stories/US-041_report_command_alias.md) |

---

## Other Files

| File | Purpose |
|------|---------|
| `requirements_cleaning.txt` | Python dependency list for the text-cleaning subsystem |
