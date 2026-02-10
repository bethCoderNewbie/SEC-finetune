# Feature Engineering Scripts

Scripts for extracting semantic features from preprocessed SEC filings.

## Architecture

**Separation of Concerns**:
- `scripts/data_preprocessing/` → Structural operations (parse, extract, clean, segment)
- `scripts/feature_engineering/` → Semantic operations (sentiment, readability, topic modeling)

## Scripts

### `extract_sentiment_features.py`
Extract sentiment features using Loughran-McDonald dictionary.

**Input**: `data/processed/*_segmented_risks.json` (SegmentedRisks)
**Output**: `data/features/sentiment/*_sentiment.json` (List[SentimentFeatures])

**Usage**:
```bash
# Single file
python scripts/feature_engineering/extract_sentiment_features.py --input data/processed/AAPL_10K_segmented_risks.json

# Batch mode
python scripts/feature_engineering/extract_sentiment_features.py --batch

# With resume (skip already processed)
python scripts/feature_engineering/extract_sentiment_features.py --batch --resume
```

### `run_feature_pipeline.py`
Orchestrator that runs all feature extraction steps in sequence.

**Usage**:
```bash
# Run all features
python scripts/feature_engineering/run_feature_pipeline.py --batch

# Run specific features only
python scripts/feature_engineering/run_feature_pipeline.py --batch --features sentiment readability
```

## Pipeline Workflow

### Separated Pipeline (Recommended for Production)

```bash
# Step 1: Preprocessing (structural)
python scripts/data_preprocessing/run_preprocessing.py --batch
# → Output: data/processed/*_segmented_risks.json

# Step 2: Feature Engineering (semantic)
python scripts/feature_engineering/run_feature_pipeline.py --batch
# → Output: data/features/sentiment/*_sentiment.json
#           data/features/readability/*_readability.json
#           data/features/combined/*_features.json
```

### Combined Pipeline (Backward Compatible)

```bash
# Single command (mixes concerns for convenience)
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch
# → Output includes both segments AND sentiment features
```

## Future Features

- `extract_readability_metrics.py` - Flesch-Kincaid, FOG index, etc.
- `extract_topic_features.py` - LDA topic modeling
- `combine_features.py` - Merge all feature types into single JSON

## Design Principles

1. **Single Responsibility**: Each script does one thing well
2. **Composability**: Features can be run independently or orchestrated
3. **Idempotency**: Re-running produces same output
4. **Resume Support**: Skip already processed files with `--resume`
5. **Metadata Preservation**: Carry forward SIC codes, CIK, company name
