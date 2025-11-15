# SEC 10-K Risk Factor Analyzer - MVP

A minimal viable product for testing the core NLP analysis pipeline for SEC 10-K filings. This MVP processes a single local file through the complete pipeline: Parse → Extract → Clean → Segment → Categorize → Display.

## Purpose

This MVP is designed as a **vertical slice** to test the most critical, high-risk component—the NLP analysis logic—before investing in the surrounding infrastructure (databases, data acquisition, model fine-tuning).

## Features

- **Parse**: Read 10-K filing text files
- **Extract**: Identify and extract Risk Factors section (Item 1A)
- **Clean**: Normalize and clean extracted text
- **Segment**: Split text into individual risk segments
- **Categorize**: Classify risks using zero-shot classification
- **Display**: Interactive Streamlit UI with results visualization

## Architecture

```
data/raw/company_10k.txt
        ↓
    [Parser] → Parse .txt file
        ↓
    [Extractor] → Extract Item 1A
        ↓
    [Cleaner] → Clean text
        ↓
    [Segmenter] → Split into risks
        ↓
    [Classifier] → Zero-shot categorization
        ↓
    [Streamlit UI] → Display results
```

## Project Structure

```
sec-filing-analyzer/
├── data/
│   ├── raw/              # Place 10-K .txt files here
│   ├── interim/          # (Future) Intermediate data
│   └── processed/        # (Future) Final datasets
├── src/
│   ├── preprocessing/
│   │   ├── parser.py     # Parse .txt files
│   │   ├── extractor.py  # Extract Risk Factors section
│   │   ├── cleaning.py   # Clean text
│   │   └── segmenter.py  # Segment into individual risks
│   ├── analysis/
│   │   ├── inference.py  # Zero-shot classification
│   │   └── taxonomies/
│   │       └── risk_taxonomy.yaml  # Risk categories
│   └── visualization/
│       └── app.py        # Streamlit application
├── pyproject.toml       # Project metadata and dependencies
└── README.md            # This file
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip

### Setup

1. **Clone or navigate to the project directory**

```bash
cd "C:\Users\bichn\MSBA\SEC finetune"
```

2. **Create a virtual environment (recommended)**

```bash
python -m venv venv
```

3. **Activate the virtual environment**

Windows:
```bash
venv\Scripts\activate
```

Linux/Mac:
```bash
source venv/bin/activate
```

4. **Install dependencies**

```bash
pip install -e .
```

This will install:
- `sec-parser` - Parse SEC EDGAR filings
- `sec-downloader` - Download SEC filings from EDGAR
- `spacy` - Advanced NLP text preprocessing
- `streamlit` - Web UI framework
- `transformers` - Hugging Face transformers for NLP
- `torch` - PyTorch for model execution
- `pandas` - Data manipulation
- `PyYAML` - YAML parsing for taxonomy
- Other supporting libraries

**Optional**: Install with additional dependencies:
```bash
# For future model fine-tuning
pip install -e ".[finetune]"

# For development tools (pytest, black, mypy, jupyter)
pip install -e ".[dev]"

# Install everything
pip install -e ".[all]"
```

5. **Download spaCy language model (required)**

After installing the dependencies, you must download the spaCy language model:

```bash
python -m spacy download en_core_web_sm
```

This downloads the small English language model (~40MB) needed for text preprocessing. For better accuracy, you can use larger models:
```bash
# Medium model (40 MB) - better accuracy
python -m spacy download en_core_web_md

# Large model (560 MB) - best accuracy
python -m spacy download en_core_web_lg
```

## Usage

### Step 1: Prepare Data

Place a 10-K filing `.txt` file in the `data/raw/` directory.

Example:
```
data/raw/AAPL_10K_2023.txt
data/raw/MSFT_10K_2023.txt
```

You can download 10-K filings from [SEC EDGAR](https://www.sec.gov/edgar/searchedgar/companysearch.html).

### Step 2: Run the Application

```bash
streamlit run src/visualization/app.py
```

This will:
1. Start a local web server
2. Open your browser to `http://localhost:8501`
3. Display the SEC Risk Analyzer interface

### Step 3: Analyze a Filing

1. Select a filing from the dropdown menu
2. Click the "🚀 Run Analysis" button
3. Wait for the pipeline to complete (may take 5-10 minutes depending on filing size)
4. View the results:
   - Summary metrics
   - Risk category distribution chart
   - Detailed table of segments and categories
   - Full text of each segment (expandable)
5. Download results as CSV

## Risk Categories

The system classifies risks into the following categories (defined in `src/analysis/taxonomies/risk_taxonomy.yaml`):

- **Market Risk** - Market volatility, competition, demand fluctuations
- **Operational Risk** - Business operations, supply chain, execution
- **Financial Risk** - Liquidity, credit, interest rates
- **Regulatory and Compliance Risk** - Laws, regulations, compliance
- **Technology Risk** - Cybersecurity, IT infrastructure
- **Legal Risk** - Litigation, intellectual property
- **Strategic Risk** - Business strategy, acquisitions
- **Reputation Risk** - Brand reputation, public perception
- **Human Capital Risk** - Talent retention, workforce management
- **Environmental and Climate Risk** - Climate change, sustainability
- **Geopolitical Risk** - International operations, political instability
- **Product and Service Risk** - Product liability, quality issues

## Model

The MVP uses **zero-shot classification** via Hugging Face Transformers:

- **Model**: `facebook/bart-large-mnli`
- **Method**: Zero-shot classification (no training required)
- **Input**: Risk segment text
- **Output**: Category label + confidence score

This approach allows immediate testing without model training. Future iterations will implement fine-tuned models.

## Constraints and Limitations

### MVP Constraints (By Design)

- **Data**: Single local file only (no database)
- **Model**: Zero-shot only (no fine-tuning)
- **Infrastructure**: Local execution (no cloud services)
- **Performance**: Not optimized for speed

### Known Limitations

1. **Extraction Accuracy**: Relies on pattern matching for Item 1A; may fail on non-standard formats
2. **Segmentation Quality**: Heuristic-based; may not perfectly split risks
3. **Classification Accuracy**: Zero-shot models have lower accuracy than fine-tuned models
4. **Processing Time**: Classification can take 5-10 minutes for large filings
5. **Text Length**: Long segments are truncated to 2000 characters for classification

## Troubleshooting

### No .txt files found

**Issue**: Application shows "No .txt files found in data/raw/"

**Solution**:
1. Verify files are in the correct directory: `data/raw/`
2. Ensure files have `.txt` extension
3. Refresh the browser page after adding files

### Cannot find Risk Factors section

**Issue**: "Could not find Risk Factors section (Item 1A)"

**Solution**:
1. Verify the file is a 10-K (not 10-Q or other filing type)
2. Check that the file contains "Item 1A" or "ITEM 1A"
3. Try a different filing - some formats may not be compatible

### Model loading is slow

**Issue**: First run takes several minutes to load the model

**Solution**: This is expected behavior. The model downloads on first use (~1.5GB). Subsequent runs will be faster as the model is cached.

### Out of memory errors

**Issue**: System runs out of memory during classification

**Solution**:
1. Close other applications
2. Process smaller filings first
3. Consider using a machine with more RAM (8GB+ recommended)

## Next Steps (Beyond MVP)

This MVP validates the core analysis pipeline. Future enhancements include:

1. **Data Acquisition**: Automated EDGAR filing downloads
2. **Database Integration**: MongoDB for metadata, PostgreSQL for results
3. **Model Fine-tuning**: Train custom models on labeled data
4. **Batch Processing**: Process multiple filings
5. **API**: RESTful API for programmatic access
6. **Advanced Analytics**: Trend analysis, comparative analysis
7. **Deployment**: Cloud deployment for production use

## Technical Details

### Pipeline Components

#### 1. Parser (`src/preprocessing/parser.py`)
- Reads .txt files with encoding detection
- Handles UTF-8 and Latin-1 encodings
- Returns raw filing text

#### 2. Extractor (`src/preprocessing/extractor.py`)
- Uses regex patterns to locate Item 1A
- Identifies section boundaries
- Extracts Risk Factors text blob

#### 3. Cleaner (`src/preprocessing/cleaning.py`)
- Removes page numbers and headers
- Normalizes whitespace
- Removes HTML artifacts (if present)
- Standardizes punctuation

#### 4. Segmenter (`src/preprocessing/segmenter.py`)
- Segments by headers/bullet points (preferred)
- Falls back to paragraph-based segmentation
- Filters segments by length and quality
- Splits overly long segments

#### 5. Classifier (`src/analysis/inference.py`)
- Loads risk taxonomy categories
- Initializes zero-shot classification pipeline
- Classifies each segment
- Returns label, confidence, and all scores

#### 6. UI (`src/visualization/app.py`)
- Streamlit-based web interface
- File selection and processing
- Results visualization
- CSV export functionality

## Dependencies

Key dependencies (see `pyproject.toml` for complete list):

- `sec-parser==0.54.0` - SEC EDGAR filing parsing
- `sec-downloader>=0.10.0` - SEC filing downloads
- `spacy>=3.7.0` - Advanced NLP text preprocessing
- `streamlit>=1.28.0` - Web UI
- `transformers>=4.35.0` - NLP models
- `torch>=2.0.0` - Deep learning framework
- `pandas>=2.0.0` - Data manipulation
- `PyYAML>=6.0` - Configuration parsing

Optional dependency groups:
- `[finetune]` - Model fine-tuning tools (datasets, peft, trl, etc.)
- `[external]` - External services (yfinance, openai)
- `[dev]` - Development tools (pytest, black, mypy, jupyter)
- `[all]` - All optional dependencies

## Configuration

### Risk Taxonomy

Edit `src/analysis/taxonomies/risk_taxonomy.yaml` to modify risk categories:

```yaml
categories:
  - name: "Your Category Name"
    description: "Category description"
```

### Segmentation Parameters

Edit `src/config.py` to adjust:

```python
MIN_SEGMENT_LENGTH = 50    # Minimum characters
MAX_SEGMENT_LENGTH = 2000  # Maximum characters
```

### Model Selection

Edit `src/config.py` to change the zero-shot model:

```python
ZERO_SHOT_MODEL = "facebook/bart-large-mnli"  # Default
# ZERO_SHOT_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"  # Alternative
```

## License

This project is for educational and research purposes.

## Contact

For questions or issues, please contact the development team or create an issue in the project repository.

---

**Built with**: Python, Streamlit, Hugging Face Transformers, PyTorch
