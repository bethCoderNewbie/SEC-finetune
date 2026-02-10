---
date: 2025-12-29T16:05:00-06:00
researcher: bethCoderNewbie
git_commit: 648bf25
branch: main
repository: SEC finetune
topic: "Comprehensive Pipeline Testing Strategy - Code Logic vs Data Quality"
tags: [testing, validation, pipeline, best-practices, strategy]
status: complete
---

# Pipeline Testing Strategy: Code Logic vs Data Quality Validation

## The Golden Rule

> **Unit tests validate CODE logic. Validation scripts validate DATA quality.**

## Complete Testing Pyramid for SEC Preprocessing Pipeline

```
                    /\
                   /  \
                  / 4. \       Layer 4: DATA QUALITY VALIDATION
                 /VALID \      ────────────────────────────────
                /────────\     • Batch validation scripts
               /          \    • Production data checks
              /   3. BENCH \   • Runtime quality metrics
             /    MARKS     \
            /--------------  \ Layer 3: PERFORMANCE BENCHMARKS
           /                  \──────────────────────────────
          /  2. INTEGRATION   \• Latency, throughput, memory
         /       TESTS         \• End-to-end pipeline tests
        /--------------------  \• Serialization validation
       /                        \
      /      1. UNIT TESTS       \ Layer 1: UNIT TESTS
     /      (CODE LOGIC)          \──────────────────
    /                              \• Fast, isolated
   /                                \• Mocked dependencies
  /                                  \• Every function
 /____________________________________\
```

## Layer 1: Unit Tests (Code Logic)

### Purpose
Validate that **individual functions work correctly** with controlled inputs.

### Characteristics
- ✅ **Fast**: <1s per test
- ✅ **Deterministic**: Same input → same output
- ✅ **Isolated**: No file I/O, no network, no database
- ✅ **Mocked**: External dependencies stubbed
- ✅ **Frequent**: Every commit

### What to Test

#### Preprocessing Module Unit Tests

**File**: `tests/unit/preprocessing/test_extractor_unit.py`

```python
import pytest
from src.preprocessing.extractor import SECSectionExtractor

def test_identify_section_boundary_start():
    """Test section start boundary detection logic."""
    extractor = SECSectionExtractor()

    # Test ITEM 1A pattern detection
    html_text = '<p><b>Item 1A. Risk Factors</b></p>'
    result = extractor._identify_section_start(html_text)

    assert result is not None
    assert result['item'] == '1A'
    assert 'Risk Factors' in result['title']

def test_identify_section_boundary_end():
    """Test section end boundary detection logic."""
    extractor = SECSectionExtractor()

    # Test NEXT item pattern stops extraction
    current_section = "Item 1A"
    next_text = "Item 1B. Unresolved Staff Comments"

    should_stop = extractor._is_next_section(current_section, next_text)

    assert should_stop == True

def test_filter_page_headers():
    """Test page header removal logic."""
    extractor = SECSectionExtractor()

    # Page header pattern
    text_with_header = "Apple Inc. | 2021 Form 10-K | 6\nActual content here."

    cleaned = extractor._filter_page_headers(text_with_header)

    assert "Apple Inc. |" not in cleaned
    assert "Actual content here" in cleaned
```

**Key Points**:
- Tests **individual methods** (`_identify_section_start`, `_is_next_section`)
- Uses **golden samples** (known good inputs)
- No file I/O - data passed as strings
- Fast execution - hundreds of tests run in seconds

#### Feature Module Unit Tests

**File**: `tests/unit/features/test_sentiment_structure.py`

```python
from src.config.qa_validation import ThresholdRegistry
from src.features.dictionaries import LMDictionaryManager
from src.features.sentiment import SentimentAnalyzer

def test_lm_dictionary_word_count():
    """Validate LM dictionary structure."""
    threshold = ThresholdRegistry.get("lm_dictionary_word_count")

    mgr = LMDictionaryManager.get_instance()
    word_count = len(mgr._word_to_categories)

    assert word_count >= threshold.target, \
        f"Dictionary has {word_count} words, expected >={threshold.target}"

def test_sentiment_feature_field_count():
    """Validate sentiment feature completeness."""
    threshold = ThresholdRegistry.get("feature_field_count")

    analyzer = SentimentAnalyzer()
    features = analyzer.extract_features("Sample risk text here.")

    field_count = len(features.asdict())

    assert field_count >= threshold.target, \
        f"Features have {field_count} fields, expected >={threshold.target}"

def test_sentiment_tokenization_logic():
    """Test tokenization handles edge cases."""
    analyzer = SentimentAnalyzer()

    # Test hyphenated words
    text = "risk-adjusted returns"
    tokens = analyzer.tokenize(text)

    assert "risk-adjusted" in tokens
    assert "returns" in tokens

    # Test case normalization
    text2 = "NEGATIVE positive UncERtain"
    tokens2 = analyzer.tokenize(text2)

    # Should be lowercased for dictionary lookup
    assert all(t.islower() for t in tokens2)
```

**Key Points**:
- Tests **module initialization** and **data structures**
- Validates **static properties** (word counts, field counts)
- Tests **logic correctness** (tokenization, normalization)
- No external data files required

---

## Layer 2: Integration Tests (Pipeline Logic)

### Purpose
Validate that **components work together correctly** in realistic scenarios.

### Characteristics
- ⚡ **Medium Speed**: 5-30s per test
- 🔗 **Connected**: Multiple components interact
- 💾 **File I/O**: Reads/writes files, uses temp directories
- 🎯 **End-to-End**: Tests full workflows
- 📅 **Frequency**: Every PR

### What to Test

#### Serialization and Idempotency

**File**: `tests/integration/features/test_sentiment_pipeline.py`

```python
import json
from pathlib import Path
from src.features.sentiment import SentimentAnalyzer, SentimentFeatures

def test_sentiment_json_roundtrip(tmp_path):
    """Verify sentiment features survive JSON save/load."""
    analyzer = SentimentAnalyzer()

    text = """
    Our business is subject to numerous risks that could adversely
    affect our financial condition and results of operations.
    """

    # Extract features
    features_original = analyzer.extract_features(text)

    # Save to JSON
    json_path = tmp_path / "sentiment.json"
    features_original.save_to_json(json_path)

    # Verify file exists
    assert json_path.exists()

    # Load from JSON
    features_loaded = SentimentFeatures.load_from_json(json_path)

    # Verify all fields match exactly
    assert features_original.asdict() == features_loaded.asdict()

def test_sentiment_idempotency():
    """Verify same input produces identical output."""
    analyzer = SentimentAnalyzer()

    text = "Competition risk, regulatory uncertainty, litigation losses."

    # Run twice
    features1 = analyzer.extract_features(text)
    features2 = analyzer.extract_features(text)

    # Should be identical
    assert features1.negative_count == features2.negative_count
    assert features1.uncertainty_count == features2.uncertainty_count
    assert features1.total_sentiment_words == features2.total_sentiment_words
```

#### End-to-End Preprocessing Pipeline

**File**: `tests/integration/preprocessing/test_preprocessing_pipeline.py`

```python
from pathlib import Path
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor
from src.preprocessing.cleaning import TextCleaner
from src.preprocessing.segmenter import RiskSegmenter

def test_full_preprocessing_pipeline(tmp_path, sample_10k_file):
    """Test complete preprocessing workflow."""
    if not sample_10k_file or not sample_10k_file.exists():
        pytest.skip("No 10-K file available")

    # Step 1: Parse HTML
    parser = SECFilingParser()
    filing = parser.parse_10k(sample_10k_file)

    assert filing is not None
    assert filing.sections  # Has sections

    # Step 2: Extract Risk Factors
    extractor = RiskFactorExtractor()
    risk_section = extractor.extract_item_1a_risks(filing)

    assert risk_section is not None
    assert risk_section.text  # Has content

    # Step 3: Clean text
    cleaner = TextCleaner()
    cleaned = cleaner.clean_extracted_section(risk_section)

    assert cleaned.text != risk_section.text  # Something changed
    assert len(cleaned.text) > 0  # Still has content

    # Step 4: Segment into risks
    segmenter = RiskSegmenter()
    segments = segmenter.segment_risks(cleaned.text)

    assert len(segments) > 0  # Has segments

    # Step 5: Save and reload
    output_path = tmp_path / "test_segmented.json"
    segmented_data = {
        "identifier": "test_10k",
        "segments": segments,
        "metadata": {"source": "integration_test"}
    }

    with open(output_path, 'w') as f:
        json.dump(segmented_data, f)

    # Reload
    with open(output_path, 'r') as f:
        loaded = json.load(f)

    assert loaded['identifier'] == "test_10k"
    assert len(loaded['segments']) == len(segments)
```

**Key Points**:
- Tests **multi-component workflows**
- Uses **real file I/O** with temp directories
- Validates **data persistence** (save/load cycles)
- Tests **integration points** between modules

---

## Layer 3: Benchmark Tests (Performance)

### Purpose
Validate **performance characteristics** and detect regressions.

### Characteristics
- 🐌 **Slow**: 30s - 5min per test
- 📊 **Profiling**: Measures time, memory, throughput
- 📈 **Baseline**: Compares against historical performance
- 🔬 **Real Data**: Uses actual 10-K filings
- 📅 **Frequency**: Weekly or on-demand

### What to Test

**File**: `tests/benchmarks/test_sentiment_performance.py`

```python
import time
import tracemalloc
import pytest
from src.features.sentiment import SentimentAnalyzer

@pytest.mark.slow
def test_sentiment_latency_single_segment(sample_risk_text):
    """Measure single-segment processing latency."""
    analyzer = SentimentAnalyzer()

    # Warm-up run (load dictionary, JIT compile)
    analyzer.extract_features(sample_risk_text)

    # Timed runs
    timings = []
    for _ in range(10):
        start = time.perf_counter()
        features = analyzer.extract_features(sample_risk_text)
        elapsed = time.perf_counter() - start
        timings.append(elapsed)

    avg_latency = sum(timings) / len(timings)

    # Target: <100ms per segment
    assert avg_latency < 0.1, \
        f"Avg latency {avg_latency*1000:.1f}ms exceeds 100ms threshold"

@pytest.mark.slow
def test_sentiment_batch_throughput(aapl_segments):
    """Measure batch processing throughput."""
    if not aapl_segments:
        pytest.skip("No AAPL segments available")

    analyzer = SentimentAnalyzer()

    # Time batch processing
    start = time.perf_counter()

    for seg in aapl_segments:
        analyzer.extract_features(seg["text"])

    elapsed = time.perf_counter() - start
    throughput = len(aapl_segments) / elapsed

    # Target: >10 segments/second
    assert throughput > 10, \
        f"Throughput {throughput:.1f} seg/s below 10 seg/s threshold"

@pytest.mark.slow
def test_sentiment_memory_efficiency(aapl_segments):
    """Measure peak memory usage during batch processing."""
    if not aapl_segments:
        pytest.skip("No AAPL segments available")

    analyzer = SentimentAnalyzer()

    tracemalloc.start()

    # Process batch
    for seg in aapl_segments:
        analyzer.extract_features(seg["text"])

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / 1024 / 1024

    # Target: <100MB peak memory
    assert peak_mb < 100, \
        f"Peak memory {peak_mb:.1f}MB exceeds 100MB threshold"
```

**Key Points**:
- Marked with `@pytest.mark.slow` (run separately)
- Measures **latency**, **throughput**, **memory**
- Uses **real data** for realistic profiling
- Establishes **performance baselines**

---

## Layer 4: Data Quality Validation (Production QA)

### Purpose
Validate **actual pipeline output** meets quality standards.

### Characteristics
- 🏭 **Production-Scale**: Processes entire run directories
- 📦 **Batch Processing**: Parallel execution with checkpointing
- 📋 **Comprehensive**: 12+ metrics per validation domain
- ✅ **Go/No-Go**: Blocking failures prevent downstream usage
- 📅 **Frequency**: After every preprocessing run

### What to Validate

#### Feature Quality Validation

**Script**: `scripts/validation/feature_quality/check_nlp_batch.py`

```bash
# After preprocessing run completes
RUN_DIR="data/processed/20251229_161906_preprocessing_648bf25"

python scripts/validation/feature_quality/check_nlp_batch.py \
    --run-dir "$RUN_DIR" \
    --max-workers 8 \
    --output reports/nlp_validation_$(date +%Y%m%d).json
```

**What it validates** (12 runtime metrics):

```yaml
Sentiment Validation:
  ✅ lm_hit_rate: >=2% (dictionary effectiveness)
  ✅ zero_vector_rate: <=50% (no empty segments)
  ✅ negative_gt_positive: true (10-K profile)
  ✅ uncertainty_negative_correlation: >=0.3 (domain consistency)

Readability Validation:
  ✅ gunning_fog_avg: 14-22 (appropriate complexity)
  ✅ gunning_fog_min: >=8 (no over-splitting)
  ✅ gunning_fog_max: <=35 (no missing periods)
  ✅ fk_fog_correlation: >=0.7 (metric consistency)
  ✅ fk_ari_correlation: >=0.7 (metric consistency)
  ✅ financial_adjustment_delta: >=0.005 (domain adjustment working)
  ✅ obfuscation_score_avg: 35-80 (reasonable range)
  ✅ obfuscation_complexity_corr: >=0.6 (score validity)
```

**Output**: JSON/Markdown report with Go/No-Go status

#### Extraction Quality Validation

**Script**: `scripts/validation/extraction_quality/check_extractor_batch.py`

```bash
# After extraction step
EXTRACT_DIR="data/interim/extracted/20251229_140000_batch_extract"

python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir "$EXTRACT_DIR" \
    --max-workers 8 \
    --format markdown \
    --output reports/extraction_qa_$(date +%Y%m%d).md
```

**What it validates** (8 extraction metrics):

```yaml
Extraction Accuracy:
  ✅ section_boundary_precision_start: >=0.95
  ✅ section_boundary_precision_end: >=0.95
  ✅ key_item_recall: >=0.99 (Item 1, 1A, 7, 7A)
  ✅ false_positive_rate: <=0.05

Content Quality:
  ✅ toc_filtering_rate: 1.0 (no ToC in output)
  ✅ page_header_filtering_rate: 1.0 (no headers)
  ✅ subsection_classification_accuracy: >=0.95
  ✅ noise_to_signal_ratio: <=0.05
```

#### Data Health Check Validation

**Script**: `scripts/validation/data_quality/check_preprocessing_batch.py`

```bash
# Validate complete preprocessing output
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir "$RUN_DIR" \
    --max-workers 8
```

**What it validates** (data health metrics):

```yaml
Completeness:
  ✅ All expected files present
  ✅ Required JSON fields exist
  ✅ No empty/null values

Cleanliness:
  ✅ No HTML artifacts
  ✅ No excessive whitespace
  ✅ Proper encoding (UTF-8)

Substance:
  ✅ Minimum text length
  ✅ Segment count in range
  ✅ Readability scores reasonable
```

---

## Decision Matrix: Which Test Type to Use?

| Question | Answer | Test Type |
|----------|--------|-----------|
| Does this function parse text correctly? | Code logic | **Unit Test** |
| Does the regex pattern match edge cases? | Code logic | **Unit Test** |
| Does save → load preserve data? | Pipeline integration | **Integration Test** |
| Do components work together? | Pipeline integration | **Integration Test** |
| Is this fast enough for production? | Performance | **Benchmark Test** |
| Does memory usage grow unbounded? | Performance | **Benchmark Test** |
| Is the extracted data high quality? | Data quality | **Validation Script** |
| Does output meet production standards? | Data quality | **Validation Script** |

---

## Best Practices for Your SEC Pipeline

### 1. **Test Pyramid Balance**

```
Ratio recommendation:
  Unit Tests:        70% (many, fast, isolated)
  Integration Tests: 20% (fewer, realistic)
  Benchmark Tests:    5% (rare, slow)
  Validation:         5% (after each run)
```

### 2. **Use Golden Sentences for Unit Tests**

```python
# tests/conftest.py
@pytest.fixture
def golden_sentence():
    """Deterministic test sentence with known LM matches."""
    return "The company anticipates litigation and catastrophic losses."

@pytest.fixture
def golden_expected():
    """Pre-computed expected values."""
    return {
        'negative_count': 3,      # catastrophic, losses, litigation
        'uncertainty_count': 1,    # anticipates
        'litigious_count': 1,      # litigation
    }
```

### 3. **Separate Test Data from Production Data**

```
tests/
└── fixtures/
    ├── sample_10k.html          # Small sample for tests
    └── golden_sentences.json    # Known-good test cases

data/
└── processed/                   # Production data (validated)
    └── 20251229_*/
```

### 4. **Use Markers for Test Organization**

```python
# pytest.ini
[pytest]
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (medium speed)
    slow: Benchmark tests (run separately)
    requires_data: Needs preprocessed data

# Run only fast tests in CI
pytest -m "unit and not slow"

# Run benchmarks manually
pytest -m slow --benchmark-only
```

### 5. **Validate After Every Pipeline Stage**

```bash
#!/bin/bash
# scripts/run_with_validation.sh

# Stage 1: Parse
python scripts/data_preprocessing/batch_parse.py
PARSE_DIR=$(ls -td data/interim/parsed/2025* | head -1)

# Stage 2: Extract
python scripts/data_preprocessing/batch_extract.py
EXTRACT_DIR=$(ls -td data/interim/extracted/2025* | head -1)

# ✅ VALIDATE extraction
python scripts/validation/extraction_quality/check_extractor_batch.py \
    --run-dir "$EXTRACT_DIR" || exit 1

# Stage 3: Clean & Segment
python scripts/data_preprocessing/run_preprocessing_pipeline.py
PROCESS_DIR=$(ls -td data/processed/2025* | head -1)

# ✅ VALIDATE data health
python scripts/validation/data_quality/check_preprocessing_batch.py \
    --run-dir "$PROCESS_DIR" || exit 1

# Stage 4: Extract Features
python scripts/feature_engineering/run_feature_pipeline.py
FEATURE_DIR=$(ls -td data/features/2025* | head -1)

# ✅ VALIDATE feature quality
python scripts/validation/feature_quality/check_nlp_batch.py \
    --run-dir "$FEATURE_DIR" || exit 1

echo "✅ All validations passed - data ready for training!"
```

---

## Summary: The Complete Testing Strategy

| Layer | Purpose | Tools | Frequency | Coverage |
|-------|---------|-------|-----------|----------|
| **Unit** | Code correctness | pytest | Every commit | 9 static metrics |
| **Integration** | Pipeline integrity | pytest + fixtures | Every PR | 2 serialization metrics |
| **Benchmark** | Performance baselines | pytest + profiling | Weekly | 3 performance metrics |
| **Validation** | Data quality | Batch scripts | After preprocessing | 28 runtime metrics |

**Total Metric Coverage**: 42 metrics across all quality dimensions

**Key Insight**: You need **BOTH**:
- ✅ **Unit tests** to ensure code works correctly
- ✅ **Validation scripts** to ensure output data meets quality standards

They serve different purposes and **both are essential** for a robust pipeline.
