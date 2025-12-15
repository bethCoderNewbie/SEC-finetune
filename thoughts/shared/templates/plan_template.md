---
date: {{DATE_ISO}}
researcher: {{RESEARCHER}}
git_commit: {{GIT_COMMIT}}
branch: {{BRANCH}}
repository: {{REPOSITORY}}
topic: "{{TOPIC}}"
tags: [plan, {{TAGS}}]
status: ready_for_review
last_updated: {{DATE_SHORT}}
last_updated_by: {{RESEARCHER}}
related_research: thoughts/shared/research/{{RELATED_RESEARCH_FILE}}
---

# Plan: {{TOPIC}}

**Date**: {{DATE_ISO}}
**Researcher**: {{RESEARCHER}}
**Git Commit**: {{GIT_COMMIT}}
**Branch**: {{BRANCH}}

## Desired End State

<!--
Describe EXACTLY what the user will have upon completion.
Be specific and measurable. Use bullet points.
-->

After this plan is complete, the user will have:

* {{END_STATE_1}}
* {{END_STATE_2}}
* {{END_STATE_3}}

### Key Discoveries (from Research)

<!--
Summarize critical findings from the related research document.
Include file:line references for quick verification.
-->

* `src/file.py:123-145` - {{DISCOVERY_1}}
* `src/other.py:67` - {{DISCOVERY_2}}

## What We're NOT Doing (Anti-Scope)

<!--
CRITICAL: Explicitly define boundaries to prevent scope creep.
Be specific about what is out of scope.
-->

* **NOT** {{ANTI_SCOPE_1}}
* **NOT** {{ANTI_SCOPE_2}}
* **NOT** {{ANTI_SCOPE_3}}

## Implementation Approach

<!--
High-level strategy before diving into phases.
Explain WHY this approach was chosen.
-->

{{APPROACH_DESCRIPTION}}

---

## Phase 1: {{PHASE_1_NAME}}

**Overview:** {{PHASE_1_OVERVIEW}}

### Changes Required:

**1. {{CHANGE_1_TITLE}}**
**File:** `src/path/to/file.py` (new file | update)
**Source:** `src/original.py:123-145` (if refactoring)

```python
# Code snippet showing the implementation
# Include enough context for copy-paste
```

**2. {{CHANGE_2_TITLE}}**
**File:** `src/path/to/other.py` (new file | update)

```python
# Another code snippet
```

---

## Phase 2: {{PHASE_2_NAME}}

**Overview:** {{PHASE_2_OVERVIEW}}

### Changes Required:

<!-- Repeat pattern from Phase 1 -->

---

## Phase 3: {{PHASE_3_NAME}} (if needed)

<!-- Add more phases as needed -->

---

## Success Criteria

### Automated Verification

<!--
Commands that can be run to verify success.
All checks should pass for the plan to be complete.
-->

```bash
# Run all tests
pytest tests/ -v

# Verify imports work
python -c "from src.module import thing; print('OK')"

# Type checking
mypy src/

# Linting
ruff check src/
```

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Import verification: `{{IMPORT_CHECK}}`
- [ ] Type checking passes: `mypy src/`
- [ ] No lint errors: `ruff check src/`

### Manual Verification

<!--
Steps that require human judgment.
Include expected outcomes.
-->

- [ ] {{MANUAL_CHECK_1}}
- [ ] {{MANUAL_CHECK_2}}

---

## File Summary

<!--
Table summarizing all files that will be created/modified/deleted.
Helps reviewer understand scope at a glance.
-->

| File | Action | Lines (approx) | Description |
|------|--------|----------------|-------------|
| `src/new_file.py` | New | ~100 | {{DESCRIPTION}} |
| `src/existing.py` | Update | +20/-10 | {{DESCRIPTION}} |
| `src/deprecated.py` | Delete | -150 | {{DESCRIPTION}} |
| **Total** | | ~{{TOTAL}} | |

---

## Rollback Plan

<!--
How to undo changes if something goes wrong.
Important for production systems.
-->

1. {{ROLLBACK_STEP_1}}
2. {{ROLLBACK_STEP_2}}

---

## Quick Start: Using This Template

1. **Complete research first**: Plans should reference a research document
2. **Get metadata**: Run `./hack/spec_metadata.sh --yaml`
3. **Replace placeholders**: Search for `{{` and replace all
4. **Define anti-scope early**: Prevents scope creep during implementation
5. **Include code snippets**: Reduces ambiguity during implementation
6. **Save with naming convention**: `YYYY-MM-DD_HH-MM_topic.md`

### Plan vs Research

| Aspect | Research | Plan |
|--------|----------|------|
| Purpose | Investigate & analyze | Define implementation |
| Contains | Findings, metrics, questions | Code snippets, phases, checklists |
| Status flow | in_progress → complete | ready_for_review → approved → implemented |
| Follows | Nothing (or prior research) | Related research document |
