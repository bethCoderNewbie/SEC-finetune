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
7. Output each filing as structured JSON: document_info / section_metadata / chunks,
   where every chunk carries a formatted chunk_id ("1A_001") and parent_subsection
8. Extract fiscal_year from EDGAR header (CONFORMED PERIOD OF REPORT) for every filing

## Anti-Scope (What We Are NOT Doing)

- Not adding a new SEC form type (8-K, S-1, etc.)
- Not changing the downstream FinBERT training code
- Not replacing `sec-parser` library with a custom parser
- Not adding topic model label generation (separate task)

---

## Strategic Context: Why We Keep sec-parser

`sec-parser` is the HTML parsing backbone. This section documents the build-vs-buy
decision so it is not revisited during implementation.

### What sec-parser provides that would be expensive to reproduce

| Capability | How sec-parser implements it | Reproduce cost |
|---|---|---|
| EDGAR HTML section boundary detection | `Edgar10QParser` with EDGAR-specific lexical rules; handles multi-doc containers, nested `<div>/<font>/<span>` | **High** — SEC HTML is non-standard; corpus-tested |
| Semantic element classification | 10+ types: `TopSectionTitle`, `TitleElement`, `TextElement`, `TableElement`, `PageHeaderElement`, `PageNumberElement`, `EmptyElement`, `TableOfContentsElement`, `SupplementaryText`, `ImageElement` | **High** — requires extensive rule corpus |
| Tree construction with typed nesting | `TreeBuilder` + `AlwaysNestAsParentRule(TopSectionTitle)`, `AlwaysNestAsParentRule(TitleElement)`, `NestSameTypeDependingOnLevelRule` | **Medium** — tree logic reproducible but not EDGAR-tested |
| Table detection and export | `TableElement` + `table_to_markdown()` | **Medium** — already monkey-patched at `parser.py:26–46` for `<th>`-only crash |
| ToC page detection | `TableOfContentsElement` auto-classified at document level | **Medium** |

### What sec-parser does NOT provide (our wrapper adds this)

- **Tree depth in serialised output** — Bug in our `parsing.py:155` (`node.level`
  reads a nonexistent `TreeNode` attribute; always falls back to `0`). Fixed by Fix 1D.
- **`parent_subsection` per chunk** — Our schema requirement. Fixed by Fix 6A.
- **`fiscal_year`** — EDGAR header field, not HTML semantics. Fixed by Fix 1E.
- **Inline ToC text filtering** — sec-parser classifies `TableOfContentsElement` for
  top-level ToC _pages_ but NOT inline dot-leader lines inside section text (e.g.
  `"Item 1A. Risk Factors..... 25"`). Fixed by Fix 2A.
- **Table text exclusion from narrative** — sec-parser correctly classifies
  `TableElement` but our extractor still joins table text into `full_text`. Fixed by
  Fix 2B.

### Accepted limitation

All `TitleElement.level` values are `0` for real 10-K filings because SEC HTML uses
`<p><b>heading</b></p>` styling, not semantic `<h1>`–`<h6>` tags. sec-parser's
`AbstractLevelElement.level` is derived from the HTML element type — it cannot infer
visual heading depth from CSS alone. We compensate with:
- Fix 1D: adds `depth` field from `TreeNode.children` recursion
- Fix 6A: sequential `TitleElement` scan for `parent_subsection` (does not require depth)

---

## Phase 0: Diagnostic Baseline

**Before implementing any fix**, run a one-shot audit to measure the current scale of
each research issue. This gives a pre-fix baseline to compare against post-fix runs.

### Script: `check_corpus_quality_audit.py` (NEW)

**File:** `scripts/validation/data_quality/check_corpus_quality_audit.py`

**Purpose:** Standalone diagnostic — no side effects, no data modification.
Reads all `*_segmented_risks.json` in a run directory.

**CLI:**
```bash
python scripts/validation/data_quality/check_corpus_quality_audit.py \
    --run-dir data/processed/<run_dir> [--output audit_report.md]
```

**7 checks:**

| Check | Metric | Research Issue |
|-------|--------|----------------|
| A | Segments matching `r'\.{3,}.*\d+\s*$'` (ToC lines) | §NEW Critical |
| B | Filings where `total_segments == 0` | §3 Critical |
| C | Segments with 4+ consecutive numeric tokens | §7 High |
| D | Segments whose first word is ≤3 chars + lowercase (abbreviation split) | §4 High |
| E | SHA-256 segment-level exact duplicates | §6 High |
| F | Filings that pass risk keyword check via modal verbs only | §9 Medium |
| G | `yield_ppm_html` (current) vs `yield_ppm_text` (correct) delta | §10 Medium |

**Implementation:**
- Load each file via `SegmentedRisks.load_from_json()` (`src/preprocessing/models/segmentation.py:112`)
- Strip HTML for check G via `TextCleaner.remove_html_tags()` (`src/preprocessing/cleaning.py:307`)
- Emit markdown with a summary table + per-check section (affected count, %, top 3 offenders, fix reference)
- Exit 1 if check A or B fire above 1%

No new dependencies required.

---

## Phase 1: Parser Fixes ✅ COMPLETE (2026-02-20)

> All five Phase 1 fixes implemented in `src/preprocessing/parser.py` and
> `src/preprocessing/models/parsing.py`. 71 parser unit tests pass.
> Pre-existing failures in `test_reporting`, `test_retry_mechanism`, `test_state_manager`
> are unrelated to these changes.

### Fix 1A — Replace DOTALL regex in `_flatten_html_nesting` with BS4 for large files ✅

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

### Fix 1B — Document the 10-K / `Edgar10QParser` limitation ✅

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

### Fix 1C — Fix dead code in `_validate_form_type` ✅

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

### Fix 1D — Fix `_to_serializable_dict` tree walk: capture depth, fix level source ✅

**File:** `src/preprocessing/models/parsing.py:143-162`

**Root causes (three compounding bugs):**
1. `parsing.py:155` reads `node.level` — `TreeNode` has no `level` attribute, so the
   `hasattr` check always falls back to `0`. Every serialized node gets `"level": 0`.
2. Even fixing to `node.semantic_element.level` (the `AbstractLevelElement.level` attr)
   would still produce all-zeros: real 10-K HTML uses `<p><b>...</b></p>` styling, not
   semantic `<h1>/<h2>/<h3>` tags, so sec-parser assigns `level=0` to every `TitleElement`.
3. `_to_serializable_dict` iterates `self.tree.nodes` — a **flat** generator of all
   descendants — but never records the parent-child nesting **depth** that the
   `TreeBuilder` does correctly build. Depth is the only hierarchical signal available.

**Change:** Replace the flat loop with a recursive walk that records `depth` (the node's
distance from the tree root) and fixes the level source.

```python
def _serialize_tree_recursive(
    self, nodes: list, depth: int = 0
) -> list[dict]:
    result = []
    for node in nodes:
        elem = node.semantic_element
        result.append({
            'text':  str(node.text) if hasattr(node, 'text') else '',
            'type':  elem.__class__.__name__,
            'level': getattr(elem, 'level', 0),  # HTML heading level (0 for all SEC filings)
            'depth': depth,                       # actual parent-child nesting depth in tree
        })
        result.extend(self._serialize_tree_recursive(node.children, depth + 1))
    return result

# Replace the tree_data block at parsing.py:144-162:
tree_data = self._serialize_tree_recursive(list(self.tree))  # list(tree) → root nodes only
```

**Why `depth` matters for Phase 6:** A `TextElement` at `depth=2` is a content paragraph
nested under a `TitleElement` at `depth=1`, itself under a `TopSectionTitle` at `depth=0`.
This is the signal Fix 6A uses to map each chunk to its `parent_subsection`.

**Also fix:** Remove the `html_tag` field from the `elements_data` block
(`parsing.py:132-135`). It serializes as the Python object repr string
(`"<sec_parser...HtmlTag object at 0x...>"`) — useless and noisy.

---

### Fix 1E — Extract `fiscal_year` from EDGAR header ✅

**File:** `src/preprocessing/parser.py` — `_extract_metadata()` (lines 269–325)

**Problem:** `fiscal_year` is the only `document_info` field with no extraction fix.
Every EDGAR filing header already scanned by `_extract_metadata()` contains:

```
CONFORMED PERIOD OF REPORT:	20251231
```

This is `YYYYMMDD` format; the year is the first 4 characters.

**Change:** Add one regex alongside the existing `cik_match` / `company_name_match`
blocks:

```python
period_match = re.search(
    r'CONFORMED PERIOD OF REPORT[:\s]+(\d{8})', html_content, re.IGNORECASE
)
fiscal_year = period_match.group(1)[:4] if period_match else None

return {
    ...  # existing fields
    'fiscal_year': fiscal_year,
    'period_of_report': period_match.group(1) if period_match else None,
}
```

`fiscal_year` flows through:
`ParsedFiling.metadata` → `ExtractedSection.metadata` → `SegmentedRisks.metadata`
→ promoted to `document_info.fiscal_year` by Fix 6C.

**Fallback (Fix 6C):** If `fiscal_year` is `None` (e.g., filing pre-dates the EDGAR
header format), Fix 6C derives it from the filename stem:
`re.search(r'_(\d{4})[_.]', file_path.stem)`.

---

## Phase 2: Extractor — ToC Contamination (NEW PRIORITY) ✅ COMPLETE (2026-02-20)

> Fix 2A and Fix 2B implemented in `src/preprocessing/extractor.py`.
> `TOC_PATTERNS_COMPILED` imported from constants; `_is_toc_node` method added.
> Both `_extract_section_content` (live tree path) and `extract_risk_factors_from_dict`
> (dict path) now exclude TableElement and ToC-matching nodes from `full_text`.
> 67/69 extractor tests pass; 1 pre-existing failure (form_type in metadata key,
> unrelated to Phase 2); 1 xpass.

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

## Phase 3: Segmenter — Sentence Splitting ✅ COMPLETE (2026-02-20)

> Fix 3A and Fix 3B implemented in `src/preprocessing/segmenter.py`.
> Module-level `_get_sentencizer()` lazy-initialises `spacy.blank("en")` + sentencizer pipe
> (no downloaded model needed). `_get_sentences()` method added to `RiskSegmenter`.
> Both regex split sites replaced (`_split_into_chunks:329`, `_segment_by_semantic_breaks:367`).
> `SEMANTIC_MIN_SEGMENTS = 5` class constant added; threshold check updated from `> 1` to `>= 5`.

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

## Phase 4: Validation — Data Quality Blockers ✅ COMPLETE (2026-02-20)

> All five Phase 4 fixes implemented.
> Fix 4A: `_check_substance` now emits FAIL with `actual=1.0` against `empty_segment_rate`
>   when zero segments extracted; `min_segment_count` threshold added to `health_check.yaml`.
> Fix 4B: `_check_segment_duplicates` method added to `HealthCheckValidator`; called from
>   `_check_domain`; `segment_duplicate_rate` threshold added to `health_check.yaml`.
> Fix 4C: `RISK_KEYWORDS` expanded to 22 domain-specific terms; min count raised 10 → 25.
> Fix 4D: yield denominator now strips HTML tags (falling back to 40% density estimate).
> Fix 4E: `validate_single_file` temp dir now PID-stamped (`_temp_validation_{pid}`).

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

## Phase 5: Cleaning — False Positive Fixes ✅ COMPLETE (2026-02-20)

> Fix 5A implemented in `src/preprocessing/cleaning.py:161`.
> Page-number regex changed from `\d+` to `\d{2,}` — single-digit lines are no longer stripped.

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

## Phase 6: Output Schema

**Goal:** Produce `_segmented_risks.json` files that match the target schema below.
Each pipeline stage owns specific fields; per-stage checkpoints catch gaps early.

### Target Schema

```json
{
  "document_info": {
    "company_name": "Apple Inc.",
    "ticker": "AAPL",
    "cik": "0000320193",
    "sic_code": "3571",
    "sic_name": "ELECTRONIC COMPUTERS",
    "form_type": "10-K",
    "fiscal_year": "2021"
  },
  "processing_metadata": {
    "parser_version": "1.0",
    "finbert_model": "ProsusAI/finbert",
    "chunking_strategy": "sentence_level",
    "max_tokens_per_chunk": 512
  },
  "section_metadata": {
    "identifier": "part1item1a",
    "title": "Item 1A. Risk Factors",
    "cleaning_settings": {
      "removed_html_tags": true,
      "normalized_whitespace": true,
      "removed_page_numbers": true,
      "discarded_tables": true
    },
    "stats": {
      "total_chunks": 3,
      "num_tables": 0
    }
  },
  "chunks": [
    {
      "chunk_id": "1A_001",
      "parent_subsection": "Introduction",
      "text": "..."
    }
  ]
}
```

### Gap Analysis (Current → Target)

| Field | Current State | Target | Owning Stage |
|-------|--------------|--------|--------------|
| `document_info.fiscal_year` | absent | `"2021"` (EDGAR header via Fix 1E; filename fallback in Fix 6C) | Parse (Fix 1E) |
| `document_info.ticker` | always `None` | `"AAPL"` (DEI `dei:TradingSymbol` inline XBRL tag; present in 99.9% of filings) | Parse (Fix 1F) ✅ |
| `processing_metadata` | absent | experiment record: parser version, model, chunking config | Segment (Fix 6B) |
| `section_metadata.cleaning_settings.discarded_tables` | absent | `true` | Clean (Fix 2B) |
| `cleaning_settings` key names | `remove_html_tags` | `removed_html_tags` (past tense) | Clean |
| `chunks[].chunk_id` | `0` (int index) | `"1A_001"` (section-prefixed, 3-digit) | Segment |
| `chunks[].parent_subsection` | absent | `"Introduction"` (nearest preceding `TitleElement`) | Segment |
| Top-level structure | flat `SegmentedRisks` object | `document_info` / `processing_metadata` / `section_metadata` / `chunks` | Segment (Fix 6B) |
| `total_segments` | present | renamed `total_chunks` (under `section_metadata.stats`) | Segment |

### Fix 6A — Sequential `parent_subsection` tracking in extractor

**File:** `src/preprocessing/extractor.py` — `_extract_section_content` and
`extract_risk_factors_from_dict`

**Problem:** `parent_subsection` is not tracked per element. The `subsections` list on
`ExtractedSection` contains the right titles, but they are not mapped to individual
content nodes.

**Approach:** Sequential scan — the nearest preceding `TitleElement` in the content node
list is the `parent_subsection` for all following `TextElement`s until the next title.
This is correct for 10-K Risk Factors sections, where subsection headings appear in
document order.

```python
# In _extract_section_content, after filtering content_nodes (post ToC + table filter):
current_subsection: Optional[str] = None
subsection_map: list[tuple[Any, Optional[str]]] = []

for node in content_nodes:
    if isinstance(node.semantic_element, sp.TitleElement):
        current_subsection = node.text.strip() or current_subsection
    elif hasattr(node, 'text') and node.text.strip():
        subsection_map.append((node, current_subsection))

# Pass subsection_map (node + its subsection) downstream to the segmenter
# via a new ExtractedSection field: node_subsections: List[Tuple[str, Optional[str]]]
```

Add `node_subsections: List[Tuple[str, Optional[str]]] = []` to `ExtractedSection`
(`src/preprocessing/models/extraction.py`). Each entry is `(node_text, subsection_title)`.

---

### Fix 6B — `chunk_id` format + `parent_subsection` field in `RiskSegment`

**Files:**
- `src/preprocessing/models/segmentation.py:14-28` (`RiskSegment`)
- `src/preprocessing/segmenter.py:143-156` (segment construction)

**Change 1 — `RiskSegment` model:**

```python
class RiskSegment(BaseModel):
    chunk_id: str                          # was: index: int  →  now "1A_001", "1A_002"
    parent_subsection: Optional[str] = None  # NEW — nearest preceding TitleElement text
    text: str
    word_count: int = 0
    char_count: int = 0
```

**Change 2 — Segmenter construction** (`segmenter.py:segment_extracted_section`):

When iterating over sentences/chunks to build `RiskSegment` objects, use
`extracted_section.node_subsections` (populated by Fix 6A) to resolve which subsection
each chunk belongs to, and format `chunk_id` as `f"1A_{i+1:03d}"`:

```python
segments = []
for i, (text, subsection) in enumerate(chunk_texts_with_subsections):
    segments.append(RiskSegment(
        chunk_id=f"1A_{i+1:03d}",
        parent_subsection=subsection,
        text=text,
    ))
```

**Change 3 — `SegmentedRisks` top-level restructure** (`segmentation.py:31-58`):

Rename `segments` → `chunks`, `total_segments` → `total_chunks`, and group output
fields into `document_info`, `processing_metadata`, `section_metadata`, `chunks` as
per the target schema. The `save_to_json` / `load_from_json` methods must be updated
to write and read the new structure.

`processing_metadata` field sources:

| Field | Source |
|-------|--------|
| `parser_version` | hardcoded `"1.0"` — matches `ParsedFiling._to_serializable_dict` version field (`parsing.py:165`) |
| `finbert_model` | `settings.models.finbert_model_name` (config) |
| `chunking_strategy` | `segmenter.strategy` attribute or hardcoded `"sentence_level"` |
| `max_tokens_per_chunk` | `settings.segmentation.max_tokens` (config) |

`processing_metadata` is written by `SegmentedRisks.save_to_json` at serialization time
(not stored as model fields — avoids coupling the Pydantic model to config). The segmenter
passes a `processing_metadata: Dict[str, Any]` argument to `save_to_json`.

---

### Per-Stage Validation Checkpoints

#### Stage 1 — After Parse (`*_parsed.json`)

Verify all `document_info` fields flow into the pipeline and `fiscal_year` resolves.

```bash
python -c "
import json, re, sys
d = json.load(open(sys.argv[1]))
meta = d.get('metadata', {})
required = ['company_name', 'cik', 'sic_code', 'sic_name', 'form_type']
missing = [f for f in required if not meta.get(f)]
fy = meta.get('fiscal_year') or (re.search(r'_(\d{4})[_.]', sys.argv[1]) or [None, 'MISSING'])[1]
print('missing identity fields:', missing or 'none')
print('fiscal_year:', fy)
" data/interim/parsed/<stem>_parsed.json
```

**Pass criteria:** `missing` is empty; `fiscal_year` is a 4-digit string.

---

#### Stage 2 — After Extract (`*_extracted_risks.json`)

Verify `section_metadata` fields are present and `TitleElement` nodes exist for
`parent_subsection` mapping.

```bash
python -c "
import json, sys
d = json.load(open(sys.argv[1]))
print('identifier:', d.get('identifier'))
print('title:', d.get('title'))
print('subsections:', d.get('subsections', []))
print('num_tables (stats):', d.get('stats', {}).get('num_tables'))
title_els = [e for e in d.get('elements', []) if e.get('type') == 'TitleElement']
print('TitleElements:', len(title_els), '(needed for parent_subsection mapping)')
" data/interim/extracted/<stem>_extracted_risks.json
```

**Pass criteria:**
- `identifier` is non-empty (`"part1item1a"`)
- `subsections` is a non-empty list
- `stats.num_tables` is an integer (0 is valid)
- At least one `TitleElement` present in `elements`

---

#### Stage 3 — After Clean (`*_cleaned_risks.json`)

Verify `cleaning_settings` has all 4 past-tense keys and no HTML remains in text.

```bash
python -c "
import json, re, sys
d = json.load(open(sys.argv[1]))
cs = d.get('metadata', {}).get('cleaning_settings', {})
required = ['removed_html_tags', 'normalized_whitespace', 'removed_page_numbers', 'discarded_tables']
missing = [k for k in required if k not in cs]
html_left = bool(re.search(r'<[a-zA-Z][^>]*>', d.get('text', '')))
print('cleaning_settings:', json.dumps(cs))
print('missing keys:', missing or 'none')
print('HTML remaining:', html_left)
" data/interim/extracted/<stem>_cleaned_risks.json
```

**Pass criteria:**
- All 4 keys present (requires Fix 2B to add `discarded_tables`)
- Keys use past-tense form (`removed_*`, `normalized_*`)
- No HTML tags remain in `text`

---

#### Stage 4 — After Segment (`*_segmented_risks.json`)

Verify the complete target schema: top-level groups, `chunk_id` format, and
`parent_subsection` on every chunk.

```bash
python -c "
import json, re, sys
d = json.load(open(sys.argv[1]))
di = d.get('document_info', {})
pm = d.get('processing_metadata', {})
sm = d.get('section_metadata', {})
chunks = d.get('chunks', [])
print('document_info fields:', sorted(di.keys()))
print('fiscal_year:', di.get('fiscal_year'))
print('processing_metadata fields:', sorted(pm.keys()))
print('cleaning_settings keys:', sorted(sm.get('cleaning_settings', {}).keys()))
print('total_chunks:', sm.get('stats', {}).get('total_chunks'), '/ actual:', len(chunks))
bad_ids  = [c['chunk_id'] for c in chunks if not re.match(r'^1A_\d{3}$', c.get('chunk_id',''))]
no_sub   = [c['chunk_id'] for c in chunks if not c.get('parent_subsection')]
print('malformed chunk_ids:', bad_ids or 'none')
print('chunks missing parent_subsection:', no_sub or 'none')
" data/processed/<run_dir>/<stem>_segmented_risks.json
```

**Pass criteria:**
- `document_info` contains all 7 fields including `fiscal_year`
- `processing_metadata` contains all 4 fields: `parser_version`, `finbert_model`, `chunking_strategy`, `max_tokens_per_chunk`
- `section_metadata.cleaning_settings` has 4 past-tense keys
- `stats.total_chunks` equals `len(chunks)`
- Every `chunk_id` matches `r'^1A_\d{3}$'`
- No chunk missing `parent_subsection`

---

## Verification

### Automated checks
```bash
# Run existing tests
python -m pytest tests/ -x -q

# Run pre-fix baseline audit
python scripts/validation/data_quality/check_corpus_quality_audit.py \
    --run-dir data/processed/<run_dir> --output audit_baseline.md

# Validate a single 10-K run dir
python scripts/validation/data_quality/check_preprocessing_single.py \
    --run-dir data/processed/<run_dir> -v

# Batch validate with fail-on-warn for CI
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir data/processed/<run_dir> --fail-on-warn
```

### Manual spot-checks
1. Parse one known 10-K → confirm Item 1A section is found
2. Count chunks → confirm > 5 chunks extracted
3. Check chunk text → confirm no `<td>`, `<tr>`, or raw number sequences
4. Run Stage 1–4 checkpoint commands on a sample filing → all pass criteria met
5. Run batch validator on a corpus dir → confirm 0-segment filings are FAIL

---

## Implementation Order (Revised 2026-02-18, updated 2026-02-20)

> Reordered based on cross-referencing past research. Section boundary fix removed
> (extractor works). ToC contamination elevated to #1 priority (56.6% failure rate,
> DEFERRED since Dec 2025). flatten_html fix revised from "disable" to "BS4 for large files".

### Done ✅

- **Fix 1A** (BS4 flatten for large files) — size gate + `_flatten_html_nesting_bs4` added; `parser.py:430-499`
- **Fix 1B** (10-K / Edgar10QParser doc + UserWarning) — comment updated, `warnings.warn` added at `parse_from_content`; `parser.py:81-197`
- **Fix 1C** (dead `"10-K"` branches in `_validate_form_type`) — replaced with single-string equality checks; `parser.py:268-277`
- **Fix 1D** (recursive tree serializer, `depth` field, drop `html_tag` noise) — `_serialize_tree_recursive` added, flat walk replaced; `parsing.py:111-155`
- **Fix 1E** (`fiscal_year` + `period_of_report` from EDGAR header) — two new keys in `_extract_metadata` return dict; `parser.py:320-342`
- **Fix 1F** (`ticker` from DEI inline XBRL `dei:TradingSymbol` tag) — regex extracts plain-text ticker from both direct-text and `<span>`-wrapped formats; present in 99.9% of corpus; `parser.py:328-335`

### Remaining

0. **Audit script** (`check_corpus_quality_audit.py`) — baseline before any change
1. **Fix 4A** (zero segments = FAIL) ✅ — stops broken filings entering training data
2. **Fix 2A** (ToC node filter in extractor) ✅ — fixes the #1 known data quality gap
3. **Fix 2B** (exclude tables from text) ✅ — clean training samples
4. **Fix 3A** (spaCy sentence splitting) ✅ — correct segment boundaries
5. **Fix 4B** (segment-level dedup) ✅ — training data quality
6. **Fix 4C + 4D** (keyword + yield metric) ✅ — validation calibration
7. **Fix 5A** (narrow page number regex) ✅ — cleaning precision
8. **Fix 4E** (batch validator race condition) ✅ — housekeeping
9. **Fix 6A** (parent_subsection tracking in extractor) — sequential TitleElement scan; populate `node_subsections` on `ExtractedSection`
10. **Fix 6B** (chunk_id + RiskSegment model) — `"1A_NNN"` chunk ids, `parent_subsection` field, `SegmentedRisks` top-level restructure
11. **Fix 6C** (SegmentedRisks restructure + cleaning_settings rename + fiscal_year promotion) — promote `fiscal_year` from metadata (Fix 1E primary, filename fallback); rename `remove_*` keys to `removed_*`; add `discarded_tables` flag

**REMOVED:**
- ~~Fix 2A (re.search boundary)~~ — extractor `_is_next_section()` works correctly,
  zero overshoot in 309 files. Validator false positive fix is in `check_extractor_batch.py`
  (separate QA tooling, not in scope for training data quality).
