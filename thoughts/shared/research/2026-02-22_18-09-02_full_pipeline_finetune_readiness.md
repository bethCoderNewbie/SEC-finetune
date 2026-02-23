---
title: "Full Pipeline Research: Fine-tuning Readiness (Supersedes 2026-02-18_15-26-29)"
date: "2026-02-22"
timestamp: "2026-02-22_18-09-02"
commit: "b9fb777361d5efd1cfbb4678442a8ebacda17d9e"
branch: "main"
researcher: "bethCoderNewbie"
status: "complete"
supersedes: "thoughts/shared/research/2026-02-18_15-26-29_full_pipeline_finetune_readiness.md"
tags: [parser, sec-parser, finetune, data-quality, toc-contamination, segmenter, validation, roadmap, architecture, corpus-structure, xbrl, sgml, metadata-gap, performance]
related_plans:
  - thoughts/shared/plans/2026-02-18_10-00-00_parser_finetune_fixes.md
  - thoughts/shared/plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md
  - thoughts/shared/plans/2026-02-16_16-52-14_preprocessing_pipeline_optimization.md
related_research:
  - thoughts/shared/research/2026-02-22_10-00-00_aapl_parser_metrics_audit.md
  - thoughts/shared/research/2026-02-18_18-00-00_parser_finetune_critique.md
  - thoughts/shared/research/2025-12-30_17-43_section_end_precision_investigation.md
  - thoughts/shared/research/2025-12-30_14-39-03_extractor_qa_findings_verification.md
  - thoughts/shared/research/2025-12-30_18-20-45_parser_performance_analysis.md
related_reports:
  - reports/sec_html_structure/2026-02-22_17-57-43_sec_html_structure_findings.md
---

# Full Pipeline Research: Fine-tuning Readiness Assessment (v2)

**What changed since 2026-02-18:** Two new empirical sources added:
1. `2026-02-22_10-00-00_aapl_parser_metrics_audit.md` — live metrics on AAPL_10K_2021.html
   against the current codebase (commit b9fb777). Fix 1A confirmed active.
2. `reports/sec_html_structure/2026-02-22_17-57-43_sec_html_structure_findings.md` — corpus-wide
   structural analysis of 959 EDGAR files (194 unique tickers). Reveals SGML container nature,
   metadata coverage, extraction gap, and XBRL availability.

---

## 1. Project Objectives (Ground Truth)

### Primary Goal
Build a **training data factory** for fine-tuning FinBERT (and similar financial LLMs) on
SEC 10-K filings. The two downstream ML tasks are:

- **Risk classification** — categorise individual risk segments (market, regulatory, cyber,
  operational, liquidity, etc.)
- **Topic modeling** — surface latent risk themes across a corpus of filings

### Data Pipeline (Parse → Train)
```
SGML container files (data/raw/*.html)
       ↓ [SGML pre-read — MISSING — pipeline passes full file to BS4/sec-parser]
       ↓
[parser.py]       Parse iXBRL body → semantic elements + metadata
       ↓
[extractor.py]    Isolate Item 1A Risk Factors section
       ↓
[cleaning.py]     Remove artifacts (page numbers, HTML, ToC lines)
       ↓
[segmenter.py]    Split section into discrete risk segments
       ↓
SegmentedRisks.json  ← THE TRAINING UNIT (one file per filing)
       ↓
[feature/]        Sentiment + Readability + Topic features
       ↓
[models/]         FinBERT fine-tuning / LDA topic modeling
```

> **NEW (2026-02-22):** Each `.html` file is an SGML container embedding 67–684 separate
> documents. The pipeline currently treats the entire container as HTML and passes it to
> `sec-parser`, which only processes Document 1 (the iXBRL 10-K body, mean 5.2 MB). The
> remaining 151 embedded documents (XBRL financials, exhibits, MetaLinks.json) are invisible
> to the pipeline. The full container mean is 28.5 MB; the iXBRL body mean is 5.2 MB.

---

## 2. Pipeline Implementation Status

### Complete ✅
| Component | File | Notes |
|-----------|------|-------|
| SEC Filing Parser | `src/preprocessing/parser.py` | sec-parser v0.54.0 backend |
| Risk Factors Extractor | `src/preprocessing/extractor.py` | 3-strategy section finding |
| Text Cleaner | `src/preprocessing/cleaning.py` | spaCy + regex |
| Risk Segmenter | `src/preprocessing/segmenter.py` | Semantic + heuristic |
| Sentiment Analyzer | `src/features/sentiment.py` | Loughran-McDonald dict |
| Readability Analyzer | `src/features/readability/` | 6 indices + obfuscation score |
| Topic Modeling | `src/features/topic_modeling/` | LDA (Gensim) |
| Memory-aware batch | `src/utils/memory_semaphore.py` | OOM prevention |
| Adaptive timeouts | pipeline + retry scripts | 600s–2400s by file size |
| Production worker reuse | `src/preprocessing/pipeline.py` | 50x model load reduction |
| DLQ retry mechanism | `scripts/utils/retry_failed_files.py` | Adaptive timeout retry |
| Checkpoint/resume | `src/utils/checkpoint.py` | Crash-safe batches |
| **BS4 flatten path (Fix 1A)** | `src/preprocessing/parser.py:412-466` | **CONFIRMED ACTIVE** (b9fb777) |

### Fix 1A Status — Confirmed Live (2026-02-22)
AAPL_10K_2021 audit (`commit b9fb777`) confirms the BS4 flatten path fires for files >10 MB
(threshold 10,485,760 bytes). AAPL at 10,502,225 bytes routes to BS4 path. Measured time:
**2.12s** (11% of total parse; down from documented hang risk on DOTALL path). DOTALL
catastrophic backtracking eliminated for large files.

### In Progress 🚧
| Work | Owner doc | Status |
|------|-----------|--------|
| State manifest + atomic writes | `plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md` | Active |
| Inline gatekeeper + quarantine | same | Active |
| Auto-documentation (markdown reports) | same | Active |
| Training data quality fixes (Plan B) | `plans/2026-02-18_10-00-00_parser_finetune_fixes.md` | Planned |

### Open Blockers for Fine-tuning ❌
| Blocker | Scale | Months Open |
|---------|-------|-------------|
| ToC contamination in extracted text | 175 / 309 files (56.6%) | 2+ months |
| Zero-segment filings pass validation | Unknown % silently broken | 2+ months |
| Tables included in training text | All files with tables | 2+ months |
| Regex sentence splitter on abbreviations | All files | 2+ months |
| No segment-level deduplication | All filings w/ multi-year coverage | 2+ months |

---

## 3. Corpus Structure Reality (NEW — 2026-02-22)

Source: `reports/sec_html_structure/2026-02-22_17-57-43_sec_html_structure_findings.md`
(959 files, 194 unique tickers, full corpus).

### 3.1 EDGAR Files Are SGML Containers

Each `.html` file is a flat concatenation of `<DOCUMENT>` blocks:

```
<SGML HEADER>  ~80 lines, plain text — company/filing metadata
<DOCUMENT 1>   iXBRL main 10-K body         ← sec-parser sees this
<DOCUMENT 2>   EX-101.SCH (XBRL schema)     ← invisible to pipeline
<DOCUMENT 3>   EX-101.CAL (calculations)    ← invisible to pipeline
<DOCUMENT 4+>  R*.htm XBRL render sheets    ← invisible to pipeline (mean 118/file)
...            MetaLinks.json, exhibits, GRAPHIC files
```

**Impact:** sec-parser only processes Document 1. All XBRL financials, calculation trees,
and MetaLinks definitions are present in the raw files but currently never read.

### 3.2 File Size Distribution

| Metric | Full container | Main 10-K body (Document 1) |
|--------|---------------|----------------------------|
| Min | 6.6 MB | 0.8 MB |
| Median | 22.1 MB | 3.9 MB |
| Mean | 28.5 MB | 5.2 MB |
| P95 | 74.4 MB | 15.3 MB |
| Max | 205.1 MB (EXC_10K_2022) | 26.2 MB |

**Performance implication:** Fix 1A (BS4 path) fires when main body > 10 MB. At P95 = 15.3 MB,
roughly 5% of filings will trigger the BS4 path. However, the AAPL audit shows that even
with BS4 flatten resolved, `sec-parser.Edgar10QParser.parse()` on a 10 MB body costs 16.30s.
Files at P95 (15.3 MB) will cost proportionally more.

### 3.3 Industries with Largest Files (Systematic Performance Risk)

| SIC | Industry | Avg file size | Avg R*.htm |
|-----|----------|--------------|-----------|
| 4931 | Electric & Other Services | 75.4 MB | 168 |
| 6311 | Life Insurance | 72.6 MB | 220 |
| 4911 | Electric Services | 70.5 MB | 170 |
| 6022 | State Commercial Banks | 55.9 MB | 180 |
| 6021 | National Commercial Banks | 55.0 MB | 168 |
| 6331 | Fire/Marine/Casualty Insurance | 49.1 MB | 153 |
| 6211 | Security Brokers/Dealers | 44.4 MB | 185 |

Utilities (AEP, DUK, SO, D, EXC), large banks (JPM, BAC, C, WFC, BK), and insurers
(MET, PRU, AIG, AFL, CB) are the worst-case files. AEP's main body is ~25 MB;
parse time on current backend is estimated at ~40–60s per file.

### 3.4 Two Metadata Sources

The pipeline currently only uses the SGML header. A richer set of fields is available in
the DEI `<ix:hidden>` block embedded in Document 1:

| Source | Speed | Fields | Reliability |
|--------|-------|--------|-------------|
| SGML header | Fast (regex, no HTML parse) | company_name, cik, sic, period, fiscal_year, accession_number | EIN: 12% coverage |
| DEI `<ix:hidden>` | Requires HTML parse | All SGML fields + ticker, exchange, shares_outstanding, public_float, filer_category, amendment_flag, EIN | EIN: 100% coverage |

**EIN reliability:** Only 115/959 (12%) SGML headers contain `ein`. But
`dei:EntityTaxIdentificationNumber` was present in 958/959 (100%) DEI blocks. Always use
DEI source for EIN.

**Ticker reliability:** `TradingSymbol` is the only source for ticker (not in SGML header).
Present in 952/959 (99%). Two format variants in corpus — requires `.get()` guard.

### 3.5 Extraction Gap: 7/22 Fields Currently Extracted

| Field | Source | Currently Extracted | Notes |
|-------|--------|---------------------|-------|
| `company_name` | SGML | ✓ | All-caps; DEI has proper casing |
| `cik` | SGML | ✓ | |
| `sic_code` | SGML | ✓ | |
| `sic_name` | SGML | ✓ | |
| `ticker` | DEI iXBRL | ✓ | Two format variants |
| `fiscal_year` | SGML | ✓ | Derived from `period_of_report[:4]` |
| `period_of_report` | SGML | ✓ | |
| `ein` | SGML | ✗ | **Use DEI instead; SGML unreliable (12%)** |
| `state_of_incorporation` | SGML | ✗ | SGML=2-letter; DEI=full name |
| `fiscal_year_end` | SGML | ✗ | MMDD format e.g. `0925` = Sep 25 |
| `accession_number` | SGML | ✗ | Unique EDGAR filing ID — needed for API lookups |
| `sec_file_number` | SGML | ✗ | |
| `exchange` | DEI iXBRL | ✗ | `SecurityExchangeName` |
| `shares_outstanding` | DEI iXBRL | ✗ | `EntityCommonStockSharesOutstanding` |
| `public_float` | DEI iXBRL | ✗ | `EntityPublicFloat`; formatting varies |
| `filer_category` | DEI iXBRL | ✗ | `EntityFilerCategory` |
| `amendment_flag` | DEI iXBRL | ✗ | `AmendmentFlag` |
| `FASB element definitions` | MetaLinks.json | ✗ | definitions, calc tree, presentation |
| `all financial facts` | XBRL instance XML | ✗ | All tagged monetary/numeric values |
| `calculation tree` | EX-101.CAL | ✗ | |
| `named financial statements` | FilingSummary.xml | ✗ | R*.htm name + MenuCategory |
| `company graphics` | GRAPHIC documents | ✗ | UUencoded; rarely needed |

**32% coverage (7/22).** The most actionable gaps: `accession_number` (100% SGML presence,
0 lines of new parsing needed), `ein` (switch source from SGML to DEI), and
`state_of_incorporation` / `fiscal_year_end` (already in SGML, just not extracted).

---

## 4. Parser Performance Reality (UPDATED — 2026-02-22)

Source: `thoughts/shared/research/2026-02-22_10-00-00_aapl_parser_metrics_audit.md`
(live run against AAPL_10K_2021.html, 10.01 MB, commit b9fb777).

### 4.1 Empirical Timing on AAPL_10K_2021 (10 MB)

| Step | Time | % of total |
|------|------|-----------|
| `_flatten_html_nesting` (BS4 path, Fix 1A) | 2.12s | 11% |
| `sp.Edgar10QParser().parse()` | 16.30s | **87%** |
| `sp.TreeBuilder().build()` | 0.02s | <1% |
| **Total** | **18.44s** | 100% |

**Root cause of slowness:** The bottleneck is **entirely the sec-parser library**, not our
wrapper code. Fix 1A eliminated the DOTALL catastrophic backtracking. No further optimization
of our code changes `Edgar10QParser.parse()` timing.

**5-second target is unachievable** for 10 MB+ files with the current sec-parser backend.
Realistic targets: ~18–20s for 10 MB, ~40–60s for 25 MB (AEP-class files), timeout risk
for 26 MB files.

### 4.2 Metrics Audit Results (7/10 PASS)

| Metric | Target | Result | Status |
|--------|--------|--------|--------|
| Section Hit Rate (4 items) | 100% | 100% (4/4) | PASS |
| Tree Depth Verification | Flat iteration | Max depth=6; flat iteration via `tree.nodes` | NUANCED |
| Text Cleanliness | 0 HTML tags | 0 HTML tags in 66,655-char Item 1A | PASS |
| Table Reconstruction | No crashes | 741 tables, 0 crashes | PASS |
| Title/Header Classification | 100% | 100% via 3-strategy search | PASS |
| Parsing Latency | <5s | **18.68s** | **FAIL** |
| Throughput | 1–2 MB/s | **0.54 MB/s** | **FAIL** |
| Memory Footprint | Not measured | Not measured | N/A |
| Error Rate | 0% | 0 exceptions | PASS |
| Idempotency | 100% | 2,017 elements x2 identical | PASS |

### 4.3 sec-parser Internals (v0.54.0)

Processing pipeline:
```
IndividualSemanticElementExtractor
  → ImageClassifier
  → EmptyElementClassifier
  → TableClassifier               ← classifies <table> elements
  → TableOfContentsClassifier     ← classifies HTML-table ToC ONLY (not text-line ToC)
  → TopSectionManagerFor10Q       ← promotes item\s+\d+a? to TopSectionTitle
  → IntroductorySectionClassifier
  → TextClassifier
  → HighlightedTextClassifier
  → SupplementaryTextClassifier
  → PageHeaderClassifier
  → PageNumberClassifier
  → TitleClassifier               ← promotes bold/highlighted text to TitleElement
  → TextElementMerger             ← reassembles <span>-fragmented text
```

`TopSectionManagerFor10Q` item pattern: `re.compile(r"item\s+(\d+a?)[.\s]*", re.IGNORECASE)`.
Only numeric + optional-`a` suffix items become `TopSectionTitle`; Items 1B, 1C, 7, 7A, 8, 9
become `TitleElement`. This is why the 3-strategy extractor fallback is necessary.

### 4.4 Pros and Cons of Keeping sec-parser

**Pros:**
- `TextElementMerger` reassembles `<span>`-fragmented text — the hardest part to rewrite;
  EDGAR HTML splits single sentences across 5–10 styled `<span>` tags
- Bold/highlighted text → `TitleElement` detection handles diverse formatting
- `TableOfContentsClassifier` catches HTML-table ToC correctly
- `PageHeaderElement` / `PageNumberElement` / `TableElement` classification saves extractor work
- 3+ years of EDGAR-specific tuning; MIT license; BS4 already its own dependency
- 100% Key Item Recall via 3-strategy fallback (verified on 309 files)

**Cons:**
- **Processes entire document body** (mean 5.2 MB) to find one section — no seek capability
- **Text-line ToC not detected** — `TableOfContentsClassifier` only handles `{TableElement}`
- `TableOfContentsElement` nodes not filtered by extractor (1-line fix, unimplemented)
- No streaming/chunking — peak RAM scales with file body size
- `ParsingOptions` has one knob (`html_integrity_checks`); cannot customise pipeline steps
- Monkey patch required for `approx_table_metrics` bug (`parser.py:26-46`)
- Single parser for all form types; no 10K-specific parser forthcoming

### 4.5 Hybrid Pre-Seek Architecture (Plan C — Recommended)

EDGAR filings use named anchor IDs linking ToC `href` targets to section bodies:
```html
<!-- Inside a <table> — the ToC -->
<a href="#i4bf6d0bde838478985b72eb4052bc976_19">Item 1A-Risk Factors</a>

<!-- The actual section, elsewhere in document -->
<a id="i4bf6d0bde838478985b72eb4052bc976_19"></a>
```

**Proposed architecture:**
```
Full SGML container (6–205 MB)
       ↓
[NEW] SGML pre-read: extract Document 1 boundary only (< 0.1s, string seek)
       ↓
[NEW] Anchor-based section pre-seek (BS4 on Document 1 only, < 0.5s)
    – Find <a id="..."> for Item 1A start  (via href from ToC entry)
    – Find <a id="..."> for Item 1B / Item 2 end
    – Slice raw HTML to ~50–200 KB Item 1A fragment
       ↓
[EXISTING] sec-parser (now processes 50–200 KB, not 5.2 MB)
    – ~1–2s instead of 18s
    – TextElementMerger handles <span> fragmentation
    – TitleElement detection finds subsection headers
       ↓
[EXISTING + FIXES] Extractor filters:
    + Filter TableOfContentsElement (1-line fix)
    + Filter text-line ToC via TOC_PATTERNS_COMPILED (Fix 2A)
    + Filter TableElement from full_text (Fix 2B)

Fallback: for filings without named anchors, fall back to full-document parse path.
```

**Estimated performance:** < 2s per file vs 18–20s current (10–15x improvement).

---

## 5. Training Data Quality Issues (UPDATED — 2026-02-22)

All findings cross-referenced against past research corpus. Fix 1A confirmed active (§2).
Remaining open issues below.

### 5.1 Critical: Zero Segments Passes Validation
**File:** `src/config/qa_validation.py:787-788`

```python
if total_segments == 0:
    return results  # returns [] — no ValidationResult fires
```

Both `_check_cleanliness` and `_check_substance` guard with `if total_segments == 0:
return results`. Empty lists propagate to `determine_overall_status([])` which returns
`PASS`. Broken filings with zero segments silently enter training data.

**Fix:** Emit a blocking `ValidationResult(FAIL)` when `total_segments == 0` before the
guard returns. Single-line change.

---

### 5.2 Critical: ToC Contamination (56.6% of Files)
**Files:** `src/preprocessing/extractor.py:459-468`, `src/preprocessing/cleaning.py:168-200`
**Evidence:** 175/309 files confirmed; 93 files (34.3%) fail *only* ToC check.

Two distinct ToC formats cause contamination:

1. **HTML-table format ToC** — sec-parser classifies these as `TableOfContentsElement`
   (a `TableElement` subclass). The extractor's `_extract_section_content` does not filter
   `TableOfContentsElement` nodes. A single `isinstance` check in `extractor.py:459` fixes this.

2. **Text-line format ToC** — dot-leader lines like `"Item 1A. Risk Factors..... 25"` arrive
   as `TextElement` nodes. `TableOfContentsClassifier` only processes `{TableElement}`, so
   these pass through unclassified. `cleaning.py:168-200` has 7 ToC patterns applied on
   aggregated text post-extraction but does not catch all formats in the corpus.

**Impact on fine-tuning:** ToC lines train FinBERT on boilerplate structure ("Item 1A..... 25")
rather than risk language. dot-leader sequences corrupt sentence and segment boundaries.

---

### 5.3 High: Tables Included in Training Text
**File:** `src/preprocessing/extractor.py:459-468`

`TableElement` nodes are collected into `content_nodes` and serialised into `full_text`.
Risk factor tables typically contain numerical sensitivity analyses that produce garbled
text when serialised: `"3.2% 4.1% 5.0% (12.3) (14.6) (16.2)"`.

FinBERT is a text classifier — injecting serialised table rows degrades classification
accuracy and distorts topic model vocabulary.

---

### 5.4 High: Regex Sentence Splitter Breaks on Financial Abbreviations
**File:** `src/preprocessing/segmenter.py:307, 349`

```python
sentences = re.split(r'([.!?]\s+)', text)         # line 307 — _split_into_chunks
sentences = re.split(r'(?<=[.!?])\s+', text)       # line 349 — _segment_by_semantic_breaks
```

Dense financial abbreviations (`U.S.`, `Inc.`, `Corp.`, `No.`, `vs.`, `Sec.`, `approx.`,
`i.e.`, `e.g.`, `Jan.`, `Feb.`) each create a false sentence boundary. False boundaries
corrupt cosine similarity scores between adjacent "sentences", which drives incorrect
semantic break points. Training samples begin mid-sentence or end mid-argument.

**Correct fix:** Replace both split calls with `spacy.sentencizer` (already a dependency).

---

### 5.5 High: No Segment-Level Deduplication
**File:** `src/config/qa_validation.py:890-908`

Hash deduplication operates on whole-filing content hash. Companies carry forward risk factor
language year-over-year nearly verbatim. Near-identical segments from the same company
(e.g., AAPL 2021 vs AAPL 2022) will appear in the corpus. Corpus has 193/194 tickers with
multiple filing years (most have 5y). Near-duplicate segments:
- Inflate apparent training set size
- Cause memorisation rather than generalisation
- Violate train/test independence (same company in both splits)

---

### 5.6 Medium: Line-Number Removal Deletes Enumerated List Items
**File:** `src/preprocessing/cleaning.py:160`

```python
text = re.sub(r'^[\s\-]*\d+[\s\-]*$', '', text, flags=re.MULTILINE)
```

Removes any line consisting solely of a digit. Single-digit enumerated list items
(a line containing just `"3"` between numbered paragraphs) are silently deleted.

---

### 5.7 Medium: Risk Keyword Validation Too Weak
**File:** `src/config/qa_validation.py:619-622`

```python
RISK_KEYWORDS = {"risk", "adverse", "material", "uncertain",
                 "may", "could", "might", "potential"}
```

Modal verbs (`may`, `could`, `might`) appear in virtually any English text. The `>= 10`
threshold at `qa_validation.py:918` is trivially satisfied by non-risk content.

**Stronger anchors for risk domain:** `impair`, `litigation`, `regulatory`, `infringement`,
`cybersecurity`, `volatility`, `liquidity`, `covenant`, `indemnif`, `recall`, `injunction`,
`write-down`.

---

### 5.8 Medium: `extraction_yield_ppm` Wrong Denominator
**File:** `src/config/qa_validation.py:873`

```python
yield_ppm = (extracted_chars / file_size_bytes) * 1_000_000
```

`file_size_bytes` is the **full SGML container** size (mean 28.5 MB), not the iXBRL body
(mean 5.2 MB), not the stripped text. A filing with 5.2 MB iXBRL body inside a 28.5 MB
container, yielding 150 KB of extracted text, produces yield ≈ 5,263 PPM against the body
but ≈ 1,053 PPM against the container — appearing to fail the threshold while extraction
is actually good. Thresholds are therefore miscalibrated against the actual denominator.

**Correct denominator:** stripped iXBRL body text byte count (HTML tags removed).

---

### 5.9 Issue Priority Matrix (Current)

| # | Severity | Issue | File:Line | Fine-tune Impact | Status |
|---|----------|-------|-----------|-----------------|--------|
| — | — | **Fix 1A: BS4 flatten (>10 MB)** | `parser.py:412` | Eliminates DOTALL hangs | ✅ **LIVE** (b9fb777) |
| 1 | **Critical** | ToC contamination 56.6% | `extractor.py:459`, `cleaning.py:168` | Boilerplate in training data | ❌ DEFERRED open |
| 2 | **Critical** | 0 segments = PASS | `qa_validation.py:787` | Broken filings enter training | ❌ Open |
| 3 | **High** | Tables in training text | `extractor.py:459` | Garbled number sequences | ❌ Open |
| 4 | **High** | Regex sentence splitter | `segmenter.py:307,349` | Bad segment boundaries | ❌ Open |
| 5 | **High** | No segment-level dedup | `qa_validation.py:890` | Train/test data leakage | ❌ Open |
| 6 | **High** | sec-parser 16s/file on 10 MB | `parser.py` → library | Pipeline throughput | ❌ Not addressed |
| 7 | Medium | Line-number regex | `cleaning.py:160` | Silently deleted list items | ❌ Open |
| 8 | Medium | Weak risk keywords | `qa_validation.py:619` | Trivially-passing check | ❌ Open |
| 9 | Medium | Yield PPM wrong denominator | `qa_validation.py:873` | Miscalibrated metric | ❌ Open |
| 10 | Low | Batch validator race condition | `check_preprocessing_batch.py:110` | Concurrency corruption | ❌ Open |
| 11 | Low | Dead code form type | `parser.py:260` | None | ❌ Open (trivial) |
| — | ~~Critical~~ | Edgar10QParser for 10-K | `parser.py:83` | None — 100% recall | ✅ Mitigated (intentional library limitation) |
| — | ~~High~~ | Section boundary bleeds | `extractor.py:500` | None — 0 overshoot in 309 files | ✅ Extractor working correctly |

---

## 6. Data Quality Standards (Current Config)

### 4-Pillar Validation Framework (`configs/qa_validation/health_check.yaml`)

| Pillar | Metric | Target | Operator | Blocking |
|--------|--------|--------|----------|---------|
| **Identity** | CIK present rate | 100% | >= | Yes |
| **Identity** | Company name rate | 100% | >= | Yes |
| **Identity** | SIC code rate | 95% (warn 90%) | >= | No |
| **Cleanliness** | HTML artifact rate | 0% | == | Yes |
| **Cleanliness** | Page number rate | <1% | <= | No |
| **Substance** | Empty segment rate | 0% | == | Yes |
| **Substance** | Short segment rate | <5% (warn 10%) | <= | No |
| **Substance** | Min file size | 100 KB | >= | Yes |
| **Substance** | Max file size (standard) | 50 MB | <= | No |
| **Substance** | Max file size (financial SIC 6000-6799) | 150 MB | <= | No |
| **Substance** | Extraction yield | ≥1000 PPM | >= | No |
| **Domain** | Duplicate rate | 0% | == | Yes |
| **Domain** | Risk keywords present | Boolean | == | No |

### Known Gaps
1. No zero-segment hard block — `total_segments == 0` returns empty results (PASS)
2. No segment-level dedup — only whole-filing hash comparison
3. Yield PPM miscalibrated — denominator is full SGML container, not iXBRL body stripped text
4. Risk keywords too generic — modal verbs pass for any English text
5. No structural check for ToC text presence in segments

---

## 7. Feature Engineering Status

### Implemented and Ready
| Feature | Algorithm | Config | Status |
|---------|-----------|--------|--------|
| Sentiment (8 categories) | Loughran-McDonald dict | `configs/features/sentiment.yaml` | ✅ Complete |
| Readability (6 indices) | FK, GF, SMOG, ARI, CLI, FRE | `configs/features/readability.yaml` | ✅ Complete |
| Custom obfuscation score | Weighted composite | same | ✅ Complete |
| Topic modeling | LDA (Gensim) | `configs/features/topic_modeling.yaml` | ✅ Complete |
| Combined pipeline | Orchestrator | `run_feature_pipeline.py` | ✅ Complete |

### Readability Diagnostic for Sentence Splitter Bug
Gunning Fog < 10 on 10-K segments is a red flag indicator that the regex sentence splitter
is counting financial abbreviations as sentence-ending periods (`segmenter.py:307`).
Past research documented this at `2025-12-03_21-45_sentiment_readability_validation_plan.md:338-339`.

---

## 8. Active Plans (Consolidated)

### Plan A: MLOps Infrastructure (19.5h total, Dec 2025 roadmap)
| Phase | Work | Est. | Status |
|-------|------|------|--------|
| 1 | StateManifest + atomic writes | 6.5h | 🚧 Active |
| 2 | Inline gatekeeper + quarantine | 6.5h | 🚧 Active |
| 3 | Auto-documentation (markdown reports) | 4.5h | 🚧 Active |
| 4 | Code consolidation | 2h | 📋 Pending |

### Plan B: Training Data Quality Fixes (Feb 2026 fix plan)
| Priority | Fix | Files | Status | Unblocks |
|----------|-----|-------|--------|---------|
| ✅ | Fix 1A: BS4 flatten for files >10 MB | `parser.py:412` | **LIVE** | Eliminates DOTALL hangs |
| 1 | Fix 4A: Zero segments = hard FAIL | `qa_validation.py:787` | Open | Broken filings rejected |
| 2 | Fix 2A: ToC node filter in extractor | `extractor.py:459` | Open | 56.6% files cleaned |
| 3 | Fix 2B: Exclude table text from segments | `extractor.py:459` | Open | Clean training samples |
| 4 | Fix 3A: spaCy sentencizer | `segmenter.py:307,349` | Open | Correct boundaries |
| 5 | Fix 4B: Segment-level dedup check | `qa_validation.py:890` | Open | Prevent data leakage |
| 6 | Fix 4C/4D: Keyword set + yield denominator | `qa_validation.py:619,873` | Open | Calibrated validation |
| 7 | Fix 5A: Narrow page-number regex | `cleaning.py:160` | Open | Preserve list items |
| 8 | Fix 1B/1C/4E: Comments + race condition | various | Open | Housekeeping |

### Plan C: Hybrid Pre-Seek Parser Architecture (NEW, from §4.5)
| Step | Work | Impact |
|------|------|--------|
| 1 | SGML document boundary extraction (Document 1 only) | Pass 5.2 MB to BS4 instead of 28.5 MB |
| 2 | BS4 anchor-based Item 1A pre-seek | ~50–200 KB fragment instead of full body |
| 3 | sec-parser on Item 1A fragment only | 18s → ~1–2s per file |
| 4 | Filter `TableOfContentsElement` in extractor | Removes HTML-table ToC |
| 5 | Fallback to full-parse for anchor-less filings | Maintains 100% coverage |

### Plan D: Metadata Enrichment (NEW, from §3.5)
| Field | Source | Effort |
|-------|--------|--------|
| `accession_number` | SGML header | Trivial — already parsed in SGML pass |
| `fiscal_year_end` | SGML header | Trivial — already in SGML |
| `sec_file_number` | SGML header | Trivial |
| `ein` | DEI `<ix:hidden>` | Switch source; requires DEI parse already done for ticker |
| `state_of_incorporation` | SGML header | Trivial |
| `exchange` | DEI `<ix:hidden>` | Same pass as ticker extraction |
| `shares_outstanding` | DEI `<ix:hidden>` | Same pass |
| `amendment_flag` | DEI `<ix:hidden>` | Same pass |

SGML trivial fields (accession_number, fiscal_year_end, sec_file_number, state_of_incorporation)
are zero-cost additions to the existing SGML header parse in `extractor.py`. DEI fields
require one additional DEI parse (same HTML parse as ticker extraction).

---

## 9. Synthesis: What's Blocking Fine-tuning

### Immediate Blockers (Training Data Currently Unfit)

```
Issue                           Impact on FinBERT training
─────────────────────────────   ──────────────────────────────────────────────────
ToC lines in 56.6% of files  →  Model learns "Item 1A..... 25" patterns
Tables in all files          →  Model sees "3.2% 4.1% 5.0% (12.3) (14.6)"
Broken sentence boundaries   →  Segments start mid-sentence, end mid-thought
Zero-segment filings → PASS  →  Empty JSON records in training corpus
No segment dedup             →  AAPL 2021 ≈ AAPL 2022 contaminate train/test splits
```

### Performance Reality at Corpus Scale

With the current sec-parser backend and 959 files:
- **Optimistic** (mean 5.2 MB body, ~12s/file): 959 × 12s = **3.2 hours** for parsing alone
- **Realistic** (mix of 5–25 MB bodies, 18–60s/file): **5–16 hours** for parsing alone
- **With Plan C** (hybrid pre-seek, ~2s/file): 959 × 2s = **32 minutes**

Files above the mean+1σ threshold (48.2 MB total container, ~120+ files) are the tail that
drives most batch time. These are disproportionately utilities, banks, and insurers.

### Dependency Chain (Revised)

```
[Plan B: Training Data Quality Fixes]   ← must come first (data fitness gate)
              ↓
[Plan C: Hybrid Pre-Seek]               ← performance prerequisite for 959-file scale
              ↓
[Plan D: Metadata Enrichment]           ← enriches training records; low effort
              ↓
[Plan A: MLOps Infrastructure]          ← meaningful once data is clean and fast
              ↓
[Drift Detection]                       ← deferred (monitoring garbage = garbage)
              ↓
[FinBERT Fine-tuning]                  ← the actual goal
```

### Three Forward Paths

**Path A — Fix training data quality first (recommended, ~1–2 days)**
Implement Plan B remaining fixes in priority order (Fix 4A → 2A → 2B → 3A → 4B).
Directly unblocks fine-tuning. Does not require architectural changes. Incremental.

**Path B — Hybrid parser architecture (~2–3 days)**
SGML document extraction + BS4 pre-seek + sec-parser on fragment. Solves the 18s/file
performance problem at the root. Also simplifies ToC filtering (working on 50 KB fragment
rather than 5 MB body). Best taken after Plan B data quality fixes are in.

**Path C — Metadata enrichment (~0.5 days)**
Add SGML-trivial fields (accession_number, fiscal_year_end, sec_file_number) in a single
commit. Add DEI fields (exchange, shares_outstanding, amendment_flag) in a second commit.
Independent of Plans A and B; can be done in parallel.

---

## 10. Verification Commands

```bash
# Run all tests
python -m pytest tests/ -x -q

# Validate a processed run directory
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/<run_dir> -v

# Batch validate with CI-style fail-on-warn
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/processed/<run_dir> --fail-on-warn

# Time parsing on a single file (check Fix 1A path)
python -c "
from src.preprocessing.parser import SECFilingParser
import time
p = SECFilingParser()
start = time.time()
f = p.parse_filing('data/raw/AAPL_10K_2021.html', form_type='10-K', quiet=True)
print(f'Time: {time.time()-start:.2f}s  Elements: {len(f)}')
"

# Check section extraction on a specific file
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/<run_dir>
```

---

## 11. Key File Locations

| Purpose | Path |
|---------|------|
| Main pipeline | `src/preprocessing/pipeline.py` |
| Parser (Fix 1A active) | `src/preprocessing/parser.py` |
| Extractor (ToC + table fix needed) | `src/preprocessing/extractor.py` |
| Cleaner | `src/preprocessing/cleaning.py` |
| Segmenter (sentence split fix needed) | `src/preprocessing/segmenter.py` |
| Validation (zero-seg + dedup fix needed) | `src/config/qa_validation.py` |
| QA thresholds | `configs/qa_validation/health_check.yaml` |
| Sentiment config | `configs/features/sentiment.yaml` |
| Readability config | `configs/features/readability.yaml` |
| Topic modeling config | `configs/features/topic_modeling.yaml` |
| Main app config | `configs/config.yaml` |
| MLOps roadmap | `thoughts/shared/plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md` |
| Pipeline optimisation plan | `thoughts/shared/plans/2026-02-16_16-52-14_preprocessing_pipeline_optimization.md` |
| Parser fix plan | `thoughts/shared/plans/2026-02-18_10-00-00_parser_finetune_fixes.md` |
| Parser critique | `thoughts/shared/research/2026-02-18_18-00-00_parser_finetune_critique.md` |
| AAPL parser metrics audit | `thoughts/shared/research/2026-02-22_10-00-00_aapl_parser_metrics_audit.md` |
| Corpus HTML structure findings | `reports/sec_html_structure/2026-02-22_17-57-43_sec_html_structure_findings.md` |
| Boundary investigation | `thoughts/shared/research/2025-12-30_17-43_section_end_precision_investigation.md` |
| Extractor QA verification | `thoughts/shared/research/2025-12-30_14-39-03_extractor_qa_findings_verification.md` |
| Parser performance analysis | `thoughts/shared/research/2025-12-30_18-20-45_parser_performance_analysis.md` |
