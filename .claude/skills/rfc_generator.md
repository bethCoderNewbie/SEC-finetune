You are an expert software architect generating a Request for Comments (RFC) for the SEC-finetune
project — a Python pipeline that parses SEC 10-K filings, extracts Risk Factor sections, and
produces JSONL training data for FinBERT fine-tuning.

## Your Task

Generate a complete RFC that explores design options for:

> {{INPUT}}

Use document ID **{{DOC_ID}}**.

---

## Output Rules

- Output ONLY the raw Markdown document. No preamble. No explanation. No surrounding code fences.
- An RFC explores open questions and trade-offs. It does NOT make a final decision — that is the
  job of an ADR, written after consensus is reached.
- Reference real project paths wherever possible: `src/preprocessing/pipeline.py`,
  `src/extraction/extractor.py`, `src/segmentation/segmenter.py`,
  `src/validation/qa_validation.py`, `src/utils/`, `configs/config.yaml`.
- Include concrete code sketches (not full implementations) to illustrate each option.
- Status is always `DRAFT`. Author is `beth88.career@gmail.com`. Created date is 2026-02-18.

---

## Required Document Structure

### YAML Frontmatter

```yaml
---
id: {{DOC_ID}}
title: <Short descriptive title>
status: DRAFT
author: beth88.career@gmail.com
created: 2026-02-18
last_updated: 2026-02-18
superseded_by: null
---
```

### Status Block

```
## Status

**DRAFT** — open for review. Once a decision is reached, write an ADR that records the choice
and references this RFC as context.
```

### Context Section

Describe the current state of the codebase — what exists, what is missing, and why a design
decision is needed now. Cite specific file paths and line numbers where the gap or complexity
lives. Name the concrete questions that must be answered before implementation can begin.

### One Section Per Design Question

For each open design question (typically 2–4 questions), write a section:

```
## Question N: <Question Title>

Brief framing paragraph.

### Option A — <Name>

<1-paragraph description>

```python
# Minimal code sketch illustrating the approach
```

**Pros:** <bullet list>
**Cons:** <bullet list>

### Option B — <Name>

... same structure ...

### Option C — <Name> (if applicable)

... same structure ...
```

### Recommendation Section

```
## Recommendation

Briefly state which combination of options the author recommends and why.
Note any dependencies between questions (e.g. "Option A for Q1 forces Option B for Q2").
State explicitly: "This is a recommendation, not a decision. An ADR must be filed to record
the final choice."
```

### Open Questions Section

```
## Open Questions

1. <Unresolved question that blocks decision> — Owner: <name>, Due: <date or "before implementation">
```

### Next Steps Section

```
## Next Steps

1. <Action item>
2. Write ADR-NNN recording the final decision.
3. Update PRD-NNN §5 (Phase-Gate) to reflect the chosen design.
```
