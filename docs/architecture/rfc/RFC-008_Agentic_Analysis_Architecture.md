# RFC-008: Agentic Analysis Architecture

| Field | Value |
|-------|-------|
| **Status** | CLOSED → ADR-017 |
| **Author** | Beth |
| **Created** | 2026-07-07 |
| **Last Updated** | 2026-07-07 |
| **Resolves** | PRD-005 §4 (Agent Architecture), OQ-A01, OQ-A02, OQ-A04, OQ-A06 |
| **Related** | RFC-001 (Fine-tuning Pipeline), ADR-006 (Modular Config), ADR-007 (Stamped Runs) |

---

## 1. Problem Statement

PRD-005 adds an agentic analysis layer above the existing preprocessing pipeline. The key
architectural question is: **how should agents, skills, and the Claude API client be structured to
maximize testability, composability, and operational transparency?**

Three distinct sub-questions arise:

1. **Orchestration model**: single orchestrator with direct skill calls vs. multi-agent hierarchy
   with delegating sub-agents vs. pure tool-use loop with no explicit sub-agents.
2. **Skill transport**: Python function calls vs. MCP (Model Context Protocol) server vs.
   subprocess-based tool execution.
3. **YoY delta algorithm**: TF-IDF cosine similarity vs. sentence-embedding cosine similarity for
   `detect_yoy_delta`.

---

## 2. Option Analysis

### 2.1 Orchestration Model

#### Option A — Pure Tool-Use Loop (Single Agent)

One `AnalysisOrchestrator` runs a `while` loop: sends messages to Claude with a registered
`tools=` list; Claude responds with `tool_use` blocks; orchestrator executes the matching Python
skill function; appends `tool_result` to conversation; repeats until Claude responds with
`stop_reason="end_turn"`.

```
AnalysisOrchestrator
    │
    ├── tools=[load_filing, classify_segment, summarize_cluster, score_risk, ...]
    │
    └── while not done:
            response = claude.messages.create(...)
            for block in response.content:
                if block.type == "tool_use":
                    result = dispatch(block.name, block.input)
                    append tool_result
```

Pros:
- Minimal code; no inter-agent communication.
- Easy to trace (one conversation thread per command).
- Claude naturally sequences skill calls based on goal.

Cons:
- Long tool-use chains can exhaust context window on large filings (161 segments × ~100 chars
  each = ~16K chars; within 200K context, but risky for `compare` across two large filings).
- Harder to parallelize skill execution (Claude calls skills sequentially in one thread).
- No natural boundary to unit-test "which skills get called for which command."

#### Option B — Multi-Agent Hierarchy (Orchestrator + Specialized Sub-Agents)

`AnalysisOrchestrator` delegates sub-tasks to named agents (`ClassifierAgent`, `NarratorAgent`,
etc.). Each sub-agent has its own Claude conversation and a narrow skill set.

```
AnalysisOrchestrator
    ├── calls ClassifierAgent.classify(segments) → labeled_segments
    ├── calls NarratorAgent.narrate(clusters) → narratives
    ├── calls ScorerAgent.score(labeled_segments) → risk_score
    └── calls ReportBuilderAgent.build(...) → report
```

Pros:
- Each agent context window is small and focused.
- Sub-agents can run in parallel (Python `ThreadPoolExecutor` or `asyncio`).
- Unit-testable at sub-agent boundary (mock sub-agents for orchestrator tests).

Cons:
- More Claude API calls → higher latency and cost.
- Sub-agent coordination logic in orchestrator must handle partial failures.
- Overhead: 4–6 agents per `analyze company` run vs. 1 agent in Option A.

#### Option C — Hybrid (Orchestrator + Skills; Sub-Agents Only When Needed) ← **Recommended**

`AnalysisOrchestrator` runs a tool-use loop for the happy path (single company analysis). For
commands that require independent parallel sub-tasks (`compare`, `analyze sector`, `trend`), it
instantiates a specialized sub-agent to handle the independent workload.

Rule: **sub-agent only when task is independently parallelizable and context-isolated**.

```
analyze company AAPL:
    AnalysisOrchestrator (tool-use loop)
        → load_filing, classify_segment, summarize_cluster, score_risk, format_report

compare AAPL MSFT:
    AnalysisOrchestrator
        ├── spawn ClassifierAgent(AAPL)  ← parallel
        ├── spawn ClassifierAgent(MSFT)  ← parallel
        └── merge → diff_risk_profiles → format_report

analyze sector 3571:
    AnalysisOrchestrator
        ├── spawn ClassifierAgent(filing_1), ..., ClassifierAgent(filing_N)  ← parallel
        └── merge → aggregate_sector → format_report

trend AAPL --years 3:
    AnalysisOrchestrator (tool-use loop; sequential by year)
        → load_filing(2024), load_filing(2023), load_filing(2022)
        → detect_yoy_delta(2024, 2023), detect_yoy_delta(2023, 2022)
        → format_report
```

Pros:
- Single-company path stays simple (Option A).
- Parallel path remains testable (mock sub-agents).
- Context isolation: each ClassifierAgent sees only its own filing.

Cons:
- Two modes to maintain (tool-use loop + sub-agent dispatch).
- Need a clear rule for "when to spawn a sub-agent" (defined above).

**Decision:** Option C. Sub-agent threshold = 2+ independent filing analyses.

---

### 2.2 Skill Transport

#### Option A — Python Function Calls (Direct Dispatch) ← **Recommended**

Skills are Python callables. The orchestrator maintains a `skill_registry: dict[str, Callable]`
and dispatches by name from Claude's `tool_use` block.

```python
SKILL_REGISTRY = {
    "load_filing": load_filing,
    "classify_segment": classify_segment,
    "summarize_cluster": summarize_cluster,
    ...
}

result = SKILL_REGISTRY[block.name](**block.input)
```

Pros:
- No network overhead; skills run in-process.
- Standard Python testing (pytest, monkeypatch).
- No MCP server infrastructure required.
- Skills can share Python objects (e.g., loaded `TaxonomyManager` singleton).

Cons:
- Skills run in main process; a skill crash can bring down the orchestrator.
  Mitigation: wrap each dispatch in `try/except SkillError`.

#### Option B — MCP Server (Tool Execution via Protocol)

Skills exposed as MCP tools; orchestrator connects to MCP server via stdio or SSE.

Pros: Skills in a separate process (isolation); MCP tooling ecosystem.

Cons: Infrastructure overhead (MCP server process, protocol serialization); debugging harder;
MCP not yet stable across all Claude SDK versions. Not justified for a single-machine, single-engineer
tool.

**Decision:** Option A. Direct Python function dispatch.

---

### 2.3 YoY Delta Algorithm

#### Option A — TF-IDF Cosine Similarity

Build TF-IDF matrices from prior-year and current-year segment texts; compute cluster-level
cosine similarity to detect added/removed/shifted topics.

Pros: No model load; fast; interpretable feature weights.
Cons: Vocabulary drift between years confounds similarity; doesn't capture semantic shift in
paraphrased language (e.g., "supply chain disruption" → "supplier concentration risk").

#### Option B — Sentence Embedding Cosine Similarity ← **Recommended**

Use `all-MiniLM-L6-v2` (already in `worker_pool.py` global init) to embed cluster centroids;
cosine similarity across years at cluster level.

```python
current_embeddings = model.encode([cluster.representative_text for cluster in current_clusters])
prior_embeddings   = model.encode([cluster.representative_text for cluster in prior_clusters])
delta_matrix = cosine_similarity(current_embeddings, prior_embeddings)
# New cluster: row max < 0.70 threshold
# Removed cluster: col max < 0.70 threshold
# Shifted cluster: row max ≥ 0.70 but < 0.85
# Stable cluster: row max ≥ 0.85
```

Pros: Handles paraphrase; leverages existing model (no new dependency); resolves OQ-A04.
Cons: Requires `SentenceTransformer` in the analysis process; adds ~100ms per cluster pair.

**Decision:** Option B. Sentence embeddings with threshold 0.70 / 0.85 (new/shifted/stable).

---

## 3. Resolved Questions from PRD-005

| Open Question | Resolution | Rationale |
|---------------|------------|-----------|
| OQ-A01: Streaming vs. blocking Claude calls | **Blocking calls** for Phase C (narrator). Add streaming as Phase F optimization if P95 latency > 60 s in integration testing. | Simpler to implement; streaming complicates `agent_trace.jsonl` assembly. |
| OQ-A02: `composite_risk_score` formula | **Frequency-weighted average with confidence multiplier**, scaled to 1–100: `raw = Σ(count_i × mean_confidence_i) / total_segments`; `score = round(raw × 100)`. Weights: each of the 5 archetypes (excluding "other") contributes proportionally. | Simple, interpretable, uses the `confidence` field already emitted by `ClassificationResult`. Severity signals (sentiment polarity) deferred to a future scoring version via ADR. |
| OQ-A04: TF-IDF vs. sentence embeddings for delta | **Sentence embeddings** (Option B in §2.3 above) | Handles paraphrase; no new dependency; `all-MiniLM-L6-v2` already in worker pool. |
| OQ-A06: Full segment text vs. segment ID in trace | **Segment IDs only** in `agent_trace.jsonl` `input` field (cross-reference `*_segmented.json`). | Keeps trace payloads small; avoids duplicating segment text that already lives in the segmented JSON. |

---

## 4. Architecture Summary (Option C)

### Component Diagram

```
src/analysis/
├── cli.py                     # argparse; maps command → orchestrator call
├── orchestrator.py            # AnalysisOrchestrator
│   ├── _tool_loop()           # tool-use loop for single-company commands
│   └── _parallel_dispatch()   # spawn sub-agents for compare/sector
├── agents/
│   ├── classifier_agent.py    # ClassifierAgent (own Claude context; spawned by _parallel_dispatch)
│   ├── narrator_agent.py      # NarratorAgent — NOT a sub-agent with its own Claude context.
│   │                          # Invoked as an inline skill call in the orchestrator's tool-use
│   │                          # loop via summarize_cluster. PRD-005 §4.1 lists it as an agent
│   │                          # for organizational clarity only.
│   ├── comparator_agent.py    # ComparatorAgent
│   ├── trend_agent.py         # TrendAgent
│   └── report_builder.py      # ReportBuilderAgent
└── skills/
    ├── filing_loader.py       # load_filing
    ├── classifier.py          # classify_segment (wraps SegmentAnnotator)
    ├── narrator.py            # summarize_cluster (Claude API call)
    ├── scorer.py              # score_risk
    ├── delta_detector.py      # detect_yoy_delta (sentence embeddings)
    ├── comparator.py          # diff_risk_profiles, aggregate_sector
    └── reporter.py            # format_report, export_report
```

### Skill Registration Pattern

```python
# src/analysis/orchestrator.py
from anthropic.types import ToolParam

TOOLS: list[ToolParam] = [
    {
        "name": "load_filing",
        "description": "Load a SegmentedRisks JSON for a given ticker and fiscal year.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "fiscal_year": {"type": "string"},
                "run_dir": {"type": "string"}
            },
            "required": ["ticker", "fiscal_year"]
        }
    },
    # ... other tools
]
```

### Trace Log Schema

Each line in `agent_trace.jsonl` is one JSON object:

```json
{
  "ts": "2026-07-07T14:23:01.123Z",
  "event": "tool_use",
  "tool": "classify_filing",
  "input": {"ticker": "AAPL", "fiscal_year": "2024", "run_dir": "data/processed/20260220_185647_preprocessing_b9fb777"},
  "output": {"segment_count": 161, "label_distribution": {"business_model": 57, "governance": 22}},
  "duration_ms": 3420,
  "status": "ok"
}
```

Event types: `"orchestrator_start"`, `"llm_call"`, `"tool_use"`, `"tool_error"`,
`"sub_agent_spawn"`, `"sub_agent_result"`, `"orchestrator_end"`.

---

## 5. Constraints & Non-Negotiables

1. **ADR-001 (Pydantic V2):** All new models in `src/analysis/models/` use
   `model_config = ConfigDict(validate_assignment=True, extra="forbid")`.
2. **ADR-006 (Modular Config):** New `AnalysisConfig` is a separate `BaseSettings` module; not
   merged into existing config modules.
3. **ADR-007 (Stamped Runs):** `data/reports/{YYYYMMDD_HHMMSS}_analysis_{git_sha}/` mandatory.
4. **No new ML model dependencies:** Skills must use models already present (`all-MiniLM-L6-v2`,
   `facebook/bart-large-mnli`) or the Claude API. No HuggingFace model downloads in Phase A–C.
5. **No LLM calls in unit tests:** Skill unit tests mock `anthropic.Anthropic`; integration tests
   use `@pytest.mark.integration` and are excluded from default `pytest` run.

---

## 6. Open Questions (Remaining)

| ID | Question | Target Phase |
|----|----------|--------------|
| OQ-A03 | Minimum number of filings for `analyze sector` to be meaningful (proposed: ≥ 5)? | Before Phase D |
| OQ-A05 | `compare` command: require same `--run-dir` or allow mixed? | Before Phase D |

*OQ-A02 and OQ-A06 resolved — see §3 above.*

---

## 7. Next Steps

Once OQ-A02, OQ-A03, OQ-A05, OQ-A06 are resolved, file **ADR-017** capturing the orchestration
model (Option C), skill transport (Option A), and delta algorithm (Option B) as accepted
decisions. This RFC then becomes historical context.
