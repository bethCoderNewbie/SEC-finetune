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

---

## Requests for Comments (RFCs)

RFCs are proposals for complex design questions. Once a decision is reached, write an ADR and the RFC becomes historical context.

Location: `docs/architecture/rfc/RFC-{NNN}_{ShortName}.md`

| ID | Title | Status | Date |
|----|-------|--------|------|
| [RFC-001](rfc/RFC-001_Finetuning_Pipeline.md) | Fine-tuning Pipeline Architecture | DRAFT | 2026-02-18 |

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
