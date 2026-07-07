# Architecture

Index of engineering lifecycle documents: ADRs (immutable decisions) and RFCs (proposals).

> **PRDs** (product requirements) are indexed separately in
> [`docs/requirements/README.md`](../requirements/README.md).

---

## Architecture Decision Records (ADRs)

ADRs record immutable design choices. Never edit an existing ADR — write a new one that supersedes it.

Location: `docs/architecture/adr/ADR-{NNN}_{ShortName}.md`

| ID | Title | Status | Date |
|----|-------|--------|------|
| [ADR-001](adr/ADR-001_pydantic_v2_enforcement.md) | Enforce Pydantic V2 for All Data Schemas | Accepted | 2025-11-17 |
| [ADR-002](adr/ADR-002_sec_parser_over_regex.md) | Use `sec-parser` Library Over Custom Regex Parsing | Accepted | 2025-11-17 |
| [ADR-003](adr/ADR-003_global_worker_pool.md) | Global Worker Pool — Models Loaded Once Per Worker | Accepted | 2026-02-10 |
| [ADR-004](adr/ADR-004_sanitization_removed.md) | Remove HTML Sanitization from the Hot Path | Accepted | 2026-02-10 |
| [ADR-005](adr/ADR-005_custom_dlq_checkpoint.md) | Custom CheckpointManager and DeadLetterQueue over Off-the-Shelf Tools | Accepted | 2026-02-16 |
| [ADR-006](adr/ADR-006_modular_config.md) | Decompose Monolithic `src/config.py` into 16 Domain Modules | Accepted | 2025-12-03 |
| [ADR-007](adr/ADR-007_stamped_run_directories.md) | Immutable Stamped Run Directories for Output Provenance | Accepted | 2026-02-16 |
| [ADR-008](adr/ADR-008_finetuned_encoder_classifier.md) | Use Fine-Tuned Encoder Classifier (ProsusAI/finbert) | Accepted | 2026-02-17 |
| [ADR-009](adr/ADR-009_hybrid_pre_seek_parser.md) | Hybrid Pre-Seek Parser (Stage 1 Anchor-Based Fragment Extraction) | Accepted | 2026-02-17 |
| [ADR-010](adr/ADR-010_hybrid_pre_seek_parser_corrected.md) | Hybrid Pre-Seek Parser — Corrected (Rule 7 Full-Doc Fallback) | Accepted | 2026-02-17 |
| [ADR-011](adr/ADR-011_preseeker_single_section_constraint.md) | PreSeeker Single-Section Constraint (Rule 9) | Accepted | 2026-02-18 |
| [ADR-012](adr/ADR-012_word_count_segment_ceiling.md) | Word-Count Segment Ceiling — RFC-003 Option A Deployed | Accepted | 2026-02-24 |
| [ADR-013](adr/ADR-013_rfc006_layout_annotation_a1_a2a.md) | RFC-006 Layout Annotation — Rule-Based Post-Processing (A1/A2A) | Accepted | 2026-02-25 |
| [ADR-014](adr/ADR-014_rfc007_ancestors_field.md) | RFC-007 Contextual Enrichment — `ancestors` Breadcrumb Field | Accepted | 2026-02-25 |
| [ADR-015](adr/ADR-015_label_source_namespace.md) | Label Source Namespace (7 Values) | Accepted | 2026-02-26 |
| [ADR-016](adr/ADR-016_sasb_5dimension_taxonomy.md) | Replace 9-Class Archetype Taxonomy with SASB 5-Dimension 6-Class Schema | Accepted | 2026-03-11 |
| [ADR-017](adr/ADR-017_agentic_analysis_orchestration.md) | Agentic Analysis Orchestration Model — Option C Hybrid, Direct Dispatch, Sentence Embeddings | Accepted | 2026-07-07 |

---

## Requests for Comments (RFCs)

RFCs are proposals for complex design questions. Once a decision is reached, write an ADR and the RFC becomes historical context.

Location: `docs/architecture/rfc/RFC-{NNN}_{ShortName}.md`

| ID | Title | Status | Date |
|----|-------|--------|------|
| [RFC-001](rfc/RFC-001_Finetuning_Pipeline.md) | Fine-tuning Pipeline Architecture | DRAFT | 2026-02-18 |
| [RFC-002](rfc/RFC-002_sasb_two_layer_schema.md) | SASB Two-Layer Schema (Archetype + Material Topic) | CLOSED → ADR-016 | 2026-02-20 |
| [RFC-003](rfc/RFC-003_segment_token_length_enforcement.md) | Segment Token Length Enforcement | CLOSED → ADR-012 | 2026-02-22 |
| [RFC-004](rfc/RFC-004_hybrid_pre_seek_parser.md) | Hybrid Pre-Seek Parser | CLOSED → ADR-009, ADR-010 | 2026-02-17 |
| [RFC-005](rfc/RFC-005_multisection_full_document_dispatch.md) | Multisection Full-Document Dispatch | CLOSED → ADR-011 | 2026-02-18 |
| [RFC-006](rfc/RFC-006_layout_analysis_model_evaluation.md) | Layout Analysis Model Evaluation | CLOSED → ADR-013 | 2026-02-24 |
| [RFC-007](rfc/RFC-007_contextual_enrichment_breadcrumb.md) | Contextual Enrichment — Breadcrumb (`ancestors`) Field | CLOSED → ADR-014 | 2026-02-25 |
| [RFC-008](rfc/RFC-008_Agentic_Analysis_Architecture.md) | Agentic Analysis Architecture — Agents, Skills & Commands | CLOSED → ADR-017 | 2026-07-07 |

---

## Other Files

| File | Purpose |
|------|---------|
| `data_dictionary.md` | Schema reference for all pipeline output fields |
| `PROJECT_SUMMARY.md` | Goals, pipeline overview, and data flow |
| `FILE_ORGANIZATION.md` | Where files live and the reasoning behind directory layout |
| `CHANGES.md` | Chronological changelog of significant system changes |
| `adr/` | Immutable architecture decision records |
| `rfc/` | Proposals and design discussions |
