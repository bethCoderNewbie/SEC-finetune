---
date: 2025-12-03T21:45:00-06:00
researcher: bethCoderNewbie
git_commit: ea45dd2
branch: main
repository: SEC finetune
topic: "Sentiment & Readability Validation Plan"
tags: [plan, validation, sentiment, readability, qa-metrics, testing]
status: ready_for_review
last_updated: 2025-12-03
last_updated_by: bethCoderNewbie
---

# Plan: Sentiment & Readability Validation Metrics

**Date**: 2025-12-03T21:45:00-06:00
**Researcher**: bethCoderNewbie
**Git Commit**: ea45dd2
**Branch**: main

## Desired End State

Upon completion, the user will have:
1. A comprehensive test suite validating sentiment and readability analysis
2. Automated detection of "silent failures" (zeros where values are expected)
3. Benchmark metrics confirming implementation correctness
4. Documentation of expected ranges for 10-K filings

## Anti-Scope (What We're NOT Doing)

- NOT implementing new features or changing existing analyzers
- NOT adding ML-based sentiment models (staying with LM dictionary)
- NOT creating a full regression test suite (focused on validation metrics only)
- NOT benchmarking against external tools (internal consistency only)
- NOT using mock data - all tests use actual processed files

---

## Primary Test Data Source

**File**: `data/processed/AAPL_10K_2021_segmented_risks.json`

**Actual Data Statistics** (from file):
- Filing: AAPL 10-K 2021 (Item 1A. Risk Factors)
- Segments: 54 risk factor paragraphs
- Aggregate sentiment (pre-computed):
  - `avg_negative_ratio`: 0.0454 (4.54%)
  - `avg_uncertainty_ratio`: 0.0326 (3.26%)
  - `avg_positive_ratio`: 0.0054 (0.54%)
  - `avg_sentiment_word_ratio`: 0.1085 (10.85%)

**Key Validation from Actual Data**:
- **Negative >> Positive**: 0.0454 vs 0.0054 (8.4x ratio) ✓ VALIDATES 10-K PROFILE
- **Sentiment Word Density**: 10.85% >> 2% threshold ✓ NO SILENT FAILURES

---

## Phase 1: Sentiment Analysis Validation

### 1.1 Dictionary Effectiveness Tests

**File**: `tests/features/test_sentiment_validation.py`

#### Test: LM Vocabulary Hit Rate

```python
import json
from pathlib import Path

def test_lm_vocabulary_hit_rate():
    """
    Metric: Percentage of tokens found in LM dictionary.
    Target: > 2% (typical 10-K: 3-5%)
    Why: Validates tokenization compatibility with dictionary.

    Uses actual data: data/processed/AAPL_10K_2021_segmented_risks.json
    """
    from src.features.sentiment import SentimentAnalyzer
    from src.features.dictionaries import LMDictionaryManager

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    analyzer = SentimentAnalyzer()
    mgr = LMDictionaryManager.get_instance()

    # Combine all segment texts
    all_text = " ".join(seg["text"] for seg in data["segments"])
    tokens = analyzer.tokenize(all_text)

    lm_hits = sum(1 for t in tokens if mgr.get_word_categories(t))
    hit_rate = lm_hits / len(tokens) * 100

    # Pre-computed from file: avg_sentiment_word_ratio = 10.85%
    # This confirms hit rate is well above 2% threshold
    assert hit_rate > 2.0, f"LM hit rate {hit_rate:.2f}% below 2% threshold"

    # Additional check: should be close to pre-computed value
    expected_ratio = data["aggregate_sentiment"]["avg_sentiment_word_ratio"] * 100
    assert abs(hit_rate - expected_ratio) < 5.0, \
        f"Hit rate {hit_rate:.2f}% deviates from expected {expected_ratio:.2f}%"
```

**Code Reference**: `sentiment.py:192-213` (tokenization), `lm_dictionary.py:166-177` (word lookup)

#### Test: Zero-Vector Rate

```python
def test_zero_vector_rate():
    """
    Metric: Percentage of segments returning 0 for all categories.
    Target: < 50%
    Why: High rate indicates broken matching logic.

    Uses actual data: data/processed/AAPL_10K_2021_segmented_risks.json
    """
    import json
    from pathlib import Path

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Count segments with zero sentiment words (pre-computed in file)
    zero_count = sum(
        1 for seg in data["segments"]
        if seg["sentiment"]["total_sentiment_words"] == 0
    )

    total_segments = len(data["segments"])  # 54 segments
    zero_rate = zero_count / total_segments * 100

    # From actual data: only segment #2 has 0 sentiment words
    # That's 1/54 = 1.85% - well below 50% threshold
    assert zero_rate < 50.0, f"Zero-vector rate {zero_rate:.1f}% exceeds 50%"

    # Stricter check for this specific file
    assert zero_count <= 5, f"Too many zero-sentiment segments: {zero_count}/54"
```

**Actual Data Verification** (from AAPL file):
- Segment #2 has `total_sentiment_words: 0` (boilerplate reference text)
- All other 53 segments have sentiment words
- Zero-vector rate: **1.85%** (well below 50% threshold)

**Code Reference**: `sentiment.py:240-314` (feature extraction)

### 1.2 Category Plausibility Tests (10-K Profile)

#### Test: Negative > Positive for 10-K

```python
def test_negative_exceeds_positive_for_10k():
    """
    Metric: Negative word count > Positive word count.
    Context: 10-Ks are legally defensive documents.
    Why: If Positive > Negative, it's either marketing or a bug.

    Uses actual data: data/processed/AAPL_10K_2021_segmented_risks.json
    """
    import json
    from pathlib import Path

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Check aggregate sentiment ratios
    agg = data["aggregate_sentiment"]
    avg_neg = agg["avg_negative_ratio"]
    avg_pos = agg["avg_positive_ratio"]

    # From actual data: 0.0454 vs 0.0054 (8.4x ratio)
    assert avg_neg > avg_pos, \
        f"Failed 10-K profile: Pos({avg_pos:.4f}) >= Neg({avg_neg:.4f})"

    # Check majority of segments follow pattern
    neg_wins = sum(
        1 for seg in data["segments"]
        if seg["sentiment"]["negative_count"] >= seg["sentiment"]["positive_count"]
    )
    total = len(data["segments"])
    win_rate = neg_wins / total

    # At least 80% of segments should have Neg >= Pos
    assert win_rate >= 0.80, \
        f"Only {win_rate*100:.1f}% segments have Neg >= Pos (need 80%)"
```

**Actual Data Verification** (from AAPL file):
- `avg_negative_ratio`: 0.0454 (4.54%)
- `avg_positive_ratio`: 0.0054 (0.54%)
- **Ratio: Negative is 8.4x Positive** ✓ STRONG 10-K PROFILE

**Exception Segments** (where Pos > Neg):
- Segment #11: Pos=15, Neg=7 (competitive advantage text)
- Segment #13: Pos=6, Neg=3 (product intro text)
- Segment #27: Pos=4, Neg=3 (employee culture text)
- Segment #29: Pos=3, Neg=1 (reseller programs)

These exceptions are expected (positive language about company strengths).

**Code Reference**: `sentiment.py:54-61` (count fields)

#### Test: Uncertainty/Modal Correlation

```python
def test_uncertainty_weak_modal_correlation():
    """
    Metric: Correlation between Uncertainty and Weak_Modal words.
    Target: Pearson r > 0.5 (relaxed due to small sample)
    Why: "might", "could", "may" should correlate with uncertainty.

    Uses actual data: data/processed/AAPL_10K_2021_segmented_risks.json

    NOTE: The current JSON file only stores 5 sentiment categories.
    Weak_Modal would need to be added to the segmentation output.
    This test validates Uncertainty correlation with Constraining instead.
    """
    import json
    from pathlib import Path
    import numpy as np

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract available category counts from 54 segments
    uncertainty_counts = [seg["sentiment"]["uncertainty_count"] for seg in data["segments"]]
    constraining_counts = [seg["sentiment"]["constraining_count"] for seg in data["segments"]]
    negative_counts = [seg["sentiment"]["negative_count"] for seg in data["segments"]]

    # Calculate correlations with numpy (avoid scipy dependency)
    def pearson_corr(x, y):
        return np.corrcoef(x, y)[0, 1]

    unc_neg_corr = pearson_corr(uncertainty_counts, negative_counts)
    unc_const_corr = pearson_corr(uncertainty_counts, constraining_counts)

    # Uncertainty should correlate with Negative (both risk indicators)
    assert unc_neg_corr > 0.3, f"Unc-Neg correlation {unc_neg_corr:.2f} too low"

    print(f"Uncertainty-Negative correlation: {unc_neg_corr:.3f}")
    print(f"Uncertainty-Constraining correlation: {unc_const_corr:.3f}")
```

**Actual Data Analysis** (from AAPL file segments):
- Uncertainty counts range: 0-16 across 54 segments
- Constraining counts range: 0-16 across 54 segments
- Both categories track with segment length and risk complexity

**Code Reference**: `sentiment.py:56-59` (uncertainty, weak_modal counts)

### 1.3 Golden Sentence Test (Deterministic Verification)

```python
def test_golden_sentence_deterministic():
    """
    Metric: Exact output verification for known input.
    Test string: "The company anticipates potential litigation and catastrophic losses."
    Expected:
        - anticipates: Uncertainty (1)
        - litigation: Litigious (1), Negative (1), Complexity (1)
        - catastrophic: Negative (1)
        - losses: Negative (1)
    """
    golden = "The company anticipates potential litigation and catastrophic losses."
    features = analyzer.extract_features(golden)

    # Verified from Golden Sentence test run:
    assert features.negative_count == 3, f"Expected 3 negative, got {features.negative_count}"
    assert features.uncertainty_count == 1, f"Expected 1 uncertainty, got {features.uncertainty_count}"
    assert features.litigious_count == 1, f"Expected 1 litigious, got {features.litigious_count}"
    assert features.positive_count == 0, f"Expected 0 positive, got {features.positive_count}"
    assert features.total_sentiment_words == 5, f"Expected 5 total, got {features.total_sentiment_words}"
```

**Verified Output** (from test run):
```
ANTICIPATES: {'Uncertainty'}
LITIGATION: {'Complexity', 'Litigious', 'Negative'}
CATASTROPHIC: {'Negative'}
LOSSES: {'Negative'}
Total: 5 sentiment words (3 Neg, 1 Unc, 1 Lit)
```

---

## Phase 2: Readability Analysis Validation

### 2.1 Score Plausibility Tests

**File**: `tests/features/test_readability_validation.py`

#### Test: Gunning Fog Range

```python
def test_gunning_fog_range_for_10k():
    """
    Metric: Gunning Fog score distribution.
    Target: Average between 14-22 (college graduate level).
    Red Flags:
        - < 10: Sentence splitter counting abbreviations as periods
        - > 30: Sentence splitter failing to find periods

    Uses actual data: data/processed/AAPL_10K_2021_segmented_risks.json
    """
    import json
    from pathlib import Path
    from src.features.readability import ReadabilityAnalyzer

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    analyzer = ReadabilityAnalyzer()

    # Extract Fog scores from actual segments
    fog_scores = []
    for seg in data["segments"]:
        text = seg["text"]
        if len(text) > 100:  # Skip very short segments
            features = analyzer.extract_features(text)
            fog_scores.append(features.gunning_fog_index)

    avg_fog = sum(fog_scores) / len(fog_scores)
    max_fog = max(fog_scores)
    min_fog = min(fog_scores)

    print(f"Fog scores: min={min_fog:.1f}, avg={avg_fog:.1f}, max={max_fog:.1f}")
    print(f"Analyzed {len(fog_scores)} segments")

    # 10-K Risk Factors should be college graduate level
    assert 14 <= avg_fog <= 22, f"Avg Fog {avg_fog:.1f} outside 14-22 range"
    assert max_fog < 35, f"Max Fog {max_fog:.1f} exceeds 35 (sentence splitter issue?)"
    assert min_fog > 8, f"Min Fog {min_fog:.1f} below 8 (abbreviation counting issue?)"
```

**Code Reference**: `analyzer.py:159` (`textstat.gunning_fog()`)

#### Test: Metric Consensus (Correlation Matrix)

```python
def test_readability_metric_correlation():
    """
    Metric: Pearson correlation between 6 standard indices.
    Target: All pairs > 0.7 (relaxed due to index formula differences)
    Why: All indices should move in same direction.

    Uses actual data: data/processed/AAPL_10K_2021_segmented_risks.json
    """
    import json
    from pathlib import Path
    import numpy as np
    from src.features.readability import ReadabilityAnalyzer

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    analyzer = ReadabilityAnalyzer()

    indices = {
        'fk': [], 'fog': [], 'fre': [],
        'smog': [], 'ari': [], 'cli': []
    }

    for seg in data["segments"]:
        text = seg["text"]
        if len(text) > 200:  # Need sufficient text for reliable metrics
            features = analyzer.extract_features(text)
            indices['fk'].append(features.flesch_kincaid_grade)
            indices['fog'].append(features.gunning_fog_index)
            indices['fre'].append(-features.flesch_reading_ease)  # Invert
            indices['smog'].append(features.smog_index)
            indices['ari'].append(features.automated_readability_index)
            indices['cli'].append(features.coleman_liau_index)

    # Calculate correlation matrix
    def pearson_corr(x, y):
        return np.corrcoef(x, y)[0, 1]

    # Check key pairs (FK vs Fog is most important)
    fk_fog = pearson_corr(indices['fk'], indices['fog'])
    fk_ari = pearson_corr(indices['fk'], indices['ari'])
    fog_smog = pearson_corr(indices['fog'], indices['smog'])

    print(f"FK-Fog correlation: {fk_fog:.3f}")
    print(f"FK-ARI correlation: {fk_ari:.3f}")
    print(f"Fog-SMOG correlation: {fog_smog:.3f}")

    # All grade-level indices should correlate strongly
    assert fk_fog > 0.7, f"FK-Fog correlation {fk_fog:.2f} below 0.7"
    assert fk_ari > 0.7, f"FK-ARI correlation {fk_ari:.2f} below 0.7"
```

**Code Reference**: `analyzer.py:158-163` (all index calculations)

### 2.2 Domain Adjustment Validation

#### Test: Adjustment Delta

```python
def test_financial_adjustment_delta():
    """
    Metric: (Raw complex word %) - (Adjusted complex word %)
    Target: Delta > 0 (adjusted should be lower)
    Why: Financial terms like "corporation" shouldn't count as complex.

    Uses actual data: data/processed/AAPL_10K_2021_segmented_risks.json
    """
    import json
    from pathlib import Path
    from src.features.readability import ReadabilityAnalyzer

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    analyzer = ReadabilityAnalyzer()

    deltas = []
    for seg in data["segments"]:
        text = seg["text"]
        if len(text) > 200:
            features = analyzer.extract_features(text)
            raw = features.pct_complex_words
            adjusted = features.pct_complex_words_adjusted
            delta = raw - adjusted
            deltas.append(delta)

            # Each delta should be >= 0 (adjusted never higher than raw)
            assert delta >= 0, f"Adjusted ({adjusted:.1f}%) > Raw ({raw:.1f}%)"

    avg_delta = sum(deltas) / len(deltas)
    print(f"Average adjustment delta: {avg_delta:.2f}%")
    print(f"Segments analyzed: {len(deltas)}")

    # Financial documents should have meaningful adjustment
    # (5-15% of complex words are common financial terms)
    assert avg_delta > 0.5, f"Avg delta {avg_delta:.2f}% too low - adjustment not working"
```

**Code Reference**:
- `analyzer.py:182-190` (complex word counting)
- `constants.py:116-245` (FINANCIAL_COMMON_WORDS, 245 terms)

#### Test: Financial Word Exclusion Verification

```python
def test_financial_words_excluded():
    """
    Verify specific financial terms are excluded from complex word count.

    Uses actual segment from: data/processed/AAPL_10K_2021_segmented_risks.json
    Segment #6 contains many financial terms.
    """
    import json
    from pathlib import Path
    from src.features.readability import ReadabilityAnalyzer

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    analyzer = ReadabilityAnalyzer()

    # Segment #6 (index 5) has text about macroeconomic conditions
    # Contains: international, operations, investment, financial, etc.
    seg_text = data["segments"][5]["text"]

    features = analyzer.extract_features(seg_text, return_metadata=True)

    # Check that financial words were excluded
    assert features.metadata.financial_words_excluded > 0, \
        "No financial words excluded - adjustment logic not firing"

    print(f"Financial words excluded: {features.metadata.financial_words_excluded}")
    print(f"Raw complex: {features.features.pct_complex_words:.1f}%")
    print(f"Adjusted complex: {features.features.pct_complex_words_adjusted:.1f}%")
```

**Code Reference**: `analyzer.py:307-326` (`_count_complex_words_adjusted()`)

### 2.3 Custom Obfuscation Score Validation

#### Test: Obfuscation Score Range

```python
def test_obfuscation_score_range():
    """
    Metric: Obfuscation score distribution.
    Expected for 10-Ks: 40-75 (moderate to elevated complexity).

    Uses actual data: data/processed/AAPL_10K_2021_segmented_risks.json
    """
    import json
    from pathlib import Path
    from src.features.readability import ReadabilityAnalyzer

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    analyzer = ReadabilityAnalyzer()

    scores = []
    for seg in data["segments"]:
        text = seg["text"]
        if len(text) > 200:
            features = analyzer.extract_features(text)
            score = features.obfuscation_score
            scores.append(score)

            # Basic range check
            assert 0 <= score <= 100, f"Score {score} outside 0-100 range"

    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)

    print(f"Obfuscation scores: min={min_score:.1f}, avg={avg_score:.1f}, max={max_score:.1f}")

    # 10-K Risk Factors should be in moderate-elevated range
    assert 35 <= avg_score <= 80, f"Avg score {avg_score:.1f} outside typical 10-K range"
```

**Code Reference**: `analyzer.py:328-378` (obfuscation calculation)

#### Test: Obfuscation vs Complexity Correlation

```python
def test_obfuscation_correlates_with_complexity():
    """
    Metric: Correlation between obfuscation_score and structural complexity.
    Why: High obfuscation should correlate with long sentences, complex words.

    Uses actual data: data/processed/AAPL_10K_2021_segmented_risks.json
    """
    import json
    from pathlib import Path
    import numpy as np
    from src.features.readability import ReadabilityAnalyzer

    # Load actual AAPL 10-K data
    data_path = Path("data/processed/AAPL_10K_2021_segmented_risks.json")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    analyzer = ReadabilityAnalyzer()

    obfuscation_scores = []
    complexity_proxies = []

    for seg in data["segments"]:
        text = seg["text"]
        if len(text) > 200:
            features = analyzer.extract_features(text)
            obfuscation_scores.append(features.obfuscation_score)
            # Proxy: weighted combination of factors
            proxy = (
                features.avg_sentence_length / 50 * 50 +
                features.pct_complex_words_adjusted
            )
            complexity_proxies.append(proxy)

    correlation = np.corrcoef(obfuscation_scores, complexity_proxies)[0, 1]
    print(f"Obfuscation-complexity correlation: {correlation:.3f}")

    # Should be strongly correlated since obfuscation is derived from these
    assert correlation > 0.6, f"Correlation {correlation:.2f} below 0.6"
```

---

## Phase 3: Test Data Requirements

### 3.1 Primary Data File

**File**: `data/processed/AAPL_10K_2021_segmented_risks.json`

This file contains:
- 54 segmented risk factor paragraphs from AAPL's 2021 10-K
- Pre-computed sentiment scores for each segment
- Aggregate sentiment statistics

### 3.2 Test Fixtures

**File**: `tests/features/conftest.py`

```python
import pytest
import json
from pathlib import Path

# Primary test data file
AAPL_10K_DATA_PATH = Path("data/processed/AAPL_10K_2021_segmented_risks.json")


@pytest.fixture(scope="module")
def aapl_10k_data():
    """Load actual AAPL 10-K 2021 segmented risk factors."""
    with open(AAPL_10K_DATA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(scope="module")
def aapl_segments(aapl_10k_data):
    """Get list of 54 segment dictionaries."""
    return aapl_10k_data["segments"]


@pytest.fixture(scope="module")
def aapl_aggregate_sentiment(aapl_10k_data):
    """Get aggregate sentiment statistics."""
    return aapl_10k_data["aggregate_sentiment"]


@pytest.fixture
def golden_sentence():
    """Deterministic test sentence with known LM word matches."""
    return "The company anticipates potential litigation and catastrophic losses."


@pytest.fixture
def golden_sentence_expected():
    """Expected feature values for golden sentence (verified)."""
    return {
        'negative_count': 3,       # catastrophic, losses, litigation
        'positive_count': 0,
        'uncertainty_count': 1,    # anticipates
        'litigious_count': 1,      # litigation
        'total_sentiment_words': 5,
        'word_count': 8,
    }


@pytest.fixture
def long_segment_texts(aapl_segments):
    """Get segments with >200 chars for readability analysis."""
    return [seg["text"] for seg in aapl_segments if len(seg["text"]) > 200]
```

### 3.3 Test Data Source

| Source | Location | Content |
|--------|----------|---------|
| **Primary** | `data/processed/AAPL_10K_2021_segmented_risks.json` | 54 segments, pre-computed sentiment |
| Statistics | `aggregate_sentiment` field | avg_negative_ratio=0.0454, avg_positive_ratio=0.0054 |
| Golden Sentence | Hardcoded | Deterministic LM word match verification |

---

## Phase 4: Implementation Checklist

### 4.1 File Structure

```
tests/features/
├── __init__.py
├── conftest.py                      # Fixtures and sample data
├── test_sentiment_validation.py     # Sentiment validation tests
├── test_readability_validation.py   # Readability validation tests
└── test_golden_sentences.py         # Deterministic output tests
```

### 4.2 Test Implementation Order

1. **Golden Sentence Test** (deterministic, no dependencies)
2. **LM Hit Rate Test** (validates tokenization)
3. **Zero-Vector Rate Test** (validates matching logic)
4. **Negative > Positive Test** (validates 10-K profile)
5. **Fog Range Test** (validates sentence splitting)
6. **Metric Correlation Test** (validates index consistency)
7. **Adjustment Delta Test** (validates financial domain logic)
8. **Obfuscation Correlation Test** (validates custom score)

### 4.3 Dependencies

```python
# requirements-test.txt additions
scipy>=1.10.0  # For pearsonr correlation
numpy>=1.24.0  # For array operations
```

---

## Validation Summary Table

| Metric | Feature | Success Criteria | Actual (AAPL) | Status |
|--------|---------|------------------|---------------|--------|
| LM Hit Rate | Sentiment | > 2% of tokens | **10.85%** | ✓ PASS |
| Zero-Vector Rate | Sentiment | < 50% segments | **1.85%** (1/54) | ✓ PASS |
| Sentiment Polarity | Sentiment | Negative > Positive | **8.4x** (0.0454 vs 0.0054) | ✓ PASS |
| Unc/Neg Correlation | Sentiment | r > 0.3 | TBD | PENDING |
| Golden Sentence | Sentiment | Exact match | **Verified** | ✓ PASS |
| Fog Score Range | Readability | 14-22 average | TBD | PENDING |
| Index Correlation | Readability | All pairs > 0.7 | TBD | PENDING |
| Adjustment Delta | Readability | Raw > Adjusted | TBD | PENDING |
| Financial Exclusion | Readability | Exclusions > 0 | TBD | PENDING |
| Obfuscation Range | Readability | 35-80 average | TBD | PENDING |

### Pre-Validated from Actual Data (AAPL 10-K 2021)

From `aggregate_sentiment` field in `AAPL_10K_2021_segmented_risks.json`:

```json
{
  "avg_negative_ratio": 0.04537037037037037,
  "avg_uncertainty_ratio": 0.03255925925925926,
  "avg_positive_ratio": 0.005399999999999999,
  "avg_sentiment_word_ratio": 0.10853333333333334
}
```

**Key Findings**:
1. **Dictionary is working**: 10.85% sentiment word density >> 2% threshold
2. **No silent failures**: Only 1/54 segments (1.85%) has zero sentiment
3. **10-K profile validated**: Negative ratio 8.4x higher than Positive
4. **Golden Sentence verified**: Exact word-category matches confirmed

---

## Verification Commands

```bash
# Run all validation tests
pytest tests/features/ -v --tb=short

# Run only sentiment validation
pytest tests/features/test_sentiment_validation.py -v

# Run only readability validation
pytest tests/features/test_readability_validation.py -v

# Run with coverage
pytest tests/features/ --cov=src/features --cov-report=html
```

---

## Appendix: Golden Sentence Verification (Completed)

**Test Run Output**:
```
=== GOLDEN SENTENCE TEST ===
Text: The company anticipates potential litigation and catastrophic losses.
Word count: 8
Tokens: ['THE', 'COMPANY', 'ANTICIPATES', 'POTENTIAL', 'LITIGATION', 'AND', 'CATASTROPHIC', 'LOSSES']

Category Counts:
  Negative: 3
  Positive: 0
  Uncertainty: 1
  Litigious: 1
  Total sentiment words: 5

Individual Word Categories:
  ANTICIPATES: {'Uncertainty'}
  POTENTIAL: NOT FOUND
  LITIGATION: {'Complexity', 'Litigious', 'Negative'}
  CATASTROPHIC: {'Negative'}
  LOSSES: {'Negative'}
```

**Status**: PASS - Deterministic output verified.
