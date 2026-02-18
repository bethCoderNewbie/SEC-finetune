# Requirements

Index of all product and technical specification documents.

Naming convention: `{Type}-{ID}_{ShortName}.md`
- **PRD** — Product Requirements Document ("What are we building?")
- **TRD** — Technical Requirements Document ("Detailed system constraints")
- **RFC** — Request for Comments ("How should we build this?")
- **ADR** — Architecture Decision Record ("Why did we decide X?")

Status values: `DRAFT` · `IN-REVIEW` · `APPROVED` · `DEPRECATED`

---

## Active Documents

| ID | Type | Title | Status | Last Updated |
|----|------|-------|--------|-------------|
| [PRD-001](PRD-001_SEC_Finetune_MVP.md) | PRD | SEC 10-K Risk Factor Analyzer — MVP | APPROVED | 2026-02-18 |

---

## Planned Documents

| ID | Type | Title | Blocks |
|----|------|-------|--------|
| PRD-002 | PRD | Feature Engineering (Sentiment, Readability, Topics) | PRD-001 approved |
| PRD-003 | PRD | Database Integration & API | PRD-001 shipped |
| RFC-004 | RFC | Fine-tuning Pipeline Architecture | PRD-001 approved |
| ADR-005 | ADR | Pydantic V2 Enforcement Decision | — |

---

## Archive

Old or deprecated specs live in `archive/`. Do not use for current guidance.

---

## Other Files

| File | Purpose |
|------|---------|
| `requirements_cleaning.txt` | Python dependency list for the text-cleaning subsystem |
