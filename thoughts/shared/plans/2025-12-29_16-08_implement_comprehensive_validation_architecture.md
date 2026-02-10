---
date: 2025-12-29T16:08:41-06:00
researcher: bethCoderNewbie
git_commit: 648bf25
branch: main
repository: SEC finetune
topic: "Implementation Plan: Comprehensive 4-Layer Validation Architecture"
tags: [plan, testing, validation, architecture, implementation]
status: pending
priority: high
dependencies:
  - configs/qa_validation/features.yaml
  - src/config/qa_validation.py
  - tests/conftest.py
---

# Plan: Implement Comprehensive 4-Layer Validation Architecture

**Date**: 2025-12-29T16:08:41-06:00
**Researcher**: bethCoderNewbie
**Git Commit**: 648bf25
**Branch**: main
**Repository**: SEC finetune

## Problem Statement

Currently, the validation system has **57% metric coverage** (12/21 metrics) with all coverage concentrated in batch validation scripts. This creates several issues:

### Critical Gaps

1. **Missing 9 Static/Structural Metrics** ❌
   - No validation of dictionary structure (word count, categories)
   - No validation of schema completeness (field counts)
   - No validation of configuration bounds (score ranges)
   - **Location**: Should be in unit tests, NOT validation scripts

2. **Missing 2 Serialization Metrics** ❌
   - No JSON save/load cycle validation
   - No idempotency testing (same input → same output)
   - **Location**: Should be in integration tests

3. **Missing 3 Performance Metrics** ❌
   - No latency benchmarks (processing speed)
   - No throughput measurements (batch efficiency)
   - No memory profiling (resource usage)
   - **Location**: Should be in benchmark tests

4. **Architectural Issues** ⚠️
   - All tests depend on preprocessed data (brittle)
   - No separation between code logic vs data quality
   - No clear testing pyramid (70% unit, 20% integration, 10% slow)
   - Slow feedback loops (can't test without running preprocessing)

### Source Documents

- **Research**: `thoughts/shared/research/2025-12-29_15-57_comprehensive_validation_architecture.md`
- **Strategy**: `thoughts/shared/research/2025-12-29_16-05_pipeline_testing_strategy.md`
- **Existing Config**: `configs/qa_validation/features.yaml` (lines 21-237)
- **Batch Script**: `scripts/validation/feature_quality/check_nlp_batch.py` (validates 12 runtime metrics)

---

## Desired End State

**User Capabilities Upon Completion:**

1. ✅ **100% Metric Coverage** - All 26 metrics validated across 4 layers
2. ✅ **Fast Feedback Loops** - Unit tests run in <10s, provide immediate feedback
3. ✅ **Clear Separation** - Code logic tests (unit) vs data quality checks (validation)
4. ✅ **Performance Baselines** - Established benchmarks for latency/throughput/memory
5. ✅ **Idempotency Guarantees** - Serialization validated, same input → same output
6. ✅ **CI/CD Integration** - Tests run automatically on every commit/PR
7. ✅ **Testing Pyramid** - Proper distribution: 70% unit, 20% integration, 10% slow
8. ✅ **Golden Fixtures** - Deterministic test data for unit tests (no file dependencies)

---

## Anti-Scope (What We're NOT Doing)

1. ❌ **NOT** modifying existing batch validation scripts (they work correctly)
2. ❌ **NOT** changing config structure or threshold definitions
3. ❌ **NOT** refactoring feature extraction modules (focus on tests only)
4. ❌ **NOT** implementing automated fixes for failing tests
5. ❌ **NOT** adding UI/dashboard for test results (CLI output only)
6. ❌ **NOT** creating new preprocessing steps or data pipelines
7. ❌ **NOT** modifying existing integration tests in `tests/features/`
8. ❌ **NOT** removing or deprecating any existing functionality

---

## Implementation Strategy

### Phase 1: Unit Tests - Static/Structural Metrics (Priority 1) ⭐⭐⭐

**Goal**: Create unit tests for 9 static metrics validating module structure and initialization.

**Estimated Time**: 8-10 hours

#### Step 1.1: Create Unit Test Infrastructure

**File**: `tests/unit/features/conftest.py`

```python
"""
Feature unit test fixtures.

Provides shared fixtures for sentiment and readability unit tests.
"""

import pytest
from src.features.sentiment import SentimentAnalyzer
from src.features.readability import ReadabilityAnalyzer
from src.features.dictionaries import LMDictionaryManager


@pytest.fixture(scope="module")
def sentiment_analyzer():
    """
    Create SentimentAnalyzer instance for unit tests.

    Module-scoped - initialized once per test module.
    """
    return SentimentAnalyzer()


@pytest.fixture(scope="module")
def readability_analyzer():
    """
    Create ReadabilityAnalyzer instance for unit tests.

    Module-scoped - initialized once per test module.
    """
    return ReadabilityAnalyzer()


@pytest.fixture(scope="module")
def lm_manager():
    """
    Get LM dictionary manager singleton.

    Module-scoped - uses existing singleton instance.
    """
    return LMDictionaryManager.get_instance()


@pytest.fixture(scope="session")
def golden_sentence():
    """
    Deterministic test sentence with known LM word matches.

    Verified LM dictionary words:
    - anticipates: Uncertainty
    - litigation: Litigious, Negative, Complexity
    - catastrophic: Negative
    - losses: Negative
    """
    return "The company anticipates potential litigation and catastrophic losses."


@pytest.fixture(scope="session")
def golden_expected():
    """
    Expected feature values for golden sentence.

    Pre-computed and verified against LM dictionary v2024.
    """
    return {
        'negative_count': 3,       # catastrophic, losses, litigation
        'positive_count': 0,
        'uncertainty_count': 1,    # anticipates
        'litigious_count': 1,      # litigation
        'total_sentiment_words': 5,
        'word_count': 8,
    }
```

**Verification**:
```bash
# Test fixture loads correctly
pytest tests/unit/features/conftest.py --collect-only
# Expected: 0 tests collected (fixtures only)
```

#### Step 1.2: Sentiment Structure Tests

**File**: `tests/unit/features/test_sentiment_structure.py`

```python
"""
Sentiment Analysis Structure Unit Tests.

Validates static/structural metrics for sentiment analysis:
- Dictionary structure (word count, categories)
- Feature completeness (field count)
- Tokenization logic
- Category counting logic
"""

import pytest
from src.config.qa_validation import ThresholdRegistry
from src.features.dictionaries import LMDictionaryManager
from src.features.sentiment import SentimentAnalyzer


class TestDictionaryStructure:
    """Test LM dictionary structure and initialization."""

    def test_lm_dictionary_word_count(self, lm_manager):
        """
        Metric: lm_dictionary_word_count (>=4000)
        Validates: Dictionary has sufficient vocabulary coverage.
        Config: configs/qa_validation/features.yaml:21-28
        """
        threshold = ThresholdRegistry.get("lm_dictionary_word_count")

        word_count = len(lm_manager._word_to_categories)

        assert word_count >= threshold.target, \
            f"Dictionary has {word_count} words, expected >={threshold.target}"

    def test_category_coverage(self, lm_manager):
        """
        Metric: category_coverage (>=8)
        Validates: All required sentiment categories exist.
        Config: configs/qa_validation/features.yaml:30-37
        """
        threshold = ThresholdRegistry.get("category_coverage")

        # Get all unique categories
        all_categories = set()
        for word_cats in lm_manager._word_to_categories.values():
            all_categories.update(word_cats)

        category_count = len(all_categories)

        assert category_count >= threshold.target, \
            f"Found {category_count} categories, expected >={threshold.target}"

        # Verify expected categories exist
        expected_categories = {
            'Negative', 'Positive', 'Uncertainty', 'Litigious',
            'Strong_Modal', 'Weak_Modal', 'Constraining', 'Complexity'
        }
        assert all_categories >= expected_categories, \
            f"Missing categories: {expected_categories - all_categories}"

    def test_dictionary_load_time(self):
        """
        Metric: dictionary_load_time (<=0.5s)
        Validates: Dictionary loads quickly (pickle cache working).
        Config: configs/qa_validation/features.yaml:39-47
        """
        import time
        from src.features.dictionaries import LMDictionaryManager

        threshold = ThresholdRegistry.get("dictionary_load_time")

        # Force reload to measure load time
        LMDictionaryManager._instance = None

        start = time.perf_counter()
        mgr = LMDictionaryManager.get_instance()
        elapsed = time.perf_counter() - start

        assert elapsed <= threshold.target, \
            f"Load time {elapsed:.3f}s exceeds {threshold.target}s threshold"


class TestSentimentFeatureCompleteness:
    """Test sentiment feature extraction completeness."""

    def test_feature_field_count(self, sentiment_analyzer, golden_sentence):
        """
        Metric: feature_field_count (>=30)
        Validates: All expected sentiment fields are extracted.
        Config: configs/qa_validation/features.yaml:49-57
        """
        threshold = ThresholdRegistry.get("feature_field_count")

        features = sentiment_analyzer.extract_features(golden_sentence)
        field_count = len(features.asdict())

        assert field_count >= threshold.target, \
            f"Features have {field_count} fields, expected >={threshold.target}"

    def test_golden_sentence_extraction(
        self,
        sentiment_analyzer,
        golden_sentence,
        golden_expected
    ):
        """
        Validate sentiment extraction against known-good sentence.

        This is a deterministic test with pre-computed expected values.
        """
        features = sentiment_analyzer.extract_features(golden_sentence)

        # Validate counts
        assert features.negative_count == golden_expected['negative_count']
        assert features.positive_count == golden_expected['positive_count']
        assert features.uncertainty_count == golden_expected['uncertainty_count']
        assert features.litigious_count == golden_expected['litigious_count']
        assert features.total_sentiment_words == golden_expected['total_sentiment_words']
        assert features.word_count == golden_expected['word_count']


class TestTokenizationLogic:
    """Test tokenization and normalization logic."""

    def test_tokenization_hyphenated_words(self, sentiment_analyzer):
        """Validate hyphenated words are tokenized correctly."""
        text = "risk-adjusted returns"
        tokens = sentiment_analyzer.tokenize(text)

        assert "risk-adjusted" in tokens
        assert "returns" in tokens

    def test_tokenization_case_normalization(self, sentiment_analyzer):
        """Validate case normalization for dictionary lookup."""
        text = "NEGATIVE positive UncERtain"
        tokens = sentiment_analyzer.tokenize(text)

        # Should be lowercased for dictionary matching
        assert all(t.islower() for t in tokens)

    def test_tokenization_special_characters(self, sentiment_analyzer):
        """Validate special characters are handled correctly."""
        text = "risk! uncertainty? litigation."
        tokens = sentiment_analyzer.tokenize(text)

        # Punctuation should be removed
        assert "risk" in tokens
        assert "uncertainty" in tokens
        assert "litigation" in tokens
        assert "!" not in tokens
        assert "?" not in tokens
```

**Verification**:
```bash
# Run sentiment structure tests
pytest tests/unit/features/test_sentiment_structure.py -v

# Expected: 10 tests passed
# - test_lm_dictionary_word_count
# - test_category_coverage
# - test_dictionary_load_time
# - test_feature_field_count
# - test_golden_sentence_extraction
# - test_tokenization_hyphenated_words
# - test_tokenization_case_normalization
# - test_tokenization_special_characters
```

#### Step 1.3: Readability Structure Tests

**File**: `tests/unit/features/test_readability_structure.py`

```python
"""
Readability Analysis Structure Unit Tests.

Validates static/structural metrics for readability analysis:
- Index coverage (6 standard indices)
- Financial adjustment word count
- Obfuscation score bounds (0-100)
- Feature completeness (22 fields)
"""

import pytest
from src.config.qa_validation import ThresholdRegistry
from src.features.readability import ReadabilityAnalyzer
from src.features.readability.constants import FINANCIAL_COMMON_WORDS


class TestReadabilityIndices:
    """Test readability index coverage."""

    def test_standard_index_count(self, readability_analyzer, golden_sentence):
        """
        Metric: standard_index_count (>=6)
        Validates: All required readability indices are computed.
        Config: configs/qa_validation/features.yaml:62-69
        """
        threshold = ThresholdRegistry.get("standard_index_count")

        features = readability_analyzer.extract_features(golden_sentence)

        # Count standard indices
        indices = [
            features.flesch_kincaid_grade,
            features.gunning_fog_index,
            features.flesch_reading_ease,
            features.smog_index,
            features.automated_readability_index,
            features.coleman_liau_index,
        ]

        # All should be computed (not None)
        computed_count = sum(1 for idx in indices if idx is not None)

        assert computed_count >= threshold.target, \
            f"Computed {computed_count} indices, expected >={threshold.target}"


class TestFinancialAdjustments:
    """Test financial domain adjustments."""

    def test_financial_adjustment_word_count(self):
        """
        Metric: financial_adjustment_word_count (>=200)
        Validates: Sufficient financial words for domain adjustment.
        Config: configs/qa_validation/features.yaml:71-78
        """
        threshold = ThresholdRegistry.get("financial_adjustment_word_count")

        word_count = len(FINANCIAL_COMMON_WORDS)

        assert word_count >= threshold.target, \
            f"Financial word list has {word_count} words, expected >={threshold.target}"

    def test_financial_adjustment_applied(self, readability_analyzer):
        """Validate financial adjustment reduces complexity."""
        # Text with financial terms
        financial_text = """
        The investment management regulatory compliance requirements
        necessitate comprehensive disclosure documentation.
        """

        features = readability_analyzer.extract_features(financial_text)

        # Adjusted should be lower than unadjusted
        # (financial words excluded from "complex" count)
        assert features.pct_complex_words_adjusted <= features.pct_complex_words


class TestObfuscationScore:
    """Test obfuscation score computation."""

    def test_obfuscation_score_range_min(self, readability_analyzer, golden_sentence):
        """
        Metric: obfuscation_score_range_min (>=0)
        Validates: Score lower bound is correct.
        Config: configs/qa_validation/features.yaml:80-88
        """
        threshold = ThresholdRegistry.get("obfuscation_score_range_min")

        features = readability_analyzer.extract_features(golden_sentence)

        assert features.obfuscation_score >= threshold.target, \
            f"Obfuscation score {features.obfuscation_score} below {threshold.target}"

    def test_obfuscation_score_range_max(self, readability_analyzer, golden_sentence):
        """
        Metric: obfuscation_score_range_max (<=100)
        Validates: Score upper bound is correct.
        Config: configs/qa_validation/features.yaml:90-97
        """
        threshold = ThresholdRegistry.get("obfuscation_score_range_max")

        features = readability_analyzer.extract_features(golden_sentence)

        assert features.obfuscation_score <= threshold.target, \
            f"Obfuscation score {features.obfuscation_score} exceeds {threshold.target}"

    def test_obfuscation_score_components(self, readability_analyzer, golden_sentence):
        """Validate obfuscation score has all required components."""
        features = readability_analyzer.extract_features(golden_sentence)

        # All components should be non-null
        assert features.flesch_kincaid_grade is not None
        assert features.gunning_fog_index is not None
        assert features.avg_sentence_length is not None
        assert features.pct_complex_words is not None


class TestReadabilityFeatureCompleteness:
    """Test readability feature extraction completeness."""

    def test_readability_feature_count(self, readability_analyzer, golden_sentence):
        """
        Metric: readability_feature_count (>=22)
        Validates: All expected readability fields are extracted.
        Config: configs/qa_validation/features.yaml:99-106
        """
        threshold = ThresholdRegistry.get("readability_feature_count")

        features = readability_analyzer.extract_features(golden_sentence)
        field_count = len(features.model_dump())

        assert field_count >= threshold.target, \
            f"Features have {field_count} fields, expected >={threshold.target}"
```

**Verification**:
```bash
# Run readability structure tests
pytest tests/unit/features/test_readability_structure.py -v

# Expected: 8 tests passed
# - test_standard_index_count
# - test_financial_adjustment_word_count
# - test_financial_adjustment_applied
# - test_obfuscation_score_range_min
# - test_obfuscation_score_range_max
# - test_obfuscation_score_components
# - test_readability_feature_count
```

**Success Criteria for Phase 1**:
- ✅ All 9 static metrics validated
- ✅ Tests run in <5 seconds
- ✅ No dependency on preprocessed data
- ✅ All tests use golden fixtures or config

---

### Phase 2: Integration Tests - Serialization Metrics (Priority 2) ⭐⭐

**Goal**: Create integration tests for JSON I/O and idempotency validation.

**Estimated Time**: 4-6 hours

#### Step 2.1: Create Integration Test Infrastructure

**File**: `tests/integration/conftest.py`

```python
"""
Integration test fixtures.

Provides shared fixtures for integration tests.
"""

import pytest
from pathlib import Path


@pytest.fixture(scope="module")
def sample_risk_paragraph():
    """
    Realistic risk factor paragraph for integration testing.

    Based on actual 10-K language patterns.
    """
    return """
    Our business is subject to intense competition in all of our markets.
    Our competitors may have greater financial resources and may be able
    to respond more quickly to new or emerging technologies and changes
    in customer requirements. If we are unable to compete successfully,
    our market share and revenues may decline.

    We are also subject to various federal, state, and local laws and
    regulations that could increase our costs of operations and adversely
    impact our business. Changes in laws and regulations could require
    us to modify our business practices or incur significant compliance
    costs. Failure to comply with applicable regulations could result in
    fines, penalties, or suspension of our operations.
    """
```

#### Step 2.2: Sentiment Serialization Tests

**File**: `tests/integration/features/test_sentiment_pipeline.py`

```python
"""
Sentiment Analysis Integration Tests.

Validates serialization and pipeline integration:
- JSON save/load cycle
- Idempotency (same input → same output)
- Cross-version compatibility
"""

import json
import pytest
from pathlib import Path
from src.features.sentiment import SentimentAnalyzer, SentimentFeatures


class TestSentimentSerialization:
    """Test sentiment feature serialization."""

    def test_json_save_load_cycle(self, tmp_path, sample_risk_paragraph):
        """
        Metric: JSON save/load cycle
        Validates: No data loss during serialization.
        """
        analyzer = SentimentAnalyzer()

        # Extract features
        features_original = analyzer.extract_features(sample_risk_paragraph)

        # Save to JSON
        json_path = tmp_path / "sentiment_features.json"
        features_original.save_to_json(json_path)

        # Verify file exists and has content
        assert json_path.exists()
        assert json_path.stat().st_size > 0

        # Load from JSON
        features_loaded = SentimentFeatures.load_from_json(json_path)

        # Verify all fields match exactly
        original_dict = features_original.asdict()
        loaded_dict = features_loaded.asdict()

        assert original_dict == loaded_dict, \
            "Loaded features differ from original"

        # Verify specific fields
        assert features_loaded.negative_count == features_original.negative_count
        assert features_loaded.positive_count == features_original.positive_count
        assert features_loaded.uncertainty_count == features_original.uncertainty_count

    def test_json_schema_validation(self, tmp_path, sample_risk_paragraph):
        """Validate JSON schema has all required fields."""
        analyzer = SentimentAnalyzer()
        features = analyzer.extract_features(sample_risk_paragraph)

        # Save to JSON
        json_path = tmp_path / "sentiment_schema.json"
        features.save_to_json(json_path)

        # Load raw JSON
        with open(json_path, 'r') as f:
            data = json.load(f)

        # Verify required fields exist
        required_fields = [
            'negative_count', 'positive_count', 'uncertainty_count',
            'litigious_count', 'total_sentiment_words', 'word_count',
            'negative_ratio', 'positive_ratio', 'uncertainty_ratio',
            'sentiment_word_ratio'
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestSentimentIdempotency:
    """Test sentiment analysis idempotency."""

    def test_same_input_same_output(self, sample_risk_paragraph):
        """
        Metric: Idempotency
        Validates: Same input produces identical output.
        """
        analyzer = SentimentAnalyzer()

        # Run twice
        features1 = analyzer.extract_features(sample_risk_paragraph)
        features2 = analyzer.extract_features(sample_risk_paragraph)

        # Should be identical
        assert features1.asdict() == features2.asdict()

    def test_multiple_runs_identical(self, sample_risk_paragraph):
        """Validate consistency across multiple runs."""
        analyzer = SentimentAnalyzer()

        # Run 5 times
        results = []
        for _ in range(5):
            features = analyzer.extract_features(sample_risk_paragraph)
            results.append(features.asdict())

        # All should be identical
        first = results[0]
        for i, result in enumerate(results[1:], 1):
            assert result == first, \
                f"Run {i+1} differs from run 1"
```

#### Step 2.3: Readability Serialization Tests

**File**: `tests/integration/features/test_readability_pipeline.py`

```python
"""
Readability Analysis Integration Tests.

Validates serialization and pipeline integration.
"""

import json
import pytest
from src.features.readability import ReadabilityAnalyzer


class TestReadabilitySerialization:
    """Test readability feature serialization."""

    def test_json_save_load_cycle(self, tmp_path, sample_risk_paragraph):
        """
        Metric: JSON save/load cycle
        Validates: Pydantic model serialization works correctly.
        """
        analyzer = ReadabilityAnalyzer()

        # Extract features
        features_original = analyzer.extract_features(sample_risk_paragraph)

        # Save to JSON
        json_path = tmp_path / "readability_features.json"
        features_original.model_dump_to_json_file(json_path)

        # Verify file exists
        assert json_path.exists()

        # Load from JSON
        from src.features.readability import ReadabilityFeatures
        features_loaded = ReadabilityFeatures.model_validate_json_file(json_path)

        # Verify all fields match
        assert features_loaded.model_dump() == features_original.model_dump()


class TestReadabilityIdempotency:
    """Test readability analysis idempotency."""

    def test_same_input_same_output(self, sample_risk_paragraph):
        """
        Metric: Idempotency
        Validates: Deterministic output for same input.
        """
        analyzer = ReadabilityAnalyzer()

        # Run twice
        features1 = analyzer.extract_features(sample_risk_paragraph)
        features2 = analyzer.extract_features(sample_risk_paragraph)

        # Should be identical (within floating point precision)
        assert features1.gunning_fog_index == features2.gunning_fog_index
        assert features1.flesch_kincaid_grade == features2.flesch_kincaid_grade
        assert features1.obfuscation_score == features2.obfuscation_score
```

**Verification**:
```bash
# Run integration tests
pytest tests/integration/features/ -v

# Expected: 7 tests passed
# Sentiment: 4 tests
# Readability: 3 tests
```

**Success Criteria for Phase 2**:
- ✅ 2 serialization metrics validated
- ✅ Tests complete in <30 seconds
- ✅ No data loss in save/load cycles
- ✅ Idempotency guaranteed

---

### Phase 3: Benchmark Tests - Performance Metrics (Priority 3) ⭐

**Goal**: Create benchmark tests for latency, throughput, and memory profiling.

**Estimated Time**: 6-8 hours

#### Step 3.1: Create Benchmark Infrastructure

**File**: `tests/benchmarks/conftest.py`

```python
"""
Benchmark test fixtures.

Provides performance testing utilities.
"""

import pytest
import time
import tracemalloc
from typing import Callable, Any


@pytest.fixture
def measure_latency():
    """
    Fixture for measuring function latency.

    Usage:
        def test_performance(measure_latency):
            elapsed = measure_latency(lambda: expensive_function())
            assert elapsed < 0.1  # <100ms
    """
    def _measure(func: Callable, warmup: int = 1, runs: int = 10) -> float:
        """
        Measure average latency of function.

        Args:
            func: Function to measure
            warmup: Warmup runs (excluded from timing)
            runs: Timed runs to average

        Returns:
            Average elapsed time in seconds
        """
        # Warmup runs
        for _ in range(warmup):
            func()

        # Timed runs
        timings = []
        for _ in range(runs):
            start = time.perf_counter()
            func()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        return sum(timings) / len(timings)

    return _measure


@pytest.fixture
def measure_memory():
    """
    Fixture for measuring peak memory usage.

    Usage:
        def test_memory(measure_memory):
            peak_mb = measure_memory(lambda: process_large_batch())
            assert peak_mb < 100  # <100MB
    """
    def _measure(func: Callable) -> float:
        """
        Measure peak memory usage of function.

        Returns:
            Peak memory in MB
        """
        tracemalloc.start()

        func()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        return peak / 1024 / 1024  # Convert to MB

    return _measure
```

#### Step 3.2: Sentiment Performance Tests

**File**: `tests/benchmarks/test_sentiment_performance.py`

```python
"""
Sentiment Analysis Performance Benchmarks.

Validates performance metrics:
- Processing latency (single segment)
- Batch throughput (segments/second)
- Memory efficiency (peak usage)
"""

import pytest
from src.features.sentiment import SentimentAnalyzer


@pytest.mark.slow
class TestSentimentLatency:
    """Test sentiment analysis latency."""

    def test_single_segment_latency(self, measure_latency, sample_risk_paragraph):
        """
        Metric: Processing latency
        Target: <100ms per segment
        """
        analyzer = SentimentAnalyzer()

        elapsed = measure_latency(
            lambda: analyzer.extract_features(sample_risk_paragraph),
            warmup=2,
            runs=20
        )

        # Target: <100ms per segment
        assert elapsed < 0.1, \
            f"Latency {elapsed*1000:.1f}ms exceeds 100ms threshold"


@pytest.mark.slow
class TestSentimentThroughput:
    """Test sentiment analysis throughput."""

    def test_batch_throughput(self, aapl_segments):
        """
        Metric: Batch throughput
        Target: >10 segments/second
        """
        if not aapl_segments:
            pytest.skip("No AAPL segments available")

        analyzer = SentimentAnalyzer()

        # Warmup
        analyzer.extract_features(aapl_segments[0]["text"])

        # Time batch processing
        import time
        start = time.perf_counter()

        for seg in aapl_segments[:20]:  # Sample 20 segments
            analyzer.extract_features(seg["text"])

        elapsed = time.perf_counter() - start
        throughput = 20 / elapsed

        # Target: >10 segments/second
        assert throughput > 10, \
            f"Throughput {throughput:.1f} seg/s below 10 seg/s threshold"


@pytest.mark.slow
class TestSentimentMemory:
    """Test sentiment analysis memory usage."""

    def test_memory_efficiency(self, measure_memory, aapl_segments):
        """
        Metric: Memory efficiency
        Target: <100MB peak memory
        """
        if not aapl_segments:
            pytest.skip("No AAPL segments available")

        analyzer = SentimentAnalyzer()

        def process_batch():
            for seg in aapl_segments:
                analyzer.extract_features(seg["text"])

        peak_mb = measure_memory(process_batch)

        # Target: <100MB peak memory
        assert peak_mb < 100, \
            f"Peak memory {peak_mb:.1f}MB exceeds 100MB threshold"
```

#### Step 3.3: Readability Performance Tests

**File**: `tests/benchmarks/test_readability_performance.py`

```python
"""
Readability Analysis Performance Benchmarks.
"""

import pytest
from src.features.readability import ReadabilityAnalyzer


@pytest.mark.slow
class TestReadabilityLatency:
    """Test readability analysis latency."""

    def test_single_segment_latency(self, measure_latency, sample_risk_paragraph):
        """
        Metric: Processing latency
        Target: <50ms per segment (faster than sentiment)
        """
        analyzer = ReadabilityAnalyzer()

        elapsed = measure_latency(
            lambda: analyzer.extract_features(sample_risk_paragraph),
            warmup=2,
            runs=20
        )

        # Target: <50ms (textstat is very fast)
        assert elapsed < 0.05, \
            f"Latency {elapsed*1000:.1f}ms exceeds 50ms threshold"


@pytest.mark.slow
class TestReadabilityThroughput:
    """Test readability analysis throughput."""

    def test_batch_throughput(self, long_segment_texts):
        """
        Metric: Batch throughput
        Target: >20 segments/second
        """
        if not long_segment_texts:
            pytest.skip("No long segment texts available")

        analyzer = ReadabilityAnalyzer()

        # Time batch
        import time
        start = time.perf_counter()

        for text in long_segment_texts[:20]:
            analyzer.extract_features(text)

        elapsed = time.perf_counter() - start
        throughput = 20 / elapsed

        # Target: >20 segments/second
        assert throughput > 20, \
            f"Throughput {throughput:.1f} seg/s below 20 seg/s threshold"
```

**Verification**:
```bash
# Run benchmarks (slow tests)
pytest tests/benchmarks/ -v -m slow

# Expected: 6 tests passed
# Sentiment: 3 tests (latency, throughput, memory)
# Readability: 3 tests (latency, throughput, memory)
```

**Success Criteria for Phase 3**:
- ✅ 3 performance metrics validated
- ✅ Benchmarks establish performance baselines
- ✅ Tests use real data for realistic profiling
- ✅ Results saved for regression detection

---

### Phase 4: pytest Configuration & Markers (Priority 4)

**Goal**: Configure pytest for proper test organization and execution.

**Estimated Time**: 1-2 hours

#### Step 4.1: Update pytest.ini

**File**: `pytest.ini` (create in project root)

```ini
[pytest]
# Test discovery patterns
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Test paths
testpaths = tests

# Markers
markers =
    unit: Unit tests (fast, isolated, no external dependencies)
    integration: Integration tests (medium speed, realistic scenarios)
    slow: Benchmark tests (slow, comprehensive performance profiling)
    requires_data: Tests requiring preprocessed data files
    requires_10k_files: Tests requiring raw 10-K HTML files
    requires_10q_files: Tests requiring raw 10-Q HTML files
    requires_preprocessing_data: Tests requiring preprocessing output

# Output options
console_output_style = progress
log_cli = false
log_cli_level = INFO

# Coverage options (if using pytest-cov)
addopts =
    --strict-markers
    --tb=short
    -ra

# Ignore paths
norecursedirs =
    .git
    .tox
    dist
    build
    *.egg
    __pycache__
    data
    reports
    thoughts
```

#### Step 4.2: Update conftest.py Markers

**File**: `tests/conftest.py` (add to existing file)

```python
# Add to existing pytest_configure function
def pytest_configure(config):
    """Register custom markers and initialize test output run."""

    # Existing markers
    config.addinivalue_line(
        "markers", "requires_10k_files: mark test to skip if no 10-K files available"
    )
    config.addinivalue_line(
        "markers", "requires_10q_files: mark test to skip if no 10-Q files available"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "requires_preprocessing_data: mark test to skip if no preprocessing data available"
    )

    # NEW markers
    config.addinivalue_line(
        "markers", "unit: unit tests (fast, isolated, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "slow: benchmark tests (slow, comprehensive performance profiling)"
    )
    config.addinivalue_line(
        "markers", "requires_data: tests requiring preprocessed data files"
    )

    # ... rest of existing code ...
```

**Verification**:
```bash
# List all markers
pytest --markers

# Expected output includes:
# @pytest.mark.unit: Unit tests (fast, isolated)
# @pytest.mark.integration: Integration tests
# @pytest.mark.slow: Benchmark tests
```

**Success Criteria for Phase 4**:
- ✅ pytest.ini configured correctly
- ✅ All markers registered
- ✅ Tests can be filtered by marker
- ✅ No marker warnings during test runs

---

### Phase 5: CI/CD Integration (Priority 5)

**Goal**: Integrate tests into automated CI/CD pipeline.

**Estimated Time**: 2-3 hours

#### Step 5.1: Create GitHub Actions Workflow

**File**: `.github/workflows/test.yml`

```yaml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  unit-tests:
    name: Unit Tests (Fast)
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-cov

    - name: Run unit tests
      run: |
        pytest tests/unit/ -v --tb=short
        # Expected: <10 seconds

    - name: Check coverage
      run: |
        pytest tests/unit/ --cov=src --cov-report=term-missing

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: unit-tests

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest

    - name: Run integration tests
      run: |
        pytest tests/integration/ -v --tb=short
        # Expected: <30 seconds

  validation-check:
    name: Validation Script Tests
    runs-on: ubuntu-latest
    needs: integration-tests

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest

    - name: Run validation tests
      run: |
        pytest tests/validation/ -v --tb=short

  # Benchmarks run only on main branch merges
  benchmarks:
    name: Performance Benchmarks
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-benchmark

    - name: Run benchmarks
      run: |
        pytest tests/benchmarks/ -v -m slow --benchmark-only

    - name: Archive benchmark results
      uses: actions/upload-artifact@v3
      with:
        name: benchmark-results
        path: .benchmarks/
```

**Verification**:
```bash
# Test locally with act (GitHub Actions local runner)
act -j unit-tests

# Or manually run the test commands
pytest tests/unit/ -v --tb=short
pytest tests/integration/ -v --tb=short
```

**Success Criteria for Phase 5**:
- ✅ CI/CD workflow runs on every commit
- ✅ Unit tests run in <10 seconds
- ✅ Integration tests run in <30 seconds
- ✅ Benchmarks run only on main branch
- ✅ Failed tests block merge

---

## Verification Plan

### Automated Verification

#### Test Suite Execution

```bash
# 1. Run all fast tests (unit + integration)
pytest -m "not slow" -v

# Expected:
# - tests/unit/features/test_sentiment_structure.py: 10 passed
# - tests/unit/features/test_readability_structure.py: 8 passed
# - tests/integration/features/test_sentiment_pipeline.py: 4 passed
# - tests/integration/features/test_readability_pipeline.py: 3 passed
# Total: 25 passed in <30s

# 2. Run benchmarks separately
pytest -m slow -v

# Expected:
# - tests/benchmarks/test_sentiment_performance.py: 3 passed
# - tests/benchmarks/test_readability_performance.py: 3 passed
# Total: 6 passed in ~60s

# 3. Verify metric coverage
python -c "
from src.config.qa_validation import ThresholdRegistry

# Count thresholds by category
sentiment_static = len([t for t in ThresholdRegistry.by_category('sentiment_analysis')])
readability_static = len([t for t in ThresholdRegistry.by_category('readability_analysis')])
sentiment_runtime = len([t for t in ThresholdRegistry.by_category('sentiment_validation')])
readability_runtime = len([t for t in ThresholdRegistry.by_category('readability_validation')])

print(f'Static metrics: {sentiment_static + readability_static}')
print(f'Runtime metrics: {sentiment_runtime + readability_runtime}')
print(f'Total: {sentiment_static + readability_static + sentiment_runtime + readability_runtime}')

# Expected:
# Static metrics: 9
# Runtime metrics: 12
# Total: 21 (config-defined metrics)
# Plus 5 from tests (serialization + performance) = 26 total
"
```

#### Coverage Analysis

```bash
# Check test coverage
pytest tests/unit/features/ --cov=src/features --cov-report=html

# Open htmlcov/index.html to verify:
# - src/features/sentiment.py: >80% coverage
# - src/features/readability/analyzer.py: >80% coverage
# - src/features/dictionaries/lm_dictionary.py: >80% coverage
```

### Manual Verification

#### 1. Test Organization

```bash
# Verify directory structure
tree tests/ -L 3

# Expected:
# tests/
# ├── conftest.py
# ├── unit/
# │   ├── conftest.py
# │   └── features/
# │       ├── conftest.py
# │       ├── test_sentiment_structure.py
# │       └── test_readability_structure.py
# ├── integration/
# │   ├── conftest.py
# │   └── features/
# │       ├── test_sentiment_pipeline.py
# │       └── test_readability_pipeline.py
# └── benchmarks/
#     ├── conftest.py
#     ├── test_sentiment_performance.py
#     └── test_readability_performance.py
```

#### 2. Marker Functionality

```bash
# Run only unit tests
pytest -m unit -v
# Should run 18 tests (sentiment + readability structure tests)

# Run only integration tests
pytest -m integration -v
# Should run 7 tests (sentiment + readability serialization)

# Run everything except slow tests (CI mode)
pytest -m "not slow" -v
# Should run 25 tests (all except benchmarks)

# Run only benchmarks
pytest -m slow -v
# Should run 6 tests (performance tests)
```

#### 3. Fixture Availability

```bash
# Verify fixtures are accessible
pytest --fixtures tests/unit/features/

# Expected fixtures:
# - sentiment_analyzer (from tests/unit/features/conftest.py)
# - readability_analyzer (from tests/unit/features/conftest.py)
# - lm_manager (from tests/unit/features/conftest.py)
# - golden_sentence (from tests/unit/features/conftest.py)
# - golden_expected (from tests/unit/features/conftest.py)
```

#### 4. Performance Baselines

```bash
# Run benchmarks and save results
pytest tests/benchmarks/ -v -m slow --benchmark-save=baseline

# View results
pytest-benchmark list
pytest-benchmark compare baseline
```

---

## Success Criteria

### Go Criteria

#### Phase 1: Unit Tests
- ✅ All 9 static metrics have passing unit tests
- ✅ Tests run in <5 seconds
- ✅ No dependency on preprocessed data files
- ✅ All tests use golden fixtures or config
- ✅ Test coverage >80% for tested modules

#### Phase 2: Integration Tests
- ✅ 2 serialization metrics validated
- ✅ Save/load cycle preserves all data
- ✅ Idempotency guaranteed (same input → same output)
- ✅ Tests complete in <30 seconds
- ✅ Pydantic models validate correctly

#### Phase 3: Benchmark Tests
- ✅ 3 performance metrics established
- ✅ Latency baselines defined
- ✅ Throughput targets met
- ✅ Memory usage within limits
- ✅ Performance results saved for comparison

#### Phase 4: Configuration
- ✅ pytest.ini configured correctly
- ✅ All markers registered and functional
- ✅ Test filtering works correctly
- ✅ No marker warnings during runs

#### Phase 5: CI/CD
- ✅ GitHub Actions workflow configured
- ✅ Tests run automatically on commits
- ✅ Unit tests complete in <10s
- ✅ Integration tests complete in <30s
- ✅ Failed tests block merge

### Overall Success
- ✅ **100% metric coverage** (26/26 metrics)
- ✅ **Testing pyramid achieved** (18 unit, 7 integration, 6 benchmark)
- ✅ **Fast feedback loops** (unit tests provide instant feedback)
- ✅ **Clear separation** (code logic vs data quality)
- ✅ **CI/CD integrated** (automated testing on every commit)

### No-Go Criteria

- ❌ Any static metric without unit test coverage
- ❌ Tests depend on preprocessed data (unit/integration only)
- ❌ Performance regressions detected in benchmarks
- ❌ Save/load cycle loses data
- ❌ CI/CD pipeline fails to run

---

## Timeline & Effort Estimate

| Phase | Priority | Effort | Dependencies |
|-------|----------|--------|--------------|
| Phase 1: Unit Tests | ⭐⭐⭐ | 8-10 hours | None |
| Phase 2: Integration Tests | ⭐⭐ | 4-6 hours | Phase 1 fixtures |
| Phase 3: Benchmark Tests | ⭐ | 6-8 hours | Phase 1 fixtures |
| Phase 4: Configuration | ⭐⭐ | 1-2 hours | None |
| Phase 5: CI/CD | ⭐⭐ | 2-3 hours | All phases |
| **TOTAL** | - | **21-29 hours** | Sequential |

**Recommended Approach**: 3-4 days of focused work

- **Day 1**: Phase 1 (unit tests) + Phase 4 (config)
- **Day 2**: Phase 2 (integration tests)
- **Day 3**: Phase 3 (benchmark tests)
- **Day 4**: Phase 5 (CI/CD) + verification

---

## Migration Guide

### For Existing Tests

No changes required for existing tests:
- ✅ `tests/features/` - Keep as-is (runtime validation tests)
- ✅ `tests/preprocessing/` - Keep as-is (preprocessing integration tests)
- ✅ `tests/validation/` - Keep as-is (validation script tests)
- ✅ `scripts/validation/` - Keep as-is (batch validation scripts)

### For CI/CD Pipelines

Update test commands:
```bash
# Old (runs everything, slow)
pytest tests/

# New (fast tests only)
pytest -m "not slow" tests/

# New (with coverage)
pytest -m "not slow" --cov=src --cov-report=term-missing tests/
```

### For Developers

New workflow:
```bash
# Before committing - run fast tests
pytest -m "not slow"

# Before PR - run all tests except benchmarks
pytest tests/unit/ tests/integration/

# Weekly - run benchmarks
pytest -m slow tests/benchmarks/
```

---

## Open Questions

1. **Benchmark Frequency**: Should benchmarks block PRs or only run on main?
   - **Recommendation**: Run on main only to avoid slowing PR feedback

2. **Performance Thresholds**: Are latency/throughput targets realistic?
   - **Recommendation**: Start conservative, adjust based on actual measurements

3. **Test Data**: Should we commit golden fixtures to repo?
   - **Recommendation**: Yes - golden sentences are small and deterministic

4. **Coverage Targets**: What's the minimum acceptable test coverage?
   - **Recommendation**: >80% for feature modules, >60% for preprocessing

5. **Benchmark History**: How to track performance over time?
   - **Recommendation**: Use pytest-benchmark plugin with JSON storage

---

## Notes

- All unit tests use golden fixtures (no file I/O)
- Integration tests use tmp_path for file operations
- Benchmark tests use real data for realistic profiling
- Existing validation scripts remain unchanged (already working correctly)
- Config thresholds remain single source of truth
- Tests follow Testing Pyramid: 70% unit, 20% integration, 10% benchmark
