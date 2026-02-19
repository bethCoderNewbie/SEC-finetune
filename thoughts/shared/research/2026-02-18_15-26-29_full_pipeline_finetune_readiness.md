---
title: "Full Pipeline Research: Fine-tuning Readiness, Parser Critique, sec-parser Evaluation, and Project Synthesis"
date: "2026-02-18"
timestamp: "2026-02-18_15-26-29"
commit: "469d6cd868222bd8472dd0f36e84e1ca06bf634c"
branch: "main"
researcher: "beth"
status: "complete"
tags: [parser, sec-parser, finetune, data-quality, toc-contamination, segmenter, validation, roadmap, architecture]
related_plans:
  - thoughts/shared/plans/2026-02-18_10-00-00_parser_finetune_fixes.md
  - thoughts/shared/plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md
  - thoughts/shared/plans/2026-02-16_16-52-14_preprocessing_pipeline_optimization.md
related_research:
  - thoughts/shared/research/2026-02-18_10-00-00_parser_finetune_critique.md
  - thoughts/shared/research/2025-12-30_17-43_section_end_precision_investigation.md
  - thoughts/shared/research/2025-12-30_14-39-03_extractor_qa_findings_verification.md
  - thoughts/shared/research/2025-12-30_18-20-45_parser_performance_analysis.md
  - thoughts/shared/research/2025-12-15_19-22_parser_test_real_data_analysis.md
---

# Full Pipeline Research: Fine-tuning Readiness Assessment

## 1. Project Objectives (Ground Truth)

### Primary Goal
Build a **training data factory** for fine-tuning FinBERT (and similar financial LLMs) on
SEC 10-K filings. The two downstream ML tasks are:

- **Risk classification** — categorise individual risk segments (e.g., market, regulatory,
  cyber, operational, liquidity)
- **Topic modeling** — surface latent risk themes across a corpus of filings

### Data Pipeline (Parse → Train)
```
HTML 10-K filings (data/raw/)
       ↓
[parser.py]       Parse HTML → semantic elements + metadata
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

### ML Hierarchy of Needs (Project's Own Framework)
```
Drift Detection          ← DEFERRED (monitoring garbage is still garbage)
────────────────────────────────────────────────────────────────────────
Audit Trails             ← Priority 3 — in progress
Inline Validation        ← Priority 2 — in progress
State Management         ← Priority 1 — in progress
────────────────────────────────────────────────────────────────────────
Data Quality             ← PRE-CONDITION (must be correct first)
```

**Key finding:** The existing roadmaps prioritise MLOps infrastructure (state manifest,
quarantine, drift detection). But the **training data quality fixes** are pre-conditions
for any model training to be meaningful. They have been open since December 2025.

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

### In Progress 🚧
| Work | Owner doc | Status |
|------|-----------|--------|
| State manifest + atomic writes | `plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md` | Active |
| Inline gatekeeper + quarantine | same | Active |
| Auto-documentation (markdown reports) | same | Active |
| Parser / extractor / segmenter fixes | `plans/2026-02-18_10-00-00_parser_finetune_fixes.md` | Planned |

### Open Blockers for Fine-tuning ❌
| Blocker | Scale | Months Open |
|---------|-------|-------------|
| ToC contamination in extracted text | 175 / 309 files (56.6%) | 2+ months |
| Zero-segment filings pass validation | Unknown % silently broken | 2+ months |
| Tables included in training text | All files with tables | 2+ months |
| Regex sentence splitter on abbreviations | All files | 2+ months |

---

## 3. Parser Critique: Confirmed Findings

All findings cross-referenced against the past research corpus
(`thoughts/shared/research/2025-12-*` and `2026-01-*`).

### 3.1 Confirmed Open Issues

#### Critical: Zero Segments Passes Validation
**File:** `src/config/qa_validation.py:787-788`

```python
if total_segments == 0:
    return results  # returns [] — no ValidationResult fires
```

`_check_cleanliness` and `_check_substance` both guard with `if total_segments == 0:
return results`. If Item 1A extraction fails entirely the segmenter produces 0 segments,
both checks return empty lists, and `determine_overall_status([])` returns `PASS`.

**Impact:** Broken filings silently enter training data as empty records.

---

#### Critical: ToC Contamination (56.6% of Files)
**Files:** `src/preprocessing/extractor.py`, `src/preprocessing/cleaning.py`
**Evidence:** `research/2025-12-29_16-33-56_visualization_controls_architecture.md` (175/309 files),
`research/2025-12-30_14-39-03_extractor_qa_findings_verification.md` (status: DEFERRED)

Two distinct ToC formats cause contamination:

1. **HTML-table format ToC** — sec-parser correctly classifies these as `TableOfContentsElement`
   (a `TableElement` subclass via `TableOfContentsClassifier`). However the extractor's
   `_extract_section_content` does not filter `TableOfContentsElement` nodes from
   `full_text`. A single isinstance check fixes this.

2. **Text-line format ToC** — Dot-leader lines like `"Item 1A. Risk Factors..... 25"`
   arrive as `TextElement` nodes. `TableOfContentsClassifier` only processes `{TableElement}`,
   so these pass through unclassified. `cleaning.py:168-200` has 7 ToC patterns but they
   are applied post-extraction on aggregated text, not at the node level.

**Impact:** 93 files (34.3%) fail *only* the ToC check — every other quality metric passes.
ToC lines train the model on boilerplate structure rather than risk language.

---

#### High: Tables Included in Training Text
**File:** `src/preprocessing/extractor.py:459-468`

`TableElement` nodes are collected into `content_nodes` and included in `full_text`.
Risk factor tables typically contain numerical sensitivity analyses:
```
"3.2% 4.1% 5.0% (12.3) (14.6) (16.2)"
```
FinBERT is a text classifier — injecting serialised table rows degrades classification
accuracy and distorts topic model vocabulary.

---

#### High: Regex Sentence Splitter Breaks on Financial Abbreviations
**File:** `src/preprocessing/segmenter.py:307, 349`

```python
sentences = re.split(r'([.!?]\s+)', text)         # line 307 — _split_into_chunks
sentences = re.split(r'(?<=[.!?])\s+', text)       # line 349 — _segment_by_semantic_breaks
```

Financial filings are dense with period-terminated abbreviations:
`U.S.`, `Inc.`, `Corp.`, `No.`, `vs.`, `Sec.`, `approx.`, `i.e.`, `e.g.`, `Jan.`, `Feb.`

Each creates a false sentence boundary → incorrect cosine similarity scores between
adjacent "sentences" → incorrect semantic break points → training samples that start
mid-sentence or cut off mid-argument.

**Evidence from past research:** `2025-12-03_21-45_sentiment_readability_validation_plan.md:338-339`
explicitly documents this as a red flag:
> `< 10 [Gunning Fog]: Sentence splitter counting abbreviations as periods`

---

#### High: `_flatten_html_nesting` DOTALL Regex on Large Files
**File:** `src/preprocessing/parser.py:412-466`
**Evidence:** `research/2025-12-30_18-20-45_parser_performance_analysis.md` (confirmed hangs)

The function performs DOTALL regex on raw HTML before sec-parser processes it.
For files > 30 MB the pattern `<div[^>]*>\s*(<div[^>]*>.*?</div>)\s*</div>` with
`re.DOTALL` causes catastrophic backtracking. Documented actual hangs on 68 MB files.

**Clarification (corrected from initial critique):** This does NOT destroy section markup
— Key Item Recall is 100% even with the function enabled. The risk is purely
performance/stability, not correctness. Disabling it by default would regress large-file
parsing (recursion limits). The correct fix is to use BeautifulSoup for files > 10 MB.

---

#### Medium: Line-Number Removal Deletes Enumerated List Items
**File:** `src/preprocessing/cleaning.py:160`

```python
text = re.sub(r'^[\s\-]*\d+[\s\-]*$', '', text, flags=re.MULTILINE)
```

Removes any line consisting solely of a digit. Single-digit enumerated list items
in risk factors (e.g., a line containing just `"3"` between numbered paragraphs)
are silently deleted.

---

#### Medium: Risk Keyword Validation Too Weak
**File:** `src/config/qa_validation.py:619-622`

```python
RISK_KEYWORDS = {"risk", "adverse", "material", "uncertain",
                 "may", "could", "might", "potential"}
```

Modal verbs (`may`, `could`, `might`) appear in virtually any English text. The `>= 10`
threshold at line 918 is trivially satisfied by non-risk content. For fine-tuning
validation, domain-specific anchors are needed: `impair`, `litigation`, `regulatory`,
`infringement`, `cybersecurity`, `volatility`, `liquidity`, `covenant`, `indemnif`.

---

#### Medium: `extraction_yield_ppm` Wrong Denominator
**File:** `src/config/qa_validation.py:873`

```python
yield_ppm = (extracted_chars / file_size_bytes) * 1_000_000
```

`file_size_bytes` is raw HTML file size. A 1 MB HTML file has ~600-800 KB of markup.
Extracted text of 150 KB produces a yield of ~150,000 PPM — appearing low when
extraction is actually good. The denominator should be stripped-text byte count.

---

#### High: No Segment-Level Deduplication
**File:** `src/config/qa_validation.py:890-908`

Hash deduplication operates on whole-filing content, not individual segments. Companies
carry forward risk factor language year-over-year. Near-identical segments from the same
company (AAPL 2021 vs AAPL 2022) appear in the corpus and will contaminate
train/test splits. No segment-level dedup check exists.

---

### 3.2 Retracted / Corrected Findings

#### ~~Critical: Edgar10QParser Wrong for 10-K~~ — Known Limitation, Mitigated
**Evidence:** `research/2025-12-30_14-39-03_extractor_qa_findings_verification.md`

`sec-parser` v0.54.0 provides only `Edgar10QParser`. This is an **intentional library
limitation** with no fix available. The 3-strategy fallback in `_find_section_node`
(`extractor.py:290-354`) handles identifier mismatches. Key Item Recall: **309/309 (100%)**.
No code change needed. Documentation comment only.

#### ~~High: Section Boundary Bleeds~~ — RETRACTED (extractor working correctly)
**Evidence:** `research/2025-12-30_17-43_section_end_precision_investigation.md`

Initial critique claimed `re.match` without `.strip()` causes boundary bleed. Actual
code at `extractor.py:497`:
```python
text = node.text.strip().lower()   # .strip() IS called before re.match
if re.match(r'item\s+\d+[a-z]?\s*\.', text):
```
Tested on 309 real 10-K filings: **zero actual boundary overshoot**. The 52.8% apparent
failure rate in QA reports was 100% validator false positives (case-sensitive pattern
matched section header, not overshoot). Extractor needs no change; the validator
`check_extractor_batch.py:235-256` needs its pattern updated.

---

### 3.3 Issue Priority Matrix (Revised)

| # | Severity | Issue | File:Line | Fine-tune Impact | Status |
|---|----------|-------|-----------|-----------------|--------|
| 1 | **Critical** | ToC contamination 56.6% | `extractor.py:459`, `cleaning.py:168` | Boilerplate in training data | ❌ DEFERRED open |
| 2 | **Critical** | 0 segments = PASS | `qa_validation.py:787` | Broken filings enter training | ❌ Open |
| 3 | **High** | Tables in training text | `extractor.py:459` | Garbled number sequences | ❌ Open |
| 4 | **High** | Regex sentence splitter | `segmenter.py:307,349` | Bad segment boundaries | ❌ Open |
| 5 | **High** | No segment-level dedup | `qa_validation.py:890` | Train/test data leakage | ❌ Open |
| 6 | **High** | flatten_html hangs >30MB | `parser.py:412` | Pipeline timeouts | ❌ Open |
| 7 | Medium | Line-number regex | `cleaning.py:160` | Silently deleted list items | ❌ Open |
| 8 | Medium | Weak risk keywords | `qa_validation.py:619` | Trivially-passing check | ❌ Open |
| 9 | Medium | Yield PPM wrong denominator | `qa_validation.py:873` | Miscalibrated metric | ❌ Open |
| 10 | Low | Batch validator race condition | `check_preprocessing_batch.py:110` | Concurrency corruption | ❌ Open |
| 11 | Low | Dead code form type | `parser.py:260` | None | ❌ Open (trivial) |
| — | ~~Critical~~ | Edgar10QParser for 10-K | `parser.py:83` | None — 100% recall | ✅ Mitigated |
| — | ~~High~~ | Section boundary bleeds | `extractor.py:500` | None — 0 overshoot in 309 files | ✅ Working |

---

## 4. sec-parser Evaluation: Use, Replace, or Hybrid

### 4.1 sec-parser Internals (v0.54.0)

**Processing pipeline** (from source inspection):
```
IndividualSemanticElementExtractor
  → ImageClassifier
  → EmptyElementClassifier
  → TableClassifier               ← classifies <table> elements
  → TableOfContentsClassifier     ← classifies HTML-table ToC ONLY
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

**Public API surface:** One parser (`Edgar10QParser`), one option
(`ParsingOptions.html_integrity_checks: bool = False`). No customisation of pipeline
steps without subclassing.

**`TopSectionManagerFor10Q` section recognition:**
```python
item_pattern = re.compile(r"item\s+(\d+a?)[.\s]*", re.IGNORECASE)
```
Only promotes items with numeric + optional-`a` suffix to `TopSectionTitle`.
Items 1B, 1C, 7, 7A, 8, 9 etc. become `TitleElement`, not `TopSectionTitle`.
This is why the 3-strategy fallback in the extractor is necessary.

### 4.2 Element Distribution Reality (COST 10K 2023, 6.35 MB)

| Element Type | Count | Useful for training? |
|---|---|---|
| `TableElement` | 667 | No — strip |
| `TextElement` | 347 | **Yes** |
| `PageHeaderElement` | 340 | No |
| `EmptyElement` | 339 | No |
| `TitleElement` | 198 | Yes (structure) |
| `PageNumberElement` | 134 | No |
| `IntroductorySectionElement` | 68 | No |
| `SupplementaryText` | 17 | Maybe |
| `TopSectionTitle` | 8 | Yes (boundaries) |
| **Total** | **2,118** | **~26% useful** |

sec-parser processes the entire 6 MB document to classify all 2,118 elements, even
though only the ~550 `TextElement` + `TitleElement` nodes inside Item 1A are needed.

### 4.3 Performance Reality

| File | Size | Parse time | Threshold |
|------|------|-----------|-----------|
| COST_10K_2023.html | 6.35 MB | **34.52s** | 5.0s (test) |
| INTC_10K_2021.html | 60.31 MB | ~300s (est.) | — |
| JPM_10K_2021.html | 67.95 MB | timeout | — |

**887 files × 34s minimum = 8.4 hours** for parsing alone.

### 4.4 Pros and Cons

**Pros of keeping sec-parser:**
- `TextElementMerger` reassembles `<span>`-fragmented text — the hardest part to rewrite;
  EDGAR HTML splits single sentences across 5–10 styled `<span>` tags
- Bold/highlighted text → `TitleElement` detection handles diverse formatting
- `PageHeaderElement` / `PageNumberElement` / `TableElement` classification
- `TableOfContentsClassifier` catches HTML-table-formatted ToC correctly
- 3+ years of EDGAR-specific tuning; MIT license; BS4 already its own dependency
- 100% Key Item Recall via 3-strategy fallback (verified on 309 files)

**Cons of sec-parser:**
- **Processes entire document** to find one section — 34s per 6 MB file, no seek
- **Text-line ToC not detected** — `TableOfContentsClassifier` only handles `{TableElement}`
- `TopSectionManagerFor10Q` only recognises `item\s+\d+a?` — 10K section hierarchy broken
- `TableOfContentsElement` nodes not filtered by extractor (1-line fix, but unimplemented)
- No streaming/chunking — peak RAM ~500 MB per large file with intermediate copies
- `ParsingOptions` has exactly one knob (`html_integrity_checks`); cannot customise pipeline
- Monkey patch required for `approx_table_metrics` bug (`parser.py:26-46`)
- Single parser for all form types; no 10K-specific parser forthcoming

### 4.5 Actual EDGAR HTML Structure (from COST_10K_2023.html)

ToC entries use hyperlinks:
```html
<!-- Inside a <table> — the ToC -->
<a href="#i4bf6d0bde838478985b72eb4052bc976_19">Item 1A-Risk Factors</a>

<!-- The actual section, elsewhere in document -->
<a id="i4bf6d0bde838478985b72eb4052bc976_19"></a>
```

EDGAR filings use named anchors / `id` attributes to link ToC entries to section
bodies. A custom or hybrid extractor can exploit this directly.

### 4.6 Recommendation: Hybrid (Section Pre-Seek + sec-parser)

Do not replace sec-parser wholesale. The `TextElementMerger` and element classification
are valuable and hard to reimplement correctly for EDGAR's irregular HTML.

**Proposed architecture:**
```
Full HTML (6–68 MB)
       ↓
[NEW] Anchor-based pre-seek (BS4, < 0.5s)
    – Find <a id="..."> for Item 1A start  (via href target from ToC entry)
    – Find <a id="..."> for Item 1B / Item 2 end
    – Slice raw HTML to ~50–200 KB Item 1A fragment
       ↓
[EXISTING] sec-parser (now processes 50 KB, not 6 MB)
    – ~1–2s instead of 34s
    – TextElementMerger handles <span> fragmentation
    – TitleElement detection finds subsection headers
       ↓
[EXISTING + FIXES] Extractor filters:
    + Filter TableOfContentsElement (1-line fix)
    + Filter text-line ToC via TOC_PATTERNS_COMPILED (Fix 2A)
    + Filter TableElement from full_text (Fix 2B)
```

**Estimated performance:** < 2s per file vs 34s current (15–20x improvement).
**Complexity:** ~100 lines of new code in extractor.py. Fully backward compatible.

**Fallback:** For filings without named anchors (older SGML-derived HTML), fall back to
current full-document parse path. This maintains 100% coverage.

---

## 5. Data Quality Standards (Current Config)

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

### Known Gaps in Current Framework

1. **No zero-segment hard block** — `total_segments == 0` returns empty results (PASS)
2. **No segment-level dedup** — only whole-filing hash comparison
3. **Yield PPM miscalibrated** — denominator is raw HTML, not stripped text
4. **Risk keywords too generic** — modal verbs pass for any text
5. **ToC contamination** — no structural check for ToC text in segments

---

## 6. Feature Engineering Status

### Implemented and Ready

| Feature | Algorithm | Config | Status |
|---------|-----------|--------|--------|
| Sentiment (8 categories) | Loughran-McDonald dict | `configs/features/sentiment.yaml` | ✅ Complete |
| Readability (6 indices) | FK, GF, SMOG, ARI, CLI, FRE | `configs/features/readability.yaml` | ✅ Complete |
| Custom obfuscation score | Weighted composite | same | ✅ Complete |
| Topic modeling | LDA (Gensim) | `configs/features/topic_modeling.yaml` | ✅ Complete |
| Combined pipeline | Orchestrator | `run_feature_pipeline.py` | ✅ Complete |

### Sentiment Categories (LM Dictionary)
Active: Negative, Positive, Uncertainty, Litigious, Constraining
Normalisation: TF-IDF (recommended for classification)
Output: raw counts, ratios, TF-IDF weighted scores, proportions per segment

### Readability Expected Ranges for 10-K
- Flesch-Kincaid Grade: 8.0–20.0
- Gunning Fog: 10.0–22.0 (red flag if < 10 → sentence splitter counting abbreviations)
- Flesch Reading Ease: 10.0–70.0
Financial adjustments enabled: common financial terms excluded from "complex word" count.

---

## 7. Active Plans (Consolidated)

### Plan A: MLOps Infrastructure (19.5h total, Dec 2025 roadmap)

| Phase | Work | Est. | Status |
|-------|------|------|--------|
| 1 | StateManifest + atomic writes (SHA-256 hash tracking, config snapshot) | 6.5h | 🚧 Active |
| 2 | Inline gatekeeper + quarantine (validate during process, not after) | 6.5h | 🚧 Active |
| 3 | Auto-documentation (markdown reports with config snapshots) | 4.5h | 🚧 Active |
| 4 | Code consolidation (worker pool + DLQ dedup, 22% reduction) | 2h | 📋 Pending |

### Plan B: Training Data Quality Fixes (Feb 2026 fix plan)

| Priority | Fix | Files | Unblocks |
|----------|-----|-------|---------|
| 1 | Fix 4A: Zero segments = hard FAIL | `qa_validation.py:787` | Broken filings rejected |
| 2 | Fix 2A: ToC node filter in extractor | `extractor.py:459` | 56.6% files cleaned |
| 3 | Fix 2B: Exclude table text from segments | `extractor.py:459` | Clean training samples |
| 4 | Fix 3A: spaCy sentencizer (financial abbrev) | `segmenter.py:307,349` | Correct boundaries |
| 5 | Fix 1A: BS4 flatten for files >10 MB | `parser.py:412` | Eliminate timeouts |
| 6 | Fix 4B: Segment-level dedup check | `qa_validation.py:890` | Prevent data leakage |
| 7 | Fix 4C/4D: Keyword set + yield denominator | `qa_validation.py:619,873` | Calibrated validation |
| 8 | Fix 5A: Narrow page-number regex | `cleaning.py:160` | Preserve list items |
| 9 | Fix 1B/1C/4E: Comments + race condition | various | Housekeeping |

### Plan C: Hybrid Pre-Seek Parser Architecture (new, from sec-parser evaluation)

| Step | Work | Impact |
|------|------|--------|
| 1 | BS4 anchor-based section pre-seek | 34s → ~2s per file |
| 2 | Pass Item 1A fragment to sec-parser | 15–20x throughput gain |
| 3 | Filter `TableOfContentsElement` in extractor | Removes HTML-table ToC |
| 4 | Fallback to full-parse for anchor-less filings | Maintains 100% coverage |

---

## 8. Synthesis: What's Blocking Fine-tuning

### Immediate blockers (training data is currently unfit)

```
Issue                           Impact on FinBERT training
─────────────────────────────   ──────────────────────────────────────────
ToC lines in 56.6% of files  →  Model learns "Item 1A..... 25" patterns
Tables in all files          →  Model sees "3.2% 4.1% 5.0% (12.3) (14.6)"
Broken sentence boundaries   →  Segments start mid-sentence, end mid-thought
Zero-segment filings → PASS  →  Empty JSON records in training corpus
No segment dedup             →  AAPL 2021 ≈ AAPL 2022 contaminate train/test
```

### Dependency chain

```
[Plan B: Training Data Quality Fixes]   ← must come first
              ↓
[Plan C: Hybrid Pre-Seek]               ← performance prerequisite for scale
              ↓
[Plan A: MLOps Infrastructure]          ← meaningful once data is clean
              ↓
[Drift Detection]                       ← deferred (monitoring garbage = garbage)
              ↓
[FinBERT Fine-tuning]                  ← the actual goal
```

### Three forward paths

**Path A — Fix training data quality (recommended, ~1–2 days)**
Implement Plan B in priority order. Directly unblocks fine-tuning. Does not require
architectural changes. Can be done incrementally.

**Path B — Hybrid parser architecture (~3 days)**
BS4 pre-seek + sec-parser hybrid. Solves the 34s/file performance problem at the root.
Makes ToC filtering simpler (working on 50KB fragment). Higher upfront cost; cleaner
long-term. Best taken after Plan B fixes are in place.

**Path C — MLOps first (current active work)**
Continue the state manifest + quarantine work. Safe if batch stability is needed before
running large-scale data collection. Does not improve training data quality.

---

## 9. Verification Commands

```bash
# Run all tests
python -m pytest tests/ -x -q

# Validate a processed run directory
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/<run_dir> -v

# Batch validate with CI-style fail-on-warn
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/processed/<run_dir> --fail-on-warn

# Check extractor quality on existing extracted files
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/<run_dir>

# Parse single file and inspect output
python -c "
from src.preprocessing.parser import SECFilingParser
import time, json
p = SECFilingParser()
start = time.time()
f = p.parse_filing('data/raw/COST_10K_2023.html', form_type='10-K', quiet=True)
print(f'Time: {time.time()-start:.2f}s  Elements: {len(f)}')
print(f'Element types: {f.metadata[\"element_types\"]}')
"
```

---

## 10. Key File Locations

| Purpose | Path |
|---------|------|
| Main pipeline | `src/preprocessing/pipeline.py` |
| Parser | `src/preprocessing/parser.py` |
| Extractor (ToC fix needed) | `src/preprocessing/extractor.py` |
| Cleaner | `src/preprocessing/cleaning.py` |
| Segmenter (sentence split fix) | `src/preprocessing/segmenter.py` |
| Validation (zero-seg fix needed) | `src/config/qa_validation.py` |
| QA thresholds | `configs/qa_validation/health_check.yaml` |
| Sentiment config | `configs/features/sentiment.yaml` |
| Readability config | `configs/features/readability.yaml` |
| Topic modeling config | `configs/features/topic_modeling.yaml` |
| Main app config | `configs/config.yaml` |
| MLOps roadmap | `thoughts/shared/plans/2025-12-28_13-33-27_consolidated_mlops_roadmap.md` |
| Pipeline optimisation | `thoughts/shared/plans/2026-02-16_16-52-14_preprocessing_pipeline_optimization.md` |
| Parser fix plan | `thoughts/shared/plans/2026-02-18_10-00-00_parser_finetune_fixes.md` |
| Parser critique | `thoughts/shared/research/2026-02-18_10-00-00_parser_finetune_critique.md` |
| Boundary investigation | `thoughts/shared/research/2025-12-30_17-43_section_end_precision_investigation.md` |
| Extractor QA verification | `thoughts/shared/research/2025-12-30_14-39-03_extractor_qa_findings_verification.md` |
| Parser performance analysis | `thoughts/shared/research/2025-12-30_18-20-45_parser_performance_analysis.md` |
| Real data parser test | `thoughts/shared/research/2025-12-15_19-22_parser_test_real_data_analysis.md` |
