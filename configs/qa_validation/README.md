# QA Validation Configuration

This directory contains QA validation thresholds for Go/No-Go test criteria.

## Directory Structure

```
configs/qa_validation/
├── README.md           # This file
├── extraction.yaml     # Section extractor and content quality thresholds
├── parsing.yaml        # SEC parser performance and stability thresholds
├── cleaning.yaml       # Text cleaner and segmenter thresholds
└── features.yaml       # Sentiment and readability analysis thresholds
```

## File Descriptions

### extraction.yaml
Thresholds for `SECSectionExtractor` (`src/preprocessing/extractor.py`):
- **extraction_accuracy**: Boundary precision, key item recall, false positive rate
- **content_quality**: ToC filtering, page header removal, subsection classification

### parsing.yaml
Thresholds for `SECFilingParser` (`src/preprocessing/parser.py`):
- **parser_performance**: P95 latency, throughput
- **parser_stability**: Error rate, idempotency

### cleaning.yaml
Thresholds for `TextCleaner` and `RiskSegmenter`:
- **cleaner_hygiene**: HTML tag removal, entity decode, whitespace normalization
- **cleaner_continuity**: Page number removal, sentence preservation
- **segmentation_distribution**: Segment counts, Gini coefficient, length variation
- **segmentation_quality**: Fallback rate, filtering

### features.yaml
Thresholds for feature extraction modules:
- **sentiment_analysis**: LM dictionary coverage, feature counts
- **readability_analysis**: Index counts, obfuscation score range

## Threshold Structure

Each threshold follows this schema:

```yaml
threshold_name:
  display_name: Human Readable Name
  metric_type: rate|count|score|latency|boolean|range
  target: 0.99           # Target value
  operator: ">="         # Comparison operator
  warn_threshold: 0.95   # Optional warning threshold
  blocking: true         # Is this a Go/No-Go blocker?
  description: What this threshold measures
  tags: [category, feature]
```

### Metric Types

| Type | Description | Example |
|------|-------------|---------|
| `rate` | 0.0 - 1.0 decimal | precision, recall |
| `count` | Integer counts | segment_count, word_count |
| `score` | 0 - 100 scale | gini_coefficient, obfuscation |
| `latency` | Seconds | p95_latency |
| `boolean` | True/False | is_idempotent |
| `range` | Min-max bounded | fk_grade (12-16) |

### Operators

| Operator | Meaning |
|----------|---------|
| `>=` | Greater than or equal |
| `>` | Greater than |
| `<=` | Less than or equal |
| `<` | Less than |
| `==` | Equal |

## Usage

### In Tests

```python
from src.config.qa_validation import ThresholdRegistry, ValidationResult

# Get threshold from config
threshold = ThresholdRegistry.get("key_item_recall")

# Validate actual measurement
result = ValidationResult.from_threshold(threshold, actual=0.98)
print(result.status)   # "PASS" or "FAIL" or "WARN"
print(result.go_no_go) # "GO" or "NO-GO" or "CONDITIONAL"
```

### Modifying Thresholds

Edit the YAML files directly - no code changes required:

```yaml
# configs/qa_validation/extraction.yaml
thresholds:
  extraction_accuracy:
    key_item_recall:
      target: 0.995  # Stricter threshold
```

### Environment Variable Override

```bash
# Override via environment variable (Pydantic Settings pattern)
QA_VALIDATION_THRESHOLDS_EXTRACTION_ACCURACY_KEY_ITEM_RECALL_TARGET=0.995
```

## Adding New Thresholds

1. Choose the appropriate file based on the module being tested
2. Add the threshold under the correct category
3. Include all required fields (display_name, metric_type, target, blocking)
4. Re-run tests to verify the threshold loads correctly

```yaml
# Example: Add a new segmentation threshold
segmentation_quality:
  new_threshold_name:
    display_name: New Threshold
    metric_type: rate
    target: 0.9
    operator: ">="
    blocking: false
    description: Description of what this measures
    tags: [segmenter, quality]
```

## Source Documentation

These thresholds are derived from QA metrics research:
- `thoughts/shared/research/2025-12-03_19-16_extractor_qa_metrics.md`
- `thoughts/shared/research/2025-12-03_19-45_parser_qa_metrics.md`
- `thoughts/shared/research/2025-12-03_20-23_cleaner_segmenter_qa_metrics.md`
- `thoughts/shared/research/2025-12-03_21-32_sentiment_readability_qa_metrics.md`
- `thoughts/shared/research/2025-12-15_18-26_flexible_test_metrics_architecture.md`
