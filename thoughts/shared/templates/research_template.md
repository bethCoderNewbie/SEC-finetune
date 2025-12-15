---
date: {{DATE_ISO}}
researcher: {{RESEARCHER}}
git_commit: {{GIT_COMMIT}}
branch: {{BRANCH}}
repository: {{REPOSITORY}}
topic: "{{TOPIC}}"
tags: [research, {{TAGS}}]
status: in_progress
last_updated: {{DATE_SHORT}}
last_updated_by: {{RESEARCHER}}
---

# Research: {{TOPIC}}

**Date**: {{DATE_ISO}}
**Researcher**: {{RESEARCHER}}
**Git Commit**: {{GIT_COMMIT}}
**Branch**: {{BRANCH}}
**Repository**: {{REPOSITORY}}

## Research Question

<!--
Define the specific question(s) this research aims to answer.
Be precise and measurable where possible.
-->

{{RESEARCH_QUESTION}}

## Summary

<!--
Executive summary of findings (2-5 sentences).
Write this AFTER completing the detailed findings.
Include: Key discovery, impact, recommendation preview.
-->

{{SUMMARY}}

## Detailed Findings

### 1. {{FINDING_SECTION_1}}

#### Working Path
<!--
Document what IS working correctly.
Include file:line references.
-->

#### Broken Path (if applicable)
<!--
Document what is NOT working as expected.
Include file:line references.
-->

### 2. {{FINDING_SECTION_2}}

<!-- Add more sections as needed -->

## Code References

<!--
Table of specific file:line locations for key findings.
This enables quick navigation and verification.
-->

| File:Line | Description | Status |
|-----------|-------------|--------|
| `src/module.py:123-145` | Description of code section | Working/Broken |
| `src/other.py:67` | Another reference | Working/Broken |

## Architecture Insights

<!--
Document architectural patterns, dependencies, and design decisions.
Use diagrams (ASCII or mermaid) where helpful.
-->

### Current Architecture
```
component_a
    └── component_b
        └── component_c
```

### Integration Points
<!-- How does this connect to other parts of the system? -->

## Metrics

<!--
Quantitative measurements where applicable.
Include: current state, target state, pass/fail criteria.
-->

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Example metric | 0.85 | > 0.90 | PENDING |

## Open Questions

<!--
List unresolved questions discovered during research.
These may become future research topics or plan considerations.
-->

1. {{OPEN_QUESTION_1}}
2. {{OPEN_QUESTION_2}}

## Recommendations

<!--
Actionable recommendations based on findings.
Prioritize by impact and effort.
-->

### Priority 1: {{RECOMMENDATION_1}}
<!-- High impact, should be addressed first -->

### Priority 2: {{RECOMMENDATION_2}}
<!-- Medium impact or dependent on Priority 1 -->

---

## Quick Start: Using This Template

1. **Get metadata**: Run `./hack/spec_metadata.sh --yaml` and paste output
2. **Replace placeholders**: Search for `{{` and replace all placeholders
3. **Fill sections**: Complete each section, removing instructions in `<!-- -->`
4. **Update status**: Change `status: in_progress` to `complete` when done
5. **Save with naming convention**: `YYYY-MM-DD_HH-MM_topic.md`

### Placeholder Reference

| Placeholder | Source | Example |
|-------------|--------|---------|
| `{{DATE_ISO}}` | `./hack/spec_metadata.sh` | `2025-12-12T15:17:08-06:00` |
| `{{DATE_SHORT}}` | `./hack/spec_metadata.sh` | `2025-12-12` |
| `{{RESEARCHER}}` | `./hack/spec_metadata.sh` | `bethCoderNewbie` |
| `{{GIT_COMMIT}}` | `./hack/spec_metadata.sh` | `ea45dd2` |
| `{{BRANCH}}` | `./hack/spec_metadata.sh` | `main` |
| `{{REPOSITORY}}` | `./hack/spec_metadata.sh` | `SEC finetune` |
| `{{TOPIC}}` | Manual | `Config Restructuring Analysis` |
| `{{TAGS}}` | Manual | `config, refactoring, pydantic` |
