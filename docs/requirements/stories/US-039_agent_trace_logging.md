---
id: US-039
epic: EP-8
priority: P1
status: Not implemented
source_prd: PRD-005
estimation: S (1–2 days)
---

# US-039: Agent Reasoning Trace Logging

## The Story

As an **ML Engineer**, I want a structured `agent_trace.jsonl` file written to every analysis run
directory, so that I can debug agent reasoning, audit LLM decisions, and improve skill logic.

## Acceptance Criteria

### Scenario: Trace file created on successful run

```gherkin
Given a successful analyze company run for AAPL
When the command exits with code 0
Then the analysis run directory contains a file named agent_trace.jsonl
And every line in agent_trace.jsonl is valid JSON parseable by json.loads()
And the first line has "event" equal to "orchestrator_start"
And the last line has "event" equal to "orchestrator_end"
And at least one line has "event" equal to "tool_use" and "tool" equal to "load_filing"
```

### Scenario: Trace contains timestamps in ISO 8601 format

```gherkin
Given a completed analysis run
When agent_trace.jsonl is read
Then every line contains a "ts" field
And every "ts" field matches the pattern YYYY-MM-DDTHH:MM:SS.sssZ
```

### Scenario: Trace contains duration for every tool_use event

```gherkin
Given a completed analysis run
When agent_trace.jsonl is filtered to lines with "event" equal to "tool_use"
Then every such line contains a "duration_ms" field that is a positive integer
```

### Scenario: Failed skill call recorded in trace

```gherkin
Given classify_segment raises SkillError during an analysis run
When the orchestrator catches the error and continues (or exits)
Then agent_trace.jsonl contains a line with "event" equal to "tool_error"
And that line has "tool" equal to "classify_segment"
And that line has "status" equal to "error"
And that line has an "error" field containing the error message string
```

### Scenario: Trace does not include full segment text by default

```gherkin
Given a completed analysis run
When agent_trace.jsonl is read
Then no "input" field in any line contains a string longer than 200 characters for the "text" key
And tool_use lines for classify_segment have "input" containing "chunk_id" not full "text"
```

## Technical Notes

- **Log location:** `data/reports/{run_id}/agent_trace.jsonl`
- **Writer:** `src/analysis/orchestrator.py` — `_log_trace(event, **kwargs)` private method
- **JSONL format:** one JSON object per line; no trailing comma; UTF-8 encoded
- **Resolve before Phase C:** OQ-A06 (segment IDs vs. full text in trace input)
- **Event types:** `orchestrator_start`, `llm_call`, `tool_use`, `tool_error`, `sub_agent_spawn`, `sub_agent_result`, `orchestrator_end`
- **No PII:** trace must not log full segment text by default (segment IDs only); full text logging opt-in via `AnalysisConfig.trace_full_text: bool = False`
