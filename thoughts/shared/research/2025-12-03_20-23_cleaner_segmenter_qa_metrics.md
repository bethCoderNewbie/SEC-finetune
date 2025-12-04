---
date: 2025-12-03T20:23:52-06:00
git_commit: f599254
branch: main
repository: SEC finetune
researcher: bethCoderNewbie
topic: Text Cleaner & Risk Segmenter QA Metrics
files_analyzed:
  - src/preprocessing/cleaning.py
  - src/preprocessing/segmenter.py
---

# Text Cleaner & Risk Segmenter QA Metrics

## Overview

This document defines the evaluation metrics framework for validating the quality of:
1. **TextCleaner** (`src/preprocessing/cleaning.py`) - Text sanitization
2. **RiskSegmenter** (`src/preprocessing/segmenter.py`) - Risk factor segmentation

---

## Part 1: Text Cleaner | `src/preprocessing/cleaning.py`

**Goal:** Prove that text is human-readable and machine-ready without accidentally deleting actual sentences.

### 1. Hygiene & Artifact Metrics

| Metric | Formula | Target | Purpose |
|--------|---------|--------|---------|
| **HTML Tag Removal Rate** | `1 - (tags_after / tags_before)` | 100% | Verify all HTML tags removed |
| **Entity Decode Rate** | `1 - (entities_after / entities_before)` | 100% | Verify `&amp;`, `&nbsp;` decoded |
| **Excessive Whitespace Ratio** | `len(re.findall(r'\s{3,}', text)) / len(text)` | < 0.01 | No triple+ spaces remain |
| **Quote Normalization** | Count of `"` `"` `'` `'` remaining | 0 | Curly quotes replaced |

**Test Cases:**
```python
def test_html_removal_rate(cleaner, raw_html, expected_text):
    """Verify HTML tags are completely removed."""
    tags_before = len(re.findall(r'<[^>]+>', raw_html))
    cleaned = cleaner.clean_html_text(raw_html)
    tags_after = len(re.findall(r'<[^>]+>', cleaned))
    assert tags_after == 0, f"Remaining tags: {tags_after}"
    assert tags_before > 0, "Test requires HTML input"

def test_entity_decode_rate(cleaner, text_with_entities):
    """Verify HTML entities are decoded."""
    entities = ['&amp;', '&nbsp;', '&lt;', '&gt;', '&#\\d+;']
    for entity in entities:
        assert not re.search(entity, cleaner.clean_html_text(text_with_entities))
```

### 2. Continuity Metrics (Page/Header Removal)

| Metric | Formula | Target | Purpose |
|--------|---------|--------|---------|
| **Page Number Removal** | `1 - (page_refs_after / page_refs_before)` | 100% | `Page 12`, `-12-` removed |
| **TOC Entry Removal** | `1 - (toc_after / toc_before)` | 100% | `Item 1..... 5` removed |
| **Sentence Preservation Rate** | `sentences_after / sentences_before` | > 95% | Don't delete real content |
| **Word Count Ratio** | `words_after / words_before` | 85-99% | Controlled reduction |

**Key Patterns (from cleaning.py:151-158):**
```python
# Page number patterns
r'^[\s\-]*\d+[\s\-]*$'           # Standalone: "12", "-12-"
r'^[\s\-]*Page\s+\d+[\s\-]*$'    # "Page 12"
r'\s*\.{3,}\s*\d+\s*$'           # TOC: "... 45"
```

**Test Cases:**
```python
def test_page_artifacts_removed(cleaner):
    """Verify page numbers removed without destroying sentences."""
    text = """
    Page 12

    The company reported strong earnings.

    -15-

    Revenue increased by 20%.
    """
    cleaned = cleaner.clean_text(text)
    assert "Page 12" not in cleaned
    assert "-15-" not in cleaned
    assert "strong earnings" in cleaned  # Sentence preserved
    assert "Revenue increased" in cleaned

def test_sentence_preservation(cleaner, original_text):
    """Verify sentence count is preserved (>95%)."""
    sentences_before = len(re.findall(r'[.!?]', original_text))
    cleaned = cleaner.clean_text(original_text)
    sentences_after = len(re.findall(r'[.!?]', cleaned))
    ratio = sentences_after / sentences_before if sentences_before > 0 else 1
    assert ratio >= 0.95, f"Sentence preservation: {ratio:.2%}"
```

### 3. Data Integrity Metrics

| Metric | Formula | Target | Purpose |
|--------|---------|--------|---------|
| **Non-Empty Output** | `len(cleaned) > 0` | True | Never return empty for non-empty input |
| **Financial Figure Preservation** | `$X.XX` patterns before/after | 100% | Don't destroy dollar amounts |
| **Date Preservation** | Date patterns before/after | 100% | Don't destroy dates |
| **Percentage Preservation** | `X%` patterns before/after | 100% | Don't destroy percentages |

**Test Cases:**
```python
def test_financial_figures_preserved(cleaner):
    """Verify dollar amounts, percentages, dates survive cleaning."""
    text = "Revenue was $1.5 billion in 2023, up 15% from $1.3 billion in 2022."
    cleaned = cleaner.clean_text(text)

    assert "$1.5 billion" in cleaned
    assert "15%" in cleaned
    assert "$1.3 billion" in cleaned
    assert "2023" in cleaned
    assert "2022" in cleaned

def test_non_empty_output(cleaner, valid_input):
    """Verify non-empty input never produces empty output."""
    cleaned = cleaner.clean_text(valid_input)
    assert len(cleaned) > 0, "Non-empty input produced empty output"
```

### Summary Validation Table - Text Cleaner

| Category | Metric | Source Line | Test Method |
|----------|--------|-------------|-------------|
| Hygiene | HTML Tag Removal | `cleaning.py:282-310` | `test_html_removal_rate` |
| Hygiene | Entity Decode | `cleaning.py:302-308` | `test_entity_decode_rate` |
| Hygiene | Whitespace Normalization | `cleaning.py:117-139` | `test_whitespace_normalization` |
| Continuity | Page Number Removal | `cleaning.py:141-158` | `test_page_artifacts_removed` |
| Continuity | TOC Removal | `cleaning.py:160-178` | `test_toc_removal` |
| Continuity | Sentence Preservation | N/A (implicit) | `test_sentence_preservation` |
| Integrity | Financial Figures | N/A (implicit) | `test_financial_figures_preserved` |
| Integrity | Non-Empty Output | `cleaning.py:93-94` | `test_non_empty_output` |

---

## Part 2: Risk Segmenter | `src/preprocessing/segmenter.py`

**Goal:** Validate that risk factors are properly segmented into individual, coherent risk statements.

### 1. Segmentation Distribution

#### Segment Count per Document

| Metric | Formula | Target | Purpose |
|--------|---------|--------|---------|
| **Segment Count** | `len(segments)` | 5-50 | Reasonable range for 10-K filings |
| **Non-Zero Segments** | `len(segments) > 0` | True | Never return empty for non-empty input |
| **Minimum Viable Segments** | `len(segments) >= 3` | True | Fallback triggers at < 3 |

**Test Cases:**
```python
def test_segment_count_range(segmenter, risk_factors_text):
    """Verify segment count is within expected range."""
    segments = segmenter.segment_risks(risk_factors_text)
    assert 5 <= len(segments) <= 50, f"Segment count: {len(segments)}"

def test_non_empty_segmentation(segmenter, valid_risk_text):
    """Verify non-empty input produces segments."""
    segments = segmenter.segment_risks(valid_risk_text)
    assert len(segments) > 0, "No segments produced"
```

#### Segment Length Consistency (Gini Coefficient)

| Metric | Formula | Target | Purpose |
|--------|---------|--------|---------|
| **Gini Coefficient** | Standard Gini formula | < 0.5 | Balanced segment lengths |
| **CV of Length** | `std(lengths) / mean(lengths)` | < 1.0 | Low variation |
| **Min/Max Ratio** | `min(lengths) / max(lengths)` | > 0.1 | No extreme outliers |

```python
def calculate_gini(lengths: List[int]) -> float:
    """Calculate Gini coefficient for segment length distribution."""
    n = len(lengths)
    if n == 0:
        return 0.0
    sorted_lengths = sorted(lengths)
    cumsum = sum((i + 1) * length for i, length in enumerate(sorted_lengths))
    return (2 * cumsum) / (n * sum(sorted_lengths)) - (n + 1) / n

def test_segment_length_consistency(segmenter, risk_text):
    """Verify segment lengths are balanced."""
    segments = segmenter.segment_risks(risk_text)
    lengths = [len(s) for s in segments]
    gini = calculate_gini(lengths)
    assert gini < 0.5, f"Gini coefficient: {gini:.3f} (too imbalanced)"
```

### 2. Fallback Logic Validation

#### Method Distribution (Header vs. Paragraph vs. Semantic)

| Metric | Description | Target | Purpose |
|--------|-------------|--------|---------|
| **Primary Method Success** | Semantic/Header yields >= 2 segments | Prefer | Track method used |
| **Fallback Rate** | % of docs using paragraph fallback | < 30% | Headers should work often |
| **Cascade Depth** | Which level of fallback triggered | Log | Debug segmentation issues |

**Fallback Logic (from segmenter.py:58-99):**
```
1. Try semantic segmentation (if model available, needs > 1 segment)
2. Fallback to header-based segmentation
3. If < 3 segments, fallback to paragraph-based
4. Apply filtering and split long segments
```

**Test Cases:**
```python
def test_fallback_cascade(segmenter, various_documents):
    """Track which segmentation method is used."""
    results = []
    for doc in various_documents:
        with capture_logs() as logs:
            segments = segmenter.segment_risks(doc['text'])
            method = 'semantic' if 'semantic' in logs else \
                     'header' if 'header' not in logs else 'paragraph'
            results.append({
                'doc_id': doc['id'],
                'method': method,
                'segment_count': len(segments)
            })

    fallback_rate = sum(1 for r in results if r['method'] == 'paragraph') / len(results)
    assert fallback_rate < 0.3, f"High fallback rate: {fallback_rate:.1%}"
```

### 3. Semantic Quality (Filtering)

| Metric | Formula | Target | Purpose |
|--------|---------|--------|---------|
| **Min Length Filter** | `len(segment) >= min_length` | All pass | No tiny fragments |
| **Word Count Filter** | `len(segment.split()) >= 10` | All pass | No header-only segments |
| **Non-Risk Content Filter** | See `_is_non_risk_content()` | 0 false positives | Don't filter real risks |

**Filter Logic (from segmenter.py:159-215):**
```python
# Rejection criteria (segmenter.py:174-186):
# - len(segment) < min_length
# - len(segment.split()) < 10 words
# - Contains TOC indicators and len < 200

# Non-risk indicators (segmenter.py:203-209):
non_risk_indicators = [
    'table of contents',
    'page ',
    'item 1a',
    'risk factors',
    'forward-looking statements',
]
```

**Test Cases:**
```python
def test_min_length_enforcement(segmenter):
    """Verify all segments meet minimum length."""
    text = "Risk 1: Short. Risk 2: This is a properly detailed risk factor."
    segments = segmenter.segment_risks(text)
    for seg in segments:
        assert len(seg) >= segmenter.min_length

def test_word_count_enforcement(segmenter):
    """Verify all segments have >= 10 words."""
    segments = segmenter.segment_risks(valid_risk_text)
    for seg in segments:
        word_count = len(seg.split())
        assert word_count >= 10, f"Segment has only {word_count} words"

def test_no_false_positive_filtering(segmenter):
    """Verify real risk content is not filtered out."""
    text = """
    Our page load times may affect customer experience and revenue.
    This risk factor describes how item 1a compliance affects operations.
    Forward-looking statements about our growth strategy are uncertain.
    """
    segments = segmenter.segment_risks(text)
    # These should NOT be filtered (they're real risks mentioning keywords)
    assert any("page load" in s for s in segments)
```

### Summary Validation Table - Risk Segmenter

| Category | Metric | Source Line | Test Method |
|----------|--------|-------------|-------------|
| Distribution | Segment Count Range | `segmenter.py:58-100` | `test_segment_count_range` |
| Distribution | Gini Coefficient | N/A (quality metric) | `test_segment_length_consistency` |
| Distribution | Min/Max Ratio | N/A (quality metric) | `test_segment_length_consistency` |
| Fallback | Primary Method Success | `segmenter.py:73-86` | `test_fallback_cascade` |
| Fallback | Fallback Rate | `segmenter.py:89-92` | `test_fallback_cascade` |
| Quality | Min Length Filter | `segmenter.py:174-176` | `test_min_length_enforcement` |
| Quality | Word Count Filter | `segmenter.py:178-180` | `test_word_count_enforcement` |
| Quality | Non-Risk Filter | `segmenter.py:182-215` | `test_no_false_positive_filtering` |

---

## Test Implementation Locations

| Component | Test File | Status |
|-----------|-----------|--------|
| TextCleaner | `tests/preprocessing/test_cleaner.py` | To create |
| RiskSegmenter | `tests/preprocessing/test_segmenter.py` | To create |

---

## Configuration Dependencies

Both modules depend on settings from `src/config/`:
- `settings.preprocessing.min_segment_length` (default: 100)
- `settings.preprocessing.max_segment_length` (default: 5000)

---

## Next Steps

1. Create `tests/preprocessing/test_cleaner.py` with hygiene, continuity, and integrity tests
2. Create `tests/preprocessing/test_segmenter.py` with distribution, fallback, and quality tests
3. Add sample fixtures from actual 10-K filings for realistic testing
4. Integrate with existing test suite (`pytest tests/preprocessing/`)
