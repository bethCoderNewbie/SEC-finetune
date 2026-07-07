# PRD-005: SEC 10-K Agentic Analysis Workflow

| Field | Value |
|-------|-------|
| **Status** | DRAFT |
| **Version** | 0.1 |
| **Author** | Beth |
| **Created** | 2026-07-07 |
| **Last Updated** | 2026-07-07 |
| **Supersedes** | — |
| **Source PRDs** | PRD-002 (pipeline v2), PRD-004 (business intelligence use cases) |

---

## 1. Context & Problem

The preprocessing pipeline (PRD-002) produces `SegmentedRisks` JSON files — one per 10-K section per
filing — containing hundreds of cleaned, tokenized risk text segments enriched with metadata
(CIK, SIC, ticker, fiscal year, ancestor breadcrumbs). This structured output exists solely to
feed the fine-tuning pipeline (PRD-003). No facility currently exists to turn that output into
**actionable analysis**.

Analysts who want to answer questions like *"What are Apple's top three cybersecurity risks this
year?"* or *"How has this company's regulatory risk language shifted over the past three years?"*
must read raw 300-page filings or write bespoke Python scripts against the JSON. Neither scales.

PRD-004 identified high-value business intelligence use cases (competitive benchmarking, M&A due
diligence, supplier risk screening) but left them aspirational: no implementation plan, no
architecture, no commands. This PRD closes that gap by defining an **agentic analysis layer** that
sits between the preprocessing pipeline output and the human consumer — transforming structured
JSON into structured **analysis reports** via composable agents, skills, and CLI commands.

---

## 2. Goals & Non-Goals

### 2.1 Goals

| ID | Goal | Success Metric |
|----|------|---------------|
| **G-A01** | Consume `SegmentedRisks` JSON as primary input | All commands read from `data/processed/` run directories without re-parsing |
| **G-A02** | Provide a CLI command `analyze company <ticker>` that produces a full risk report | Report generated end-to-end in ≤ 60 s for a single 10-K; no Python script required |
| **G-A03** | Provide a CLI command `compare <ticker1> <ticker2>` producing a side-by-side report | Two-company comparison output matches the schema in §5 |
| **G-A04** | Provide a CLI command `trend <ticker> --years N` for YoY change analysis | Delta scores and changed risk clusters surfaced per fiscal year pair |
| **G-A05** | Provide a CLI command `analyze sector <sic>` for cohort-level risk aggregation | Sector report aggregates ≥ 2 filings within the SIC; fails gracefully if fewer found |
| **G-A06** | Export reports as Markdown (default), JSON, and CSV | `--format md|json|csv` flag honored; output files written to `data/reports/` |
| **G-A07** | Agents use composable **skills** (Python callables) for each analytic step | Every skill is independently testable; orchestrator is swappable |
| **G-A08** | Agent reasoning traces logged to `data/reports/<run_id>/agent_trace.jsonl` | Every LLM call, tool invocation, and decision logged with timestamp |
| **G-A09** | Commands integrate with existing stamped run directory layout (ADR-007) | Report run directories follow `{YYYYMMDD_HHMMSS}_analysis_{git_sha}/` pattern |

### 2.2 Non-Goals

- **Not a real-time streaming system.** Analysis runs on already-preprocessed batch output; no live
  EDGAR feed.
- **Not investment advice.** Reports surface risk language patterns; they make no buy/sell/hold
  recommendations.
- **Not modifying the preprocessing pipeline.** Segmentation, cleaning, and QA validation remain
  in the preprocessing layer (PRD-002/003). This PRD adds a layer *above* that output.
- **Not a fine-tuning pipeline.** Training corpus construction remains in PRD-003; this PRD
  produces human-readable reports, not training JSONL.
- **Not a multi-user API.** The system is a single-engineer CLI tool; no REST API, no
  authentication, no multi-tenant concerns.
- **Not replacing the Streamlit UI.** The existing Streamlit app remains a separate concern.
  These CLI commands are text-driven.
- **Not supporting relative paths or partial filing inputs.** Commands require a fully preprocessed
  run directory; no raw HTML accepted as input.

---

## 3. Dataset & Feature Schema

### 3.1 Input: SegmentedRisks JSON (Existing)

The primary input is the `*_segmented.json` output produced by the preprocessing pipeline
(PRD-002 §2.1). Key fields consumed by the analysis layer:

| Field | Type | Source |
|-------|------|--------|
| `document_info.ticker` | str | SGMLManifest extraction |
| `document_info.sic_code` | str | SGMLManifest extraction |
| `document_info.company_name` | str | SGMLManifest extraction |
| `document_info.fiscal_year` | str | SGMLManifest extraction |
| `document_info.filed_as_of_date` | str (YYYYMMDD) | SGMLManifest extraction |
| `section_metadata.identifier` | str | SECSectionExtractor |
| `chunks[].text` | str | RiskSegmenter |
| `chunks[].parent_subsection` | str\|null | RiskSegmenter |
| `chunks[].ancestors` | list[str] | `RiskSegmenter._resolve_ancestors()` (ADR-014 decision; `segmenter.py:457`) |
| `chunks[].word_count` | int | RiskSegmenter |

**Annotation is always a required Phase B step.** `SegmentAnnotator` writes a separate JSONL file
via the preprocessing pipeline (US-032/US-029); it does **not** update chunk fields in-place in
`*_segmented.json`. The `classify_filing` skill in Phase B always runs annotation fresh from the
raw `SegmentedRisks` input — these fields below are produced by that skill call, not pre-populated:

| Field | Type | Produced by |
|-------|------|-------------|
| `risk_label` | str | `classify_filing` skill → `SegmentAnnotator` |
| `sasb_topic` | str\|null | `classify_filing` skill → `TaxonomyManager` |
| `sasb_industry` | str | `classify_filing` skill → `TaxonomyManager` |
| `confidence` | float | NLI classifier inside `SegmentAnnotator` |
| `label_source` | str | ADR-015 namespace (7 values) |

### 3.2 Analysis Output Schema

Each analysis command writes a report to `data/reports/<run_id>/`. The report bundle contains:

```
data/reports/{YYYYMMDD_HHMMSS}_analysis_{git_sha}/
├── report.md                      # Human-readable Markdown (default)
├── report.json                    # Machine-readable structured result
├── report.csv                     # Tabular segment-level export (optional)
└── agent_trace.jsonl              # One line per agent action (G-A08)
```

**report.json schema (top-level):**

```json
{
  "schema_version": "1.0",
  "command": "analyze company",
  "generated_at": "2026-07-07T14:23:01Z",
  "inputs": {
    "ticker": "AAPL",
    "fiscal_year": "2024",
    "run_dir": "data/processed/20260220_185647_preprocessing_b9fb777"
  },
  "summary": {
    "total_segments": 161,
    "risk_label_distribution": {
      "environment": 8,
      "social_capital": 4,
      "human_capital": 12,
      "business_model": 57,
      "governance": 22,
      "other": 58
    },
    "top_sasb_topics": ["Product Design & Lifecycle Management", "Data Privacy & Freedom of Expression", "Business Ethics"],
    "composite_risk_score": 72
  },
  "clusters": [
    {
      "archetype": "business_model",
      "sasb_topic": "Product Design & Lifecycle Management",
      "segment_count": 23,
      "representative_segments": ["..."],
      "narrative_summary": "Apple faces product concentration risk..."
    }
  ],
  "agent_model": "claude-opus-4-6",
  "skill_versions": { "classify": "1.0", "summarize": "1.0", "score": "1.0" }
}
```

---

## 4. Agent Architecture

### 4.1 Agents

The system uses a **single orchestrator agent** that delegates to **skill functions** (Python
callables registered as tools). Specialized sub-agents are optional extensions for complex
multi-step tasks (compare, trend). See RFC-008 for the full design proposal.

| Agent | Role | Skills Used |
|-------|------|-------------|
| `AnalysisOrchestrator` | Entry point; decides workflow; assembles final report | All |
| `ClassifierAgent` | Assigns SASB archetype + topic to all segments in a filing | `classify_filing`, `load_taxonomy` |
| `NarratorAgent` | Produces natural-language summaries per risk cluster | `summarize_cluster` |
| `ComparatorAgent` | Diffs two companies or two fiscal years | `load_filing`, `diff_risk_profiles` |
| `TrendAgent` | Computes YoY delta across N fiscal years | `load_filing`, `detect_yoy_delta` |
| `ReportBuilderAgent` | Assembles all analytic outputs into the report schema | `format_report`, `export_report` |

### 4.2 Skills (Tool Functions)

Skills are Python callables with typed signatures. Each is independently unit-testable. The
orchestrator calls them as LLM tool use (Anthropic SDK `tools=` parameter).

| Skill | Signature | Description |
|-------|-----------|-------------|
| `load_filing` | `(ticker: str, fiscal_year: str, run_dir: Path) → SegmentedRisks` | Locate and deserialize the correct `_segmented.json` file |
| `classify_filing` | `(ticker: str, fiscal_year: str, run_dir: str) → List[ClassificationResult]` | SASB archetype + topic classification for all segments in a filing; wraps `SegmentAnnotator.annotate()`. One tool call per filing preserves ancestor-prior context across adjacent segments. |
| `summarize_cluster` | `(segments: list[str], archetype: str) → str` | LLM call: 1–3 sentence narrative for a risk cluster |
| `score_risk` | `(segments: list[LabeledSegment]) → RiskScore` | Composite 1–100 risk score from frequency, confidence, severity heuristics |
| `detect_yoy_delta` | `(current: SegmentedRisks, prior: SegmentedRisks) → YoYDelta` | Cluster-level cosine-similarity delta; new/removed/changed clusters |
| `diff_risk_profiles` | `(a: SegmentedRisks, b: SegmentedRisks) → ComparisonResult` | Side-by-side archetype distribution diff between two companies |
| `aggregate_sector` | `(filings: list[SegmentedRisks]) → SectorProfile` | Aggregate archetype distributions across a SIC cohort |
| `format_report` | `(analysis: AnalysisResult, fmt: str) → str` | Render to Markdown, JSON, or CSV string |
| `export_report` | `(content: str, run_dir: Path, fmt: str) → Path` | Write rendered content to stamped run directory |

### 4.3 Commands (CLI)

Module: `src/analysis/cli.py` — invoked via `python -m src.analysis.cli <command> [args]`

```
Commands:
  analyze company <ticker>  [--year <YYYY>] [--run-dir <path>] [--format md|json|csv]
  analyze sector  <sic>     [--year <YYYY>] [--run-dir <path>] [--format md|json|csv]
  compare <ticker1> <ticker2> [--year <YYYY>] [--run-dir <path>] [--format md|json|csv]
  trend   <ticker>          [--years <N>]   [--run-dir <path>] [--format md|json|csv]
  report  <ticker>          [--year <YYYY>] [--run-dir <path>] [--format md|json|csv]  # US-041
```

Defaults:
- `--year`: most recent fiscal year present in `--run-dir`
- `--run-dir`: latest stamped run directory in `data/processed/`
- `--format`: `md`

Output always written to `data/reports/{run_id}/`. Path printed to stdout on completion.

---

## 5. Engineering & MLOps

### 5.1 Module Layout

New source locations (no changes to existing `src/preprocessing/` or `src/utils/`):

```
src/
└── analysis/
    ├── cli.py                    # Argument parsing + command dispatch (NEW)
    ├── orchestrator.py           # AnalysisOrchestrator (Claude API client) (NEW)
    ├── agents/
    │   ├── __init__.py
    │   ├── classifier_agent.py   # ClassifierAgent (NEW)
    │   ├── narrator_agent.py     # NarratorAgent (NEW)
    │   ├── comparator_agent.py   # ComparatorAgent (NEW)
    │   ├── trend_agent.py        # TrendAgent (NEW)
    │   └── report_builder.py     # ReportBuilderAgent (NEW)
    ├── skills/
    │   ├── __init__.py
    │   ├── filing_loader.py      # load_filing skill (NEW)
    │   ├── classifier.py         # classify_filing skill (wraps existing SegmentAnnotator) (NEW)
    │   ├── narrator.py           # summarize_cluster skill (NEW)
    │   ├── scorer.py             # score_risk skill (NEW)
    │   ├── delta_detector.py     # detect_yoy_delta skill (NEW)
    │   ├── comparator.py         # diff_risk_profiles + aggregate_sector (NEW)
    │   └── reporter.py           # format_report + export_report (NEW)
    │                             # NOTE: `src/utils/reporting.py` contains an existing
    │                             # `MarkdownReportGenerator` — consider reuse before re-implementing.
    ├── models/
    │   ├── __init__.py
    │   ├── analysis.py           # AnalysisResult, ClusterResult, RiskScore, YoYDelta, ComparisonResult (NEW)
    │   └── report.py             # ReportBundle schema (NEW)
    ├── segment_annotator.py      # EXISTING — wrapped by classifier skill
    ├── inference.py              # EXISTING — wraps BART NLI for SegmentAnnotator._classify_segment()
    └── taxonomies/               # EXISTING
        ├── taxonomy_manager.py
        ├── sasb_sics_mapping.json
        └── archetype_to_sasb.yaml
```

### 5.2 Claude API Integration

The orchestrator and narrator agents call the Anthropic Claude API using the `anthropic` Python
SDK (**not yet in `pyproject.toml`; must be added before Phase C** — see Tech Req #2).
Model: `claude-opus-4-6` (overridable via config).

Configuration via `src/config/analysis.py` (new module, following ADR-006 pattern):

```python
class AnalysisConfig(BaseSettings):
    model: str = "claude-opus-4-6"
    max_tokens: int = 4096
    temperature: float = 0.2
    skill_timeout_seconds: int = 30
    trace_logging: bool = True
    report_output_dir: Path = Path("data/reports")
```

### 5.3 Pydantic V2 Enforcement (ADR-001)

All new data models in `src/analysis/models/` must use `model_config = ConfigDict(validate_assignment=True, extra="forbid")`.

### 5.4 Run Directory Convention (ADR-007)

Analysis run directories mirror the preprocessing convention:
```
data/reports/{YYYYMMDD_HHMMSS}_analysis_{git_sha}/
```
`RunMetadata` from `src/utils/metadata.py` is reused for git SHA capture.

**Note:** `data/reports/` is excluded by `.gitignore:70` (the `data/` rule). All analysis output
is local-only and intentionally not committed to version control — the same policy as
`data/processed/`. Do not move report output outside `data/` without updating `.gitignore`.

### 5.5 Error Handling

- Skill failures raise typed exceptions (`SkillError(skill_name, reason)`) caught by the orchestrator.
- Failed skill calls are written to `agent_trace.jsonl` with `"status": "error"`.
- The orchestrator does not retry by default; failed analyses exit non-zero.
- If a ticker has no preprocessed run directory, `load_filing` raises `FilingNotFoundError`
  (not a generic `FileNotFoundError`).

---

## 6. Phase-Gate Plan

### Phase A — Foundation (CLI + Filing Loader + Report Skeleton)

Delivers `analyze company` with stub agent output (no LLM calls yet).

- [ ] **A-1** Create `src/analysis/cli.py` with `analyze company` argument parsing
- [ ] **A-2** Create `src/analysis/skills/filing_loader.py` (`load_filing` skill)
- [ ] **A-3** Create `src/analysis/models/analysis.py` (Pydantic V2 schemas)
- [ ] **A-4** Create `src/analysis/skills/reporter.py` (`format_report`, `export_report`)
- [ ] **A-5** Wire together: `analyze company AAPL` loads segments, writes stub `report.md`
- [ ] **A-6** Unit tests for `load_filing` and `format_report`

**Exit criterion:** `python -m src.analysis.cli analyze company AAPL` exits 0, writes `report.md`.

### Phase B — Classification Skill (Wraps Existing Annotator)

- [ ] **B-1** Create `src/analysis/skills/classifier.py` wrapping `SegmentAnnotator`
- [ ] **B-2** Create `src/analysis/agents/classifier_agent.py`
- [ ] **B-3** Wire classifier into `analyze company` output (populates `risk_label_distribution`)
- [ ] **B-4** Unit tests for `classify_filing` with mock `SegmentAnnotator`

**Exit criterion:** `report.json` contains non-zero `risk_label_distribution` values.

### Phase C — LLM Narration (Claude API)

- [ ] **C-1** Create `src/config/analysis.py` (`AnalysisConfig`)
- [ ] **C-2** Create `src/analysis/orchestrator.py` (Claude API client, tool loop)
- [ ] **C-3** Create `src/analysis/skills/narrator.py` (`summarize_cluster`)
- [ ] **C-4** Create `src/analysis/agents/narrator_agent.py`
- [ ] **C-5** Wire: each cluster in `report.json` has `narrative_summary`
- [ ] **C-6** Implement `agent_trace.jsonl` logging (G-A08)
- [ ] **C-7** Integration test: mock Claude API responses; verify trace log structure

**Exit criterion:** `report.json` clusters contain `narrative_summary` strings; `agent_trace.jsonl` written.

### Phase D — Scoring & Comparison Commands

- [ ] **D-1** Create `src/analysis/skills/scorer.py` (`score_risk`)
- [ ] **D-2** Create `src/analysis/skills/comparator.py` (`diff_risk_profiles`, `aggregate_sector`)
- [ ] **D-3** Wire `analyze company` to include `composite_risk_score`
- [ ] **D-4** Create `compare` command and `src/analysis/agents/comparator_agent.py`
- [ ] **D-5** Create `analyze sector` command
- [ ] **D-6** Unit tests for scoring and comparison skills

**Exit criterion:** `compare AAPL MSFT` exits 0 and writes a report with both tickers.

### Phase E — Trend Analysis Command

- [ ] **E-1** Create `src/analysis/skills/delta_detector.py` (`detect_yoy_delta`)
- [ ] **E-2** Create `src/analysis/agents/trend_agent.py`
- [ ] **E-3** Wire `trend` command
- [ ] **E-4** Unit tests for `detect_yoy_delta`

**Exit criterion:** `trend AAPL --years 3` exits 0; `YoYDelta` objects present in `report.json`.

### Phase F — Hardening & Documentation

- [ ] **F-1** End-to-end integration test: process one real 10-K, run `analyze company`, validate report
- [ ] **F-2** Update `docs/ops/runbook.md` with analysis command symptoms and fixes
- [ ] **F-3** Update `docs/architecture/data_dictionary.md` with `AnalysisResult` schema
- [ ] **F-4** Add `--format csv` export path
- [ ] **F-5** Add `report` command alias (shorthand for `analyze company` with explicit format)

---

## 7. User Stories

### EP-8: Agentic Analysis

All stories below belong to **EP-8**. See the [epic table](README.md#epics) for cross-epic context.

| ID | Priority | As a | I want to | So that | Status | Detail |
|----|----------|------|-----------|---------|--------|--------|
| [US-033](stories/US-033_analyze_company_command.md) | **P0** | Financial Analyst | Run `analyze company <ticker>` and receive a structured risk report | I can analyze a company's risk posture without writing custom code | ❌ Not implemented | [Detail](stories/US-033_analyze_company_command.md) |
| [US-034](stories/US-034_agent_classification_skill.md) | **P0** | ML Engineer | Have an agent skill classify each segment by SASB archetype and topic | Every report is grounded in the SASB taxonomy without manual labeling | ❌ Not implemented | [Detail](stories/US-034_agent_classification_skill.md) |
| [US-035](stories/US-035_multi_format_report_export.md) | **P0** | Data Scientist | Export analysis reports as Markdown, JSON, or CSV using `--format` | I can integrate analysis results into downstream tools without format conversion | ❌ Not implemented | [Detail](stories/US-035_multi_format_report_export.md) |
| [US-036](stories/US-036_compare_companies.md) | **P1** | Corporate Development Analyst | Run `compare <ticker1> <ticker2>` and get a side-by-side risk comparison | I can identify divergent risk exposures between acquisition targets | ❌ Not implemented | [Detail](stories/US-036_compare_companies.md) |
| [US-037](stories/US-037_yoy_trend_analysis.md) | **P1** | Risk Manager | Run `trend <ticker> --years N` and see which risk clusters grew or shrank | I can detect emerging or receding risk themes without reading multiple filings | ❌ Not implemented | [Detail](stories/US-037_yoy_trend_analysis.md) |
| [US-038](stories/US-038_analyze_sector_command.md) | **P1** | Strategic Analyst | Run `analyze sector <sic>` and get aggregated risk themes across a peer cohort | I can benchmark a company's risk profile against industry norms | ❌ Not implemented | [Detail](stories/US-038_analyze_sector_command.md) |
| [US-039](stories/US-039_agent_trace_logging.md) | **P1** | ML Engineer | Find a structured `agent_trace.jsonl` in every analysis run directory | I can debug agent reasoning, audit LLM decisions, and improve skill logic | ❌ Not implemented | [Detail](stories/US-039_agent_trace_logging.md) |
| [US-040](stories/US-040_composite_risk_score.md) | **P1** | Portfolio Manager | See a composite risk score (1–100) per company in the analysis report | I can triage a watchlist of companies in minutes, not hours | ❌ Not implemented | [Detail](stories/US-040_composite_risk_score.md) |
| [US-041](stories/US-041_report_command_alias.md) | **P2** | Financial Analyst | Run `report <ticker>` as a shorthand for `analyze company <ticker>` | I can generate a risk report with minimal typing | ❌ Not implemented | [Detail](stories/US-041_report_command_alias.md) |

---

## 8. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXISTING PREPROCESSING LAYER                  │
│  HTML 10-K → Parse → Extract → Clean → Segment → SegmentedRisks│
│                    data/processed/*/  *_segmented.json          │
└───────────────────────────────┬─────────────────────────────────┘
                                │  reads
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENTIC ANALYSIS LAYER (PRD-005)              │
│                                                                  │
│  CLI commands                                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  analyze company  │  compare  │  trend  │  analyze sector │  │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │ dispatches to                            │
│                      ▼                                          │
│  ┌───────────────────────────────────────────┐                 │
│  │         AnalysisOrchestrator               │                 │
│  │  (Claude claude-opus-4-6 + tool loop)          │                 │
│  └──────┬────────┬────────┬────────┬─────────┘                 │
│         │        │        │        │                            │
│    Skills (Python callables, registered as Claude tools)        │
│    ┌────▼──┐ ┌───▼───┐ ┌──▼───┐ ┌─▼──────┐ ┌─────────┐       │
│    │ load  │ │classi-│ │summ- │ │detect  │ │ format  │       │
│    │filing │ │fy_fil │ │arize │ │yoy_    │ │ report  │       │
│    └───────┘ └───────┘ └──────┘ │ delta  │ └────┬────┘       │
│                │                └────────┘       │             │
│                │ wraps                           │ writes      │
│                ▼                                 ▼             │
│    ┌───────────────────┐         data/reports/*/report.md     │
│    │  SegmentAnnotator  │              report.json             │
│    │  TaxonomyManager   │              report.csv              │
│    │  (src/analysis/)   │              agent_trace.jsonl       │
│    └───────────────────┘                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Data & Metrics

### Key Performance Indicators (KPIs)

| KPI | Target | How Measured |
|-----|--------|-------------|
| `analyze company` latency | ≤ 60 s | Wall-clock time logged in `agent_trace.jsonl` |
| `compare` latency | ≤ 90 s | Wall-clock time logged in `agent_trace.jsonl` |
| Skill unit test coverage | ≥ 90 % line coverage on `src/analysis/skills/` | `pytest --cov=src/analysis/skills` |
| `report.json` schema validity | 100% files validate against `AnalysisResult` Pydantic model | CI check on sample fixtures |
| Agent trace completeness | 100% of LLM calls and tool invocations logged | Integration test: count trace lines vs API calls |
| `classify_filing` agreement with `SegmentAnnotator` direct call | ≥ 95% label agreement | Regression test on 50-segment fixture |

---

## 10. Technical Requirements

1. **Python ≥ 3.10** — matches existing project constraint.
2. **`anthropic` Python SDK** — must be added to `pyproject.toml` dependencies if not already present.
3. **`ANTHROPIC_API_KEY` env var** — must be set; `AnalysisConfig` raises `ConfigurationError` if absent.
4. **Pydantic V2** — all new models follow ADR-001; `extra="forbid"` on all `BaseModel` subclasses.
5. **Stamped run directories** — ADR-007 pattern applied to `data/reports/`; `RunMetadata` reused from `src/utils/metadata.py`.
6. **No new database dependency** — all state in files (`data/reports/`); no SQLite, Redis, or similar.
7. **`RANDOM_SEED=42`** — any sampling operations (e.g., representative segment selection) must use this seed for reproducibility.
8. **No LLM calls in unit tests** — skill tests mock the `anthropic.Anthropic` client; integration tests tag with `@pytest.mark.integration` and are excluded from the default CI run.
9. **Skill timeouts** — each skill invocation uses `concurrent.futures.Future.result(timeout=AnalysisConfig.skill_timeout_seconds)` for thread-safe cancellation; timeout raises `SkillTimeoutError`. **`signal.alarm` / `SIGALRM` must not be used** — it only fires on the main thread and silently fails (or raises `ValueError`) when called from `ThreadPoolExecutor` worker threads used by `_parallel_dispatch()`.
10. **CLI exit codes** — 0 on success, 1 on user input error, 2 on skill/agent failure. Consistent with existing `run_preprocessing_pipeline.py` behavior.

---

## 11. Open Questions

| ID | Question | Owner | Priority |
|----|----------|-------|----------|
| OQ-A01 | Should `summarize_cluster` use Claude streaming to reduce P95 latency, or blocking calls for simplicity? | ML Engineer | Medium |
| OQ-A02 | Is `composite_risk_score` a simple frequency-weighted average, or should severity signals (e.g., sentiment polarity, specificity) also factor in? Define formula before Phase D. | Data Scientist | High |
| OQ-A03 | What is the minimum number of preprocessed filings required before `analyze sector` is meaningful? Proposed: ≥ 5 filings per SIC. | Strategic Analyst | Medium |
| OQ-A04 | Should `detect_yoy_delta` use cosine similarity on TF-IDF vectors or sentence embeddings (SentenceTransformer already in worker pool)? Sentence embeddings preferred; confirm. | ML Engineer | High |
| OQ-A05 | Does the `compare` command require both companies to be in the same `--run-dir`, or can it mix run directories? Single run-dir simplest; confirm. | ML Engineer | Medium |
| OQ-A06 | Should agent trace entries include the full segment text (large payloads) or only segment IDs (requires cross-referencing)? Segment IDs preferred; confirm. | ML Engineer | Low |
