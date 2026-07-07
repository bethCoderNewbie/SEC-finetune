---
# ADR-017: Agentic Analysis Orchestration Model

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-07 |
| **Author** | Beth |
| **Supersedes** | — |
| **References** | RFC-008, PRD-005 |

---

## Context

PRD-005 adds an agentic analysis layer above the preprocessing pipeline. RFC-008 proposed three
candidate orchestration models (Options A, B, C), two skill transport strategies (A, B), and two
YoY delta algorithms (A, B). After implementation in `src/analysis/`, these decisions are now
captured as immutable ADRs.

Four open questions from RFC-008 §6 were resolved during implementation:
- **OQ-A02** — `composite_risk_score` formula (§ Decision below)
- **OQ-A06** — `agent_trace.jsonl` segment text vs. ID (§ Decision below)
- **OQ-A03** and **OQ-A05** remain open; see § Open Questions.

---

## Decision

### 1. Orchestration Model — RFC-008 Option C (Hybrid)

`AnalysisOrchestrator` uses a **tool-use loop** for single-company commands and spawns
**`ComparatorAgent` / `ClassifierAgent` workers** via `ThreadPoolExecutor` for multi-company
commands (`compare`, `analyze sector`).

Governing rule (RFC-008 §2.1): _a sub-agent is spawned only when the task is independently
parallelisable and context-isolated_ (i.e., requires classifying two or more separate filings
simultaneously).

**Implemented in:** `src/analysis/orchestrator.py:AnalysisOrchestrator`
- `_tool_loop()` path → `analyze company`, `trend`
- `_parallel_dispatch()` / `_parallel_dispatch_sector()` path → `compare`, `analyze sector`

### 2. Skill Transport — RFC-008 Option A (Direct Python Dispatch)

Skills are Python callables in `src/analysis/skills/`. The orchestrator maintains a
`SKILL_REGISTRY`-equivalent dispatch via `if tool_name == "..."` branches. No MCP server, no
subprocess execution.

**Implemented in:** `src/analysis/orchestrator.py` tool dispatch; `src/analysis/skills/__init__.py`

### 3. YoY Delta Algorithm — RFC-008 Option B (Sentence Embeddings)

`detect_yoy_delta` uses `all-MiniLM-L6-v2` (already loaded in `worker_pool.py`) to encode
cluster representative texts, then computes cosine similarity with the following thresholds:

| Similarity | Classification |
|------------|---------------|
| < 0.70 | new cluster |
| 0.70 – 0.85 | shifted cluster |
| ≥ 0.85 | stable cluster |
| absent in current | removed cluster |

Graceful fallback: if `sentence_transformers` or `sklearn` raises during encoding, the skill
falls back to exact archetype-name matching.

**Implemented in:** `src/analysis/skills/delta_detector.py:detect_yoy_delta`

### 4. classify_filing Granularity — Filing-Level (not Per-Text)

The `classify_filing` skill wraps `SegmentAnnotator.annotate(segmented: SegmentedRisks)` at
filing granularity. One Claude tool call per filing, not one per segment. This preserves the
ancestor-prior classification path (Layer 3 of 5 in `SegmentAnnotator._classify_segment()`)
across adjacent segments.

A per-text `classify_segment(text, sic_code)` wrapper would silently drop
`label_source="ancestor_prior"` for all segments after the first.

**Implemented in:** `src/analysis/skills/classifier.py:classify_filing`

### 5. Skill Timeout — `concurrent.futures` (not `signal.alarm`)

Each skill invocation uses `concurrent.futures.Future.result(timeout=N)` inside a
`ThreadPoolExecutor(max_workers=1)` wrapper. `signal.alarm` / `SIGALRM` is explicitly
prohibited — it only fires on the main thread and raises `ValueError` when called from
`ThreadPoolExecutor` worker threads.

**Implemented in:** `src/analysis/orchestrator.py:AnalysisOrchestrator._run_skill()`
**Timeout exception:** `src/analysis/skills/filing_loader.py:SkillTimeoutError`

### 6. composite_risk_score Formula — OQ-A02

```
raw  = Σ(count_i × mean_confidence_i) / total_segments
         where i ∈ {environment, social_capital, human_capital, business_model, governance}
score = clip(round(raw × 100), 1, 100)
```

"Other"-labelled segments are excluded from the numerator (they carry no SASB signal).

**Implemented in:** `src/analysis/skills/scorer.py:score_risk`

### 7. agent_trace.jsonl Payload — Segment IDs Only (OQ-A06)

Trace entries for `classify_filing` record `{"ticker": ..., "fiscal_year": ..., "run_dir": ...}`
as input (not full segment texts). Full texts are cross-referenceable in the source
`*_segmented.json` files via `segment_id`.

**Implemented in:** `src/analysis/orchestrator.py:AnalysisOrchestrator._trace_event()`

---

## Consequences

### Positive

- Single-company path (`analyze company`, `trend`) requires exactly one `AnalysisConfig`
  instance and one `AnalysisOrchestrator` — minimal operational surface.
- Filing-level classification preserves all 5 classification layers of `SegmentAnnotator`,
  maximising label quality.
- `concurrent.futures` timeout is thread-safe and testable (mock `Future`).
- Trace payload is small; `agent_trace.jsonl` stays under 1 MB for typical runs.

### Negative / Trade-offs

- Two code paths in `AnalysisOrchestrator` (tool-use loop + parallel dispatch) require
  separate testing strategies.
- Filing-level `classify_filing` loads the NLI model once per process but cannot be
  parallelised per-segment (model is not thread-safe without separate workers).
- `composite_risk_score` formula does not incorporate severity signals (sentiment polarity,
  specificity). A v2 formula may be filed as a superseding ADR if KPI §9 targets are not met.

---

## Open Questions (not yet closed)

| ID | Question | Target |
|----|----------|--------|
| OQ-A03 | Minimum filings for `analyze sector` to be meaningful (default impl: `sector_min_filings=2`) | Before Phase D |
| OQ-A05 | `compare` command: same `--run-dir` only, or allow mixed? (default impl: same dir) | Before Phase D |

---

## Supersedes

Nothing.

## References

- `RFC-008_Agentic_Analysis_Architecture.md`
- `PRD-005_Agentic_Analysis_Workflow.md`
- `src/analysis/orchestrator.py`
- `src/analysis/skills/filing_loader.py`
- `src/analysis/skills/classifier.py`
- `src/analysis/skills/scorer.py`
- `src/analysis/skills/delta_detector.py`
