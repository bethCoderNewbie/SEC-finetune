---
title: "SEC 10-K Parser & Validation Critique for LLM Fine-tuning"
date: "2026-02-18"
commit: "469d6cd868222bd8472dd0f36e84e1ca06bf634c"
branch: "main"
researcher: "beth"
scope: "src/preprocessing/parser.py, extractor.py, cleaning.py, segmenter.py, src/config/qa_validation.py"
goal: "Fine-tune FinBERT on 10-K risk factors for risk classification + topic modeling"
---

# Research: SEC 10-K Parser & Validation Critique

## Background

The pipeline's goal is to parse SEC 10-K HTML filings → extract Item 1A Risk Factors →
segment into training samples → fine-tune a financial LLM (FinBERT) for:
- **Risk classification** (high/medium/low, risk category)
- **Topic modeling** (regulatory, market, operational, cyber, etc.)

This research documents ground-truth bugs and data quality gaps found through direct
code inspection. Every cited issue includes file:line for immediate navigation.

---

## 1. ~~Critical~~ Known Limitation (Mitigated): `Edgar10QParser` for 10-K

> **CORRECTION (2026-02-18):** Past research `2025-12-30_14-39-03_extractor_qa_findings_verification.md`
> confirmed this is an **intentional library limitation**, not an actionable bug.
> Key Item Recall is **309/309 (100%)** across 309 real 10-K filings. The 3-strategy
> fallback in `_find_section_node` (`extractor.py:309-354`) handles identifier mismatches.
> **Downgraded from Critical → Documented Limitation. No code change needed.**

**File:** `src/preprocessing/parser.py:83-86`

```python
self.parsers = {
    FormType.FORM_10K: sp.Edgar10QParser(),  # sec-parser v0.54.0 has no Edgar10KParser
    FormType.FORM_10Q: sp.Edgar10QParser(),
}
```

`sec-parser` v0.54.0 only provides `Edgar10QParser`. The 3-strategy fallback (identifier →
regex patterns → text normalization) successfully finds Item 1A at 100% recall despite
the naming mismatch. Monitor for an `Edgar10KParser` in future library versions.

**Actionable:** Add documentation comment only (see Fix 1B). No behavioral change.

---

## 2. High: `_flatten_html_nesting` is a Performance Risk, Not a Correctness Blocker

> **REVISION (2026-02-18):** Past research `2025-12-30_18-20-45_parser_performance_analysis.md`
> confirms this function is an **intentional performance optimization** for large files
> (up to 68MB). Despite markup mutation concerns, Key Item Recall remains 100% with it enabled.
> The original recommendation to "disable by default" was wrong — it would regress large-file
> parsing. The real risk is DOTALL regex catastrophic backtracking on large files.
> **Severity downgraded from Critical → High (performance/stability).**

**File:** `src/preprocessing/parser.py:412-466`

The function performs regex substitution on raw HTML before sec-parser processes it.
**Two confirmed risks:**

1. **DOTALL regex on 68MB strings** (`parser.py:442-449`): The pattern
   `<div[^>]*>\s*(<div[^>]*>.*?</div>)\s*</div>` with `re.DOTALL` across 68MB is slow
   and prone to catastrophic backtracking. Past analysis documented actual hangs.
2. **Five iterations** (`parser.py:439`): Each pass magnifies the regex cost.

**What it does NOT do (tested):** It does NOT break Item 1A detection — 100% recall
holds across 309 files. The section markers sec-parser uses are preserved in practice.

**Correct fix:** Replace DOTALL regex with BeautifulSoup-based approach for files > 10MB,
or implement chunk-based processing. Do NOT disable for all files.

---

## 3. Critical: Zero Segments Returns PASS in Validation

**File:** `src/config/qa_validation.py:787-788`

```python
if total_segments == 0:
    return results  # returns [] — no check fires
```

Both `_check_cleanliness` and `_check_substance` guard with `if total_segments == 0:
return results`. If Item 1A extraction fails entirely (returns `None` or empty text),
the segmenter produces 0 segments, and both checks return no `ValidationResult`
objects. `determine_overall_status([])` returns `PASS`.

**Impact:** Filings where the parser/extractor fails completely pass data quality
validation. These empty records silently enter training data.

---

## 4. High: Sentence Splitter Breaks on Financial Abbreviations

**File:** `src/preprocessing/segmenter.py:307`

```python
sentences = re.split(r'([.!?]\s+)', text)
```

Financial filings are dense with period-terminated abbreviations:
`U.S.`, `Inc.`, `Corp.`, `No.`, `vs.`, `Sec.`, `approx.`, `i.e.`, `e.g.`,
`Ph.D.`, `Jan.`, `Feb.`, year ranges like `2020.`, etc.

Each of these creates a false sentence boundary → incorrect semantic embedding scores
→ bad segment boundaries → training samples that begin mid-sentence or cut off
mid-argument.

**Correct path:** Use `spacy.sentencizer` (already a dependency) or `nltk.sent_tokenize`.

---

## ~~5. High: Section Boundary Bleeds~~ — RETRACTED

> **RETRACTED (2026-02-18):** This critique was based on a misread of the code.
>
> Actual code at `extractor.py:497-500`:
> ```python
> text = node.text.strip().lower()  # .strip() IS called before re.match
> if re.match(r'item\s+\d+[a-z]?\s*\.', text):
> ```
>
> Past research `2025-12-30_17-43_section_end_precision_investigation.md` tested 309 real
> 10-K filings and found **ZERO actual boundary overshoot**. The apparent 52.8% failure
> rate in QA reports was 100% false positives in the **validator** (case-sensitive pattern
> matching section header, not the extractor).
>
> **The extractor `_is_next_section()` is working correctly. No fix needed.**
>
> Remaining open item: The **validator** pattern in
> `check_extractor_batch.py:235-256` needs fixing (its `r'Item\s+\d+[A-Z]?\s*\.\s+[A-Z]'`
> has false positives). Fix documented in the boundary investigation.

---

## NEW — Critical: ToC Contamination in 56.6% of Filings

> **Added (2026-02-18) from past research:**
> `2025-12-29_16-33-56_visualization_controls_architecture.md` and
> `2025-12-30_14-39-03_extractor_qa_findings_verification.md` both document this as
> the **#1 unaddressed data quality issue** — marked DEFERRED.

**File:** `src/preprocessing/extractor.py`, `src/preprocessing/cleaning.py`

**Scale:** 175/309 files (56.6%) have Table of Contents contamination in extracted text.
93 files (34.3%) fail **only** ToC filtering — every other check passes.

**What happens:** The Risk Factors section often follows the ToC in the HTML document.
The parser sometimes captures ToC entries (e.g., `"Item 1A. Risk Factors..... 25"`) as
part of the extracted section text. These entries:
- Look superficially like risk content to a language model
- Introduce dot-leader sequences and page numbers into training samples
- Corrupt sentence and segment boundaries

**Current state:** `cleaning.py:168-200` has `_remove_toc_artifacts` with 7 compiled
patterns plus a base pattern, but this does NOT catch all ToC formats present in the
corpus. The `extractor.py` does not pre-filter ToC nodes before building `full_text`.

**Impact for fine-tuning:** ToC lines like `"Item 1A. Risk Factors..... 25"` are
short-but-valid-looking tokens that train the model on boilerplate rather than risk
language.

---

## 6. High: No Segment-Level Deduplication for Fine-tuning

**File:** `src/config/qa_validation.py:890-908`

The hash-based duplicate check operates on the **whole filing content**, not individual
segments. Companies file 10-Ks annually and carry forward risk factor language nearly
verbatim year over year. Training data will contain near-identical segments from:
- Same company, different years (e.g., AAPL 2022 vs AAPL 2023)
- Different companies using boilerplate risk language

**Impact for fine-tuning:** Near-duplicate samples inflate the training set apparent
size, cause memorization rather than generalization, and violate train/test independence
if the same company appears in both splits.

---

## 7. High: Tables Included in Training Text

**File:** `src/preprocessing/extractor.py:459-468`

`TableElement` nodes are collected in `elements` and their `.text` is included in the
segment text via `node.text for node in content_nodes`. Risk Factors tables typically
contain numerical sensitivity analyses (e.g., "1% change in interest rate = $X million
impact"). These rows produce garbled text when serialized: `"3.2% 4.1% 5.0%
(12.3) (14.6) (16.2)"`.

**Impact:** FinBERT is a text classifier. Injecting tabular number sequences into
training samples degrades classification accuracy and distorts topic model vocabulary.

---

## 8. Medium: Line-Number Removal Deletes Enumerated List Items

**File:** `src/preprocessing/cleaning.py:160`

```python
text = re.sub(r'^[\s\-]*\d+[\s\-]*$', '', text, flags=re.MULTILINE)
```

Removes any line consisting solely of digits. Risk factor sections often use
single-digit line separators or numbered list formats where the number is on its own
line. Also removes valid content like fiscal year references that appear alone.

---

## 9. Medium: Risk Keyword Validation Too Weak

**File:** `src/config/qa_validation.py:619-622`

```python
RISK_KEYWORDS = {"risk", "adverse", "material", "uncertain",
                 "may", "could", "might", "potential"}
```

Modal verbs (`may`, `could`, `might`) are high-frequency in any English text.
The `>= 10` occurrences threshold at `qa_validation.py:918` is trivially satisfied
by non-risk content. A random paragraph of prose would pass this check.

For risk classification fine-tuning, domain anchors should include:
`impair`, `litigation`, `regulatory`, `infringement`, `cybersecurity`, `volatility`,
`liquidity`, `covenant`, `indemnif`, `recall`, `injunction`, `write-down`.

---

## 10. Medium: `extraction_yield_ppm` Wrong Denominator

**File:** `src/config/qa_validation.py:873`

```python
yield_ppm = (extracted_chars / file_size_bytes) * 1_000_000
```

`file_size_bytes` is the raw HTML file size. A 1 MB HTML file has ~600-800 KB of
markup tags, whitespace, and EDGAR headers. Extracted text of 150 KB from such a
file produces a yield of ~150,000 PPM — appearing low when extraction is actually
excellent. Thresholds for this metric are therefore miscalibrated.

**Correct denominator:** stripped-text byte count (HTML tags removed), not raw HTML
file size.

---

## 11. Low: Dead Code in Form Type Validation

**File:** `src/preprocessing/parser.py:258-262`

```python
form_type = form_type.upper().replace("-", "")
if form_type in ["10K", "10-K"]:  # "10-K" unreachable after replace()
```

After `.replace("-", "")`, the string `"10-K"` becomes `"10K"`. The `"10-K"` element
in the list is dead code. Cosmetic but indicative of untested edge paths.

---

## 12. Low: Batch Validator Race Condition

**File:** `scripts/validation/data_quality/check_preprocessing_batch.py:110-115`

The sequential `validate_single_file` (line 110) creates `run_dir / "_temp_validation"`
without a PID suffix. The parallel worker version (line 184) correctly uses
`_temp_validation_{os.getpid()}`. If the sequential path is ever called from a
parallel context (or if two CLI runs target the same directory simultaneously),
temp files will overwrite each other.

---

## Summary: Priority Matrix

| # | Severity | Issue | File:Line | Fine-tune Impact | Status |
|---|----------|-------|-----------|-----------------|--------|
| NEW | **Critical** | ToC contamination 56.6% of files | `cleaning.py:168`, `extractor.py` | Boilerplate in training data | ❌ DEFERRED (open) |
| 3 | **Critical** | 0 segments = PASS | `qa_validation.py:787` | Broken filings enter training data | ❌ Open |
| 2 | **High** | flatten_html DOTALL regex hangs on large files | `parser.py:412` | Parser hangs/timeouts | ❌ Open |
| 4 | **High** | Sentence splitter breaks on abbreviations | `segmenter.py:307` | Bad segment boundaries | ❌ Open |
| 6 | **High** | No segment-level dedup | `qa_validation.py:890` | Memorization / data leakage | ❌ Open |
| 7 | **High** | Tables included in training text | `extractor.py:459` | Garbled number sequences | ❌ Open |
| 8 | Medium | Line-number regex deletes list items | `cleaning.py:160` | Silently deleted content | ❌ Open |
| 9 | Medium | Weak risk keywords in validation | `qa_validation.py:619` | Bad domain validation | ❌ Open |
| 10 | Medium | Yield PPM wrong denominator | `qa_validation.py:873` | Miscalibrated metric | ❌ Open |
| 1 | ~~Critical~~ Limitation | `Edgar10QParser` for 10-K | `parser.py:83` | None — 100% Item Recall | ✅ Mitigated (intentional) |
| 5 | ~~High~~ Retracted | Section boundary bleeds | `extractor.py:500` | None — 0 actual overshoot in 309 files | ✅ Working correctly |
| 11 | Low | Dead code form type | `parser.py:260` | None | ❌ Open (trivial) |
| 12 | Low | Batch validator race condition | `batch.py:110` | Concurrency corruption | ❌ Open |
