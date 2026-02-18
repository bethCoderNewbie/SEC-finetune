# Documentation Index

SEC Filing Analyzer — documentation organized around four audience pillars.

---

## Documentation Strategy: The Four Pillars

Each pillar targets a different reader with a different question.
Don't look in the wrong pillar — you won't find what you need.

| Pillar | Audience | Core Question | Key Files |
|--------|----------|---------------|-----------|
| **[Context](#1-context)** | Stakeholders, PMs | *Why are we building this? What is the scope?* | PRD-001, CHANGELOG |
| **[Architecture](#2-architecture)** | Engineers, Contributors | *How does the system work? Why were these decisions made?* | ADRs, System_Design.md |
| **[Operations](#3-operations)** | DevOps, On-Call | *The pipeline crashed. How do I fix the Dead Letter Queue?* | Runbook.md, Config guides |
| **[Data](#4-data)** | Data Scientists, Analysts | *What does `readability_fog` mean? Is `filing_date` UTC?* | Data_Dictionary.md |

---

## 1. Context

> *For stakeholders and PMs: scope, goals, and roadmap.*

| File | Purpose |
|------|---------|
| [requirements/PRD-001_SEC_Finetune_MVP.md](requirements/PRD-001_SEC_Finetune_MVP.md) | Product charter — problem, goals, user stories, KPIs |
| [requirements/README.md](requirements/README.md) | Index of all PRDs, RFCs, and ADRs with status |
| [general/CHANGELOG.md](general/CHANGELOG.md) | Version history — all significant changes, newest first |
| [architecture/PROJECT_SUMMARY.md](architecture/PROJECT_SUMMARY.md) | Technical goals, pipeline overview, and success criteria |

---

## 2. Architecture

> *For engineers and contributors: how it works and why decisions were made.*

| File | Purpose |
|------|---------|
| [architecture/FILE_ORGANIZATION.md](architecture/FILE_ORGANIZATION.md) | Directory layout and where things belong |
| [preprocessing/README.md](preprocessing/README.md) | Parser → extractor → cleaner → segmenter pipeline |
| [config/README.md](config/README.md) | Pydantic v2 settings, enums, and YAML config system |
| [features/README.md](features/README.md) | Sentiment, readability, topic modeling |
| [utils/README.md](utils/README.md) | Checkpointing, workers, DLQ, progress logging |
| [validation/README.md](validation/README.md) | QA gates and schema validation |
| [dev/CODE_GUIDELINES.md](dev/CODE_GUIDELINES.md) | MLOps standards, Pydantic patterns, reproducibility |

---

## 3. Operations

> *For DevOps and on-call: keep it running and recover from failure.*

| File | Purpose |
|------|---------|
| [setup/QUICK_START.md](setup/QUICK_START.md) | Fast path to a working environment |
| [setup/INSTALLATION.md](setup/INSTALLATION.md) | Full dependency and environment setup |
| [setup/RUN_SCRIPTS.md](setup/RUN_SCRIPTS.md) | How to invoke the pipeline |
| [utils/RETRY_MECHANISM.md](utils/RETRY_MECHANISM.md) | DLQ retry, timeout multipliers, adaptive allocation |
| [utils/INCREMENTAL_PROCESSING_GUIDE.md](utils/INCREMENTAL_PROCESSING_GUIDE.md) | State management and resumable runs |
| [utils/GATEKEEPER_QUICK_START.md](utils/GATEKEEPER_QUICK_START.md) | Validation gates: how to configure and interpret |
| [validation/DATA_HEALTH_CHECK_GUIDE.md](validation/DATA_HEALTH_CHECK_GUIDE.md) | Running QA checks and interpreting results |
| [ops/DRIFT_DETECTION_GITHUB_ACTIONS.md](ops/DRIFT_DETECTION_GITHUB_ACTIONS.md) | Scheduled drift monitoring (deferred — see ops/) |
| [setup/POWERSHELL_GUIDE.md](setup/POWERSHELL_GUIDE.md) | Windows PowerShell equivalents |

---

## 4. Data

> *For data scientists and analysts: field semantics, units, and schema.*

| File | Purpose |
|------|---------|
| [validation/SHARED_KNOWLEDGE.md](validation/SHARED_KNOWLEDGE.md) | Ground-truth learnings: SEC parser behavior and known edge cases |
| [features/FEATURE_ENGINEERING_GUIDE.md](features/FEATURE_ENGINEERING_GUIDE.md) | Feature types, schemas, and composition |
| [features/TOPIC_MODELING_REQ.md](features/TOPIC_MODELING_REQ.md) | Data volume and format requirements for LDA training |

> **Missing:** `Data_Dictionary.md` — field names, types, units, and nullability for all output schemas.
> This is the highest-priority documentation gap.

---

## All Directories

| Directory | Pillar(s) | Purpose |
|-----------|-----------|---------|
| [requirements/](requirements/README.md) | Context | PRDs, RFCs, ADRs — versioned specs with lifecycle status |
| [general/](general/) | Context | Version history (CHANGELOG) |
| [architecture/](architecture/README.md) | Context, Architecture | Project goals, layout, changelog |
| [setup/](setup/README.md) | Operations | Installation, quickstart, run scripts |
| [preprocessing/](preprocessing/README.md) | Architecture | Parser, extractor, cleaner, segmenter |
| [config/](config/README.md) | Architecture | Pydantic v2 settings, enums, YAML config |
| [features/](features/README.md) | Architecture, Data | Sentiment, readability, topic modeling |
| [utils/](utils/README.md) | Architecture, Operations | Checkpointing, workers, DLQ, progress logging |
| [validation/](validation/README.md) | Operations, Data | QA checks, schema validation, domain gotchas |
| [ops/](ops/README.md) | Operations | Drift detection, CI/CD, scheduled jobs |
| [dev/](dev/README.md) | Architecture | Code guidelines and MLOps standards |
| [implementation/](implementation/README.md) | — | Historical sprint reports |
| [archive/](archive/README.md) | — | Rotting docs — do not use for current guidance |

---

## Naming Conventions

- `{Type}-{ID}_{ShortName}.md` — versioned specs (`PRD-001_SEC_Finetune_MVP.md`, `RFC-004_Finetune_Pipeline.md`)
- `UPPER_CASE.md` — normative docs (guides, specs, references)
- `YYYY-MM-DD_snake_case.md` — temporal records (incidents, logs, research dumps)
- Every directory has a `README.md` acting as its table of contents
