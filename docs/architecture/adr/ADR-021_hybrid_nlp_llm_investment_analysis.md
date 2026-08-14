---
# ADR-021: Hybrid Traditional NLP + LLM Architecture for Investment Analysis

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-08-13 |
| **Author** | Beth |
| **Supersedes** | — |
| **References** | PRD-006, ADR-017, ADR-018 |

---

## Context

PRD-006 requires extracting all key 10-K sections (not just Item 1A) and producing
investment analysis reports. Two architectural approaches were considered:

**Option A — Full LLM Analysis (API-heavy):**
Send all extracted section text to the Claude API for every analysis. This is the approach
used by the existing agentic analysis layer (PRD-005/ADR-017). With 7 sections per filing
(~500–2,000 segments, ~150K–600K tokens), this becomes prohibitively expensive for
screening large numbers of companies. A single filing analysis costs ~$0.50–2.00 in API
tokens; a 50-company watchlist costs $25–100 per run.

**Option B — Full Traditional NLP (no LLM):**
Use only deterministic NLP techniques (sentiment dictionaries, TF-IDF, NER, topic
modeling). Zero token cost, fully reproducible, fast. But unable to perform complex
reasoning: cross-section synthesis, management tone assessment, qualitative investment
thesis generation. Outputs are feature vectors, not narratives.

**Option C — Hybrid Two-Tier (selected):**
Tier 1 uses traditional NLP to produce a structured Basic Investment Report (zero tokens).
Tier 2 feeds a compressed summary (~8K tokens) to Claude Code CLI for complex reasoning.
This achieves 95%+ token reduction vs. Option A while preserving LLM reasoning capability.

The second key decision is the LLM execution model: Claude API (programmatic, billed per
token) vs. Claude Code CLI (interactive, covered by Pro/Team subscription, no per-token
billing).

---

## Decision

### 1. Two-Tier Hybrid Architecture — Option C

All investment analysis follows a two-tier pipeline:

**Tier 1 — Traditional NLP (deterministic, zero token cost):**

| Technique | Implementation | Purpose |
|-----------|----------------|---------|
| Loughran-McDonald + FinBERT sentiment ensemble | `sentiment_ensemble.py` wrapping `src/features/sentiment.py` | Section-level sentiment scoring (LM dict + neural) |
| Readability (Flesch-Kincaid, FOG, SMOG) | Existing `src/features/readability/` | Text complexity assessment |
| LDA + BERTopic topic ensemble | `topic_ensemble.py` wrapping `src/features/topic_modeling/` | Thematic decomposition (classical + neural) |
| TF-IDF + KeyBERT keyword extraction | `keyword_extractor.py` | Section-discriminative terms and keyphrases |
| Named Entity Recognition | `ner_extractor.py` — `spacy` (en_core_web_sm) | Company, person, geography, money extraction |
| Forward-looking statement detection | `forward_looking.py` — regex + LM modal words | MD&A optimism/caution signals |
| Going-concern / auditor opinion | `going_concern.py` — regex patterns | Item 8 red flag detection |
| Cross-section overlap | `cross_section_overlap.py` — Jaccard on TF-IDF keyword sets | Theme correlation across sections |
| Extractive summarization | `summarizer.py` — TextRank via sumy | Key sentence extraction per section |
| Investment flag computation | `flag_computer.py` — threshold-based | 9 binary triage signals |

Governing rule: **No feature extractor in Tier 1 may call an LLM API.** Every technique
must be deterministic and reproducible given the same input text. This ensures Tier 1 can
run on 1,000+ filings at near-zero marginal cost.

**Tier 2 — LLM Deep Analysis (Claude Code CLI, token-efficient):**

The Tier 1 output is compressed into a structured text summary (`tier2_context.txt`,
≤4K tokens by default — `configs/features/investment.yaml: tier2_max_tokens: 4000`)
containing metrics, flags, and top keywords — not raw filing text. This summary is the
primary input to Claude Code CLI for complex reasoning tasks. Implemented by
`Tier2ContextGenerator` in `src/features/investment/tier2_context.py`.

Governing rule: **Tier 2 receives structured metrics, not raw text.** Raw text is
available on-demand via a retrieval helper (`src/analysis/retrieve.py`, not yet
implemented) but is never bulk-loaded into the LLM context.

### 2. LLM Execution Model — Claude Code CLI (Not API)

Tier 2 analysis runs through **Claude Code in VS Code terminal**, not through the
Anthropic API (`anthropic` Python SDK). Rationale:

| Criterion | Claude API (PRD-005) | Claude Code CLI (PRD-006) |
|-----------|---------------------|--------------------------|
| **Token cost** | Billed per token ($3–15/MTok) | Covered by Pro/Team subscription |
| **Automation** | Fully automated tool-use loop | Human-in-the-loop; operator reviews |
| **Batch scale** | Suitable for automated batch runs | Best for selective deep-dives |
| **Reproducibility** | Deterministic with seed parameter | Varies by session |
| **Integration** | `src/analysis/orchestrator.py` | Prompt templates + manual piping |

The existing PRD-005 agentic layer (Claude API) is **not replaced**. It remains available
for users who need fully automated analysis. PRD-006's Tier 2 is an alternative path
optimized for token efficiency when the operator can participate interactively.

**Planned implementation:** Prompt template files in `prompts/investment_analysis/` (not
yet created) and a retrieval CLI at `src/analysis/retrieve.py` (not yet implemented).
Currently, Tier 1 is invoked via `scripts/feature_engineering/run_investment_analysis.py`
or the `analyze invest` CLI command (`src/analysis/cli.py:141`).

### 3. Compression Target — 95%+ Token Reduction

The `tier2_context.txt` file must compress a full 10-K analysis (150K–600K raw tokens)
into ≤4K tokens (configurable via `tier2_max_tokens`). The compression strategy:

1. **Section-level aggregation:** Per-section metrics (sentiment scores, readability
   indices, keyword lists, entity lists) replace raw text. A 15,000-word MD&A section
   becomes ~200 tokens of structured metrics.
2. **Top-N filtering:** Only top-20 TF-IDF keywords and top-10 entities per section.
3. **Binary flags:** Going concern, material weakness, qualified audit, etc. are
   single-line boolean flags.
4. **Cross-section signals:** Jaccard overlap scores and shared keywords as structured
   lists, not prose.

### 4. Feature Module Location — `src/features/investment/`

New investment-specific features live in `src/features/investment/`, not in the existing
`src/features/` top-level modules. Rationale:

- Existing `src/features/sentiment.py`, `readability/`, `topic_modeling/` operate on
  individual segments. Investment features operate on **section-level** and
  **cross-section** aggregations.
- `src/features/investment/` imports and wraps the existing segment-level features,
  aggregating them to section level.
- Keeps the existing feature API surface unchanged (no breaking changes for PRD-003
  fine-tuning consumers).

### 5. Multi-Section Extraction — Config-Driven Section List

`SECSectionExtractor` is extended to accept a list of section identifiers from
`configs/config.yaml`:

```yaml
extraction:
  target_sections:
    - part1item1a  # default (backward compatible)
  # For investment analysis:
  # target_sections:
  #   - part1item1
  #   - part1item1a
  #   - part1item1b
  #   - part1item1c
  #   - part2item7
  #   - part2item7a
  #   - part2item8
```

CLI override: `--sections all` expands to all sections in `SecSectionsConfig.sections_10k`.

Governing rule: **One `*_segmented.json` file per section per filing.** The existing
single-section output format is preserved; multi-section extraction produces multiple
output files, not a merged file.

### 6. Feature Cache Storage — Single `section_features` Table with JSON Column

Tier 1 produces 12 feature types per section (sentiment, readability, keywords, entities,
FLS, hedging, going-concern, auditor opinion, topic distribution, section length,
cross-section overlap, YoY delta). Two storage approaches were evaluated:

**Option A — One table per feature type (12 tables):**
Each feature extractor gets its own table with typed columns matching the Pydantic model
fields. Enables SQL queries on individual fields without `json_extract()`. Requires 12
CREATE TABLE + migration statements, 12 CRUD method sets, and any schema change to a
Pydantic model requires an ALTER TABLE migration.

**Option B — Single `section_features` table with JSON column (selected):**
One table with columns `(filing_id, section_id, feature_type, feature_version,
feature_json)`. The `feature_json` column stores the full `.model_dump_json()` output.
SQLite `json_extract()` supports queries like
`WHERE json_extract(feature_json, '$.negative_ratio') > 0.1`.

**Why Option B:**
- **Migration simplicity:** 1 table vs. 12. Adding a new feature type requires no schema
  change — just insert with a new `feature_type` value.
- **Cache invalidation:** `feature_version` (a config hash) is part of the UNIQUE
  constraint. When extractor config changes, new rows are inserted without deleting old
  ones. `has_section_feature()` checks cache validity.
- **Performance trade-off:** `json_extract()` queries are slower than native columns for
  large-scale filtering. If batch triage (US-051, 50+ companies) becomes a bottleneck,
  hot fields (e.g., `negative_ratio REAL`) can be denormalized into indexed columns via a
  future migration. Start simple, optimize later.

Filing-level `investment_flags` are stored in a separate dedicated table with native
BOOLEAN columns (not in `section_features`) because they are the primary triage mechanism
for batch screening and need fast `WHERE` queries without `json_extract()`.

Implementation: `src/storage/database.py:_MIGRATIONS[3]`, schema version 3.

---

## Consequences

### Positive

- **95%+ token cost reduction** vs. sending raw text to the LLM. A 50-company watchlist
  screening via Tier 1 costs zero LLM tokens; Tier 2 deep-dives on selected companies
  cost ~8K tokens each (~$0.02–0.12 per company).
- **Minimal new dependencies.** Core Tier 1 techniques use libraries already in
  `pyproject.toml` (scikit-learn, spaCy, Gensim, Pydantic). Ensemble enhancements
  (KeyBERT, BERTopic, sumy) are isolated in the `[investment]` optional extra.
- **Backward compatible.** Default extraction remains Item 1A only. Existing agentic
  analysis (PRD-005) is unaffected.
- **Deterministic Tier 1.** Traditional NLP features are fully reproducible across runs
  (no LLM temperature variance). Suitable for longitudinal studies.
- **Scalable screening.** Tier 1 can process 100+ filings/hour on 8 cores. An entire
  sector (50–200 companies) can be screened in a single batch run.

### Negative / Trade-offs

- **Two execution models.** PRD-005 (API-automated) and PRD-006 (CLI-interactive) coexist.
  Operators must understand which to use when. Risk of confusion.
- **Tier 2 is not automated.** Unlike PRD-005's tool-use loop, Tier 2 requires human
  participation (copy-paste into Claude Code CLI). Not suitable for fully automated
  pipelines.
- **Compression is lossy.** The 95% token reduction means the LLM never sees raw filing
  text by default. Subtle language nuances (e.g., specific phrasing of a risk factor) may
  be lost. Mitigated by the retrieval helper for targeted deep-dives.
- **Regex-based detectors (going concern, auditor opinion, FLS) are brittle.** Novel
  phrasing may be missed. Mitigation: maintain pattern dictionaries and validate against
  ground truth periodically.
- **spaCy NER on financial text has known limitations.** `en_core_web_sm` is not trained
  on SEC filings. Entity recognition accuracy may be lower for financial-domain entities
  (e.g., ticker symbols, regulatory body abbreviations). Mitigation: domain-specific
  entity rules layered on top of spaCy output.

---

## Supersedes

Nothing. Coexists with ADR-017 (agentic analysis orchestration via Claude API).

## References

- `PRD-006_Full_10K_Investment_Analysis.md` (v0.3)
- `ADR-017_agentic_analysis_orchestration.md` — existing API-based analysis layer
- `ADR-018_sqlite_filing_database.md` — caching layer extended for Tier 1 features
- `src/features/investment/` — Tier 1 feature engine (17 modules)
- `src/features/investment/pipeline.py` — `InvestmentAnalysisPipeline` orchestrator
- `src/features/investment/schemas.py` — all Pydantic v2 output models
- `src/features/sentiment.py` — existing Loughran-McDonald sentiment (wrapped by `sentiment_ensemble.py`)
- `src/features/readability/` — existing readability metrics
- `src/features/topic_modeling/` — existing LDA topic modeling (wrapped by `topic_ensemble.py`)
- `src/config/sec_sections.py` — `SecSectionsConfig` section identifier configuration
- `src/config/features/investment.py` — `InvestmentConfig` settings
- `configs/features/investment.yaml` — Tier 1 configuration (thresholds, model names, etc.)
- `src/storage/database.py:159–211` — schema v3 migration (3 new tables)
- `scripts/feature_engineering/run_investment_analysis.py` — Tier 1 CLI entry point
