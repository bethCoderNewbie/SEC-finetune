---
id: PRD-003
title: SEC 10-K Training Data Quality Remediation
status: DRAFT
author: beth88.career@gmail.com
created: 2026-02-18
last_updated: 2026-02-18
version: 0.3.0
supersedes: null
depends_on: PRD-002
git_sha: c142655
---

# PRD-003: SEC 10-K Training Data Quality Remediation

## 1. Context & Problem Statement

PRD-002 describes a complete operational pipeline: Parse → Extract → Clean → Segment →
Validate → Feature Engineering. The pipeline runs without crashing, produces structured
JSON output, and has a 660-test suite.

**The training data it produces is currently unfit for FinBERT fine-tuning.**

Five independent data quality defects, open for 2+ months, corrupt the training corpus
before a model ever sees it:

| Defect | Scale | File:Line |
|--------|-------|-----------|
| Table of Contents text in extracted Risk Factors | 175 / 309 files (56.6%) | `extractor.py:459`, `cleaning.py:168` |
| HTML tables serialised into training text | All files with tables | `extractor.py:459-468` |
| Regex sentence splitter misfires on financial abbreviations | All files | `segmenter.py:307,349` |
| Zero-segment filings pass QA validation (PASS on empty data) | Unknown count | `qa_validation.py:787` |
| No segment-level deduplication | All multi-year corpora | `qa_validation.py:890-908` |

Additionally, sec-parser's full-document parse processes 6–68 MB per filing at ~34 seconds
each, making a 887-filing corpus take **8.4 hours** for parsing alone — unsustainable for
iteration.

The MLOps hierarchy of needs demands data quality be correct **before** model training is
meaningful. These defects are pre-conditions, not nice-to-haves.

---

## 2. Goals & Non-Goals

### 2.1 Goals

| ID | Goal | Acceptance Criterion |
|:---|:-----|:---------------------|
| G-01 | Zero ToC lines in any segment's training text | `_check_toc_contamination` returns 0 violations on a 309-filing corpus |
| G-02 | Zero `TableElement` text in any segment | All segments contain only `TextElement` / `TitleElement` derived text |
| G-03 | Sentence boundaries do not split on financial abbreviations | Gunning Fog index ≥ 10.0 on all processed segments; zero `U.S.` / `Inc.` mid-sentence splits in spot-check of 20 files |
| G-04 | Zero-segment filings produce a hard FAIL in QA | `total_segments == 0` triggers a blocking `ValidationResult(status=FAIL)` |
| G-05 | Near-duplicate segments are flagged and excluded from training splits | Segment-level SHA-256 + MinHash dedup runs at batch validation time |
| G-06 | Parse time ≤ 3s per filing (median) via anchor-based pre-seek | Measured on COST_10K_2023.html (6.35 MB): ≤ 3s vs 34.52s baseline |
| G-07 | 100% Key Item Recall maintained after all changes | `check_extractor_batch.py` reports 309/309 on existing corpus |
| G-08 | Risk keyword validator anchored to domain-specific terms | `RISK_KEYWORDS` set includes ≥ 5 domain anchors; modal-verb-only text does not pass |
| G-09 | `extraction_yield_ppm` uses stripped-text denominator | Yield for AAPL_10K_2021 in acceptable range (1,000–500,000 PPM) after fix |

### 2.2 Non-Goals

- FinBERT fine-tuning itself — this PRD delivers a clean corpus, not a trained model
- Replacing sec-parser entirely — the hybrid architecture retains sec-parser's `TextElementMerger` and element classification
- Real-time or streaming processing
- Changing the output schema (`SegmentedRisks`) — only the content quality changes
- Fixing the batch validator race condition (`check_preprocessing_batch.py:110`) — low severity, separate ticket
- Dead code removal in `parser.py:260` — trivial, out of scope

---

## 3. Dataset Definition

### 3.1 Corpus

| Attribute | Value |
|:----------|:------|
| Filing type | SEC 10-K annual reports |
| Section targeted | Item 1A — Risk Factors |
| Current corpus size | 309 filings (verified) |
| Target corpus size | 887 filings |
| Source | `data/raw/*.html` (EDGAR HTML filings) |
| File size range | 100 KB – 150 MB (financial SIC 6000-6799) |
| Output unit | `SegmentedRisks` JSON, one file per filing |

### 3.2 Training Unit Schema (unchanged from PRD-002)

```json
{
  "cik": "0000320193",
  "company_name": "APPLE INC",
  "form_type": "10-K",
  "filing_date": "2021-10-29",
  "segments": [
    {
      "segment_id": "seg_0001",
      "text": "...",
      "word_count": 142,
      "segment_index": 0
    }
  ],
  "metadata": {
    "total_segments": 47,
    "extraction_method": "anchor_seek_v2",
    "pipeline_version": "0.3.0",
    "git_sha": "c142655"
  }
}
```

**New field:** `extraction_method` distinguishes anchor-seek path from full-parse fallback.

### 3.3 Quality Gates (Post-Remediation)

Every `SegmentedRisks` file must satisfy all blocking checks before entering training:

| Check | Rule | Blocking |
|:------|:-----|:---------|
| Non-empty | `total_segments > 0` | **Yes** |
| No HTML artifacts | `html_artifact_rate == 0.0` | **Yes** |
| No empty segments | `empty_segment_rate == 0.0` | **Yes** |
| Identity complete | CIK + company name present | **Yes** |
| No duplicate (filing) | SHA-256 of full text not in manifest | **Yes** |
| No ToC contamination | ToC pattern match rate == 0.0 per segment | **Yes** (new) |
| Domain vocabulary | ≥ 1 domain anchor keyword per segment | No (warn) |
| Segment dedup | MinHash similarity < 0.85 across segments | No (warn → quarantine) |

---

## 4. Technical Requirements

### 4.1 Fix 1 — Zero Segments = Hard FAIL
**File:** `src/config/qa_validation.py:787-788`

Remove the early-return guard in `_check_cleanliness` and `_check_substance`. Replace
with an explicit blocking `ValidationResult`:

```python
if total_segments == 0:
    return [ValidationResult(
        check_name="segment_count",
        status=ValidationStatus.FAIL,
        message="Zero segments produced — extraction failed",
        value=0,
        threshold=1,
        is_blocking=True,
    )]
```

Both methods must be updated. `determine_overall_status([])` returning `PASS` is a
latent bug — this fix eliminates the empty-list case.

### 4.2 Fix 2A — ToC Node Filtering in Extractor
**File:** `src/preprocessing/extractor.py:459-468`

At `_extract_section_content`, filter `TableOfContentsElement` nodes before assembling
`full_text`:

```python
from sec_parser.semantic_elements import TableOfContentsElement, TableElement

content_nodes = [
    node for node in elements
    if not isinstance(node, (TableOfContentsElement, TableElement))
]
```

This single isinstance check eliminates HTML-table-format ToC nodes (correctly
classified by sec-parser's `TableOfContentsClassifier`) and table numerical text.

### 4.3 Fix 2B — Text-Line ToC in Extractor
**File:** `src/preprocessing/extractor.py` (new filter pass)

`TableOfContentsClassifier` only processes `{TableElement}` nodes — text-line ToC
entries (`"Item 1A. Risk Factors..... 25"`) arrive as `TextElement` and pass through.
Apply compiled patterns from `cleaning.py`'s `TOC_PATTERNS_COMPILED` at the node level
before building `full_text`, not only post-extraction on aggregated text.

### 4.4 Fix 3 — spaCy Sentencizer for Sentence Boundaries
**File:** `src/preprocessing/segmenter.py:307,349`

Replace bare regex sentence splitting with spaCy's `sentencizer` component (spaCy is
already a declared dependency). The `sentencizer` uses a configurable abbreviation list
and does not split on `U.S.`, `Inc.`, `Corp.`, `i.e.`, `e.g.`, or month abbreviations.

Affected methods: `_split_into_chunks` (line 307) and `_segment_by_semantic_breaks`
(line 349). Both must use the same sentencizer instance (load once, reuse via the
production worker pool).

### 4.5 Fix 4 — Segment-Level Deduplication
**File:** `src/config/qa_validation.py:890-908`

Add a segment-level dedup check using SHA-256 for exact duplicates and MinHash LSH
(via `datasketch`, already a common NLP dependency) for near-duplicates:

- Exact duplicate: SHA-256 of `segment.text` appears in the run's segment hash set → quarantine
- Near-duplicate: MinHash Jaccard similarity ≥ 0.85 with any other segment in the corpus → warning + exclude from training split
- The segment hash set is accumulated in `StateManager` alongside the existing filing-level manifest

### 4.6 Fix 5 — Hybrid Anchor-Based Pre-Seek
**File:** `src/preprocessing/extractor.py` (new method `_anchor_seek_section`)

Rather than passing the full 6–68 MB HTML to sec-parser, use BeautifulSoup to locate
the Item 1A anchor before parsing:

```
Full HTML (6–68 MB)
  ↓
BS4 anchor seek (< 0.5s)
  – Find <a href="#anchor_id"> for "Item 1A" in ToC table
  – Resolve target <a id="anchor_id"> in document body
  – Slice raw HTML: Item 1A anchor → next top-level section anchor
  ↓
sec-parser on ~50–200 KB fragment
  – TextElementMerger handles <span> fragmentation
  – TitleElement detection finds subsection headers
  – ~1–2s instead of 34s
  ↓
[Fallback] If no named anchors found: full-document parse (existing path)
```

The anchor seek exploits EDGAR's native hyperlink structure:
```html
<!-- ToC entry -->
<a href="#i4bf6d0bde838478985b72eb4052bc976_19">Item 1A-Risk Factors</a>

<!-- Section body -->
<a id="i4bf6d0bde838478985b72eb4052bc976_19"></a>
```

100% Key Item Recall is maintained via fallback. `extraction_method` in output metadata
records which path was taken.

### 4.7 Fix 6 — Calibrated Validators
**File:** `src/config/qa_validation.py:619-622,873`

**Risk keywords:** Replace modal verbs with domain anchors:
```python
RISK_KEYWORDS = {
    "risk", "adverse", "material", "uncertain",
    "impair", "litigation", "regulatory", "infringement",
    "cybersecurity", "volatility", "liquidity", "covenant",
    "indemnif", "recall", "injunction", "write-down",
}
```

**Yield denominator:** Replace `file_size_bytes` (raw HTML) with `stripped_text_bytes`
(HTML tags stripped via `re.sub(r'<[^>]+>', '', html)`). Compute once during extraction
and pass through to the validator.

### 4.8 Fix 7 — Narrow Line-Number Regex
**File:** `src/preprocessing/cleaning.py:160`

```python
# Before (too aggressive — deletes enumerated list items):
text = re.sub(r'^[\s\-]*\d+[\s\-]*$', '', text, flags=re.MULTILINE)

# After (only removes standalone page-number-like integers ≥ 2 digits):
text = re.sub(r'^\s*\d{2,}\s*$', '', text, flags=re.MULTILINE)
```

Single-digit lines (enumerated list items like `"3"`) are preserved. Page numbers
(typically 2–3 digits) are still removed.

### 4.9 Fix 8 — BS4 Pre-processing for Large Files
**File:** `src/preprocessing/parser.py:412-466`

`_flatten_html_nesting` uses DOTALL regex on 6–68 MB HTML strings with five iterations,
causing catastrophic backtracking on files > 30 MB. Replace with a BeautifulSoup tree
walk for files where `len(html_bytes) > 10_000_000`:

```python
if len(html_content) > 10_000_000:
    html_content = _flatten_html_nesting_bs4(html_content)
else:
    html_content = _flatten_html_nesting_regex(html_content)
```

The regex path is preserved for small files where it performs well.

---

## 5. Engineering & MLOps

### 5.1 Pipeline Version

This PRD targets pipeline version `0.3.0`. The `pipeline_version` field in
`SegmentedRisks.metadata` must be bumped to `"0.3.0"` in `src/preprocessing/pipeline.py`.

### 5.2 Backward Compatibility

- `SegmentedRisks` schema is additive only (`extraction_method` field added; no existing fields removed)
- Run directories from v0.2.0 remain valid; they will fail the new zero-segment check if re-validated (expected behaviour)
- `StateManager` manifest format is extended with a `segment_hashes` key (additive)

### 5.3 Test Requirements

Each fix requires a corresponding test or extension to an existing test:

| Fix | Test location | Minimum coverage |
|:----|:--------------|:----------------|
| Fix 1 (zero-segment FAIL) | `tests/test_qa_validation.py` | `total_segments=0` → `FAIL` |
| Fix 2A/2B (ToC filter) | `tests/test_extractor.py` | Fixture with known ToC HTML verifies no ToC text in output |
| Fix 3 (spaCy sentencizer) | `tests/test_segmenter.py` | `"U.S. economy"` not split; `"end of paragraph. Next"` correctly split |
| Fix 4 (segment dedup) | `tests/test_qa_validation.py` | Identical segment text → dedup warning |
| Fix 5 (anchor seek) | `tests/test_extractor.py` | COST_10K_2023.html → anchor path taken; parse time ≤ 3s |
| Fix 6 (keyword calibration) | `tests/test_qa_validation.py` | Modal-verb-only text fails keyword check |
| Fix 7 (narrow regex) | `tests/test_cleaning.py` | Line `"3"` preserved; line `"42"` removed |
| Fix 8 (BS4 large files) | `tests/test_parser.py` | Synthetic 11 MB HTML takes BS4 path |

### 5.4 Verification Commands

```bash
# Full test suite (must stay green throughout)
python -m pytest tests/ -x -q

# Confirm zero-segment fix fires
python -m pytest tests/test_qa_validation.py -k "zero_segment" -v

# Smoke-test anchor seek on real filing
python -c "
from src.preprocessing.extractor import RiskFactorExtractor
import time
e = RiskFactorExtractor()
start = time.time()
result = e.extract('data/raw/COST_10K_2023.html')
elapsed = time.time() - start
assert elapsed < 3.0, f'Anchor seek too slow: {elapsed:.2f}s'
print(f'OK: {elapsed:.2f}s, method={result.metadata[\"extraction_method\"]}')
"

# Batch validate existing corpus — confirm G-07 (100% Key Item Recall)
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir data/interim/extracted/<run_dir>

# QA batch with new zero-segment gate
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/processed/<run_dir> --fail-on-warn
```

---

## 6. Phase-Gate Plan

### Phase 1 — Validation Fixes (no parser changes, immediate unblock)
**Scope:** Fix 1, Fix 6, Fix 7

| Step | File | Change |
|:-----|:-----|:-------|
| 1.1 | `qa_validation.py:787` | Zero-segment = hard FAIL |
| 1.2 | `qa_validation.py:619` | Domain keyword anchors |
| 1.3 | `qa_validation.py:873` | Yield PPM denominator |
| 1.4 | `cleaning.py:160` | Narrow line-number regex |

**Gate:** All existing tests pass; zero-segment test added and passing.

### Phase 2 — Extractor & Cleaner Quality (ToC + tables)
**Scope:** Fix 2A, Fix 2B

| Step | File | Change |
|:-----|:-----|:-------|
| 2.1 | `extractor.py:459` | Filter `TableOfContentsElement` and `TableElement` nodes |
| 2.2 | `extractor.py` (new) | Text-line ToC filter at node level |

**Gate:** Re-run `check_extractor_batch.py` on 309-filing corpus; ToC contamination rate = 0%;
Key Item Recall = 309/309 (100%).

### Phase 3 — Segmenter Quality (sentence boundaries)
**Scope:** Fix 3

| Step | File | Change |
|:-----|:-----|:-------|
| 3.1 | `segmenter.py:307` | Replace regex split with spaCy sentencizer in `_split_into_chunks` |
| 3.2 | `segmenter.py:349` | Same replacement in `_segment_by_semantic_breaks` |

**Gate:** Gunning Fog ≥ 10.0 on 20-file spot-check; abbreviation split test passing.

### Phase 4 — Performance: Hybrid Pre-Seek
**Scope:** Fix 5, Fix 8

| Step | File | Change |
|:-----|:-----|:-------|
| 4.1 | `extractor.py` | `_anchor_seek_section` method |
| 4.2 | `extractor.py` | Wire anchor seek as primary path with full-parse fallback |
| 4.3 | `parser.py:412` | BS4 large-file flatten path (> 10 MB) |

**Gate:** COST_10K_2023.html parse ≤ 3s; Key Item Recall = 309/309; `extraction_method`
field populated in all output files.

### Phase 5 — Segment Deduplication
**Scope:** Fix 4

| Step | File | Change |
|:-----|:-----|:-------|
| 5.1 | `qa_validation.py:890` | SHA-256 segment-level exact dedup |
| 5.2 | `qa_validation.py` (new) | MinHash near-dedup check |
| 5.3 | `src/utils/checkpoint.py` or `StateManager` | Persist segment hash set |

**Gate:** Synthetic fixture with duplicate segment text triggers warning; manifest
`segment_hashes` key populated after batch run.

---

## 7. User Stories

> Acceptance criteria (Gherkin Given/When/Then) are in individual story files linked below.

| ID | Priority | As a… | I want to… | So that… | Detail |
|:---|:---------|:------|:-----------|:---------|:-------|
| US-009 | **P0** | Data Scientist | The extracted corpus contains no ToC lines or HTML table text | Training loss decreases monotonically on clean risk factor prose | [→](stories/US-009_clean_training_corpus.md) |
| US-010 | **P0** | ML Engineer | A filing that produces zero segments fails QA with a hard FAIL | Silent empty training examples never reach the corpus | [→](stories/US-010_zero_segment_hard_fail.md) |
| US-011 | **P0** | Pipeline Operator | Parsing completes in ≤ 3s per filing (median) | I can iterate on segmenter parameters on the 887-filing corpus within a work session | [→](stories/US-011_anchor_parse_performance.md) |
| US-012 | **P1** | Data Scientist | Segments contain complete sentences not split on financial abbreviations | Training examples express coherent risk arguments | [→](stories/US-012_sentence_boundary_quality.md) |

---

## 8. Architecture

### Current State (v0.2.0)
```
HTML (6–68 MB)
  → sec-parser (full document, 34s–300s)
  → extractor._extract_section_content (includes ToC + Table nodes)
  → cleaning._remove_toc_artifacts (post-hoc, incomplete)
  → segmenter (regex sentence split, abbreviation errors)
  → qa_validation (zero-seg → PASS, no segment dedup)
```

### Target State (v0.3.0)
```
HTML (6–68 MB)
  → BS4 anchor seek (< 0.5s) → 50–200 KB Item 1A fragment
      [fallback: full-document parse for anchor-less filings]
  → sec-parser on fragment (1–2s)
  → extractor (filters TableOfContentsElement + TableElement + text-line ToC)
  → cleaning (narrowed line-number regex)
  → segmenter (spaCy sentencizer — no abbreviation splits)
  → qa_validation
      → zero-seg = hard FAIL
      → segment-level SHA-256 + MinHash dedup
      → domain keyword anchors
      → yield PPM with stripped-text denominator
```

---

## 9. Data & Metrics

### KPIs (Post-v0.3.0 corpus re-run)

| Metric | Current (v0.2.0) | Target (v0.3.0) |
|:-------|:-----------------|:----------------|
| ToC contamination rate | 56.6% (175/309 files) | 0% |
| Median parse time (6 MB file) | 34.52s | ≤ 3.0s |
| Zero-segment PASS (silent failure) | Unknown | 0 (hard FAIL) |
| Key Item Recall | 100% (309/309) | 100% (maintained) |
| Segment dedup coverage | 0% (filing-level only) | 100% (segment-level) |
| Gunning Fog (median, corpus) | Unknown (splitter artifacts) | ≥ 10.0 |
| Table text in segments | ~100% of filings | 0% |
| Test count | 660 collected | ≥ 680 (new fixture tests) |

---

## 10. Technical Requirements

| ID | Requirement | Priority |
|:---|:------------|:---------|
| TR-01 | spaCy `sentencizer` configured with financial abbreviation list | Must |
| TR-02 | `datasketch` MinHash (or equivalent) for segment near-dedup | Must |
| TR-03 | `_anchor_seek_section` falls back to full-parse when no EDGAR anchors present | Must |
| TR-04 | `extraction_method: "anchor_seek_v2" \| "full_parse_fallback"` in output metadata | Must |
| TR-05 | `pipeline_version: "0.3.0"` in all output metadata | Must |
| TR-06 | All Phase 1–5 gates pass on 309-filing corpus before corpus expansion to 887 files | Must |
| TR-07 | No change to `SegmentedRisks` top-level schema keys (additive only) | Must |
| TR-08 | `stripped_text_bytes` computed once per filing; reused for yield PPM | Should |
| TR-09 | Segment hash set persisted in `StateManager`; survives `--resume` restarts | Should |
| TR-10 | `_flatten_html_nesting` BS4 path used for files > 10 MB | Should |

---

## 11. Open Questions

| # | Question | Owner | Decision Needed By |
|:--|:---------|:------|:-------------------|
| Q-01 | Should near-duplicate segments (MinHash ≥ 0.85) be quarantined or only excluded from train split? Quarantine is more conservative; exclusion-from-split preserves them for eval. | beth | Phase 5 design |
| Q-02 | spaCy model size: `en_core_web_sm` (12 MB) vs `en_core_web_md` (43 MB) for sentencizer? `sm` suffices if only `sentencizer` is used; `md` needed if dependency parse is added later. | beth | Phase 3 implementation |
| Q-03 | Anchor seek slices to the next top-level section anchor (`Item 1B` or `Item 2`). For filings where Item 1B is absent, what is the correct end boundary? | beth | Phase 4 implementation |
| Q-04 | Should `extraction_yield_ppm` threshold be re-calibrated after the denominator fix, or kept at `≥ 1,000 PPM` pending empirical observation on re-processed corpus? | beth | Phase 1 completion |
