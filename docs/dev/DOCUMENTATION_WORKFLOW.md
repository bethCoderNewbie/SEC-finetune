# Documentation Workflow — The V-Model

How PRDs, RFCs, ADRs, and User Stories interact, constrain each other, and validate each other.

---

## 1. The High-Level Flow (Abstract → Concrete → Validation)

```
Abstract (Business)
        │
        ▼
   PRD — "What"       Defines the business goal and acceptance criteria
        │
        ▼
   RFC — "How"        Explores technical options to meet the PRD goal
        │
        ▼
   ADR — "Law"        Locks down the chosen option; immutable thereafter
        │
        ▼
 Stories — "Tasks"    Breaks the decision into executable implementation steps
        │
        ▼
Abstract (Validation) Stories passing QA marks PRD goals ✅
```

---

## 2. The Goal-Setting Matrix (How Each Doc Constrains the Next)

| Source | Target | The Constraint Link |
|--------|--------|---------------------|
| **PRD → RFC** | PRD constraints drive RFC scope | PRD says "must run on CPU without GPU." RFC must research CPU-compatible options only — GPU-heavy approaches (e.g., BERTopic) are out of scope before the RFC is even written. |
| **RFC → ADR** | RFC options drive ADR decision | RFC lists 3 candidate parsers. ADR selects `sec-parser` and explicitly rejects regex (see [ADR-002](../architecture/adr/ADR-002_sec_parser_over_regex.md)). The rejected options are not revisited without a new RFC. |
| **ADR → Stories** | ADR decisions become story constraints | A story says "Build the segmenter." The story's acceptance criteria must cite ADR-001 (Pydantic V2) — the segmenter's output schema must use `BaseModel`, not a plain dict. |
| **Stories → PRD** | Stories validate PRD success | When Story US-009 ("Clean training corpus, zero ToC lines") passes all Gherkin scenarios, the corresponding PRD-003 goal G-01 is marked ✅. No story passing = no PRD goal closed. |

---

## 3. Step-by-Step Workflow (Example: Adding a New Capability)

### Step 1 — Write the PRD

**Owner:** Product Owner / Lead
**File:** `docs/requirements/PRD-NNN_<topic>.md`

- Define the business goal in plain language.
- Set non-negotiable constraints (e.g., "Must run on CPU," "Must produce JSONL," "P99 latency < 5s").
- Write P0/P1 user stories in the table. These are placeholder IDs until stories are filed.
- Status: `DRAFT` until the RFC and ADR phases confirm feasibility.

**Real example:** [PRD-003](../requirements/PRD-003_Training_Data_Quality_Remediation.md) defines G-01–G-09
goals with exact acceptance criteria before any code was written.

---

### Step 2 — Write the RFC

**Owner:** Senior Engineer
**File:** `docs/architecture/rfc/RFC-NNN_<topic>.md`

- **Goal:** Answer the open design questions raised by the PRD.
- List 2–4 options per question with concrete code sketches and pros/cons.
- Apply the PRD's constraints as filters — any option that violates a PRD constraint is invalid.
- The RFC does **not** make a final decision. That is the ADR's job.
- Status: `DRAFT` — open for team review until the ADR is filed.

**Real example:** [RFC-001](../architecture/rfc/RFC-001_Finetuning_Pipeline.md) explores four open
questions (integration pattern, output format, model selection, truncation strategy) that PRD-002
left unresolved.

---

### Step 3 — Write the ADR

**Owner:** Tech Lead
**File:** `docs/architecture/adr/ADR-NNN_<slug>.md`

- State the chosen option from the RFC (or explain why a new option was selected).
- Record any governing rules that flow from the decision (e.g., "all seeds fixed to 42").
- **Immutable:** never edit after writing. Write a superseding ADR instead.
- The ADR becomes the law that all downstream stories must cite.

**Real example:** [ADR-002](../architecture/adr/ADR-002_sec_parser_over_regex.md) permanently
records the choice of `sec-parser` over regex. Any future story touching parsing must work within
this constraint — or file a new ADR to supersede it.

---

### Step 4 — File the User Stories

**Owner:** Dev Team
**File:** `docs/requirements/stories/US-NNN_<slug>.md`

- Each story is derived from a PRD goal or an ADR constraint — cite the source.
- Acceptance criteria (Gherkin) must be concrete enough to become automated tests.
- Stories are the only layer that is "ephemeral" — they can be closed, archived, or superseded
  once implemented.

**Real example:** [US-020](../requirements/stories/US-020_quality_circuit_breaker.md) derives
directly from PRD-003's G-04 goal and constrains the implementation to a specific exit code
and flag file format — both traceable back to the PRD.

---

## 4. Document Lifecycle Summary

| Document | Location | Mutability | Lifecycle |
|----------|----------|-----------|-----------|
| PRD | `docs/requirements/` | Append-only (version bump) | `DRAFT` → `APPROVED` → superseded by new PRD |
| RFC | `docs/architecture/rfc/` | Mutable until ADR filed | `DRAFT` → `CLOSED` (historical context) |
| ADR | `docs/architecture/adr/` | **Immutable** | `Accepted` → superseded by new ADR |
| Story | `docs/requirements/stories/` | Mutable until closed | `Not implemented` → `Partial` → `Implemented` |

---

## 5. The Feedback Loop (Upstream Revision)

Downstream work sometimes reveals that an upstream document was wrong.

```
Story implementation blocked
          │
          ▼
  Re-open or create new RFC
  (explore the alternative)
          │
          ▼
  Write superseding ADR
  (record the new decision)
          │
          ▼
  Update Story constraints
  (cite new ADR)
          │
          ▼
  Update PRD if goal changes
  (version bump, note supersedes)
```

**Rule:** Never change the code in a way that violates the current ADR without first filing a
new ADR. The decision layer (ADR) must always reflect what the code actually does.

**Trigger for upstream revision:**

| Signal | Action |
|--------|--------|
| Story is blocked for > 2 days by a technical constraint | Re-examine the ADR; open a new RFC if the constraint is architectural |
| Implementation runs 10× slower than the PRD's latency KPI | Open new RFC; don't silently break the goal |
| A PRD goal turns out to be technically infeasible | Mark PRD goal with `⚠️ Revised` note; update version; do not delete the original goal |

---

## 6. Quick Reference: Which Document Do I Write?

| Situation | Document |
|-----------|----------|
| Stakeholder asks "what are we building?" | PRD |
| Engineer asks "how should we build this?" (no consensus yet) | RFC |
| Team has agreed on an approach | ADR |
| Dev picks up a task from the backlog | User Story |
| A past decision needs to be changed | New ADR (supersedes old) |
| An old PRD goal was met | Update Story status → link to PRD goal |
