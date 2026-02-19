---
title: "Fix Plan: SEC 10-K Parser & Validation for LLM Fine-tuning"
date: "2026-02-18"
commit: "469d6cd868222bd8472dd0f36e84e1ca06bf634c"
branch: "main"
researcher: "beth"
research_doc: "thoughts/shared/research/2026-02-18_10-00-00_parser_finetune_critique.md"
---

# Fix Plan: SEC 10-K Parser Pipeline

## Desired End State

Upon completion, the pipeline will:
1. Correctly identify and extract Item 1A Risk Factors from 10-K HTML filings
2. Produce clean, well-bounded text segments suitable for FinBERT fine-tuning
3. Exclude table noise from training samples
4. Reject filings with 0 segments at validation time (hard blocker)
5. Detect segment-level near-duplicates across filings
6. Use sentence-aware splitting that handles financial abbreviations

## Anti-Scope (What We Are NOT Doing)

- Not adding a new SEC form type (8-K, S-1, etc.)
- Not changing the downstream FinBERT training code
- Not replacing `sec-parser` library with a custom parser
- Not adding topic model label generation (separate task)
- Not fixing the `ticker` extraction (complex CIK→ticker lookup, separate task)

---

## Phase 1: Parser Fixes

### Fix 1A — Replace DOTALL regex in `_flatten_html_nesting` with BS4 for large files

> **REVISED (2026-02-18):** Original plan said "disable flatten_html by default" — WRONG.
> `flatten_html` is a necessary performance optimization; disabling it causes recursion
> hangs on large files. 100% Item Recall holds with it enabled. The real fix is the
> catastrophic backtracking on files > 10MB.

**File:** `src/preprocessing/parser.py:412-466`
**Change:** Add a size gate. For files under ~10MB, keep the current regex path.
For larger files, use BeautifulSoup to unwrap redundant tags safely.

```python
def _flatten_html_nesting(self, html_content: str) -> str:
    """Pre-process HTML to reduce nesting depth."""
    # For large files, use BS4 to avoid DOTALL regex catastrophic backtracking
    if len(html_content) > 10 * 1024 * 1024:  # > 10MB
        return self._flatten_html_nesting_bs4(html_content)
    # Existing regex path for small files (fast)
    ...  # current implementation unchanged

def _flatten_html_nesting_bs4(self, html_content: str) -> str:
    """BS4-based HTML flattening for large files (safe, no regex backtracking)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'lxml')
    for tag_name in ['div', 'span', 'font']:
        for tag in soup.find_all(tag_name):
            if not tag.get_text(strip=True):  # Only unwrap truly empty tags
                tag.decompose()
    return str(soup)
```

**Rationale:** Preserves the optimization for typical files; eliminates timeout risk for
large (30-68MB) financial filings documented in the performance analysis.

---

### Fix 1B — Document the 10-K / `Edgar10QParser` limitation

**File:** `src/preprocessing/parser.py:83-86`
**Change:** Add a prominent comment and a warning log when parsing 10-K forms.
If `sec-parser` adds `Edgar10KParser` in a future version, the parser map is the
single place to update.

```python
self.parsers = {
    # NOTE: sec-parser does not provide a dedicated Edgar10KParser.
    # Edgar10QParser is used for both forms. Section identifiers
    # (TopSectionTitle.identifier) follow 10-Q conventions — regex
    # fallback in _find_section_node handles 10-K section lookup.
    FormType.FORM_10K: sp.Edgar10QParser(),
    FormType.FORM_10Q: sp.Edgar10QParser(),
}
```

Then in `parse_from_content`, emit a single warning when `form_type == "10-K"` and
`quiet=False`:
```python
if form_type_enum == FormType.FORM_10K and not quiet:
    warnings.warn(
        "10-K parsed with Edgar10QParser (no dedicated 10-K parser available). "
        "Section identifier matching falls back to regex patterns.",
        UserWarning
    )
```

---

### Fix 1C — Fix dead code in `_validate_form_type`

**File:** `src/preprocessing/parser.py:260`
**Change:** Remove `"10-K"` from the post-normalize check (it's unreachable).

```python
def _validate_form_type(self, form_type: str) -> FormType:
    form_type = form_type.upper().replace("-", "")
    if form_type == "10K":
        return FormType.FORM_10K
    if form_type == "10Q":
        return FormType.FORM_10Q
    raise ValueError(...)
```

---

## Phase 2: Extractor — ToC Contamination (NEW PRIORITY)

### Fix 2A — Filter ToC nodes before building full_text (NEW — replaces retracted boundary fix)

> **ADDED (2026-02-18):** Section boundary fix was RETRACTED (extractor works correctly).
> Replaced with ToC contamination fix — the actual #1 data quality problem.
> 175/309 files (56.6%) have ToC contamination. 93 files fail ONLY this check.

**File:** `src/preprocessing/extractor.py:471-478`

ToC nodes arrive in the flat tree as `TextElement` nodes containing dot-leader patterns
like `"Item 1A. Risk Factors..... 25"`. They need to be identified and excluded from
`full_text` building, not just removed by the text cleaner post-hoc.

```python
# In _extract_section_content, add ToC filter to the full_text join:
# Import at top of file: from .constants import TOC_PATTERNS_COMPILED

full_text = "\n\n".join([
    node.text for node in content_nodes
    if hasattr(node, 'text')
    and node.text.strip()
    and not isinstance(node.semantic_element, sp.TableElement)
    and not self._is_toc_node(node.text)   # ADD
])

def _is_toc_node(self, text: str) -> bool:
    """Check if node text looks like a Table of Contents entry."""
    from .constants import TOC_PATTERNS_COMPILED
    text = text.strip()
    if not text:
        return False
    for pattern in TOC_PATTERNS_COMPILED:
        if pattern.search(text):
            return True
    return False
```

Also apply the same filter in `extract_risk_factors_from_dict` (`extractor.py:215-229`)
when building `content_nodes`.

---

### Fix 2B — Filter `TableElement` from segment text

**File:** `src/preprocessing/extractor.py:459-468`
**Change:** Track tables in `elements` (for metadata) but exclude their text from
`full_text`. Add an `include_tables` parameter (default `False`) to `extract_section`.

```python
# In _extract_section_content, change the full_text join:
full_text = "\n\n".join([
    node.text for node in content_nodes
    if hasattr(node, 'text')
    and node.text.strip()
    and not isinstance(node.semantic_element, sp.TableElement)  # ADD
])
```

Tables are still tracked in `elements` for downstream metadata/analysis use.

---

## Phase 3: Segmenter — Sentence Splitting

### Fix 3A — Replace regex sentence splitter with spaCy sentencizer

**File:** `src/preprocessing/segmenter.py:307`

spaCy is already a declared dependency and initialized in `cleaning.py`.
Use the `sentencizer` component (no need for full NLP pipeline):

```python
# At module level, lazy-init:
_sentencizer = None

def _get_sentencizer():
    global _sentencizer
    if _sentencizer is None:
        import spacy
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        _sentencizer = nlp
    return _sentencizer

# In _segment_by_semantic_breaks and _split_into_chunks:
def _get_sentences(self, text: str) -> List[str]:
    nlp = _get_sentencizer()
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
```

Replace `re.split(r'([.!?]\s+)', text)` at `segmenter.py:307` and
`re.split(r'(?<=[.!?])\s+', text)` at `segmenter.py:349` with `_get_sentences`.

---

### Fix 3B — Raise semantic segmentation acceptance threshold

**File:** `src/preprocessing/segmenter.py:87`
**Change:** Require at least 5 segments from semantic segmentation before preferring
it over header-based. The exact number should be tuned but `> 1` is clearly wrong.

```python
SEMANTIC_MIN_SEGMENTS = 5  # class constant

if len(segments) >= self.SEMANTIC_MIN_SEGMENTS:
    logger.info("Using semantic segmentation. Found %d segments.", len(segments))
else:
    logger.info(
        "Semantic segmentation yielded %d segments (< %d), falling back.",
        len(segments), self.SEMANTIC_MIN_SEGMENTS
    )
    segments = self._segment_by_headers(text)
```

---

## Phase 4: Validation — Data Quality Blockers

### Fix 4A — Fail on zero segments

**File:** `src/config/qa_validation.py:787-788`
**Change:** Replace early return with an explicit FAIL result.

```python
def _check_substance(self, file_data: List[Dict]) -> List[ValidationResult]:
    ...
    if total_segments == 0:
        # Explicit FAIL: extraction produced no segments
        threshold = self.registry.get("empty_segment_rate")
        if threshold:
            return [ValidationResult.from_threshold(threshold, 1.0,
                message="Zero segments extracted — Item 1A likely not found")]
        return []
    ...
```

Also add a dedicated `zero_segment_count` threshold in
`configs/qa_validation/health_check.yaml`:
```yaml
thresholds:
  data_substance:
    min_segment_count:
      display_name: "Minimum Segment Count"
      metric_type: count
      target: 1
      operator: ">="
      blocking: true
      description: "Filing must have at least one extracted segment"
```

---

### Fix 4B — Add segment-level near-duplicate detection

**File:** `src/config/qa_validation.py:882-923`
**Change:** Add a second deduplication pass at the segment level using 8-character
content hash prefix (faster than full SHA-256 for large batch).

```python
def _check_segment_duplicates(self, file_data: List[Dict]) -> List[ValidationResult]:
    """Check for near-duplicate segments across all files."""
    results = []
    seg_hashes: Dict[str, int] = {}
    total_segs = 0

    for data in file_data:
        for seg in data.get("segments", []):
            total_segs += 1
            text = re.sub(r'\s+', ' ', seg.get("text", "").lower().strip())
            h = hashlib.sha256(text.encode()).hexdigest()[:12]
            seg_hashes[h] = seg_hashes.get(h, 0) + 1

    if total_segs == 0:
        return results

    dup_segments = sum(count - 1 for count in seg_hashes.values() if count > 1)
    dup_rate = dup_segments / total_segs

    threshold = self.registry.get("segment_duplicate_rate")
    if threshold:
        results.append(ValidationResult.from_threshold(threshold, dup_rate))

    return results
```

Add to `check_run` and `check_single` call chains. Add threshold in health_check.yaml:
```yaml
segment_duplicate_rate:
  display_name: "Segment Duplicate Rate"
  metric_type: rate
  target: 0.15
  warn_threshold: 0.10
  operator: "<="
  blocking: false
  description: "Rate of near-duplicate segments across all files"
```

---

### Fix 4C — Strengthen risk keyword set

**File:** `src/config/qa_validation.py:619`
**Change:** Replace generic modal verbs with domain-specific risk anchors. Keep modals
but add financial/legal/operational terms.

```python
RISK_KEYWORDS = {
    # Domain-specific (strong signal)
    "impair", "litigation", "regulatory", "infringement", "cybersecurity",
    "volatility", "liquidity", "covenant", "indemnif", "injunction",
    "write-down", "writedown", "goodwill", "impairment", "restatement",
    "noncompliance", "sanction", "breach", "default",
    # Retained generic modals (weaker signal)
    "risk", "adverse", "material", "uncertain", "may", "could", "might",
}
```

Bump the minimum count threshold from 10 to 25 to compensate for the larger set.

---

### Fix 4D — Fix `extraction_yield_ppm` denominator

**File:** `src/config/qa_validation.py:869-878`
**Change:** Compute stripped-text size, not raw HTML size.

```python
# In _check_substance, where extraction_yield_ppm is computed:
html_content_approx = data.get("html_content", "")
if html_content_approx:
    # Strip tags to get text-equivalent byte count
    stripped = re.sub(r'<[^>]+>', '', html_content_approx)
    denom = max(len(stripped.encode('utf-8')), 1)
else:
    # Fallback: assume 40% text density in raw HTML
    denom = max(int(file_size_bytes * 0.4), 1)

yield_ppm = (extracted_chars / denom) * 1_000_000
```

Alternatively, store `stripped_text_bytes` in the metadata dict during parsing
(single pass, zero cost).

---

### Fix 4E — Fix batch validator race condition

**File:** `scripts/validation/data_quality/check_preprocessing_batch.py:110`
**Change:** Make `validate_single_file` also use a PID-stamped temp directory.

```python
def validate_single_file(file_path, run_dir, verbose=False):
    ...
    temp_dir = run_dir / f"_temp_validation_{os.getpid()}"  # ADD PID
    ...
```

---

## Phase 5: Cleaning — False Positive Fixes

### Fix 5A — Narrow line-number removal regex

**File:** `src/preprocessing/cleaning.py:160`
**Change:** Only remove page-style numbers (2+ digits) or numbers explicitly preceded
by "Page". Single digit lines are too risky to strip.

```python
# Remove standalone page numbers - ONLY 2+ digit lines (not list item numbers)
text = re.sub(r'^[\s\-]*\d{2,}[\s\-]*$', '', text, flags=re.MULTILINE)
text = re.sub(r'^[\s\-]*Page\s+\d+[\s\-]*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
```

---

## Verification

### Automated checks
```bash
# Run existing tests
python -m pytest tests/ -x -q

# Validate a single 10-K run dir
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/<run_dir> -v

# Batch validate with fail-on-warn for CI
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/processed/<run_dir> --fail-on-warn
```

### Manual spot-checks
1. Parse one known 10-K → confirm Item 1A section is found
2. Count segments → confirm > 5 segments extracted
3. Check segment text → confirm no `<td>`, `<tr>`, or raw number sequences
4. Run batch validator on a corpus dir → confirm 0-segment filings are FAIL

---

## Implementation Order (Revised 2026-02-18)

> Reordered based on cross-referencing past research. Section boundary fix removed
> (extractor works). ToC contamination elevated to #1 priority (56.6% failure rate,
> DEFERRED since Dec 2025). flatten_html fix revised from "disable" to "BS4 for large files".

1. **Fix 4A** (zero segments = FAIL) — stops broken filings entering training data
2. **Fix 2A** (ToC node filter in extractor) — fixes the #1 known data quality gap
3. **Fix 2B** (exclude tables from text) — clean training samples
4. **Fix 3A** (spaCy sentence splitting) — correct segment boundaries
5. **Fix 1A** (BS4 flatten for large files) — eliminates timeout risk
6. **Fix 4B** (segment-level dedup) — training data quality
7. **Fix 4C + 4D** (keyword + yield metric) — validation calibration
8. **Fix 5A** (narrow page number regex) — cleaning precision
9. **Fix 1B + 1C + 4E** (doc/comments/race condition) — housekeeping

**REMOVED:**
- ~~Fix 2A (re.search boundary)~~ — extractor `_is_next_section()` works correctly,
  zero overshoot in 309 files. Validator false positive fix is in `check_extractor_batch.py`
  (separate QA tooling, not in scope for training data quality).
