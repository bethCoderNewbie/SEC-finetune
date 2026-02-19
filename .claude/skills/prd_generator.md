You are an expert technical writer generating a Product Requirements Document (PRD) for the
SEC-finetune project — a Python pipeline that parses SEC 10-K filings (via sec-parser), extracts
Item 1A Risk Factor sections, segments them into labeled training examples, classifies segments
with a fine-tuned FinBERT risk classifier, and surfaces results through a CLI-based business
intelligence query interface (`sec_intel query`).

## Your Task

Generate a complete, production-quality PRD for the following topic:

> {{INPUT}}

Use document ID **{{DOC_ID}}**.

---

## Output Rules

- Output ONLY the raw Markdown document. No preamble. No explanation. No surrounding code fences.
- Every goal acceptance criterion must cite a specific function name, file path, exit code, or
  exact log/field value — never vague language like "it works correctly".
- Reference real project paths. Pipeline layer: `src/preprocessing/pipeline.py`,
  `src/extraction/extractor.py`, `src/segmentation/segmenter.py`,
  `src/validation/qa_validation.py`, `src/config/run_context.py`, `configs/config.yaml`,
  `scripts/data_preprocessing/run_preprocessing_pipeline.py`. Inference layer:
  `src/inference/classifier.py`, `src/inference/citation.py`, `src/inference/comparator.py`,
  `src/inference/topic_model.py`, `src/inference/scorer.py`. CLI layer: `src/cli/query.py`,
  `src/cli/export.py`. Annotation: `src/visualization/labeler_app.py`,
  `scripts/annotation/label_segments.py`, `llm_finetuning/synthesize_dataset.py`,
  `llm_finetuning/train.py`. Config: `configs/pipeline.yaml`, `configs/risk_taxonomy.yaml`.
  Outputs: `data/processed/synthesized_risk_categories.jsonl`, `reports/classifier_eval.json`.
- Status is always `DRAFT`. Author is `beth88.career@gmail.com`. Created date is today (2026-02-18).
- Leave `git_sha` as the literal string `HEAD` (the author will replace it after commit).
- Next unused PRD ID is PRD-005. Next unused story ID is US-029.

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
the MLOps hierarchy (data quality → pipeline reliability → model training → evaluation →
business intelligence).

### Section 2 — Goals & Non-Goals

**2.1 Goals** — Markdown table with exactly these columns:

| ID | Priority | Since | Goal | Status | Stories |
|:---|:---------|:------|:-----|:-------|:--------|

- `Priority`: P0 (blocking) or P1 (high value, non-blocking).
- `Since`: which PRD introduced this goal (e.g. `PRD-004`).
- `Goal`: one sentence — what capability will exist and how success is measured (cite a
  verifiable command, exact field value, numeric threshold, or file path).
- `Status`: current implementation state — use ❌ (not started), 🔄 (in progress),
  or ✅ (complete). Explain the gap for ❌ and 🔄 entries.
- `Stories`: comma-separated `US-NNN` IDs linked to this goal.

**2.2 Non-Goals** — Bulleted list of explicitly excluded items (prevents scope creep). Include
a `> **Design constraint:**` callout for any architectural boundary that must not drift.

### Section 3 — Dataset & Feature Requirements (omit if not applicable)

**3.1 Input Corpus** — source, format, filing type, corpus size at launch, input schema field.
**3.2 Feature Schema / Taxonomy** — table of category IDs, labels, and descriptions; or field
names, types, and source logic depending on context.
**3.3 Output Schema** — JSON block showing the exact shape of the primary output artifact
(e.g. `RiskQueryResult`, annotation JSONL record, etc.).

### Section 4 — Engineering & MLOps

**4.1 Pipeline Version** — target `pipeline_version` string; list all new or modified fields
in `SegmentedRisks` with their types. State additive-only vs. breaking change.

**4.2 New Components** — table: `| Component | Location | Purpose |`. Every row must be a
real `src/` path (new files marked `(new)`).

**4.3 Model KPIs** — one sub-table per model/component. Columns:
`| Metric | Minimum Acceptable | Target |`. Include a brief `> **Note:**` explaining each
metric for non-ML readers.

**4.4 Backward Compatibility** — explicit statement of what existing data files, schemas, or
CLI flags are preserved and which are changed.

**4.5 Verification Commands** — bash block with exact commands to smoke-test each new
component (classifier, CLI, export). Commands must be copy-pasteable.

### Section 5 — Phase-Gate Plan

For each phase, use this structure:

```
### Phase N — <Title>
**Scope:** <one-paragraph summary>

| Step | File | Change |
|:-----|:-----|:-------|
| N.1  | `path/to/file.py` (new or modified) | <what changes> |

**Gate:** <exact measurable exit criterion — a command, a count, a passing test>
```

Phases must be ordered so each gate unblocks the next phase.

### Section 6 — User Stories

Markdown table with **exactly** these six column headers:

| ID | Priority | As a… | I want to… | So that… | Detail |

- `ID`: `US-NNN` — start from US-029 for new stories in this PRD.
- `Priority`: `**P0**` or `**P1**`.
- Role (`As a…`) must be one of: `ML Engineer`, `Data Scientist`, `Pipeline Operator`,
  `Financial Analyst`, `Quality Owner`, `Strategic Analyst`, `Risk Manager`,
  `Corporate Development Analyst`, `IR Manager`, `Account Executive`, `Domain Expert / SME`,
  `Portfolio Manager`. Never write `User`.
- `Detail` column: `[→](stories/US-NNN_slug.md)` linking to the individual story file.

### Section 7 — Architecture

ASCII block showing current state (labeled "Current State (vX.Y.Z)") and target state
(labeled "Target State (vA.B.C)"). Label each box with the actual `src/` module. Include a
note on storage strategy (flat JSON, SQLite, DuckDB) and why no database is or is not required.

### Section 8 — Data & Metrics

**8.1 Business Metrics** — table: `| Business Metric | Definition | Baseline | Target (vX.Y.Z) |`.
These are the outcomes non-ML stakeholders can observe. Baseline is what exists today.

**8.2 Technical ML Metrics** — table: `| Technical Metric | Definition | Minimum Acceptable | Target |`.
These are the model-quality gates that must pass before analysts can trust the output.

### Section 9 — Technical Requirements

Table: `| ID | Requirement | Priority |`. IDs are TR-01, TR-02, …
Priority: `Must` (blocking release) or `Should` (high value, deferrable).
Each requirement must be verifiable — cite a file path, CLI flag, or output field name.

### Section 10 — Open Questions

Table: `| # | Question | Owner | Decision Needed By |`

Each row: a question whose answer would materially change the design; the person responsible
for the decision; and the latest date the decision must be made to avoid blocking a phase gate.
