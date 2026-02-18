# SEC 10-K Risk Factor Analyzer

An end-to-end NLP pipeline for downloading, parsing, and analyzing risk factors from SEC 10-K/10-Q filings. The pipeline extracts Item 1A (Risk Factors), cleans and segments the text, and produces structured feature datasets for model training or downstream analysis.

## Pipeline Overview

```
[EDGAR] → download_sec_filings.py
              ↓
          data/raw/*.html
              ↓
        [HTMLSanitizer] → pre-parse cleanup (EDGAR headers, unicode normalization)
              ↓
        [SECFilingParser] → ParsedFiling
              │               ├─ cik, ticker, company_name
              │               ├─ sic_code, sic_name, form_type
              │               └─ semantic element tree
              ↓
        [SECSectionExtractor] → ExtractedSection (Item 1A)
              │                   ├─ metadata preserved
              │                   └─ subsections, elements
              ↓
        [TextCleaner] → normalized text
              ↓
        [RiskSegmenter] → SegmentedRisks
              │             ├─ segments[] (RiskSegment)
              │             └─ metadata preserved end-to-end
              ↓
    ┌─────────┴──────────┐
[SentimentAnalyzer]  [ReadabilityAnalyzer]  [LDATrainer]
 (Loughran-McDonald)  (Flesch-Kincaid, FOG)  (topic modeling)
              ↓
          data/processed/features/
              ↓
        [Model Training / Fine-tuning]
```

### Metadata Preservation

Filing metadata flows through the entire pipeline without loss:

| Field | Source | Preserved in |
|-------|--------|-------------|
| `cik` | HTML header | ParsedFiling → ExtractedSection → SegmentedRisks |
| `ticker` | HTML header | ParsedFiling → ExtractedSection → SegmentedRisks |
| `company_name` | HTML header | ParsedFiling → ExtractedSection → SegmentedRisks |
| `sic_code` | HTML header | ParsedFiling → ExtractedSection → SegmentedRisks |
| `sic_name` | HTML header | ParsedFiling → ExtractedSection → SegmentedRisks |
| `form_type` | HTML header | ParsedFiling → ExtractedSection → SegmentedRisks |

## Project Structure

```
SEC-finetune/
├── configs/
│   ├── config.yaml              # Main configuration (sec-parser, models, preprocessing)
│   ├── features/                # Per-feature configs (sentiment, readability, topic modeling)
│   └── qa_validation/           # QA check thresholds (cleaning, extraction, parsing, features)
├── data/
│   ├── raw/                     # Downloaded SEC HTML filings
│   ├── interim/
│   │   ├── parsed/              # ParsedFiling JSON outputs
│   │   └── extracted/           # ExtractedSection + cleaned JSON outputs
│   ├── processed/
│   │   ├── features/            # Feature matrices (sentiment, readability)
│   │   └── labeled/             # Labeled datasets for training
│   └── dictionary/              # Loughran-McDonald sentiment dictionaries
├── src/
│   ├── config/                  # Pydantic v2 settings (paths, models, preprocessing, features)
│   │   ├── __init__.py          # settings singleton + legacy constants
│   │   ├── paths.py             # PathsConfig (all data dirs)
│   │   └── legacy.py            # Backward-compatible path constants
│   ├── preprocessing/
│   │   ├── pipeline.py          # SECPreprocessingPipeline orchestrator
│   │   ├── sanitizer.py         # HTMLSanitizer (pre-parse cleanup)
│   │   ├── parser.py            # SECFilingParser → ParsedFiling
│   │   ├── extractor.py         # SECSectionExtractor → ExtractedSection
│   │   ├── cleaning.py          # TextCleaner
│   │   ├── segmenter.py         # RiskSegmenter → SegmentedRisks
│   │   └── models/              # Pydantic models for each pipeline stage
│   ├── features/
│   │   ├── sentiment.py         # SentimentAnalyzer (Loughran-McDonald)
│   │   ├── readability.py       # ReadabilityAnalyzer (Flesch-Kincaid, FOG, SMOG)
│   │   └── topic_modeling.py    # TopicModelingAnalyzer, LDATrainer
│   ├── models/
│   │   └── registry.py          # ModelRegistryManager for trained model tracking
│   └── utils/
│       ├── parallel.py          # ParallelProcessor (ProcessPoolExecutor wrapper)
│       ├── worker_pool.py       # Shared worker initialization for multiprocessing
│       ├── checkpoint.py        # CheckpointManager (crash-safe batch recovery)
│       ├── state_manager.py     # StateManifest (hash-based incremental processing)
│       ├── resume.py            # ResumeFilter (output-existence-based skip)
│       ├── dead_letter_queue.py # DeadLetterQueue (quarantine failed files)
│       ├── progress_logger.py   # ProgressLogger, BatchProgressLogger
│       ├── resource_tracker.py  # ResourceTracker (per-module timing + memory)
│       ├── reporting.py         # ReportFormatter, MarkdownReportGenerator
│       ├── metadata.py          # RunMetadata (git SHA, timestamp, branch)
│       └── naming.py            # Output filename/run-ID formatting
├── scripts/
│   ├── data_collection/         # Download SEC filings from EDGAR
│   ├── data_preprocessing/      # Batch parse, extract, and combined pipeline scripts
│   ├── feature_engineering/     # Sentiment, readability, topic modeling extraction
│   ├── validation/              # Data quality checks (preprocessing, extraction, NLP)
│   ├── training/                # Fine-tune language models
│   ├── inference/               # Prediction on new filings
│   ├── evaluation/              # Model evaluation metrics
│   ├── data_splitting/          # Train/val/test splits
│   ├── eda/                     # Exploratory data analysis
│   └── utils/                   # Setup, debugging, retry helpers
├── tests/
│   ├── unit/
│   └── integration/
├── models/                      # Trained model checkpoints
├── logs/                        # Processing logs and dead letter queue
├── reports/                     # Generated batch reports
├── docs/                        # Project documentation
└── pyproject.toml
```

## Installation

**Requirements:** Python 3.10+

```bash
git clone https://github.com/bethCoderNewbie/SEC-finetune.git
cd SEC-finetune

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -e .
```

**Optional dependency groups:**
```bash
pip install -e ".[finetune]"    # Model fine-tuning (datasets, peft, trl, accelerate)
pip install -e ".[dev]"         # Development tools (pytest, black, ruff, mypy, jupyter)
pip install -e ".[all]"         # Everything
```

**Download spaCy model** (required for `deep_clean` mode):
```bash
python -m spacy download en_core_web_sm   # ~40 MB
# or for better accuracy:
python -m spacy download en_core_web_md
```

**Verify installation:**
```bash
python scripts/utils/check_installation.py
```

## Quick Start

### Single Filing (Python API)

```python
from src.preprocessing import process_filing

result = process_filing("data/raw/AAPL_10K.html")

print(f"Company: {result.company_name}")
print(f"CIK:     {result.cik}")
print(f"SIC:     {result.sic_code} - {result.sic_name}")
print(f"Segments: {len(result)}")

for seg in result.segments[:3]:
    print(f"[{seg.index}] {seg.text[:120]}...")

result.save_to_json("data/processed/AAPL_risks.json")
```

### Pipeline with Options

```python
from src.preprocessing import SECPreprocessingPipeline, PipelineConfig

config = PipelineConfig(
    deep_clean=True,            # spaCy-based cleaning
    save_intermediates=True,    # Write parsed/extracted to data/interim/
)

pipeline = SECPreprocessingPipeline(config)
result = pipeline.process_risk_factors("data/raw/AAPL_10K.html")
```

### Batch Processing (Python API)

```python
from pathlib import Path
from src.preprocessing import SECPreprocessingPipeline

pipeline = SECPreprocessingPipeline()
files = list(Path("data/raw").glob("*.html"))

results = pipeline.process_batch(
    files,
    output_dir=Path("data/processed"),
    resume=True,                # Skip already-processed files
)
```

## Command-Line Scripts

### Download Filings

```bash
python scripts/data_collection/download_sec_filings.py
```

### Module Entry Point (Single Filing)

Run the pipeline directly as a Python module for quick single-file processing:

```bash
# Process a 10-K filing (default form type)
python -m src.preprocessing data/raw/AAPL_10K_2025.html

# Process a 10-Q filing
python -m src.preprocessing data/raw/AFL_10Q_2024.html 10-Q
```

Prints company metadata and a preview of the first 3 risk segments:

```
SEC Preprocessing Pipeline
==================================================

Flow: Parse → Extract → Clean → Segment

Metadata preserved throughout:
  - sic_code, sic_name
  - cik, ticker, company_name
  - form_type

==================================================
Company: APPLE INC
CIK: 0000320193
SIC Code: 3571
SIC Name: ELECTRONIC COMPUTERS
Form Type: 10-K
Total Segments: 45

First 3 segments:
  [1] The following risk factors ...
```

> **Note:** Always invoke via `python -m src.preprocessing`, not `python src/preprocessing/pipeline.py` — running the module file directly triggers an import conflict with the package `__init__.py`.

### Preprocessing Pipeline (Parse → Extract → Clean → Segment + optional Sentiment)

```bash
# Single file
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --input data/raw/AAPL_10K.html

# Batch — all HTML files in data/raw/
python scripts/data_preprocessing/run_preprocessing_pipeline.py --batch

# Batch with options
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch \
    --workers 8 \
    --resume \
    --chunk-size 100 \
    --quiet

# Skip sentiment analysis (faster structural-only run)
python scripts/data_preprocessing/run_preprocessing_pipeline.py \
    --batch --no-sentiment
```

### Separated Preprocessing Scripts

For production workflows, use the separated scripts:

```bash
# Step 1: Parse HTML → ParsedFiling JSON  (data/interim/parsed/)
python scripts/data_preprocessing/batch_parse.py --batch --resume

# Step 2: Extract risk sections  (data/interim/extracted/)
python scripts/data_preprocessing/batch_extract.py --batch --resume
```

### Feature Engineering

```bash
# Full feature pipeline (sentiment + readability + topic modeling)
python scripts/feature_engineering/run_feature_pipeline.py --batch

# Sentiment only
python scripts/feature_engineering/extract_sentiment_features.py --batch
```

### Data Quality Validation

```bash
# Validate preprocessing output
python scripts/validation/data_quality/check_preprocessing_batch.py

# Validate extraction output
python scripts/validation/extraction_quality/check_extractor_batch.py
```

### Retry Failed Files

Files that timeout or raise exceptions are written to `logs/failed_files.json` automatically. To reprocess them:

```bash
python scripts/utils/retry_failed_files.py
```

## Output Format

Processed files are written to `data/processed/` as `{stem}_segmented_risks.json`:

```json
{
  "version": "2.0",
  "sic_code": "3571",
  "sic_name": "ELECTRONIC COMPUTERS",
  "cik": "0000320193",
  "company_name": "APPLE INC",
  "form_type": "10-K",
  "num_segments": 45,
  "aggregate_sentiment": {
    "avg_negative_ratio": 0.042,
    "avg_uncertainty_ratio": 0.031,
    "avg_positive_ratio": 0.018
  },
  "segments": [
    {
      "id": 1,
      "text": "...",
      "length": 612,
      "word_count": 98,
      "sentiment": { "negative_ratio": 0.05, ... }
    }
  ]
}
```

Intermediate outputs:
- `data/interim/parsed/{stem}_{form_type}_{timestamp}_parsed.json` — `ParsedFiling`
- `data/interim/extracted/{stem}_extracted_risks.json` — `ExtractedSection`
- `data/interim/extracted/{stem}_cleaned_risks.json` — cleaned `ExtractedSection`

## Configuration

All settings are managed via `configs/config.yaml` (Pydantic v2 Settings).

**Override via environment variable:**
```bash
export PREPROCESSING__TASK_TIMEOUT=2400
export PREPROCESSING__MAX_WORKERS=16
export SEC_PARSER__SUPPORTED_FORM_TYPES='["10-K"]'
```

**Override via config file** (`configs/config.yaml`):
```yaml
preprocessing:
  min_segment_length: 50
  task_timeout: 1200          # seconds per file in batch mode

models:
  default_model: "ProsusAI/finbert"
  zero_shot_model: "facebook/bart-large-mnli"
```

**Access in code:**
```python
from src.config import settings

print(settings.preprocessing.min_segment_length)
print(settings.paths.processed_data_dir)
```

## Resilience Features

The batch pipeline is designed for long-running jobs on large datasets:

| Feature | Implementation | Description |
|---------|---------------|-------------|
| Resume | `ResumeFilter` | Skip files whose output already exists |
| Incremental | `StateManifest` | Hash-based tracking; re-runs only changed files |
| Checkpoint | `CheckpointManager` | Save progress; resume after crash |
| Dead Letter Queue | `DeadLetterQueue` | Quarantine timeout/error files to `logs/failed_files.json` |
| Worker isolation | `ProcessPoolExecutor` + `worker_pool` | Each worker gets its own model copies; `max_tasks_per_child=50` prevents memory leaks |
| Resource tracking | `ResourceTracker` | Per-module wall-clock and RSS memory profiling |
| Progress logging | `ProgressLogger` | Real-time per-file logging to `data/processed/_progress.log` |

## src/utils Reference

| Module | Class / Function | Purpose |
|--------|-----------------|---------|
| `parallel.py` | `ParallelProcessor` | `ProcessPoolExecutor` wrapper with timeout, DLQ, and progress |
| `worker_pool.py` | `init_preprocessing_worker`, `get_worker_*` | Shared worker initialization for multiprocessing |
| `checkpoint.py` | `CheckpointManager` | Crash-safe batch state save/restore |
| `state_manager.py` | `StateManifest`, `compute_file_hash` | Hash-based incremental run tracking |
| `resume.py` | `ResumeFilter` | Output-existence-based file skip |
| `dead_letter_queue.py` | `DeadLetterQueue` | JSON-backed failed-file store |
| `progress_logger.py` | `ProgressLogger`, `BatchProgressLogger` | Real-time console + file logging |
| `resource_tracker.py` | `ResourceTracker`, `ResourceUsage` | Per-module timing and memory usage |
| `reporting.py` | `ReportFormatter`, `MarkdownReportGenerator` | Human-readable batch reports |
| `metadata.py` | `RunMetadata` | Capture git SHA, branch, timestamp for reproducibility |
| `naming.py` | `parse_run_dir_metadata`, `format_output_filename` | Consistent output file naming |

## Dependencies

Key dependencies (see `pyproject.toml` for the full list):

| Package | Version | Purpose |
|---------|---------|---------|
| `sec-parser` | `==0.54.0` | Semantic HTML parsing for SEC filings |
| `sec-downloader` | `>=0.10.0` | Download filings from SEC EDGAR |
| `pydantic` | `>=2.12.4` | Type-safe configuration and data models |
| `pydantic-settings` | `>=2.0.0` | Settings management |
| `transformers` | `>=4.35.0` | Hugging Face NLP models |
| `torch` | `>=2.0.0` | PyTorch |
| `spacy` | `>=3.7.0` | NLP (lemmatization, POS tagging) |
| `gensim` | `>=4.0.0` | LDA topic modeling |
| `sentence-transformers` | `>=2.2.2` | Semantic embeddings |
| `scikit-learn` | `>=1.3.0` | ML utilities |
| `pandas` | `>=2.0.0` | Data manipulation |
| `psutil` | `>=5.9.0` | Memory/CPU monitoring |
| `beautifulsoup4` | `>=4.12.0` | HTML parsing |
| `PyYAML` | `>=6.0` | Configuration files |
| `python-dotenv` | `>=1.0.0` | `.env` support |

## License

This project is for educational and research purposes.
