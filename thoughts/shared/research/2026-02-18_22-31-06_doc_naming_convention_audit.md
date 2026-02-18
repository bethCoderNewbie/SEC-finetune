---
id: research/2026-02-18_22-31-06_doc_naming_convention_audit
title: "Documentation Naming Convention Audit — PRD / TRD / RFC / ADR"
date: 2026-02-18T22:31:06Z
author: beth88.career@gmail.com
git_sha: fd920a0
branch: main
status: complete
---

# Documentation Naming Convention Audit

## Trigger

`docs/requirements/README.md:5-9` defines a shared naming convention:

```
{Type}-{ID}_{ShortName}.md
Types: PRD · TRD · RFC · ADR
```

The selected lines imply all four types — PRD, TRD, RFC, ADR — live under
`docs/requirements/` with a single shared numeric sequence. Auditing whether
the current filesystem matches this intent.

---

## What the README Claims Should Exist

From `docs/requirements/README.md` Active + Planned tables:

| ID | Type | Status |
|:---|:-----|:-------|
| PRD-001 | PRD | APPROVED |
| PRD-002 | PRD | Planned ("Feature Engineering") |
| PRD-003 | PRD | Planned ("Database Integration & API") |
| RFC-004 | RFC | Planned ("Fine-tuning Pipeline Architecture") |
| ADR-005 | ADR | Planned ("Pydantic V2 Enforcement Decision") |

**Implied:** All live under `docs/requirements/`. Shared numeric sequence
(PRD-001, PRD-002, …, RFC-004, ADR-005).

---

## What Actually Exists on Disk

### `docs/requirements/`
```
PRD-001_SEC_Finetune_MVP.md          ← APPROVED, in README Active table ✅
PRD-002_SEC_Finetune_Pipeline_v2.md  ← COMMITTED TODAY, not in README ❌
README.md
requirements_cleaning.txt
```

### `docs/architecture/adr/`
```
ADR-001_pydantic_v2_enforcement.md   ← committed today, separate numbering ⚠️
ADR-002_sec_parser_over_regex.md
ADR-003_global_worker_pool.md
ADR-004_sanitization_removed.md
ADR-005_custom_dlq_checkpoint.md
ADR-006_modular_config.md
ADR-007_stamped_run_directories.md
```

**No TRD exists anywhere. No RFC exists anywhere.**

---

## Discrepancies Found

### D-1: README Stale — PRD-002 Not Indexed

`docs/requirements/README.md` Active Documents table still lists only PRD-001.
PRD-002 was committed today (`fd920a0`) but the README was not updated.

Additionally, the Planned table lists PRD-002 as "Feature Engineering (Sentiment,
Readability, Topics)" — which is wrong. The actual PRD-002 covers pipeline v2
current state and MLOps requirements, not feature engineering.

**Impact:** Anyone reading the README index gets a false picture of what exists.

### D-2: ADR Location Divergence — `docs/requirements/` vs. `docs/architecture/adr/`

The README naming convention implies ADRs live in `docs/requirements/` (they are
listed in the same naming table as PRDs). But ADRs were created in
`docs/architecture/adr/` — a separate directory with a separate numeric sequence.

| What README implies | What actually exists |
|:--------------------|:--------------------|
| `docs/requirements/ADR-005_...md` | `docs/architecture/adr/ADR-001_...md` through `ADR-007_...md` |

**Root cause:** CLAUDE.md (updated today, commit `fd920a0`) explicitly says
ADRs belong in `docs/architecture/adr/`. The CLAUDE.md instruction is newer and
more specific than the README convention. CLAUDE.md wins.

### D-3: Shared Numbering Sequence Collision

The README planned `ADR-005` = "Pydantic V2 Enforcement Decision".
We created `ADR-001` = "Pydantic V2 Enforcement" in `docs/architecture/adr/`
with an independent counter.

These are the same conceptual document with different IDs in different locations.
The shared sequence (PRD-001 through ADR-005) was designed as if all types were
interleaved — this makes cross-referencing fragile. Example: "see ADR-005" is
ambiguous: the README's planned-but-unbuilt file, or our ADR-005 which is
"Custom DLQ + Checkpoint"?

**Root cause:** The README was written before ADRs had their own home. The
shared sequence made sense when everything was in one directory.

### D-4: TRD — Defined but Never Written

"TRD — Technical Requirements Document" is named in the convention but no
TRD-NNN file exists anywhere. The technical requirements that would go into a
TRD are currently embedded inline in PRD-002 §9 ("Technical Requirements").

**Question this raises:** Is a separate TRD needed, or is PRD-002 §9 sufficient?

### D-5: RFC — Defined but Never Written

"RFC — Request for Comments" exists in the naming convention but zero RFCs have
been written. The README planned `RFC-004` = "Fine-tuning Pipeline Architecture"
— the biggest open design question in the project (how to integrate
`src/analysis/inference.py` into the batch pipeline, JSONL output format, model
selection for fine-tuning).

Decisions about the fine-tuning pipeline were encoded directly as ADRs
(after-the-fact), skipping the RFC (before-the-fact proposal) step. This is
acceptable if the decision maker is a sole contributor, but means there is no
record of alternatives considered for the fine-tuning architecture.

---

## Root Cause Summary

The README was written early (before CLAUDE.md established the four-pillar
directory structure) and has not been maintained as the project evolved. The
naming convention it defines is partially correct but conflicts with two later
decisions:

1. ADRs canonically live in `docs/architecture/adr/` (CLAUDE.md, 2026-02-18)
2. ADR numbering is independent of PRD/TRD/RFC numbering (seven ADRs exist)

---

## Recommended Actions

### Immediate (README accuracy)

**R-1: Update `docs/requirements/README.md` Active Documents table**
Add PRD-002, remove stale PRD-002 entry from Planned with wrong scope.
Update RFC-004 planned scope if still accurate.

**R-2: Clarify ADR location in the naming convention**
Add a note to the README that ADRs live in `docs/architecture/adr/` with their
own counter, not in `docs/requirements/`.

**R-3: Separate numbering sequences**

| Sequence | Lives in | Counter resets at |
|:---------|:---------|:------------------|
| PRD-NNN, TRD-NNN, RFC-NNN | `docs/requirements/` | Independent per type |
| ADR-NNN | `docs/architecture/adr/` | Independent; currently at ADR-007 |

### Short-term (gaps to fill)

**R-4: Write RFC-004 — Fine-tuning Pipeline Architecture**
This is the highest-value missing document. The fine-tuning pipeline is the
core open design question (PRD-002 OQ-3, OQ-4, OQ-6). An RFC forces explicit
articulation of alternatives before code is written. Proposed scope:

- How to integrate `src/analysis/inference.py` into `process_batch()`
- JSONL vs. JSON output format decision
- Model selection: continue with `facebook/bart-large-mnli` zero-shot, or
  fine-tune `ProsusAI/finbert`?
- Token truncation strategy for segments > 512 tokens (OQ-3)

**R-5: Decide TRD strategy**
Two options:

| Option | Pros | Cons |
|:-------|:-----|:-----|
| Keep technical requirements in PRD-002 §9 | Single document; no sync | PRD gets long; audience mismatch |
| Extract to `TRD-008_Pipeline_Technical_Constraints.md` | Separate audiences (PM vs. Eng) | Must maintain two docs in sync |

**Recommendation:** Stay with PRD §9 until the project has a distinct PM and
Engineering Lead audience. A TRD adds overhead without benefit for a
single-contributor project.

---

## Decision Needed

> **Should `docs/requirements/README.md` be the canonical index for ALL doc
> types (PRD, TRD, RFC, ADR), or should ADRs be indexed separately in
> `docs/architecture/adr/README.md`?**

Current state argues for **separate indexes** (ADRs are already in a different
directory and CLAUDE.md treats them differently). The requirements README should
index PRD, TRD, RFC only. A new `docs/architecture/adr/README.md` should index
ADRs.

This resolves the numbering ambiguity permanently.
