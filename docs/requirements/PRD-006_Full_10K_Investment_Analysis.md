# PRD-006: SEC 10-K Full-Section Investment Analysis — Hybrid NLP + LLM

| Field | Value |
|-------|-------|
| **Status** | DRAFT |
| **Version** | 0.3 |
| **Author** | Beth |
| **Created** | 2026-08-13 |
| **Last Updated** | 2026-08-14 |
| **Supersedes** | — |
| **Source PRDs** | PRD-001 (MVP), PRD-002 (pipeline v2), PRD-005 (agentic analysis) |
| **Git SHA** | 20f0171 |

---

## 1. Context & Problem

### 1.1 Current State

The preprocessing pipeline (PRD-002) extracts only **Item 1A (Risk Factors)** from SEC 10-K
filings. The agentic analysis layer (PRD-005) consumes that single section to produce risk
reports via Claude API tool-use orchestration. This has two limitations:

1. **Incomplete filing coverage.** A 10-K filing contains 15+ sections. Investment decisions
   require cross-referencing Risk Factors (Item 1A) with the Business description (Item 1),
   MD&A (Item 7), Financial Statements (Item 8), and other sections. Analyzing only Item 1A
   is like reading one chapter of a book.

2. **Token cost.** PRD-005's agentic layer sends full segment texts to the Claude API for
   every analysis. With all sections extracted, sending everything to an LLM becomes
   prohibitively expensive. A single 10-K can produce 500–2,000 segments across all sections;
   at ~300 tokens/segment, that is 150K–600K tokens per filing per analysis run.

### 1.2 Proposed Solution

A **two-tier hybrid architecture**:

- **Tier 1 — Traditional NLP (zero token cost):** Extract all key 10-K sections, apply
  deterministic NLP techniques (sentiment scoring, readability metrics, TF-IDF keyword
  extraction, named entity recognition, topic modeling, financial ratio extraction, change
  detection) to produce a structured **Basic Investment Report** entirely offline. No LLM
  tokens consumed.

- **Tier 2 — LLM Deep Analysis (token-efficient):** Feed only the Tier 1 structured outputs
  (not raw text) plus targeted text excerpts to Claude Code CLI for complex reasoning:
  cross-section synthesis, risk-opportunity correlation, management tone assessment,
  qualitative investment thesis generation.

### 1.3 Execution Model — Claude Code CLI (No API)

All LLM analysis runs through **Claude Code in VS Code terminal** (interactive CLI), not
through the Anthropic API. The operator pastes or pipes structured Tier 1 output into Claude
Code, which reasons over condensed data. This eliminates API billing and leverages the
unlimited Claude Pro/Team subscription context window.

---

## 2. Goals & Non-Goals

### 2.1 Goals

| ID | Goal | Success Metric |
|----|------|---------------|
| **G-B01** | Extract all investment-relevant 10-K sections (not just Item 1A) | 7 core sections extracted per filing (Items 1, 1A, 1B, 1C, 7, 7A, 8) |
| **G-B02** | Produce a **Basic Investment Report** using only traditional NLP (zero LLM tokens) | Report generated per filing with sentiment, readability, keywords, entities, topics, and financial signals |
| **G-B03** | Structure Tier 1 output as condensed context for LLM consumption | Tier 1 summary fits within ~4K tokens per filing (configurable; vs. 150K–600K raw) — a 95%+ compression ratio |
| **G-B04** | Define a CLI workflow for Tier 2 LLM analysis via Claude Code | Documented prompt templates (not yet created) and piping workflow for Claude Code CLI |
| **G-B05** | Cross-section analysis: correlate risk factors with MD&A disclosures | Tier 1 identifies shared keywords/entities across sections; Tier 2 synthesizes narrative |
| **G-B06** | Year-over-year change detection across all sections (not just Item 1A) | Delta report showing new/removed/modified language per section pair |
| **G-B07** | Investment signal extraction from financial statements section | Key ratios, accounting policy changes, and going-concern language flagged |
| **G-B08** | Reuse existing pipeline infrastructure (checkpoint, DLQ, stamped dirs, QA gates) | No new resilience code; existing `ParallelProcessor`, `CheckpointManager`, `ResumeFilter` used |
| **G-B09** | Tier 1 report exportable as Markdown, JSON, CSV | `--format md|json|csv` flag honored, consistent with PRD-005 export patterns |

### 2.2 Non-Goals

- **Not replacing PRD-005 agentic analysis.** The existing Claude API agentic layer remains
  for users who want full API-powered analysis. This PRD adds a token-efficient alternative.
- **Not parsing financial tables.** Item 8 (Financial Statements) contains XBRL-tagged
  tabular data. This PRD extracts prose narrative and flags key terms but does not parse
  balance sheets or income statements into structured financial models.
- **Not building a trading system.** Reports are informational; no buy/sell/hold signals,
  no portfolio optimization, no automated trading.
- **Not real-time.** Batch processing of already-downloaded filings only.
- **Not supporting 10-Q initially.** Phase 1 targets 10-K only; 10-Q support is a Phase 3
  stretch goal.
- **Not fine-tuning models.** This PRD consumes existing NLP models (Loughran-McDonald,
  spaCy, Gensim LDA); it does not train new ones.

---

## 3. Target 10-K Sections

### 3.1 Core Sections (Phase 1 — Must Extract)

| Section | Identifier | Investment Relevance | Tier 1 NLP Techniques |
|---------|-----------|---------------------|----------------------|
| **Item 1. Business** | `part1item1` | Company overview, competitive landscape, revenue sources, market position | NER (companies, products, geographies), TF-IDF keywords, topic modeling |
| **Item 1A. Risk Factors** | `part1item1a` | Primary risk disclosure — already extracted | Loughran-McDonald sentiment, readability, SASB classification (existing) |
| **Item 1B. Unresolved Staff Comments** | `part1item1b` | SEC regulatory scrutiny signals | Binary flag (present/absent), keyword extraction |
| **Item 1C. Cybersecurity** | `part1item1c` | Cyber risk governance and incident history | NER (frameworks, incidents), keyword density scoring |
| **Item 7. MD&A** | `part2item7` | Management's narrative on financial performance, forward-looking statements | Sentiment polarity, forward-looking statement detection, hedging language ratio, NER (financial metrics) |
| **Item 7A. Market Risk** | `part2item7a` | Interest rate, FX, commodity exposure | Keyword extraction (rate types, currencies, commodities), quantitative mention detection |
| **Item 8. Financial Statements** | `part2item8` | Auditor opinion, accounting policies, going-concern language | Going-concern flag, auditor opinion classification, accounting change detection |

### 3.2 Supplementary Sections (Phase 2)

| Section | Identifier | Investment Relevance |
|---------|-----------|---------------------|
| **Item 2. Properties** | `part1item2` | Asset base, geographic concentration |
| **Item 3. Legal Proceedings** | `part1item3` | Litigation exposure, settlement risk |
| **Item 5. Market for Registrant's Common Equity** | `part2item5` | Dividend policy, share repurchases |
| **Item 9A. Controls and Procedures** | `part2item9a` | Internal control weaknesses (material weakness flags) |

---

## 4. Tier 1 — Traditional NLP Feature Pipeline (Zero Token Cost)

### 4.1 Feature Extractors

Each extractor is a Python callable following the existing `src/features/` pattern
(ADR-001 Pydantic models, independently testable).

| Feature | Technique | Implementation | Output Schema |
|---------|-----------|----------------|---------------|
| **Sentiment Ensemble** | Loughran-McDonald dictionary + FinBERT | `sentiment_ensemble.py` wrapping existing `src/features/sentiment.py` + `ProsusAI/finbert` | `SentimentEnsembleResult` — 8 LM ratios + 3 FinBERT probs + ensemble score + agreement flag |
| **Readability** | Flesch-Kincaid, FOG, SMOG, Dale-Chall | Existing `src/features/readability/` (called by `section_analyzer.py`) | `ReadabilityFeatures.model_dump()` dict per section |
| **Topic Ensemble** | LDA (Gensim) + BERTopic | `topic_ensemble.py` wrapping existing `src/features/topic_modeling/` + BERTopic | `TopicEnsembleResult` — LDA dominant topic + entropy + BERTopic topic + coherence |
| **Keyword Extraction** | TF-IDF + KeyBERT | `keyword_extractor.py` — `TfidfVectorizer` + `keybert` | `KeywordResult` — top-20 TF-IDF + top-10 KeyBERT + deduplicated union |
| **Named Entity Recognition** | spaCy NER + domain rules | `ner_extractor.py` — `spacy` (en_core_web_sm) | `NERResult` — entity counts by type + typed lists (ORG, PERSON, GPE, MONEY, etc.) |
| **Forward-Looking Statements** | Regex + Loughran-McDonald modal words | `forward_looking.py` — custom regex patterns | `ForwardLookingResult` — fls_count, fls_ratio, strong/weak modal counts, sample sentences |
| **Going Concern + Auditor Opinion** | Keyword pattern matching + regex classification | `going_concern.py` — combined detector | `GoingConcernResult` — going_concern flag/count, material_weakness flag/count, auditor_opinion_type |
| **Extractive Summary** | TextRank (sumy) | `summarizer.py` | `SummaryResult` — top 3–5 extracted sentences + compression ratio |
| **Cross-Section Overlap** | Jaccard similarity on TF-IDF keyword sets | `cross_section_overlap.py` — scikit-learn | `CrossSectionOverlap` — section pair, jaccard score, shared keywords |
| **YoY Section Delta** | Sentiment/readability/keyword comparison | `yoy_delta.py` + existing `src/analysis/skills/delta_detector.py` | `YoYSectionDelta` — sentiment delta, readability delta, keyword Jaccard, topic shift flag |
| **Investment Flags** | Threshold-based binary signals | `flag_computer.py` — aggregates section features | `InvestmentFlags` — 9 boolean fields (going concern, material weakness, etc.) |

All investment-specific modules live in `src/features/investment/`. They import and wrap existing
segment-level features from `src/features/`, aggregating them to section level. Configuration
is in `configs/features/investment.yaml` loaded via `src/config/features/investment.py`.

### 4.2 Aggregated Basic Investment Report Schema

```python
# Source: src/features/investment/schemas.py (actual implementation)

class BasicInvestmentReport(BaseModel):
    """Top-level Tier 1 investment analysis report for a filing."""

    model_config = ConfigDict(extra="forbid")

    # Filing metadata (flat fields, not a sub-model)
    ticker: str
    company_name: str = ""
    fiscal_year: str
    form_type: str = "10-K"
    cik: str = ""
    sic_code: str = ""
    analyzed_at: datetime = Field(default_factory=datetime.now)

    # Analysis results
    sections: List[SectionAnalysis] = Field(default_factory=list)
    overlaps: List[CrossSectionOverlap] = Field(default_factory=list)
    flags: InvestmentFlags = Field(default_factory=InvestmentFlags)
    yoy_deltas: List[YoYSectionDelta] = Field(default_factory=list)

    # Timing
    processing_time_seconds: float = Field(0.0, ge=0.0)

class SectionAnalysis(BaseModel):
    """Full feature extraction result for one filing section."""

    model_config = ConfigDict(extra="forbid")

    section_id: str           # e.g. "item_1a"
    section_name: str = ""    # Human-readable, e.g. "Risk Factors"
    word_count: int = 0

    sentiment: SentimentEnsembleResult    # LM dict + FinBERT ensemble
    readability: Dict                     # ReadabilityFeatures.model_dump() dict
    keywords: KeywordResult               # TF-IDF + KeyBERT
    topics: TopicEnsembleResult           # LDA + BERTopic
    summary: SummaryResult                # TextRank extractive summary
    ner: NERResult                        # Named entities
    forward_looking: ForwardLookingResult  # FLS detection
    going_concern: GoingConcernResult | None  # Item 8 only

class InvestmentFlags(BaseModel):
    """Nine boolean investment flags derived from section features."""

    model_config = ConfigDict(extra="forbid")

    going_concern_present: bool = False
    material_weakness_mentioned: bool = False
    auditor_opinion_qualified: bool = False
    cybersecurity_incident_disclosed: bool = False
    unresolved_sec_comments: bool = False        # Item 1B non-empty
    high_litigation_language: bool = False        # litigious_ratio > threshold (0.05)
    high_uncertainty_language: bool = False       # uncertainty_ratio > threshold (0.08)
    significant_yoy_risk_change: bool = False     # delta > threshold (15.0)
    forward_looking_heavy: bool = False           # fls_ratio > threshold (0.15)
```

Flag thresholds are configured in `configs/features/investment.yaml` and loaded
via `src/config/features/investment.py:InvestmentConfig`.

### 4.3 Tier 2 Context Compression

The Tier 2 context is generated by `Tier2ContextGenerator` (`src/features/investment/tier2_context.py`)
as a separate step, not embedded in the report model. Default target: ~4K tokens
(`configs/features/investment.yaml: tier2_max_tokens: 4000`). Example format:

```
=== FILING: AAPL | FY2025 | SIC 3571 | Filed 2025-11-01 ===

[SECTION SUMMARIES]
Item 1 (Business): 12,450 words | Sentiment: neutral (neg=0.03, pos=0.02)
  Top Keywords: iPhone (0.42), services (0.38), China (0.31), supply chain (0.28)
  Top Entities: Apple Inc, Foxconn, European Commission, Tim Cook
  Topics: T1=consumer_electronics (0.45), T2=supply_chain (0.30), T3=regulation (0.25)

Item 1A (Risk Factors): 8,200 words | Sentiment: negative (neg=0.12, unc=0.08)
  Top Keywords: litigation (0.35), regulatory (0.33), competition (0.29)
  SASB Classification: {environment: 12%, social_capital: 25%, governance: 18%, ...}
  YoY Delta: 3 new clusters, 1 removed, similarity=0.72

Item 7 (MD&A): 15,300 words | Sentiment: slightly positive (pos=0.05, neg=0.04)
  Forward-Looking Statements: 47 (ratio=0.15) | Hedging: ratio=0.06
  Top Keywords: revenue growth (0.40), gross margin (0.37), services segment (0.35)

[INVESTMENT FLAGS]
- Going concern: NO
- Material weakness: NO
- Auditor opinion: Unqualified
- Cybersecurity incident: NO
- Unresolved SEC comments: NO
- High litigation language: YES (litigious_ratio=0.09 > 0.05 threshold)
- Significant YoY risk change: YES (Item 1A similarity=0.72)

[CROSS-SECTION SIGNALS]
- "supply chain" appears in Item 1 (0.28), Item 1A (0.22), Item 7 (0.18)
- "regulatory" appears in Item 1A (0.33), Item 1C (0.29), Item 7 (0.12)
- Item 1 ↔ Item 1A keyword overlap: Jaccard=0.35
- Item 1A ↔ Item 7 keyword overlap: Jaccard=0.28
```

This compressed representation gives the LLM sufficient signal to reason about investment
implications without consuming raw filing text.

---

## 5. Tier 2 — LLM Deep Analysis via Claude Code CLI

### 5.1 Execution Model

Tier 2 does **not** call the Anthropic API programmatically. Instead:

1. Tier 1 pipeline generates `basic_investment_report.json` and `tier2_context.txt`:
   ```bash
   python scripts/feature_engineering/run_investment_analysis.py \
       --ticker AAPL --year 2024 --format json
   ```
   Or via the CLI: `analyze invest --ticker AAPL --year 2024`
2. The operator opens Claude Code CLI in VS Code terminal
3. The operator uses one of the provided **prompt templates** (to be stored in
   `prompts/investment_analysis/` — not yet created)
4. Claude Code reads the `tier2_context.txt` file and reasons over it
5. The operator saves Claude Code's output as the final investment analysis

### 5.2 Prompt Templates

| Template | Purpose | Input | Expected Output |
|----------|---------|-------|-----------------|
| `investment_thesis.md` | Generate buy/hold/sell-neutral thesis | `tier2_context.txt` | Structured thesis with bull/bear cases |
| `risk_opportunity_matrix.md` | Correlate Item 1A risks with Item 7 opportunities | `tier2_context.txt` | 2x2 matrix: severity vs. likelihood, with MD&A context |
| `management_tone.md` | Assess management confidence and hedging patterns | `tier2_context.txt` + selected Item 7 excerpts | Tone assessment: confident/cautious/defensive |
| `competitive_position.md` | Evaluate competitive moat from Item 1 + Item 1A | `tier2_context.txt` | Porter's Five Forces summary with filing evidence |
| `yoy_narrative.md` | Explain year-over-year changes in plain language | `tier2_context.txt` for 2+ years | Narrative summary of what changed and why it matters |
| `red_flags.md` | Identify accounting/governance red flags | `tier2_context.txt` with flags section | Prioritized red flag list with severity ratings |
| `peer_comparison.md` | Compare two companies' Tier 1 summaries | Two `tier2_context.txt` files | Side-by-side comparison with relative strengths |

### 5.3 Selective Text Retrieval for Tier 2

When the LLM needs specific raw text (not just the Tier 1 summary), it can request
targeted excerpts. A **retrieval helper script** provides:

```bash
# Retrieve top-5 most negative segments from Item 1A
python -m src.analysis.retrieve --ticker AAPL --section part1item1a \
    --sort-by negative_ratio --top 5

# Retrieve forward-looking statements from Item 7
python -m src.analysis.retrieve --ticker AAPL --section part2item7 \
    --filter forward_looking --top 10

# Retrieve segments matching a keyword
python -m src.analysis.retrieve --ticker AAPL --keyword "supply chain" --top 10
```

This allows targeted deep-dives without loading entire sections into the LLM context.

---

## 6. Architecture

### 6.1 System Diagram

```
EDGAR HTML (data/raw/*.html)
    │
    ▼
[Existing Pipeline: Parse → Extract → Clean → Segment]
    │                                        ▲
    │                      ┌─────────────────┘
    │                      │ Extends extraction to 7+ sections
    ▼                      │
data/processed/{run_dir}/
    ├── {stem}_part1item1_segmented.json
    ├── {stem}_part1item1a_segmented.json    ◄── existing
    ├── {stem}_part1item1b_segmented.json
    ├── {stem}_part1item1c_segmented.json
    ├── {stem}_part2item7_segmented.json
    ├── {stem}_part2item7a_segmented.json
    └── {stem}_part2item8_segmented.json
                │
                ▼
    ┌───────────────────────────────────┐
    │  Tier 1: Traditional NLP Engine   │
    │  (zero LLM tokens)               │
    │                                   │
    │  ┌─────────────┐ ┌────────────┐  │
    │  │ Sentiment    │ │ TF-IDF     │  │
    │  │ (L-M dict)   │ │ Keywords   │  │
    │  └──────────────┘ └────────────┘  │
    │  ┌─────────────┐ ┌────────────┐  │
    │  │ Readability  │ │ NER        │  │
    │  │ (F-K/FOG)    │ │ (spaCy)    │  │
    │  └──────────────┘ └────────────┘  │
    │  ┌─────────────┐ ┌────────────┐  │
    │  │ Topic Model  │ │ FLS/Hedge  │  │
    │  │ (LDA)        │ │ Detection  │  │
    │  └──────────────┘ └────────────┘  │
    │  ┌─────────────┐ ┌────────────┐  │
    │  │ Going Concrn │ │ Cross-Sect │  │
    │  │ + Auditor    │ │ Overlap    │  │
    │  └──────────────┘ └────────────┘  │
    └───────────────────────────────────┘
                │
                ▼
    data/reports/{run_dir}/
        ├── {ticker}_basic_report.json
        ├── {ticker}_basic_report.md
        ├── {ticker}_tier2_context.txt     ◄── compressed for LLM
        └── RUN_REPORT.md
                │
                ▼
    ┌───────────────────────────────────┐
    │  Tier 2: Claude Code CLI (human   │
    │  in the loop, token-efficient)    │
    │                                   │
    │  Operator pastes tier2_context    │
    │  + prompt template into Claude    │
    │  Code CLI. LLM reasons over      │
    │  structured data, not raw text.   │
    └───────────────────────────────────┘
                │
                ▼
    Saved by operator as final analysis
```

### 6.2 Integration with Existing Pipeline

| Concern | Approach |
|---------|----------|
| Multi-section extraction | Extend `SECSectionExtractor` to accept a list of section identifiers (currently hardcoded to `part1item1a`). Config-driven via `configs/config.yaml` `extraction.target_sections` list. |
| Output naming | One `*_segmented.json` per section per filing: `{stem}_{section_id}_segmented.json`. Existing `part1item1a` naming preserved for backward compatibility. |
| Parallel processing | Reuse `ParallelProcessor` (ADR-003). Sections within a filing processed sequentially (shared parse tree); filings processed in parallel across workers. |
| Checkpoint/resume | Existing `CheckpointManager` tracks per-filing completion. A filing is complete when all configured sections are extracted. |
| QA validation | Extend QA gates (ADR-019) to validate per-section extraction rates. New threshold: `min_sections_extracted_ratio >= 0.5` (at least half of configured sections found). |
| Stamped run dirs | Same pattern (ADR-007): `{YYYYMMDD_HHMMSS}_investment_{git_sha}/` |
| SQLite cache | Extend `FilingDatabase` (ADR-018) with per-section feature cache tables. |

### 6.3 Database Schema Design (v0.2 — Confirmed)

The existing `filings` + `classifications` + `risk_scores` tables remain unchanged. Three
new tables support Tier 1 feature caching and investment signal storage (ADR-021):

| Table | Purpose | Unique Key |
|-------|---------|------------|
| `section_features` | Per-section NLP feature cache (JSON column per feature type) | `(filing_id, section_id, feature_type, feature_version)` |
| `investment_flags` | Filing-level binary triage signals (9 BOOLEAN columns) | `(filing_id)` |
| `cross_section_overlap` | Jaccard similarity between TF-IDF keyword sets per section pair | `(filing_id, section_id_a, section_id_b)` |

**Design decision (ADR-021 §4):** `section_features` uses a single table with a
`feature_json` TEXT column storing serialized Pydantic output (vs. one table per feature
type). This avoids 12 separate CREATE TABLE migrations. SQLite `json_extract()` enables
queries like `WHERE json_extract(feature_json, '$.negative_ratio') > 0.1`. If batch
triage performance requires it, hot fields can be denormalized into indexed columns in a
future migration.

**Cache invalidation:** `feature_version` is a hash of the extractor configuration. When
configuration changes, a new version row is inserted. `has_section_feature()` checks cache
validity before recomputing.

**Migration:** Schema v2 → v3 (additive only, no ALTER TABLE on existing tables).
Implemented in `src/storage/database.py:_MIGRATIONS[3]`.

See `docs/architecture/data_dictionary.md` for full column definitions.

---

## 7. User Stories

| ID | Priority | As a... | I want to... | So that... |
|:---|:---------|:--------|:-------------|:-----------|
| US-042 | **P0** | Financial Analyst | Run the pipeline on a 10-K and get all 7 core sections extracted | I have complete filing coverage for investment analysis |
| US-043 | **P0** | Financial Analyst | Receive a Basic Investment Report with sentiment, readability, keywords, entities, and flags — with zero LLM tokens consumed | I can screen companies cheaply at scale |
| US-044 | **P0** | Financial Analyst | Get a compressed `tier2_context.txt` file per filing that fits in ~8K tokens | I can paste it into Claude Code CLI for deep analysis without token waste |
| US-045 | **P0** | Pipeline Operator | Run multi-section extraction with `--sections all` or `--sections part1item1,part2item7` | I can control which sections are extracted per run |
| US-046 | **P1** | Financial Analyst | See binary investment flags (going concern, material weakness, qualified audit, etc.) in the basic report | I can instantly spot red flags without reading the full filing |
| US-047 | **P1** | Financial Analyst | See cross-section keyword overlap scores | I can identify themes that management emphasizes across multiple sections |
| US-048 | **P1** | Risk Manager | Get year-over-year text deltas for all sections (not just Item 1A) | I can track how the full filing narrative evolves over time |
| US-049 | **P1** | Financial Analyst | Use prompt templates in `prompts/investment_analysis/` with Claude Code CLI | I get consistent, high-quality LLM analysis without crafting prompts from scratch |
| US-050 | **P1** | Financial Analyst | Retrieve specific segments by keyword or sentiment rank via CLI | I can pull targeted excerpts for LLM deep-dives without loading entire sections |
| US-051 | **P2** | Portfolio Manager | Run Tier 1 across 50+ companies and get a sortable dashboard of flags and scores | I can triage a watchlist using only traditional NLP features |

---

## 8. Phase-Gate Plan

### Phase 1 — Multi-Section Extraction (Foundation)

- Extend `SECSectionExtractor` to handle a configurable list of sections
- Update `run_preprocessing_pipeline.py` CLI with `--sections` flag
- One `*_segmented.json` output per section per filing
- Update QA gates for multi-section validation
- **Gate:** 7 core sections extracted from ≥ 90% of test corpus filings

### Phase 2 — Tier 1 Feature Engine

- New module: `src/features/investment/` containing (17 files implemented):
  - `schemas.py` — Pydantic v2 models (`BasicInvestmentReport`, `SectionAnalysis`, etc.)
  - `pipeline.py` — `InvestmentAnalysisPipeline` orchestrator
  - `section_analyzer.py` — per-section feature extraction coordinator
  - `keyword_extractor.py` — TF-IDF + KeyBERT extraction
  - `ner_extractor.py` — spaCy NER with domain rules
  - `forward_looking.py` — forward-looking statement detection
  - `going_concern.py` — going-concern flag + auditor opinion classification
  - `sentiment_ensemble.py` — LM dictionary + FinBERT ensemble
  - `topic_ensemble.py` — LDA + BERTopic ensemble
  - `cross_section_overlap.py` — Jaccard overlap on keyword sets
  - `yoy_delta.py` — year-over-year section comparison
  - `flag_computer.py` — investment signal threshold computation
  - `summarizer.py` — TextRank extractive summarization (sumy)
  - `report_builder.py` — assembles `BasicInvestmentReport`
  - `report_exporters.py` — Markdown, JSON, CSV export
  - `tier2_context.py` — Tier 2 context compression
  - `__init__.py` — public API exports
- Config: `configs/features/investment.yaml` + `src/config/features/investment.py`
- **Gate:** All feature extractors produce valid output on 10 test filings

### Phase 3 — Report Generation & Tier 2 Compression

- `src/features/investment/report_builder.py` — assembles `BasicInvestmentReport`
- `src/features/investment/tier2_context.py` — generates `tier2_context.txt` via `Tier2ContextGenerator`
- CLI: `scripts/feature_engineering/run_investment_analysis.py` (invoked via `analyze invest`)
- Multi-format export (MD, JSON, CSV) via `report_exporters.py`
- Prompt templates in `prompts/investment_analysis/` (not yet created)
- **Gate:** `tier2_context.txt` fits within 4K tokens (configurable via `tier2_max_tokens`) for 95% of filings

### Phase 4 — Selective Retrieval & Batch Mode

- `src/analysis/retrieve.py` — CLI for targeted segment retrieval
- Batch mode: `--batch` flag to process all filings in a run directory
- SQLite cache integration for Tier 1 features
- Sortable summary CSV across all filings (for watchlist triage)
- **Gate:** Batch of 50 filings produces complete Tier 1 reports with ≤ 5% failure rate

### Phase 5 (Stretch) — 10-Q Support & Dashboard

- Extend to 10-Q sections (9 sections per `SecSectionsConfig`)
- Streamlit dashboard for Tier 1 report visualization
- Historical trend charts (sentiment, readability, flags over time)

### Implementation Status (as of 2026-08-14)

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 — Multi-Section Extraction | Partial | `SECSectionExtractor` supports multi-section; `--sections` CLI flag not yet added to preprocessing pipeline. Default extracts all 10-K sections. |
| Phase 2 — Tier 1 Feature Engine | Complete | 17 files in `src/features/investment/`. Config in `configs/features/investment.yaml`. |
| Phase 3 — Report Generation | Complete | `report_builder.py`, `report_exporters.py`, `tier2_context.py` implemented. `prompts/investment_analysis/` directory not yet created. |
| Phase 4 — Retrieval & Batch | Not Started | `src/analysis/retrieve.py` not yet implemented. Batch mode via `scripts/feature_engineering/run_investment_analysis.py` exists but no sortable dashboard. |
| Phase 5 — 10-Q & Dashboard | Not Started | — |

**Known gaps:**
- `prompts/investment_analysis/` — 7 prompt templates not yet created (§5.2)
- `src/analysis/retrieve.py` — selective text retrieval CLI not yet implemented (§5.3)
- `--sections` flag — not exposed in `run_preprocessing_pipeline.py` (§6.2)
- `docs/architecture/data_dictionary.md` — v3 schema tables not yet documented

---

## 9. Technical Requirements

### 9.1 Dependencies

**Core (already in `pyproject.toml` base dependencies):**

| Package | Purpose | Version |
|---------|---------|---------|
| `scikit-learn` | TF-IDF vectorizer, cosine similarity | `>=1.3.0` |
| `spacy` | NER (en_core_web_sm model) | `>=3.7.0` |
| `gensim` | LDA topic modeling | `>=4.0.0` |
| `pydantic` | Report schema models | `>=2.12.4` |
| `sentence-transformers` | Semantic embeddings for KeyBERT/BERTopic backends | `>=2.2.2` |
| `transformers` | FinBERT sentiment model | `>=4.35.0` |

**New optional extras (`pip install -e ".[investment]"`):**

| Package | Purpose | Version |
|---------|---------|---------|
| `keybert` | Keyphrase extraction (ensemble with TF-IDF) | `>=0.8.0` |
| `bertopic` | Neural topic modeling (ensemble with LDA) | `>=0.16.0` |
| `sumy` | TextRank extractive summarization | `>=0.11.0` |

The `[investment]` extra is defined in `pyproject.toml` lines 127–132.

### 9.2 Performance Targets

| Metric | Target |
|--------|--------|
| Tier 1 processing time per filing (7 sections) | ≤ 30s on 8-core machine |
| `tier2_context.txt` size | ≤ 4,000 tokens by default (configurable via `tier2_max_tokens`) |
| Basic Investment Report JSON size | ≤ 500KB per filing |
| Memory per worker (Tier 1 features) | ≤ 2GB (spaCy + TF-IDF + LDA) |
| Batch throughput (Tier 1 only) | ≥ 100 filings/hour on 8-core |

### 9.3 Backward Compatibility

- Existing `part1item1a`-only pipeline runs are unaffected. Default `--sections` value
  remains `part1item1a` for backward compatibility.
- Existing agentic analysis (PRD-005) continues to work on `*_part1item1a_segmented.json`.
- No schema changes to existing `SegmentedRisks` model.

---

## 10. Open Questions

| ID | Question | Owner | Target |
|----|----------|-------|--------|
| OQ-B01 | Should `tier2_context.txt` include raw text excerpts (top-3 most negative segments) or only metrics? | Beth | Before Phase 3 |
| OQ-B02 | TF-IDF corpus scope: per-filing or across the full corpus for IDF weights? Per-filing is simpler but corpus-wide gives better discrimination. | Beth | Before Phase 2 |
| OQ-B03 | Should Tier 1 run automatically after preprocessing, or as a separate CLI command? | Beth | Before Phase 2 |
| OQ-B04 | Should prompt templates include few-shot examples from real filings? | Beth | Before Phase 3 |
| OQ-B05 | Going-concern detection: regex-only or also use the existing zero-shot classifier (`facebook/bart-large-mnli`)? Zero-shot is more robust but slower. | Beth | Before Phase 2 |
