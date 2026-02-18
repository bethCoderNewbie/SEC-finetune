# Feature Engineering Guide

## Overview

Feature engineering scripts extract semantic features from preprocessed SEC filings following the **separation of concerns** principle.

## Architecture

### Separated Pipeline (Recommended for Production)

```
Preprocessing (Structural)          Feature Engineering (Semantic)
------------------------           -------------------------------
Parse → Extract → Clean             Sentiment Analysis
       ↓                                   ↓
    Segment                          Readability Metrics (future)
       ↓                                   ↓
SegmentedRisks.json                  Topic Modeling (future)
                                            ↓
                                    Combined Features
```

**Directory Structure**:
```
scripts/
├─ data_preprocessing/
│  ├─ run_preprocessing_pipeline.py    # Combined (backward compatible)
│  └─ run_preprocessing.py             # Pure preprocessing (future)
└─ feature_engineering/
   ├─ extract_sentiment_features.py    # Sentiment analysis
   ├─ extract_readability_metrics.py   # Readability (TODO)
   ├─ extract_topic_features.py        # Topic modeling (TODO)
   └─ run_feature_pipeline.py          # Orchestrator
```

## Quick Start

### Option 1: Separated Pipeline (MLOps Best Practice)

```bash
# Step 1: Preprocessing (structural operations only)
python scripts/data_preprocessing/run_preprocessing.py --batch

# Step 2: Feature Engineering (semantic operations)
python scripts/feature_engineering/run_feature_pipeline.py --batch

# Or run specific features only
python scripts/feature_engineering/extract_sentiment_features.py --batch
```

### Option 2: Combined Pipeline (Backward Compatible)

```bash
# Single command (mixes preprocessing + sentiment for convenience)
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch
```

## Feature Extractors

### Sentiment Analysis (`extract_sentiment_features.py`)

Extracts Loughran-McDonald financial sentiment features.

**Input**: `data/processed/*_segmented_risks.json`
**Output**: `data/features/sentiment/*_sentiment.json`

**Features extracted**:
- Negative, Positive, Uncertainty word counts/ratios
- Litigious, Constraining, Strong/Weak Modal counts/ratios
- Complexity metrics
- Aggregate statistics

**Usage**:
```bash
# Single file
python scripts/feature_engineering/extract_sentiment_features.py \
    --input data/processed/AAPL_10K_segmented_risks.json

# Batch mode
python scripts/feature_engineering/extract_sentiment_features.py --batch

# With resume (skip already processed)
python scripts/feature_engineering/extract_sentiment_features.py --batch --resume

# Parallel processing
python scripts/feature_engineering/extract_sentiment_features.py --batch --workers 4
```

**Output Format**:
```json
{
  "version": "1.0",
  "source_file": "AAPL_10K_segmented_risks.json",
  "sic_code": "3571",
  "sic_name": "ELECTRONIC COMPUTERS",
  "cik": "0000320193",
  "company_name": "Apple Inc.",
  "aggregate_sentiment": {
    "num_segments": 45,
    "avg_negative_ratio": 0.0234,
    "avg_positive_ratio": 0.0187,
    "avg_uncertainty_ratio": 0.0312
  },
  "segment_features": [
    {
      "text_length": 1250,
      "word_count": 215,
      "negative_count": 5,
      "positive_count": 3,
      "negative_ratio": 0.0233,
      ...
    }
  ]
}
```

### Readability Metrics (Coming Soon)

Extract readability indices: Flesch-Kincaid, FOG, SMOG, etc.

**Planned Usage**:
```bash
python scripts/feature_engineering/extract_readability_metrics.py --batch
```

### Topic Modeling (Coming Soon)

Extract LDA topic distributions.

**Planned Usage**:
```bash
python scripts/feature_engineering/extract_topic_features.py --batch
```

## Orchestrator (`run_feature_pipeline.py`)

Runs multiple feature extractors in sequence.

**Usage**:
```bash
# Run all available features
python scripts/feature_engineering/run_feature_pipeline.py --batch

# Run specific features only
python scripts/feature_engineering/run_feature_pipeline.py \
    --batch --features sentiment readability

# List available features
python scripts/feature_engineering/run_feature_pipeline.py --list

# With resume and parallel processing
python scripts/feature_engineering/run_feature_pipeline.py \
    --batch --resume --workers 4
```

## Data Flow

### Input (from preprocessing)
```
data/processed/
└─ {ticker}_{form}_{year}_segmented_risks.json
   ├─ version: "2.0"
   ├─ sic_code, sic_name, cik, company_name
   ├─ num_segments: 45
   └─ segments: [
        {text: "...", word_count: 215, ...}
      ]
```

### Output (feature engineering)
```
data/features/
├─ sentiment/
│  ├─ {ticker}_{form}_{year}_sentiment.json
│  └─ batch_sentiment_summary.json
├─ readability/ (future)
│  └─ {ticker}_{form}_{year}_readability.json
├─ topics/ (future)
│  └─ {ticker}_{form}_{year}_topics.json
└─ combined/ (future)
   └─ {ticker}_{form}_{year}_features.json
```

## Best Practices

### 1. Separation of Concerns
- Use **preprocessing** for structural operations (parse, extract, clean, segment)
- Use **feature engineering** for semantic operations (sentiment, readability, topics)
- Don't mix them in the same script (except for backward compatibility)

### 2. Metadata Preservation
All feature extractors preserve metadata from preprocessing:
- `sic_code`, `sic_name` (industry classification)
- `cik` (SEC identifier)
- `ticker`, `company_name`
- `form_type` (10-K, 10-Q)

### 3. Idempotency
Feature extraction is idempotent - re-running produces the same output.
Use `--resume` to skip already processed files.

### 4. Resume Support
For large batches, use `--resume` to continue interrupted runs:
```bash
python scripts/feature_engineering/extract_sentiment_features.py --batch --resume
```

### 5. Performance Tuning
Control parallelism with `--workers`:
```bash
# Use all CPU cores
python scripts/feature_engineering/extract_sentiment_features.py --batch

# Limit to 4 workers
python scripts/feature_engineering/extract_sentiment_features.py --batch --workers 4

# Sequential processing
python scripts/feature_engineering/extract_sentiment_features.py --batch --workers 1
```

## Migration Path

### Current Users (Using Combined Script)
Continue using the combined script:
```bash
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch
```

### New Users (Production MLOps)
Use separated pipeline:
```bash
# Step 1: Preprocessing
python scripts/data_preprocessing/run_preprocessing.py --batch

# Step 2: Feature Engineering
python scripts/feature_engineering/run_feature_pipeline.py --batch
```

## Extending the Pipeline

### Adding a New Feature Extractor

1. Create script: `scripts/feature_engineering/extract_{feature_name}_features.py`
2. Follow the pattern from `extract_sentiment_features.py`:
   - Read from `data/processed/*_segmented_risks.json`
   - Extract features using `src/features/{feature_name}.py`
   - Save to `data/features/{feature_name}/`
   - Support `--batch`, `--resume`, `--workers` flags
3. Add to `AVAILABLE_FEATURES` in `run_feature_pipeline.py`
4. Update this documentation

**Template**:
```python
"""
Extract {Feature Name} from Preprocessed Segments

Input:  data/processed/*_segmented_risks.json
Output: data/features/{feature_name}/*_{feature_name}.json
"""

from src.preprocessing.models import SegmentedRisks
from src.features.{feature_name} import {FeatureAnalyzer}

def extract_features(input_file: Path) -> Dict[str, Any]:
    # Load preprocessed segments
    risks = SegmentedRisks.load_from_json(input_file)

    # Extract features
    analyzer = {FeatureAnalyzer}()
    features = analyzer.extract_features_batch(risks.get_texts())

    # Build output with metadata
    return {
        'version': '1.0',
        'sic_code': risks.sic_code,
        'company_name': risks.company_name,
        'features': features
    }
```

## Troubleshooting

### No input files found
```bash
# Check that preprocessing has been run
ls data/processed/*_segmented_risks.json

# If empty, run preprocessing first
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch
```

### Feature already processed (resume mode)
```bash
# This is expected - files are skipped automatically
# To force re-processing, delete output files:
rm data/features/sentiment/{ticker}_*_sentiment.json

# Or disable resume mode:
python scripts/feature_engineering/extract_sentiment_features.py --batch
```

### Import errors
```bash
# Ensure you're in the project root directory
cd "C:/Users/bichn/MSBA/SEC finetune"

# Verify Python path
python -c "import sys; print('\n'.join(sys.path))"
```

## References

- **Research Document**: `thoughts/shared/research/2025-12-28_19-30_preprocessing_script_deduplication.md`
- **Production Standards**: `thoughts/shared/research/2025-12-28_13-45-00_naming_and_reporting_rules.md`
- **Source Code**: `scripts/feature_engineering/`
