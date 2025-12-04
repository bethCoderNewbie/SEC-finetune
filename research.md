---
date: [Current date and time with timezone in ISO format]
researcher: [Researcher name from thoughts status]
git_commit: [Current commit hash]
branch: [Current branch name]
repository: [Repository name]
topic: "[User's Question/Topic]"
tags: [research, codebase, relevant-component-names]
status: complete
last_updated: [Current date in YYYY-MM-DD format]
last_updated_by: [Researcher name]
---

# Research: [User's Question/Topic]

**Date**: [Current date and time with timezone in ISO format]
**Researcher**: [Researcher name from thoughts status]
**Git Commit**: [Current commit hash]
**Branch**: [Current branch name]
**Repository**: [Repository name]
**Topic**: [User's Question/Topic]
**tags**: [research, codebase, relevant-component-names]
**status**: [complete]
**last_updated**: [Current date in YYYY-MM-DD format]
**last_updated_by**: [Researcher name]

## Research Question
[Original user query or decomposed research area]

**Date**: [Current date and time with timezone from step 4]
**Researcher**: [Researcher name from thoughts status]
**Git Commit**: [Current commit hash from step 4]
**Branch**: [Current branch name from step 4]
**Repository**: [Repository name]

## Summary
[High-level findings answering the user's question. Keep this concise.]

## Detailed Findings

### [Component/Area 1 - e.g., "Component Usage Flow"]

* **Working Path**: `path/to/file.tsx` calls `functionName` -> returns expected value.
* **Broken Path**: `path/to/file.tsx` calls `functionName` -> hits default/error state.
* **Logic Gap**: [Explanation of why the logic fails, e.g., "No Bash-specific override in lines 189-228"].
- Finding with reference ([file.ext:line](link))
- Connection to other components
- Implementation details

### [Component/Area 2]
* [Finding regarding state management or data flow]
* [Connection to other components]

## Code References

* `src/components/Modal.tsx:136` - Calls `getToolIcon` (Working)
* `src/components/Stream.tsx:76` - Default assignment (Broken source)
* `src/components/Stream.tsx:189-228` - [Description of code block or missing logic]

## Architecture Insights
[Patterns, conventions, and design decisions discovered]
* [e.g., "Icons are mapped via `getToolIcon` utility, not inline."]

## Historical Context (from thoughts/)
[Relevant insights from existing documentation. IMPORTANT: Remove "searchable/" from paths]
- `thoughts/shared/prs/123.md` - Historical decision about X
- `thoughts/global/notes.md` - Past exploration of Y

## Open Questions
[Any areas that need further investigation or human input]