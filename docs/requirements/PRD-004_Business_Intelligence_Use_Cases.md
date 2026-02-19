---
id: PRD-004
title: SEC 10-K Business Intelligence — Multi-Stakeholder Analysis Use Cases
status: DRAFT
author: beth88.career@gmail.com
created: 2026-02-18
last_updated: 2026-02-18
version: 0.1.0
supersedes: null
depends_on: PRD-003
git_sha: d027985
---

# PRD-004: SEC 10-K Business Intelligence — Multi-Stakeholder Analysis Use Cases

## 1. Context & Problem Statement

PRD-001 through PRD-003 define the ML pipeline: ingest EDGAR HTML filings, extract Item 1A
risk factors, clean the corpus, and produce `SegmentedRisks` JSON ready for FinBERT
fine-tuning. The pipeline answers *how to build the model*.

**This PRD answers what the model is for.**

Five distinct business stakeholders — none of them ML engineers — derive concrete operational
value from automated 10-K risk factor analysis:

| Stakeholder | Core Question | Frequency |
|:------------|:-------------|:---------|
| Strategic Analyst | How do competitor risk profiles compare to ours? | Quarterly |
| Risk Manager | Is a supplier or partner financially stable? | Before contract |
| Corporate Development Analyst | What hidden liabilities does an M&A target carry? | Pre-LOI |
| IR Manager / Financial Analyst | How does our disclosed risk language benchmark against peers? | Pre-earnings |
| Account Executive | What challenges is a prospect's leadership team publicly worried about? | Pre-call |
| Domain Expert / SME | Are the zero-shot model's predicted categories correct for this segment? | During labeling sessions |

Today none of these users can query the corpus without writing code. The fine-tuned model
exists in a pipeline silo: no categorisation labels, no cross-company query interface,
no export format an analyst can open in Excel. The gap between *corpus exists* and
*analysts derive value* is entirely unaddressed.

---

## 2. Goals & Non-Goals

### 2.1 Goals

| ID | Priority | Since | Goal | Status | Stories |
|:---|:---------|:------|:-----|:-------|:--------|
| G-01 | P0 | PRD-004 | Risk segments carry category labels — every `RiskSegment` has a `risk_category` from the 8-class taxonomy (§3.2) and a `confidence` float ≥ 0.0; verified by classifying the 309-filing corpus and confirming 0 unlabelled segments | ❌ Zero-shot classifier exists (`src/analysis/inference.py`) but uses the PRD-002 13-class SASB taxonomy (`src/analysis/taxonomies/risk_taxonomy.yaml`); PRD-004 8-class taxonomy and fine-tuned model not started | US-021, US-022, US-023, US-024, US-025 |
| G-02 | P0 | PRD-004 | Cross-company CLI query interface — `python -m sec_intel query --ciks A,B --category cybersecurity` returns a ranked `RiskQueryResult` JSON in ≤ 5s on the 309-filing corpus | ❌ No query CLI exists | US-021, US-022, US-024, US-025 |
| G-03 | P0 | PRD-004 | Source citation on every segment — every returned segment has a `citation_url` pointing to the SEC EDGAR viewer for the source filing; ≥ 90% coverage at Phase 3 gate, 100% at v0.4.0 release | ❌ Not implemented; accession number not stored in current `SegmentedRisks` schema | US-021, US-022, US-023 |
| G-04 | P1 | PRD-004 | Analyst-ready CSV export — `--output csv` produces an Excel-openable file with columns: `company`, `cik`, `filing_date`, `category`, `confidence`, `text`, `citation_url`, sorted by `(cik ASC, confidence DESC)` | ❌ Not implemented | US-023, US-025 |
| G-05 | P1 | PRD-004 | Peer-group benchmarking with percentile ranking — `--peer-group SIC:6022` returns a cohort frequency table and percentile rank per category (e.g., "Company X cybersecurity: 90th percentile for SIC 6022") | ❌ Not implemented; `sic_code` and `sic_name` are already typed fields in `SegmentedRisks` (`src/preprocessing/models/segmentation.py:46`); Phase 4 work is wiring the existing field to the `--peer-group` CLI filter, not schema addition | US-022, US-024 |
| G-06 | P1 | PRD-004 | Risk Change Velocity score — `--compare-years` returns a cosine-similarity change score (0.0–1.0) per CIK pair; 1.0 = identical text, < 0.70 = material structural shift warranting review | ❌ Not implemented | US-026 |
| G-07 | P1 | PRD-004 | Emerging Risk Detection — `analytics.emerging_topics` lists topic labels present in year_N but absent from year_{N−1} (cosine distance > 0.30 from all prior-year topics for the same CIK) | ❌ Not implemented; requires topic model (Phase 5) | US-026 |
| G-08 | P1 | PRD-004 | Risk Prioritization Score — every filing result includes a composite `prioritization_score` (1–100) from severity weights × segment count × mean confidence; scores ≥ 70 flagged as `[ELEVATED]` in CLI text output | ❌ Not implemented; blocked on G-01 (labels and confidence required) | US-027 |
| G-09 | P0 | PRD-004 | Human-in-the-loop annotation labeler — domain experts review zero-shot predictions one segment at a time via a stateless Streamlit UI and append corrected labels to `data/processed/synthesized_risk_categories.jsonl`; output must contain ≥ 500 human-reviewed segments per non-`other` category with 0 null `corrected_category` fields before Phase 2 begins | ❌ Neither `llm_finetuning/synthesize_dataset.py` nor `llm_finetuning/train.py` exist; the `llm_finetuning/` directory has not been created; `src/visualization/labeler_app.py` is unbuilt | US-028 |

### 2.2 Non-Goals

- Training the fine-tuned model itself — this PRD defines its *output contract*, not its training procedure
- Building a production-deployed or externally-accessible web application — the query interface is a CLI; the annotation labeler (to be built at `src/visualization/labeler_app.py`, distinct from the existing `src/visualization/app.py`) is an internal local tool run via `streamlit run`, not a hosted service
- Real-time or streaming 10-K processing — batch ingestion (PRD-002) is the only ingest path
- Handling 8-K, DEF 14A, or other SEC filing types — Item 1A of 10-K only
- Private company analysis — EDGAR public filings only
- Financial modelling features (DCF, comparables, equity research) — risk text extraction only
- Natural language search — keyword and category-filter queries only in v0.4.0

> **Design constraint:** The risk classifier runs offline over the pre-processed corpus. It is not a real-time inference API. The CLI is the only supported query interface in v0.4.0; a REST API or web UI are explicitly out of scope.

---

## 3. Dataset Definition

### 3.1 Input Corpus (inherited from PRD-003)

This PRD consumes the clean corpus produced by PRD-003 v0.3.0. No new ingestion pipeline
is defined here.

| Attribute | Value |
|:----------|:------|
| Filing type | SEC 10-K annual reports |
| Section | Item 1A — Risk Factors |
| Corpus size at launch | 309 filings (887 target post-expansion) |
| Input format | `SegmentedRisks` JSON (one file per filing) |
| Source field | `segments[].text` — cleaned prose only |

### 3.2 Feature Schema — Risk Category Taxonomy

The fine-tuned model must classify each segment into **exactly one** primary category:

| Category ID | Label | Description |
|:------------|:------|:------------|
| `cybersecurity` | Cybersecurity & Data Privacy | Breach, ransomware, data loss, privacy regulation |
| `regulatory` | Regulatory & Legal | Pending legislation, litigation, sanctions, IP disputes |
| `financial` | Financial & Liquidity | Credit risk, covenant breach, capital markets access |
| `supply_chain` | Supply Chain & Operations | Vendor dependency, logistics, manufacturing disruption |
| `market` | Market & Competition | Pricing pressure, market share, new entrants |
| `esg` | Environmental & ESG | Climate, sustainability mandates, reputational exposure |
| `macro` | Macroeconomic | Interest rates, inflation, FX, geopolitical risk |
| `other` | Other / Uncategorised | Catch-all for low-confidence or novel risk types |

Multi-label classification is out of scope for v0.4.0. A segment receives its
highest-confidence category.

### 3.3 Query Output Schema

> **Schema note:** `segment_index` is the integer `RiskSegment.index` from the current schema
> (`src/preprocessing/models/segmentation.py:18`). A formatted `segment_id` string
> (`"seg_NNNN"`) does not exist in v0.3.0; the CLI must derive it from `index` at query time.
> `filing_date` is not a top-level `SegmentedRisks` field in v0.3.0; it must be added
> (see §4.1 new fields).

```json
{
  "query": {
    "ciks": ["0000320193"],
    "category": "cybersecurity",
    "peer_group": null,
    "as_of_date": "2026-02-18"
  },
  "results": [
    {
      "cik": "0000320193",
      "company_name": "APPLE INC",
      "filing_date": "2021-10-29",
      "risk_segments": [
        {
          "segment_index": 14,
          "text": "We are subject to complex and evolving U.S. and foreign laws...",
          "risk_category": "cybersecurity",
          "confidence": 0.94,
          "citation_url": "https://www.sec.gov/Archives/edgar/data/320193/..."
        }
      ],
      "analytics": {
        "prioritization_score": 72,
        "change_velocity": 0.38,
        "emerging_topics": ["AI regulation", "Taiwan supply chain"],
        "peer_percentiles": {
          "cybersecurity": 90,
          "regulatory": 55
        }
      }
    }
  ],
  "metadata": {
    "total_segments_returned": 3,
    "corpus_size": 309,
    "pipeline_version": "0.4.0",
    "model_version": "finbert-sec-risk-v1"
  }
}
```

---

## 4. Engineering & MLOps

### 4.1 Pipeline Version

This PRD targets pipeline version `0.4.0`. New fields:
- `SegmentedRisks.segments[].risk_category` (str)
- `SegmentedRisks.segments[].confidence` (float)
- `SegmentedRisks.segments[].citation_url` (str | null)
- `SegmentedRisks.filing_date` (str, ISO 8601) — not present in v0.3.0; required by G-04 CSV export and §3.3 query output
- `SegmentedRisks.metadata.model_version` (str)

> **Note:** `sic_code` and `sic_name` already exist as typed fields in `SegmentedRisks`
> (`src/preprocessing/models/segmentation.py:46`). No schema addition is needed for Phase 4.

All new fields are additive. Existing v0.3.0 files remain valid but will lack labels.

### 4.2 New Components

| Component | Location | Status | Purpose |
|:----------|:---------|:-------|:--------|
| Zero-shot seed classifier | `src/analysis/inference.py` | **Exists** | `RiskClassifier` using 13-class SASB taxonomy; provides seed predictions for Phase 1 annotation only; replaced by the fine-tuned classifier in Phase 2 |
| Fine-tuned risk classifier | `src/inference/classifier.py` | New (Phase 2) | Wrap fine-tuned FinBERT on 8-class PRD-004 taxonomy; return `risk_category` + `confidence` per segment |
| Citation builder | `src/inference/citation.py` | New (Phase 3) | Construct EDGAR viewer URL from CIK + accession number |
| Query CLI | `src/cli/query.py` | New (Phase 3) | `sec_intel query` entrypoint |
| CSV exporter | `src/cli/export.py` | New (Phase 3) | Convert `RiskQueryResult` to CSV |
| Year-over-year comparator | `src/inference/comparator.py` | New (Phase 5) | Compute cosine similarity between two filing-year segment embeddings |
| Topic modeler integration | `src/inference/topic_model.py` | New wrapper (Phase 5) | Thin adapter over existing `src/features/topic_modeling/TopicModelingAnalyzer` (LDA, already implemented); wires per-filing topic labels + C_v coherence into the query result |
| Prioritization scorer | `src/inference/scorer.py` | New (Phase 6) | Compute composite 1–100 risk prioritization score from severity, frequency, confidence |
| Annotation labeler UI | `src/visualization/labeler_app.py` | New (Phase 1) | Stateless Streamlit HITL app; distinct from existing `src/visualization/app.py`; fetches one filing live via `edgar_client.py`, runs full pipeline (Acquisition → Preprocessing → Zero-Shot Analysis) in memory, displays each segment with its predicted category, allows correction via dropdown, appends human-reviewed records to `data/processed/synthesized_risk_categories.jsonl` |

### 4.3 Model KPIs

#### Risk Classifier

| Metric | Minimum Acceptable | Target |
|:-------|:-------------------|:-------|
| Macro F1 (7 labelled categories) | 0.72 | ≥ 0.80 |
| Per-category Precision (all 7 categories) | ≥ 0.70 | ≥ 0.80 |
| Per-category Recall (all 7 categories) | ≥ 0.65 | ≥ 0.75 |
| Inference time per segment (CPU) | ≤ 1,000ms | ≤ 500ms |
| Inference time per segment (GPU) | — | ≤ 100ms |
| Coverage (`other` rate) | ≤ 30% of corpus | ≤ 15% |

> **Note:** Precision answers "are the model's positive predictions correct?" (low false-positive rate).
> Recall answers "does the model find all instances of that risk type?" (low false-negative rate).
> Macro F1 is their harmonic mean and is the primary pass/fail gate for Phase 2.

#### Year-over-Year Comparator

| Metric | Minimum Acceptable | Target |
|:-------|:-------------------|:-------|
| Cosine similarity computation time per filing pair (CPU) | ≤ 5s | ≤ 2s |
| Change velocity < 0.70 correctly identifies known high-change filings (spot-check) | 4 / 5 cases | 5 / 5 cases |

#### Topic Modeler

| Metric | Minimum Acceptable | Target |
|:-------|:-------------------|:-------|
| Topic Coherence C_v score | ≥ 0.45 | ≥ 0.55 |
| Topics per filing (median) | ≥ 3 | 5–10 |

> **Note:** C_v coherence measures whether the words in a machine-generated topic co-occur meaningfully in
> a reference corpus. A topic like `{breach, data, privacy, network}` scores high; `{risk, and, loss, market}` scores low.

### 4.4 Backward Compatibility

- `SegmentedRisks` schema is additive only (new fields; no removals)
- v0.3.0 JSON files can be re-processed through the classifier without re-running the full pipeline
- `StateManager` manifest extended with `model_version` key (additive)

### 4.5 Verification Commands

```bash
# Full test suite
python -m pytest tests/ -x -q

# Fine-tuned classifier smoke test (Phase 2+; src/inference/classifier.py)
python -c "
from src.inference.classifier import RiskClassifier
clf = RiskClassifier()
result = clf.classify_segment('We are exposed to significant cybersecurity threats...')
assert result['label'] == 'cybersecurity', f'Got {result[\"label\"]}'
assert result['score'] >= 0.70, f'Got {result[\"score\"]}'
print(f'OK: {result[\"label\"]} ({result[\"score\"]:.2f})')
"

# Zero-shot seed classifier smoke test (Phase 1; src/analysis/inference.py)
python -c "
from src.analysis.inference import RiskClassifier
clf = RiskClassifier()
result = clf.classify_segment('We are exposed to significant cybersecurity threats...')
assert result['label'] != 'Error'
print(f'Zero-shot OK: {result[\"label\"]} ({result[\"score\"]:.2f})')
"

# Query CLI integration test
python -m sec_intel query \
  --ciks 0000320193 \
  --category cybersecurity \
  --run-dir data/processed/<run_dir> \
  --output json

# CSV export
python -m sec_intel query \
  --ciks 0000320193,0001652044 \
  --run-dir data/processed/<run_dir> \
  --output csv > /tmp/risk_export.csv
```

---

## 5. Phase-Gate Plan

### Phase 1 — Risk Category Taxonomy, Bootstrap Labelling & HITL Annotation UI
**Scope:** Define taxonomy (§3.2); keyword-bootstrap the existing 309-filing corpus for seed
labels; build the Streamlit HITL labeler for domain-expert correction; produce a
`synthesized_risk_categories.jsonl` file that unblocks Phase 2 fine-tuning.

| Step | File | Change |
|:-----|:-----|:-------|
| 1.1 | `configs/risk_taxonomy.yaml` (new) | YAML definition of 8 categories with keywords, descriptions, and `severity_weight` placeholders |
| 1.2 | `scripts/annotation/label_segments.py` (new) | Keyword-bootstrap labeller to generate seed predictions over the existing 309-filing corpus |
| 1.3 | `src/preprocessing/pipeline.py` | Add `risk_category: null` placeholder to output schema |
| 1.4 | `src/visualization/labeler_app.py` (new) | Stateless Streamlit HITL labeler — CIK input → live `edgar_client.py` fetch → full pipeline in memory → segment display with zero-shot prediction → dropdown correction → "Next" / "Save" buttons → append to `data/processed/synthesized_risk_categories.jsonl` |

**Annotation output schema** (`synthesized_risk_categories.jsonl`, one JSON object per line):
```json
{
  "cik": "0001318605",
  "company_name": "TESLA INC",
  "filing_date": "2023-10-23",
  "segment_index": 14,
  "text": "Supply chain disruptions could adversely affect our operations...",
  "zero_shot_prediction": "supply_chain",
  "zero_shot_confidence": 0.78,
  "corrected_category": "supply_chain",
  "label_source": "human_accepted",
  "labeled_at": "2026-02-18T14:30:00Z"
}
```
`label_source` is `"human_accepted"` when `corrected_category == zero_shot_prediction`,
`"human_corrected"` otherwise.

**Gate:** ≥ 500 human-reviewed segments per non-`other` category in `synthesized_risk_categories.jsonl`; 0 null `corrected_category` fields; Data Dictionary updated with annotation schema; `llm_finetuning/train.py` is unblocked.

### Phase 2 — Fine-Tuned Classifier
**Scope:** Fine-tune FinBERT on labelled corpus; evaluate against held-out test set.

| Step | File | Change |
|:-----|:-----|:-------|
| 2.1 | `src/inference/classifier.py` (new) | FinBERT classifier wrapper |
| 2.2 | `scripts/training/finetune.py` (new) | Training script with HuggingFace Trainer |
| 2.3 | `src/preprocessing/pipeline.py` | Wire classifier into pipeline post-segmentation |

**Gate:** Macro F1 ≥ 0.72 on test split; `other` rate ≤ 30%.

### Phase 3 — Query CLI & Citation Builder
**Scope:** `sec_intel query` CLI; citation URL construction; JSON output.

| Step | File | Change |
|:-----|:-----|:-------|
| 3.1 | `src/inference/citation.py` (new) | Build EDGAR viewer URL from CIK + accession |
| 3.2 | `src/cli/query.py` (new) | `sec_intel query` entrypoint |
| 3.3 | `src/cli/export.py` (new) | CSV serialiser for `RiskQueryResult` |

**Gate:** G-01 through G-04 acceptance criteria pass; US-021 and US-023 scenarios green.

### Phase 4 — Peer-Group Benchmarking
**Scope:** SIC-code cohort filtering; category-frequency ranking; percentile output.

| Step | File | Change |
|:-----|:-----|:-------|
| 4.1 | `src/cli/query.py` | `--peer-group SIC:<code>` filter |
| 4.2 | `src/cli/query.py` | Cohort frequency table + per-category percentile rank in output |
| 4.3 | `src/cli/query.py` | Wire `SegmentedRisks.sic_code` (already a typed field at `segmentation.py:46`) to the `--peer-group SIC:<code>` filter; no schema change required |

**Gate:** G-05 acceptance criterion passes; US-022 and US-024 scenarios green.

### Phase 5 — Year-over-Year Change Detection & Emerging Topics
**Scope:** Cosine-similarity change velocity; topic modeling; emerging topic detection.

| Step | File | Change |
|:-----|:-----|:-------|
| 5.1 | `src/inference/comparator.py` (new) | TF-IDF or sentence-embedding cosine similarity between consecutive filing years for same CIK |
| 5.2 | `src/inference/topic_model.py` (new adapter) | Thin wrapper over existing `src/features/topic_modeling/TopicModelingAnalyzer` (LDA already implemented); exposes per-filing topic labels + C_v coherence in `RiskQueryResult` format |
| 5.3 | `src/cli/query.py` | `--compare-years` flag; populate `analytics.change_velocity` and `analytics.emerging_topics` |

**Gate:** C_v coherence ≥ 0.45; change velocity < 0.70 correctly flags known high-change filings in spot-check; US-026 scenarios green; G-06 and G-07 acceptance criteria pass.

### Phase 6 — Risk Prioritization Score
**Scope:** Composite 1–100 score per filing; severity weights configurable via YAML.

| Step | File | Change |
|:-----|:-----|:-------|
| 6.1 | `configs/risk_taxonomy.yaml` | Add `severity_weight` per category (e.g., `cybersecurity: 1.4`, `macro: 0.8`) |
| 6.2 | `src/inference/scorer.py` (new) | Compute `prioritization_score` from severity weights × segment count × mean confidence |
| 6.3 | `src/cli/query.py` | Populate `analytics.prioritization_score`; flag ≥ 70 in CLI output |
| 6.4 | `docs/architecture/data_dictionary.md` | Document score formula and weight table |

**Gate:** G-08 acceptance criterion passes; US-027 scenarios green; score formula in data dictionary.

---

## 6. User Stories

> Acceptance criteria (Gherkin Given/When/Then) are in individual story files linked below.

| ID | Priority | As a… | I want to… | So that… | Detail |
|:---|:---------|:------|:-----------|:---------|:-------|
| US-021 | **P0** | Strategic Analyst | Compare competitor risk profiles by category in a single query | I can benchmark our disclosed risk posture against peers without reading 300-page filings | [→](stories/US-021_competitive_benchmarking.md) |
| US-022 | **P1** | Risk Manager | Query a supplier's or partner's 10-K for financial and operational risk signals | I can update our vendor risk register with audited, structured data before contract renewal | [→](stories/US-022_supplier_risk_screening.md) |
| US-023 | **P0** | Corporate Development Analyst | Get a side-by-side risk category comparison of acquisition targets | I can identify material liabilities and risk concentrations before issuing a letter of intent | [→](stories/US-023_ma_due_diligence.md) |
| US-024 | **P1** | IR Manager | Benchmark our risk disclosure language against a peer-group cohort by SIC code | I can anticipate analyst questions about risk concentration before earnings calls | [→](stories/US-024_ir_peer_benchmarking.md) |
| US-025 | **P1** | Account Executive | Extract the top stated challenges from a prospect's most recent 10-K | I can tailor my sales pitch directly to the leadership team's publicly disclosed pain points | [→](stories/US-025_sales_prospect_intelligence.md) |
| US-026 | **P1** | Risk Manager | See a change velocity score comparing a company's current and prior-year risk language | I can instantly flag filings where the risk profile changed materially and prioritise deep review | [→](stories/US-026_risk_change_velocity.md) |
| US-027 | **P1** | Portfolio Manager | Get a composite risk prioritization score (1–100) for every company in my watchlist | I can triage 50 companies in minutes rather than manually reading each filing | [→](stories/US-027_risk_prioritization_score.md) |
| US-028 | **P0** | Domain Expert / SME | Review zero-shot risk predictions one segment at a time and save corrected labels to a local JSONL file | `llm_finetuning/train.py` has a high-quality human-validated dataset to train on | [→](stories/US-028_annotation_labeler_ui.md) |

---

## 7. Architecture

### Current State (v0.3.0)
```
HTML (EDGAR)
  → Pipeline (PRD-003)
  → SegmentedRisks JSON (clean prose, no labels)
  → [Dead end — no query interface]
```

### Target State (v0.4.0)
```
SegmentedRisks JSON (v0.3.0 output)
  → RiskClassifier (fine-tuned FinBERT)
      → risk_category + confidence per segment  [Phase 2]
  → CitationBuilder
      → citation_url per segment (EDGAR viewer) [Phase 3]
  → TopicModeler (BERTopic/LDA)
      → topic labels + C_v coherence per filing [Phase 5]
  → YoYComparator
      → change_velocity score per CIK pair      [Phase 5]
  → PrioritizationScorer
      → composite 1–100 score per filing        [Phase 6]
  → Labelled corpus index (JSON files on disk, keyed by CIK)
      ↓
  sec_intel query CLI
      → Filter by CIK / category / SIC peer-group / --compare-years
      → Output: RiskQueryResult JSON or CSV
      → analytics block: prioritization_score, change_velocity,
                         emerging_topics, peer_percentiles
      → Consumer: Strategic Analyst, Risk Manager, M&A, IR, Portfolio Manager, BD
```

No database is required in v0.4.0. The corpus fits in memory for a 887-filing index
(~50 MB of labelled JSON). A persistent index (SQLite or DuckDB) is an open question (Q-01).

---

## 8. Data & Metrics

### 8.1 Business Metrics (What Analysts Care About)

These are the practical outcomes that prove the system is useful to non-ML stakeholders.

| Business Metric | Definition | Baseline | Target (v0.4.0) |
|:----------------|:-----------|:---------|:----------------|
| **Risk Change Velocity** | `1 − cosine_similarity(year_N, year_{N−1})` of Item 1A text; 0 = identical, 1 = completely different | Not measured | Score produced for all multi-year CIKs; < 0.70 correctly flags known high-change filings (5/5 spot-check) |
| **Emerging Risk Detection Rate** | Count of new topic labels in year_N absent from year_{N−1} (cosine distance > 0.30 from all prior topics) | 0 | ≥ 1 topic detected per year-over-year pair where change_velocity > 0.30 |
| **Risk Prioritization Score** | Composite 1–100 derived from severity weights × segment count × mean confidence | Not produced | Score ≥ 70 correctly identifies known high-risk filings in held-out test set |
| **Peer Risk Comparison Index** | Percentile rank within SIC cohort per risk category | Not produced | Percentile rank present in all cohort query results; direction matches human expert ranking on 10-filing spot-check |
| **Analyst Efficiency Gain** | Qualitative benchmark: time to triage one filing | ~2 hours (manual read) | ≤ 15 minutes using CLI query + CSV export |

### 8.2 Technical ML Metrics (What Data Scientists Measure)

These prove the underlying model is performing correctly before it reaches analysts.

| Technical Metric | Definition | Minimum Acceptable | Target |
|:-----------------|:-----------|:-------------------|:-------|
| **Macro F1** | Harmonic mean of per-category Precision and Recall, averaged across all 7 labelled categories | 0.72 | ≥ 0.80 |
| **Per-category Precision** | Of all segments labelled `cybersecurity` (for example), what % are actually cybersecurity? | ≥ 0.70 | ≥ 0.80 |
| **Per-category Recall** | Of all true cybersecurity segments, what % does the model find? | ≥ 0.65 | ≥ 0.75 |
| **`other` rate** | Fraction of corpus segments assigned the catch-all `other` category | ≤ 30% | ≤ 15% |
| **Cosine / Jaccard similarity** | Pairwise text similarity score (0–1) powering change velocity | Computation ≤ 5s per pair | ≤ 2s per pair |
| **Topic Coherence C_v** | Co-occurrence-based coherence score for topic model topics | ≥ 0.45 | ≥ 0.55 |
| **Query latency** | Wall-clock time for `sec_intel query` on 309-filing corpus | ≤ 10s | ≤ 5s |
| **Citation URL coverage** | Fraction of returned segments with a non-null `citation_url` | 90% | 100% |

---

## 9. Technical Requirements

| ID | Requirement | Priority |
|:---|:------------|:---------|
| TR-01 | `risk_category` and `confidence` fields additive in `SegmentedRisks.segments[]` | Must |
| TR-02 | Classifier loads from a path in `configs/pipeline.yaml`; no hardcoded model path | Must |
| TR-03 | `citation_url` constructed from CIK + accession number in filing metadata | Must |
| TR-04 | `sec_intel query` CLI accepts `--ciks`, `--category`, `--peer-group`, `--output`, `--run-dir` | Must |
| TR-05 | CSV export produces columns: `company`, `cik`, `filing_date`, `category`, `confidence`, `text`, `citation_url` | Must |
| TR-06 | Macro F1 ≥ 0.72 before Phase 3 (CLI) begins; ≥ 0.80 before v0.4.0 release | Must |
| TR-07 | Classifier inference does not require GPU at query time (CPU inference ≤ 1,000ms/seg) | Must |
| TR-08 | `pipeline_version: "0.4.0"` and `model_version` in all labelled output metadata | Must |
| TR-09 | Re-classifying a v0.3.0 corpus does not require re-parsing HTML | Should |
| TR-10 | `--peer-group SIC:<code>` filters by SIC code present in filing metadata | Should |
| TR-11 | Year-over-year cosine similarity computed using TF-IDF or sentence embeddings on concatenated segment text; pairwise for same CIK across consecutive filing years | Should |
| TR-12 | Topic model (BERTopic or LDA) reports per-filing topic labels with C_v coherence ≥ 0.45; model is refit when corpus grows by > 100 filings | Should |
| TR-13 | `prioritization_score` formula documented in `docs/architecture/data_dictionary.md`; severity weights configurable in `configs/risk_taxonomy.yaml`, not hardcoded | Should |
| TR-14 | Classifier evaluation report includes per-category Precision and Recall (not only Macro F1); written to `reports/classifier_eval.json` after each training run | Must |

---

## 10. Open Questions

| # | Question | Owner | Decision Needed By |
|:--|:---------|:------|:-------------------|
| Q-01 | Should the labelled corpus index be flat JSON files or a SQLite/DuckDB table? JSON is simpler; DuckDB enables SQL queries and faster cross-company aggregation on 887+ filings. | beth | Phase 3 design |
| Q-02 | Citation URL format: EDGAR full-text search viewer vs. direct filing HTML URL? The viewer is stable but slow to load; the direct HTML URL requires knowing the exact file name in the accession archive. | beth | Phase 3 implementation |
| Q-03 | Should multi-label classification (a segment can be both `regulatory` and `financial`) be in scope for v0.4.0, or deferred to v0.5.0? Multi-label requires a different loss function and annotation scheme. | beth | Phase 1 taxonomy design |
| Q-04 | What is the minimum labelled set size per category for acceptable F1? 500 examples is the assumed floor; empirical validation needed after Phase 1 annotation. | beth | Phase 2 start |
| Q-05 | Should US-018 (source traceability) be merged into the citation builder work (Phase 3), or remain a separate story in EP-5? The implementation overlaps significantly. | beth | Phase 3 planning |
| Q-06 | Topic modeling algorithm: LDA (interpretable, no extra dependencies) vs. BERTopic (higher C_v coherence, requires `sentence-transformers` ~400 MB)? LDA is the default for Phase 5; BERTopic if C_v < 0.45 after tuning. | beth | Phase 5 design |
| Q-07 | Prioritization score weights: what should the severity multipliers be per category? An equal-weight starting point (all 1.0) is reasonable; calibrate against known high-risk filings in the test set before v0.4.0 release. | beth | Phase 6 design |
