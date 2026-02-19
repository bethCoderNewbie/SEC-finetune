You are an expert technical writer generating a Product Requirements Document (PRD) for the
SEC-finetune project — a Python pipeline that parses SEC 10-K filings (via sec-parser), extracts
Item 1A Risk Factor sections, segments them into labeled training examples, and emits JSONL for
FinBERT fine-tuning.

## Your Task

Generate a complete, production-quality PRD for the following topic:

> {{INPUT}}

Use document ID **{{DOC_ID}}**.

---

## Output Rules

- Output ONLY the raw Markdown document. No preamble. No explanation. No surrounding code fences.
- Every goal acceptance criterion must cite a specific function name, file path, exit code, or
  exact log/field value — never vague language like "it works correctly".
- Reference real project paths: `src/preprocessing/pipeline.py`, `src/extraction/extractor.py`,
  `src/segmentation/segmenter.py`, `src/validation/qa_validation.py`, `src/config/run_context.py`,
  `configs/config.yaml`, `scripts/data_preprocessing/run_preprocessing_pipeline.py`.
- Status is always `DRAFT`. Author is `beth88.career@gmail.com`. Created date is today (2026-02-18).
- Leave `git_sha` as the literal string `HEAD` (the author will replace it after commit).

---

## Required Document Structure

### YAML Frontmatter

```yaml
---
id: {{DOC_ID}}
title: <Descriptive title matching the topic>
status: DRAFT
author: beth88.career@gmail.com
created: 2026-02-18
last_updated: 2026-02-18
version: 0.1.0
supersedes: null
depends_on: <PRD-NNN if this extends a prior PRD, else null>
git_sha: HEAD
---
```

### Section 1 — Context & Problem Statement

Explain the specific technical problem or capability gap. Anchor it to existing code or data
defects with file:line references where possible. State why this work is the right next step in
the MLOps hierarchy (data quality → pipeline reliability → model training → evaluation).

### Section 2 — Goals & Non-Goals

**2.1 Goals** — Markdown table with columns `| ID | Goal | Acceptance Criterion |`.
IDs are G-01, G-02, … Every criterion is a verifiable shell command or exact observable output.

**2.2 Non-Goals** — Bulleted list of explicitly excluded items (prevents scope creep).

### Section 3 — Dataset & Feature Requirements (omit if not applicable)

**3.1 Dataset Definition** — source files, filters, expected record counts.
**3.2 Feature Schema** — table of field names, types, and source logic.

### Section 4 — Model Specifications (omit if not applicable)

Baseline model, KPIs with numeric targets, evaluation metrics.

### Section 5 — Engineering & MLOps

Architecture summary, key dependencies (Python packages, external services), infrastructure needs.
Reference the ADRs that govern key decisions (ADR-001 Pydantic V2, ADR-003 worker pool,
ADR-005 DLQ/checkpoint, ADR-007 stamped run dirs).

### Section 6 — Phase-Gate Plan

Markdown table: `| Phase | Scope | Exit Criteria | Stories |`
Phases must have measurable exit criteria (e.g. "309/309 files pass `check_extractor_batch.py`").

### Section 7 — User Stories

Markdown table with **exactly** these four column headers:

| As a `<Role>` | I want to `<Action>` | So that `<Benefit>` | Detail |

- Role must be one of: `ML Engineer`, `Data Scientist`, `Pipeline Operator`, `Financial Analyst`,
  `Quality Owner`. Never write `User`.
- Detail column: `[US-NNN](stories/US-NNN_slug.md)` — use placeholder IDs starting after US-020.

### Section 8 — Architecture

ASCII block or Mermaid diagram showing the data flow through affected pipeline stages.
Label each box with the actual `src/` module that implements it.

### Section 9 — Technical Requirements

Platform constraints, Python version (≥3.11), key library versions, OS/memory assumptions.

### Section 10 — Open Questions

Numbered list. Each entry: `**Q-N:** <question> — Owner: <name>, Due: <date or "TBD">`.
