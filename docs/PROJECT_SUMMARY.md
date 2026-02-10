# SEC 10-K Risk Factor Analyzer - Project Summary

## Project Objective

Build an NLP-powered system to **automatically analyze and categorize risk factors** from SEC 10-K and 10-Q filings. The project aims to transform unstructured regulatory text into structured, actionable insights about corporate risk exposure.

---

## Goals

### Primary Goals
1. **Parse SEC filings** - Extract semantic structure from HTML 10-K/10-Q filings using the sec-parser library
2. **Extract Risk Factors** - Isolate Item 1A (Risk Factors) section with high accuracy
3. **Segment risks** - Break down monolithic risk text into individual, discrete risk statements
4. **Classify risks** - Categorize each risk segment into standardized risk categories
5. **Generate features** - Extract quantitative NLP features (sentiment, readability, topic exposure) for downstream analysis

### Secondary Goals
- Provide an interactive UI for manual analysis (Streamlit)
- Enable model fine-tuning for improved classification accuracy
- Support batch processing of multiple filings
- Generate labeled training data for "Student" models

---

## Features

### Implemented Features

| Feature | Module | Status |
|---------|--------|--------|
| **SEC Filing Parser** | `src/preprocessing/parser.py` | Done |
| HTML parsing with sec-parser library | | |
| Semantic element extraction (titles, tables, text) | | |
| Tree structure preservation | | |
| 10-K and 10-Q form support | | |
| **Section Extractor** | `src/preprocessing/extractor.py` | Done |
| Risk Factors (Item 1A) extraction | | |
| MD&A (Item 7) extraction | | |
| Semantic tree navigation | | |
| Subsection identification | | |
| **Text Cleaner** | `src/preprocessing/cleaning.py` | Done |
| HTML artifact removal | | |
| Page number/header removal | | |
| Whitespace normalization | | |
| **Risk Segmenter** | `src/preprocessing/segmenter.py` | Done |
| Header/bullet-based segmentation | | |
| Paragraph fallback segmentation | | |
| Segment length filtering | | |
| **Zero-Shot Classifier** | `src/analysis/inference.py` | Done |
| Risk category classification | | |
| Configurable taxonomy (YAML) | | |
| Multi-label support | | |
| **Sentiment Analysis** | `src/features/sentiment.py` | Done |
| Loughran-McDonald dictionary | | |
| 8 sentiment categories | | |
| Count, ratio, proportion metrics | | |
| **Readability Analysis** | `src/features/readability/` | Done |
| 6 standard readability indices | | |
| Financial domain adjustments | | |
| Custom obfuscation score | | |
| **Topic Modeling** | `src/features/topic_modeling/` | Done |
| LDA model training | | |
| Document topic extraction | | |
| Topic entropy calculation | | |
| **Streamlit UI** | `src/visualization/app.py` | Done |
| File selection and processing | | |
| Results visualization | | |
| CSV export | | |
| **Configuration System** | `src/config.py` | Done |
| Pydantic V2 settings | | |
| YAML config files | | |
| Environment variable overrides | | |

### Features To Develop

| Feature | Priority | Description |
|---------|----------|-------------|
| **Model Fine-tuning Pipeline** | High | Train custom classifier on labeled data |
| **Batch Processing CLI** | High | Process multiple filings in batch mode |
| **SEC Downloader Integration** | Medium | Automated EDGAR filing downloads |
| **Database Integration** | Medium | Store results in PostgreSQL/MongoDB |
| **Drift Detection** | Medium | Monitor model performance over time |
| **API Endpoint** | Low | RESTful API for programmatic access |
| **Comparative Analysis** | Low | Cross-company/year risk comparison |
| **Trend Analysis** | Low | Track risk category changes over time |

### Features To Fix / Improve

| Issue | Priority | Description |
|-------|----------|-------------|
| **Extraction Accuracy** | High | Some non-standard filing formats fail to extract Item 1A |
| **Processing Speed** | Medium | Classification takes 5-10 min for large filings |
| **Text Length Truncation** | Medium | Long segments truncated to 2000 chars |
| **Segmentation Quality** | Medium | Heuristic-based; may not perfectly split risks |
| **Memory Usage** | Low | Large models consume 8GB+ RAM |
| **Import Missing** | Low | `auto_label.py` missing `PARSED_DATA_DIR`, `ensure_directories` imports |

---

## Business Logic

### Pipeline Architecture

```
                                      SEC EDGAR
                                          |
                                          v
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA COLLECTION                                 │
│   [SEC Downloader] → Download HTML filings from EDGAR                   │
└─────────────────────────────────────────────────────────────────────────┘
                                          |
                                          v
┌─────────────────────────────────────────────────────────────────────────┐
│                         PREPROCESSING                                   │
│   [Parser] → [Extractor] → [Cleaner] → [Segmenter]                     │
│                                                                         │
│   HTML → Semantic Tree → Item 1A Text → Clean Text → Risk Segments     │
└─────────────────────────────────────────────────────────────────────────┘
                                          |
                                          v
┌─────────────────────────────────────────────────────────────────────────┐
│                         FEATURE ENGINEERING                             │
│   [Sentiment] + [Readability] + [Topic Modeling] → Feature Vector      │
│                                                                         │
│   Categories:                                                           │
│   - Negative, Positive, Uncertainty, Litigious, etc. (LM Dictionary)   │
│   - Flesch-Kincaid, Gunning Fog, SMOG, etc. (Readability)             │
│   - Topic distributions (LDA)                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                          |
                                          v
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLASSIFICATION                                  │
│   [Zero-Shot Classifier] or [Fine-tuned Model]                         │
│                                                                         │
│   Risk Categories:                                                      │
│   - Market Risk            - Technology Risk                            │
│   - Operational Risk       - Legal Risk                                 │
│   - Financial Risk         - Strategic Risk                             │
│   - Regulatory Risk        - Human Capital Risk                         │
│   - Reputation Risk        - Environmental Risk                         │
│   - Geopolitical Risk      - Product/Service Risk                       │
└─────────────────────────────────────────────────────────────────────────┘
                                          |
                                          v
┌─────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT                                          │
│   - Streamlit Dashboard                                                 │
│   - CSV/JSON exports                                                    │
│   - Training data (JSONL)                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Risk Classification Taxonomy

The system uses a configurable YAML-based taxonomy (`risk_taxonomy.yaml`) with 12 standard risk categories:

1. **Market Risk** - Market volatility, competition, demand fluctuations
2. **Operational Risk** - Business operations, supply chain, execution
3. **Financial Risk** - Liquidity, credit, interest rates
4. **Regulatory and Compliance Risk** - Laws, regulations, compliance
5. **Technology Risk** - Cybersecurity, IT infrastructure
6. **Legal Risk** - Litigation, intellectual property
7. **Strategic Risk** - Business strategy, acquisitions
8. **Reputation Risk** - Brand reputation, public perception
9. **Human Capital Risk** - Talent retention, workforce management
10. **Environmental and Climate Risk** - Climate change, sustainability
11. **Geopolitical Risk** - International operations, political instability
12. **Product and Service Risk** - Product liability, quality issues

### Industry-Specific Classification (SASB)

The auto-labeling system supports **dynamic taxonomy selection** based on the company's SIC code:
- Maps SIC codes to SASB industries
- Loads industry-specific risk topics
- Ensures relevant risk categories for each company type

---

## Requirements

### System Requirements
- **Python**: >= 3.10
- **RAM**: 8GB minimum (16GB recommended for large filings)
- **Disk**: ~2GB for models and data

### Core Dependencies

```toml
# SEC Filing Parsing
sec-parser==0.54.0          # PINNED - semantic filing parser
sec-downloader>=0.10.0      # EDGAR download utility

# Core NLP/ML
transformers>=4.35.0        # Hugging Face models
torch>=2.0.0                # PyTorch
spacy>=3.7.0                # Text preprocessing
gensim>=4.0.0               # Topic modeling (LDA)
sentence-transformers>=2.2.2 # Embeddings

# Data Handling
pandas>=2.0.0
numpy>=1.24.0
dill>=0.3.7                 # Serialization

# UI/Visualization
streamlit>=1.28.0
matplotlib>=3.7.0
seaborn>=0.12.0

# Configuration
pydantic>=2.12.4            # ENFORCED - Pydantic V2
pydantic-settings>=2.0.0
PyYAML>=6.0
python-dotenv>=1.0.0

# Text Processing
beautifulsoup4>=4.12.0
lxml>=4.9.0
textstat                    # Readability metrics
scikit-learn>=1.3.0
```

### Optional Dependencies

```toml
# Fine-tuning
[finetune]
datasets, peft, bitsandbytes, accelerate, trl

# External Services
[external]
yfinance, openai

# Development
[dev]
pytest, pytest-cov, black, ruff, mypy, jupyter
```

### Required Downloads
```bash
# spaCy language model (REQUIRED)
python -m spacy download en_core_web_sm

# Loughran-McDonald Dictionary (for sentiment)
# Place in: data/dictionary/Loughran-McDonald_MasterDictionary_1993-2023.csv
```

---

## Project Structure

```
SEC finetune/
├── configs/                     # Configuration files
│   ├── config.yaml             # Main configuration
│   └── features/               # Feature-specific configs
│       ├── sentiment.yaml
│       ├── readability.yaml
│       ├── topic_modeling.yaml
│       └── risk_analysis.yaml
├── data/
│   ├── raw/                    # Input HTML filings
│   ├── interim/
│   │   ├── parsed/             # Parsed filing JSON
│   │   └── extracted/          # Extracted sections
│   ├── processed/
│   │   ├── labeled/            # Auto-labeled data
│   │   └── features/           # Computed features
│   └── dictionary/             # LM Dictionary
├── docs/                       # Documentation
├── models/                     # Trained models
│   ├── experiments/
│   ├── registry/
│   └── lda_item1a/             # Topic model
├── scripts/
│   ├── 01_data_collection/     # Download scripts
│   ├── 02_data_preprocessing/  # Parsing/extraction
│   ├── 03_eda/                 # Exploratory analysis
│   ├── 04_feature_engineering/ # Feature extraction
│   ├── 05_data_splitting/      # Train/test split
│   ├── 06_training/            # Model training
│   ├── 07_evaluation/          # Model evaluation
│   └── 08_inference/           # Prediction
├── src/
│   ├── analysis/
│   │   ├── inference.py        # Risk classifier
│   │   └── taxonomies/         # Risk taxonomies
│   ├── features/
│   │   ├── sentiment.py        # Sentiment analyzer
│   │   ├── dictionaries/       # LM Dictionary manager
│   │   ├── readability/        # Readability analyzer
│   │   └── topic_modeling/     # LDA trainer/analyzer
│   ├── preprocessing/
│   │   ├── parser.py           # SEC filing parser
│   │   ├── extractor.py        # Section extractor
│   │   ├── cleaning.py         # Text cleaner
│   │   └── segmenter.py        # Risk segmenter
│   ├── visualization/
│   │   └── app.py              # Streamlit UI
│   └── config.py               # Configuration management
├── tests/                      # Test suite
├── pyproject.toml              # Package configuration
└── README.md                   # Main documentation
```

---

## Quick Start

### Installation
```bash
# Clone and setup
git clone https://github.com/bethCoderNewbie/SEC-finetune.git
cd SEC-finetune

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Basic Usage
```bash
# Run Streamlit UI
streamlit run src/visualization/app.py

# Run preprocessing pipeline
python scripts/data_preprocessing/run_preprocessing_pipeline.py

# Extract features
python scripts/feature_engineering/extract_features.py
```

### Programmatic Usage
```python
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor
from src.analysis.inference import RiskClassifier

# Parse filing
parser = SECFilingParser()
filing = parser.parse_filing("data/raw/AAPL_10K.html", form_type="10-K")

# Extract Risk Factors
extractor = RiskFactorExtractor()
risk_section = extractor.extract(filing)

# Classify risks
classifier = RiskClassifier()
results = classifier.classify_segments(segments)
```

---

## Key Configurations

### Environment Variables (.env)
```bash
# Model Settings
MODELS_DEFAULT_MODEL=ProsusAI/finbert
MODELS_ZERO_SHOT_MODEL=facebook/bart-large-mnli

# Extraction Settings
EXTRACTION_MIN_CONFIDENCE=0.7
EXTRACTION_ENABLE_AUDIT_LOGGING=true

# Processing Settings
PREPROCESSING_MIN_SEGMENT_LENGTH=50
PREPROCESSING_MAX_SEGMENT_LENGTH=2000
```

### Risk Analysis Config (configs/features/risk_analysis.yaml)
```yaml
model:
  drift_threshold: 0.15
  labeling_model: "facebook/bart-large-mnli"
  labeling_batch_size: 16
  labeling_multi_label: true
  device: "auto"
```

---

## Version Information

| Component | Version |
|-----------|---------|
| Project | 0.1.0 |
| Python | >= 3.10 |
| sec-parser | 0.54.0 (pinned) |
| Pydantic | >= 2.12.4 (enforced) |

---

## License

MIT License - Educational and research purposes.

---

## Contact

For questions or issues:
- GitHub Issues: https://github.com/bethCoderNewbie/SEC-finetune/issues
- Email: beth88.career@gmail.com
