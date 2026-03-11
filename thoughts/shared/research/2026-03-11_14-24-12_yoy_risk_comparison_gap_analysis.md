---
title: "YoY Risk Comparison Feature — Gap Analysis & Feasibility"
date: 2026-03-11
time: "14:24:12"
author: bethCoderNewbie
git_commit: cddb2b2
branch: main
repository: SEC-finetune
status: VALIDATED — 2026-03-11; all gaps verified against live codebase HEAD cddb2b2
related_prd: PRD-002_SEC_Finetune_Pipeline_v2.md
related_goals: G-04, G-12, G-13, G-15, G-16
related_stories: US-001, US-004, US-006, US-029, US-030
related_research:
  - 2026-03-03_17-30-00_segment_annotator_jsonl_transform.md
---

# YoY Risk Comparison Feature — Gap Analysis & Feasibility

## 1. Use Case Definition

**Actor:** Financial Analyst

**Query input:** Ticker symbol (e.g. `AAPL`) or CIK (e.g. `0000320193`) entered in a
frontend UI.

**Expected output:** A table (or structured list) of risk categories with segment counts,
representative excerpts, and year-over-year deltas across available fiscal years
(e.g. 2020–2024). Example layout:

```
Risk Category        | 2021 | 2022 | 2023 | 2024 | Δ 23→24
─────────────────────┼──────┼──────┼──────┼──────┼────────
Cybersecurity        |   12 |   14 |   18 |   22 |  ↑ +4
Regulatory           |    8 |    9 |    8 |   11 |  ↑ +3
Financial            |   15 |   11 |   10 |    9 |  ↓ −1
Supply Chain         |    4 |    6 |    8 |    7 |  ↓ −1
ESG                  |    3 |    4 |    6 |    8 |  ↑ +2
...
```

Drill-down: clicking a cell surfaces the actual segment text from that year and category.

---

## 2. Current Pipeline State (Ground Truth)

### 2.1 What the pipeline produces today

Every processed filing writes one `*_segmented_risks.json` per section to
`data/processed/{run_id}/`. Confirmed fields on the live schema (`segmentation.py:47–58`):

**Filing-level (on `SegmentedRisks`):**

| Field | Present in model | Restored by `load_from_json` | Notes |
|:------|:----------------|:-----------------------------|:------|
| `ticker` | ✅ | ✅ `segmentation.py:209` | |
| `cik` | ✅ | ✅ `segmentation.py:208` | |
| `sic_code` | ✅ | ✅ `segmentation.py:206` | |
| `fiscal_year` | ✅ | ✅ `segmentation.py:212` | Use as YoY bucket key |
| `form_type` | ✅ | ✅ | Filter to `10-K` |
| `filed_as_of_date` | ✅ (model) | ❌ NOT restored | B-5; see §3 D-4 |
| `accession_number` | ✅ (model) | ❌ NOT restored | Same B-5 omission |

**Segment-level (on `RiskSegment`, `segmentation.py:15–22`):**

| Field | Present | Notes |
|:------|:--------|:------|
| `text` | ✅ | |
| `word_count` | ✅ | |
| `char_count` | ✅ | |
| `ancestors` | ✅ | ADR-014, commit `51eb8b8`; proxy labels via `ancestors[-1]` |
| `parent_subsection` | ✅ | |
| `risk_label` | ❌ | G-12 not implemented |
| `sasb_topic` | ❌ | G-15 not implemented |
| `confidence` | ❌ | G-12 not implemented |
| `label_source` | ❌ | G-12 not implemented |

### 2.2 What the Streamlit app does today

`src/visualization/app.py` (463 lines):
- `run_analysis_pipeline(file_path: Path)` at line 249 — accepts a **local file path** and
  re-runs the full pipeline in real time: `SECFilingParser → RiskFactorExtractor →
  TextCleaner → RiskSegmenter → RiskClassifier`
- `RiskClassifier` import at line 19 from `src/analysis/inference.py` — uses deprecated
  `risk_taxonomy.yaml` (Software & IT Services only, superseded by two-layer SASB schema)
- No ticker/CIK query input
- No multi-year support
- No comparison table

CSS/layout scaffolding (lines 30–220) is reusable. Data layer must be replaced entirely.

### 2.3 Corpus contamination baseline

Run `20260223_182806` (959 filings, 607,463 total segments):

| Section | Segments | % of corpus | In scope for use case |
|:--------|:---------|:------------|:----------------------|
| `part1item1a` (Risk Factors) | 112,173 | 18.5% | ✅ YES |
| `part2item7` (MD&A) | 142,142 | 23.4% | ❌ NO |
| `part2item8` (Financial Statements) | 198,860 | 32.7% | ❌ NO |
| `part1item1` (Business Description) | 108,056 | 17.8% | ❌ NO |
| Others | 46,232 | 7.6% | ❌ NO |

81.5% of the corpus is noise relative to this use case.

---

## 3. Gap Analysis

Gaps are grouped by layer and ordered by severity within each layer.

### Layer 1 — Data

---

#### D-1 — Risk labels absent **[CRITICAL BLOCKER]**

`risk_label`, `label` (int 0–8), `confidence`, and `label_source` do not exist on any
segment. G-12 (classifier integration) is ❌. Without a risk label, the category column
in the output table is undefined; YoY category identity across years is undefined.

**Workaround:** `ancestors[-1]` as a proxy category. Per PRD-002 §8, 40–60% of segments
carry headings that map to archetypes. Works for single-company YoY; breaks for
cross-company comparison because heading strings are company-specific prose not a
controlled vocabulary.

**Fix path:** `SegmentAnnotator` Stage A (BART zero-shot, `facebook/bart-large-mnli`),
fully specified in `2026-03-03_17-30-00_segment_annotator_jsonl_transform.md`.

---

#### D-2 — No per-ticker / per-CIK file index **[CRITICAL BLOCKER]**

`StateManager` (`src/utils/state_manager.py`) tracks files by content hash for
deduplication (`should_process` at line 197) but stores no searchable metadata by
ticker or year. Answering "give me all AAPL filings" requires a full directory scan of
every `*_segmented_risks.json` file in the run dir.

At scale (~959 files, each ~200 KB), this is a cold-start bottleneck on every query.

**Required:** A `TickerIndex` — a lightweight JSON map built once per run:
```json
{
  "AAPL": [
    {"path": "..._part1item1a_segmented_risks.json", "fiscal_year": "2021",
     "cik": "0000320193", "sic_code": "3571", "filed_as_of_date": "20211029"},
    ...
  ]
}
```
Natural home: alongside `batch_summary_{run_id}.json` in the stamped run dir.
`StateManager.record_success` at line 236 is the correct hook point to write this.

---

#### D-3 — Section contamination **[HIGH — degrades signal quality]**

81.5% of the current corpus is non-`part1item1a` content (see §2.3). A query that reads
all `*_segmented_risks.json` for a ticker without a section filter will pull Financial
Statement boilerplate and MD&A into the risk category table.

**Fix path:** OQ-PRD-1 Option A — add `section_filter: [part1item1a]` to the dispatch
config and re-run the batch. `SegmentAnnotator.annotate_run_dir()` enforces this at the
annotator layer via `section_include` parameter (research doc §4.2).

---

#### D-4 — `filed_as_of_date` not restored by `load_from_json` **[MEDIUM]**

`segmentation.py:204–224`: `document_info.filed_as_of_date` is written by `save_to_json`
(`segmentation.py:127`) but never passed to the constructor on load. After round-trip,
`segmented.filed_as_of_date` is always `None`.

**Impact on this use case:** `fiscal_year` IS correctly restored (line 212) and is
sufficient for annual YoY bucketing. `filed_as_of_date` is needed for exact-date display
and sub-annual analysis. **Not a hard blocker for annual YoY; low priority.**

**Fix:** One-line patch — add `filed_as_of_date=di.get('filed_as_of_date')` and
`accession_number=di.get('accession_number')` to the `SegmentedRisks` constructor call
at `segmentation.py:204`.

---

#### D-5 — Multi-year corpus coverage unknown **[HIGH — use case viability]**

A meaningful YoY trend requires ≥ 3 years of the same ticker. Whether the current corpus
has 3+ years of any ticker is unverified. No audit script counts years-per-ticker today
(G-13 `--ticker` filter is ❌).

**Verification command:**
```bash
python -c "
import json, glob, collections
years = collections.defaultdict(set)
for f in glob.glob('data/processed/**/*_segmented_risks.json', recursive=True):
    try:
        d = json.load(open(f))
        t = d.get('document_info', {}).get('ticker')
        y = d.get('document_info', {}).get('fiscal_year')
        if t and y: years[t].add(y)
    except: pass
multi = {t: sorted(ys) for t, ys in years.items() if len(ys) >= 3}
print(f'{len(multi)} tickers with ≥3 years'); [print(t, ys) for t, ys in list(multi.items())[:20]]
"
```

**Risk if unresolved:** If no ticker has ≥3 years, the feature cannot be demonstrated
until more data is downloaded. `scripts/data_collection/download_sec_filings.py` exists;
year-range parameterization must be verified.

---

#### D-6 — G-15 taxonomy files absent **[MEDIUM — SASB columns null]**

`src/analysis/taxonomies/sasb_sics_mapping.json` and `archetype_to_sasb.yaml` do not
exist. `TaxonomyManager.get_industry_for_sic()` silently returns `None`
(`taxonomy_manager.py:118`). `sasb_topic` and `sasb_industry` columns will be `null` in
all output until US-030 is completed.

**Impact on use case:** The 9-archetype row labels still work without SASB taxonomy.
`sasb_topic` is a "nice to have" column for industry-specific precision, not a prerequisite
for a functional YoY comparison table.

---

### Layer 2 — Query / Aggregation

---

#### Q-1 — No aggregation logic exists **[CRITICAL — core feature]**

Zero code exists anywhere in the repository to:
- Group segments by `(ticker, fiscal_year, risk_label)` → segment count per cell
- Select representative excerpts per cell (e.g. highest-confidence segment per category)
- Compute YoY deltas (count Δ, new categories, disappeared categories)
- Deduplicate boilerplate across years (SHA-256 of text)

This is the entire computational heart of the feature and is completely unbuilt.

---

#### Q-2 — No query API **[LOW for single-user Streamlit; MEDIUM for multi-user]**

PRD-002 Non-Goals defers "Public REST API." Streamlit's built-in server handles
single-user load adequately for an analyst tool. A FastAPI thin layer can be added later
without changing the aggregation module. Not blocking for initial delivery.

---

#### Q-3 — No cross-year deduplication **[MEDIUM — misleads trend signal]**

The same boilerplate risk disclosure (e.g. "We may not be able to maintain our quarterly
or annual revenue growth...") appears verbatim across 3–5 consecutive years in many
filings. Without SHA-256 dedup of `text` across years, stable categories show
artificially flat counts rather than "no new disclosures added." This corrupts the most
useful YoY signal — detecting year-over-year category expansion or new risk mentions.

**Fix path:** During aggregation, group by `(ticker, risk_label, sha256(text))` across
years; mark segments as `"repeated_from": [year, ...]` to distinguish new from carry-over
text.

---

### Layer 3 — Frontend

---

#### F-1 — `app.py` is single-filing, real-time mode **[HIGH — complete rewrite of data layer]**

`run_analysis_pipeline(file_path: Path)` at `app.py:249` re-runs the full preprocessing
pipeline in real time on a local file. For this use case, the data layer must be replaced
with a JSONL reader that loads pre-computed annotated output. The CSS/layout/sidebar
scaffolding (lines 30–220) is reusable.

**Correct data flow for the new view:**
```
User input (ticker / CIK)
    → TickerIndex lookup → list of JSONL files for that ticker
    → load JSONL records → filter section_identifier == "part1item1a"
    → aggregation module → pivot table (risk_label × fiscal_year)
    → Streamlit st.dataframe / custom HTML table
```

---

#### F-2 — `RiskClassifier` import in `app.py` uses deprecated taxonomy **[MEDIUM]**

`app.py:19` imports `RiskClassifier` from `src/analysis/inference.py`. That class loads
labels from `risk_taxonomy.yaml` — hardcoded to Software & IT Services. If the app is
run before the data layer is replaced, labels would silently be wrong for all non-tech
companies. The new view must never instantiate `RiskClassifier`; it reads
`risk_label` from pre-computed JSONL only.

---

#### F-3 — No YoY comparison widget exists **[CRITICAL — core UI]**

No pivot table, no year columns, no delta indicators, no drill-down to segment text, no
"new this year" / "dropped vs last year" highlighting exists in `app.py` or anywhere
else in the codebase.

---

## 4. Feasibility — Three Tiers

### Tier A: Heading-based MVP (no classifier)

**Mechanism:** Use `ancestors[-1]` as the category label. Group segments by
`(ticker, fiscal_year, ancestors[-1])`. Build a YoY table from heading counts.

**Dependencies:**
1. Section filter to `part1item1a` (D-3 fix) — config change
2. `TickerIndex` builder (D-2 fix) — new utility, ~100 LOC
3. Aggregation by heading string (Q-1 partial) — ~100 LOC
4. Normalize heading strings to a canonical set — fuzzy string match or lookup
5. Replace `app.py` data layer (F-1) — refactor
6. YoY table widget (F-3) — new Streamlit component

**Limitation:** Category identity breaks across companies. "Cybersecurity and Data
Privacy Risks" (AAPL) ≠ "Cybersecurity Risk" (MSFT) ≠ "Data Security" (JPM) — three
strings for the same concept. Normalization is heuristic and company-specific. Useful
only for same-company YoY; cross-company comparison is not reliable.

**Verdict:** Demonstrable prototype for a single company. Low analytical value without
the classifier because the taxonomy is unstable.

---

### Tier B: Archetype-label MVP (SegmentAnnotator Stage A — recommended)

**Mechanism:** `SegmentAnnotator` (BART zero-shot) assigns one of 9 archetypes to each
merged segment. Group by `(ticker, fiscal_year, risk_label)`. SASB columns are null until
G-15 is complete but are non-blocking for a working table.

**Dependencies (ordered by dependency chain):**

```
1. Decision: lock label_source namespace (OQ-A9)       [0 code, 1 decision]
   │
2. Config: dispatch filter to part1item1a only          [~10 lines config]
   │
3. Re-run batch on part1item1a-filtered corpus          [pipeline run]
   │
4. Patch segmentation.py:load_from_json (B-5)          [2 lines — filed_as_of_date,
   │                                                      accession_number]
   │
5. Create src/analysis/segment_annotator.py             [new class — fully specced
   │   + scripts/.../segment_annotator_cli.py            in 2026-03-03 research doc]
   │
6. Build TickerIndex utility                            [new — ~100 LOC]
   │
7. Build aggregation + YoY diff module                  [new — ~200 LOC]
   │  (group, count, excerpt select, SHA-256 dedup, delta compute)
   │
8. Refactor app.py: new YoY view (replace data layer)   [modify existing]
   │  ticker/CIK input → TickerIndex lookup → pivot table widget
   │
9. (Parallel, unblocked) Download ≥3 years per ticker   [data collection]
```

**Expected output quality:**
- BART zero-shot Macro F1 on SEC domain text: estimated **~0.55–0.60**
  (research doc C-4, citing SASB architecture comparison table)
- Sufficient for trend direction detection (growing / shrinking category)
- Not sufficient for precise segment-level classification
- Label clearly as "indicative — zero-shot classifier" in UI

**Verdict:** Correct long-term architecture. Well-specced. Delivers a working analyst
tool. Classifier quality is the primary caveat; Tier C (fine-tuning) improves accuracy
without changing any downstream schema or UI code.

---

### Tier C: Production-grade (fine-tuned DeBERTa + SASB)

**Mechanism:** Swap BART for the fine-tuned DeBERTa-v3-base checkpoint (PRD-004). Add
`sasb_topic` and `sasb_industry` columns to the table. Cross-company SASB comparison
becomes valid.

**Dependencies:** G-15 (US-030) + G-16 (US-031) + PRD-004 fine-tune training run.
Requires annotation corpus construction first. All Tier B schema and UI code is reused
unchanged — same `risk_label` field, same JSONL format.

**Verdict:** Adds material value for cross-industry comparison. Not a prerequisite for
a working Tier B demo.

---

## 5. Critical Path for Tier B

The minimum viable path from current HEAD (`cddb2b2`) to a working analyst demo:

```
Step 1 — Unblock data quality
  a. Decide OQ-A9 label_source namespace (no code)
  b. Set dispatch config section_filter: [part1item1a]
  c. Re-run batch; confirm part1item1a corpus = ~112,173 segments (run 20260223_182806 baseline)

Step 2 — Annotate corpus
  a. Patch segmentation.py:204-224 (B-5: filed_as_of_date + accession_number, 2 lines)
  b. Implement src/analysis/segment_annotator.py (see 2026-03-03 research doc §4)
  c. Run: segment_annotator_cli.py --run-dir <part1item1a run> --output labeled.jsonl

Step 3 — Query layer
  a. Build TickerIndex (written during batch run alongside batch_summary)
  b. Build aggregation module: group(ticker, fiscal_year, risk_label),
     count, excerpt select (highest word_count), SHA-256 dedup across years,
     delta column (count_year_N - count_year_N-1)

Step 4 — Frontend
  a. Verify ≥3 years of data available for at least one ticker (D-5 audit)
  b. Add new Streamlit page to app.py: ticker/CIK text input → TickerIndex lookup
     → load filtered JSONL → aggregation → st.dataframe pivot table
     → drill-down expander showing segment text per cell
```

---

## 6. Risk Register

| ID | Risk | Severity | Mitigation |
|:---|:-----|:---------|:-----------|
| R-1 | BART zero-shot F1 ~0.55–0.60 produces misleading YoY deltas | High | Label UI output as "indicative"; require ≥3 years to distinguish trend from noise; surface `confidence` score per cell |
| R-2 | D-5: corpus may have <3 years per ticker, making YoY demo impossible | High | Run D-5 audit (§3 D-5 command) before any implementation starts; download multi-year data via `scripts/data_collection/download_sec_filings.py` |
| R-3 | OQ-A9 decided late: `label_source` migration costs full re-annotation pass (156K records) | High | Resolve before Step 2b; define as module-level constant in `segment_annotator.py` |
| R-4 | Non-calendar fiscal year companies (CAH, MCD: FY ends June 30) produce ambiguous `fiscal_year` buckets in a calendar-year aligned table | Medium | Normalize `fiscal_year` to `int(fiscal_year[:4])`; display "FY{year}" not calendar year; document non-calendar companies |
| R-5 | Boilerplate carry-over inflates stable category counts across years (looks like consistent risk when it is just copy-paste) | Medium | SHA-256 dedup across years in aggregation module (Q-3); show "N new, M repeated" per cell |
| R-6 | `app.py` imports deprecated `RiskClassifier` — if the old code path is accidentally invoked, labels are silently wrong for non-tech sectors | Medium | New YoY view never instantiates `RiskClassifier`; reads `risk_label` from pre-computed JSONL only; mark old `RiskClassifier` import with deprecation comment |
| R-7 | Without B-5 patch, `filed_as_of_date` is null — exact filing date cannot be shown in drill-down | Low | Use `fiscal_year` for table columns; show "FY2021" not "2021-10-29" until B-5 is patched |

---

## 7. File Inventory — What to Create / Modify

| File | Action | Tier | Notes |
|:-----|:-------|:-----|:------|
| `src/analysis/segment_annotator.py` | CREATE | B | Core annotator; fully specced in 2026-03-03 research |
| `scripts/feature_engineering/segment_annotator_cli.py` | CREATE | B | CLI wrapper for batch annotation |
| `src/utils/ticker_index.py` | CREATE | B | `TickerIndex` builder; hook into `StateManager.record_success` |
| `src/analysis/aggregation.py` | CREATE | B | `group_by_risk_label`, `yoy_delta`, `select_excerpts`, `dedup_across_years` |
| `src/preprocessing/models/segmentation.py` | MODIFY | B | B-5 patch: restore `filed_as_of_date` + `accession_number` in `load_from_json:204-224` |
| `src/visualization/app.py` | MODIFY | B | Add new YoY view page; do not touch existing single-file pipeline view |
| `configs/` (dispatch config) | MODIFY | B | `section_filter: [part1item1a]` |
| `src/analysis/taxonomies/sasb_sics_mapping.json` | CREATE | C | G-15 / US-030 prerequisite |
| `src/analysis/taxonomies/archetype_to_sasb.yaml` | CREATE | C | G-15 / US-030 prerequisite |

**Do NOT modify:**
- `src/analysis/inference.py` — deprecated; new path reads pre-computed JSONL
- `src/preprocessing/segmenter.py` — no schema changes needed
- `SegmentedRisks` / `RiskSegment` model fields — no schema migration required

---

## 8. Open Questions

| ID | Question | Blocks |
|:---|:---------|:-------|
| OQ-YoY-1 | Does the current corpus have ≥3 fiscal years for any ticker? Run D-5 audit before committing to Tier B implementation. | Use case viability |
| OQ-YoY-2 | What is the preferred cell value in the pivot table: (a) raw segment count, (b) character-weighted count, (c) a single "risk intensity score" combining count + confidence? Option (a) is simplest and most transparent. | Aggregation module design |
| OQ-YoY-3 | How should "new this year / dropped vs last year" be represented in the UI: a separate column, row-level badges, or cell color coding? Analyst preference — needs UX decision before F-3 implementation. | Frontend widget design |
| OQ-YoY-4 | Should the TickerIndex be built as a side-effect of every batch run (hook in `StateManager.record_success`), or as a separate post-processing step? The hook approach is lower friction; the post-processing script is more explicit and testable. | TickerIndex architecture |
| OQ-YoY-5 | `fiscal_year` in EDGAR metadata is sourced from `period_of_report` (SGML header field). For non-calendar fiscal years (e.g. CAH FY ends June 30), `period_of_report=20210630` means the filing covers FY2021 but is filed in October. Should the YoY table bucket by `period_of_report` year or by `filed_as_of_date` year? Answer: `period_of_report` year — this is what analysts mean by "fiscal year". | Temporal bucketing logic |
| OQ-YoY-6 | Should the BART zero-shot classifier in Stage A use `ARCHETYPE_NAMES` as NLI candidates, or industry-specific SASB topic names (if `sasb_sics_mapping.json` is available)? See research doc §4.4 C-2 and OQ-A10. This decision also determines whether `archetype_to_sasb.yaml` is needed at all for NLI. | `SegmentAnnotator._classify_archetype()` |
