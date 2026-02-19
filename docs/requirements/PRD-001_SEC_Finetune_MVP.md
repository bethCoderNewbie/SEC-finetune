---
id: PRD-001
title: SEC 10-K Risk Factor Analyzer — MVP
status: APPROVED
author: beth88.career@gmail.com
created: 2025-11-17
last_updated: 2026-02-18
version: 0.1.0
---

# PRD-001: SEC 10-K Risk Factor Analyzer — MVP

## 1. Context & Problem Statement

- **What:** An end-to-end NLP pipeline that ingests SEC 10-K/10-Q HTML filings from EDGAR, extracts Item 1A (Risk Factors), segments the text into discrete risk statements, classifies each into a standard taxonomy, and generates quantitative NLP features for downstream modeling.
- **Why:** SEC risk disclosures are dense, legally verbose, and unstructured. No open dataset provides granular, section-specific risk text suitable for fine-tuning financial LLMs. Analysts must manually read hundreds of pages to compare risk exposure across companies.
- **Success looks like:** A reproducible batch pipeline that produces labeled JSONL output compatible with HuggingFace `datasets`, enabling fine-tuning of a specialized financial risk classifier.

---

## 2. Goals & Non-Goals

### Goals (Must Have)

- [x] Parse ≥95% of HTML 10-K/10-Q filings from EDGAR without crashing
- [x] Extract Item 1A (Risk Factors) with < 5% text loss vs. the raw filing
- [x] Segment risk text into atomic, individually classifiable statements
- [x] Classify each segment via zero-shot or fine-tuned model at confidence ≥ 0.7
- [x] Output JSONL compatible with HuggingFace `datasets`
- [x] Pipeline must be resumable — crashed runs continue from checkpoint
- [ ] Batch CLI: process 10,000 filings in < 2 hours on a 32-core node
- [ ] Parsing success rate KPI surfaced in run summary

### Non-Goals (Out of Scope for MVP)

- [ ] Real-time streaming ingestion (batch only)
- [ ] User-facing dashboard or UI beyond Streamlit prototype
- [ ] Database storage (PostgreSQL/MongoDB — deferred to PRD-003)
- [ ] Public REST API (deferred)
- [ ] Comparative or trend analysis across companies/years (deferred)
- [ ] Non-SEC financial documents (10-Ks and 10-Qs only)
- [ ] Sentiment analysis as a classification signal (moved to PRD-002)

---

## 3. User Stories (Functional Requirements)

> Acceptance criteria (Gherkin Given/When/Then) are in individual story files linked below.

| ID | Priority | As a… | I want to… | So that… | Detail |
|:---|:---------|:------|:-----------|:---------|:-------|
| US-001 | **P0** | Data Scientist | Run the full pipeline on a directory of HTML filings and receive JSONL output | I get a HuggingFace-compatible training dataset without format conversion | [→](stories/US-001_batch_pipeline_execution.md) |
| US-002 | **P0** | ML Engineer | Resume a crashed pipeline run | I don't lose hours of compute from a transient failure | [→](stories/US-002_pipeline_resume.md) |
| US-003 | **P0** | ML Engineer | Route malformed filings to a Dead Letter Queue | Pipeline does not halt on bad input | [→](stories/US-003_dead_letter_queue.md) |
| US-004 | **P0** | Data Scientist | Filter filings by ticker or SIC code **at the CLI before processing** | I can build a sector-specific training set without wasting compute on irrelevant filings | [→](stories/US-004_sector_filtering.md) |
| US-005 | **P1** | Data Scientist | Inspect which filings failed and why | I can improve the parser/extractor logic iteratively | [→](stories/US-005_failure_inspection.md) |
| US-006 | **P1** | Financial Analyst | View extracted risk segments in a Streamlit UI | I can validate extraction quality without writing code | [→](stories/US-006_streamlit_ui.md) |
| US-007 | **P1** | ML Engineer | Configure all pipeline settings via YAML + env vars | I can deploy to different environments without code changes | [→](stories/US-007_yaml_config.md) |
| US-008 | **P0** | Data Scientist | Get sentiment, readability, and topic features **inline in the primary JSONL record** | I can load one file and train immediately without complex joins | [→](stories/US-008_nlp_features.md) |

---

## 4. Technical Requirements (Non-Functional)

| Category | Requirement |
|----------|-------------|
| **Scalability** | Process 10,000 filings in < 2 hours on a 32-core node (batch CLI — deferred) |
| **Reliability** | Pipeline must not crash on malformed HTML; route failures to DLQ |
| **Resumability** | Checkpoint state after each filing; `ResumeFilter` skips already-processed files |
| **Reproducibility** | `sec-parser==0.54.0` pinned; `RANDOM_SEED=42`; Python ≥ 3.10 enforced |
| **Security** | No secrets in plaintext; all credentials via `.env` (never committed) |
| **Config** | All settings in `configs/config.yaml` + env vars; Pydantic V2 validation enforced |
| **Memory** | Memory-aware worker pool; default 8GB min, 16GB recommended |
| **Testability** | ≥186 unit tests; all Pydantic models and utilities covered |

### Runtime Dependencies

```toml
sec-parser==0.54.0          # PINNED — semantic filing parser
sec-downloader>=0.10.0
transformers>=4.35.0
torch>=2.0.0
spacy>=3.7.0                # + en_core_web_sm download required
gensim>=4.0.0
pydantic>=2.12.4            # V2 enforced
pydantic-settings>=2.0.0
pandas>=2.0.0
streamlit>=1.28.0
```

---

## 5. Data & Metrics

### Input

- Source: EDGAR HTML filings (10-K and 10-Q)
- Location: `data/raw/`
- Format: HTML (UTF-8, fallback latin-1)

### Output Schema (v2.0)

```json
{
  "version": "2.0",
  "filing_name": "AAPL_10K.html",
  "sic_code": "3571",
  "sic_name": "ELECTRONIC COMPUTERS",
  "cik": "0000320193",
  "ticker": "AAPL",
  "company_name": "APPLE INC",
  "form_type": "10-K",
  "section_title": "Item 1A. Risk Factors",
  "num_segments": 45,
  "segments": [
    {"index": 0, "text": "...", "word_count": 150, "char_count": 890}
  ]
}
```

### Risk Taxonomy (12 Categories)

Configured in `configs/features/risk_analysis.yaml`. Industry-specific variants selected via SIC code → SASB mapping.

`Market` · `Operational` · `Financial` · `Regulatory` · `Technology` · `Legal` · `Strategic` · `Reputation` · `Human Capital` · `Environmental` · `Geopolitical` · `Product/Service`

### KPIs

| KPI | Target | Current Status |
|-----|--------|---------------|
| Parsing success rate | ≥ 95% | Not yet measured at scale |
| Mean processing time per filing | < 2s | Not yet benchmarked |
| Extraction text loss | < 5% | Validated on AAPL_10K_2021 |
| Classifier confidence threshold | ≥ 0.7 | Configurable; default 0.7 |
| Test coverage | ≥ 186 tests passing | 186 ✅ |

---

## 6. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| OQ-1 | Should HTML tables be extracted as markdown or discarded? Tables in risk sections may contain material disclosures. | Data Eng | Open |
| OQ-2 | What is the acceptable text-loss threshold for non-standard filings (e.g., inline XBRL)? | Data Scientist | Open |
| OQ-3 | Fine-tuning: use full segment text or truncate to 512 tokens? Impact on classification quality unknown. | ML Engineer | Open |
| OQ-4 | Should `Data_Dictionary.md` be a living doc in `docs/` or generated from Pydantic model schemas? | Eng Lead | Open |
| OQ-5 | Batch CLI target: 10,000 filings / 2 hrs — is this realistic given transformer inference overhead? Needs benchmarking. | ML Engineer | Open |
