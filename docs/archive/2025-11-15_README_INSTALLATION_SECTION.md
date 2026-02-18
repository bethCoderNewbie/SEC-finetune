# Installation Section for README.md

**Add this section to your main README.md**

---

## Installation

### Quick Install

```bash
# 1. Install the package
pip install -e .

# 2. Download spaCy model (REQUIRED)
python -m spacy download en_core_web_sm

# 3. Verify installation
python check_installation.py
```

### Automated Setup

```bash
# Install package
pip install -e .

# Run automated setup (downloads spaCy model)
python setup_nlp_models.py

# Verify everything works
python check_installation.py
```

### Step-by-Step Installation

#### 1. Prerequisites
- Python 3.10 or higher
- pip package manager
- Virtual environment (recommended)

#### 2. Create Virtual Environment (Optional but Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

#### 3. Install Dependencies

```bash
# Install all dependencies
pip install -e .
```

This installs:
- **spaCy** (3.7+) - Advanced text preprocessing
- **sec-parser** - SEC filing parsing
- **sec-downloader** - Download SEC filings
- **transformers** - NLP models
- **PyTorch** - Deep learning
- **pandas**, **numpy** - Data processing
- And more...

#### 4. Download spaCy Language Model (REQUIRED)

The text cleaning module requires a spaCy language model:

**Option A: Automated (Recommended)**
```bash
python setup_nlp_models.py
```

**Option B: Manual**
```bash
# Small model (12 MB) - Fast, recommended for most users
python -m spacy download en_core_web_sm

# Medium model (40 MB) - Better accuracy
python -m spacy download en_core_web_md

# Large model (560 MB) - Best accuracy
python -m spacy download en_core_web_lg
```

#### 5. Verify Installation

```bash
# Run installation check
python check_installation.py

# Test text cleaning module
python src/preprocessing/cleaning.py

# Run tests
python tests/test_cleaning.py
```

### Installation with Optional Features

```bash
# Install with development tools
pip install -e ".[dev]"

# Install with fine-tuning capabilities
pip install -e ".[finetune]"

# Install everything
pip install -e ".[all]"
```

### Troubleshooting

**Issue**: `Can't find model 'en_core_web_sm'`
```bash
# Solution: Download the model
python -m spacy download en_core_web_sm
```

**Issue**: `ModuleNotFoundError: No module named 'spacy'`
```bash
# Solution: Install spaCy
pip install spacy>=3.7.0
```

**Issue**: Installation verification fails
```bash
# Solution: Run the check script for details
python check_installation.py
```

For more troubleshooting, see [INSTALLATION.md](INSTALLATION.md)

---

## Quick Start

After installation, try the text cleaning module:

```python
from src.preprocessing.cleaning import clean_filing_text

# Basic HTML removal
html_text = "<p>The company's revenue increased by 15%.</p>"
cleaned = clean_filing_text(html_text, remove_html=True)
print(cleaned)  # Output: "The company's revenue increased by 15%."

# Advanced preprocessing with lemmatization
cleaned = clean_filing_text(
    html_text,
    remove_html=True,
    deep_clean=True,
    use_lemmatization=True,
    remove_stopwords=True
)
print(cleaned)  # Output: "company revenue increase"
```

For more examples, see:
- [Cleaning Usage Guide](src/preprocessing/CLEANING_USAGE.md)
- [Quick Reference](src/preprocessing/QUICK_REFERENCE.md)
- [Implementation Summary](CLEANING_SUMMARY.md)

---

## Project Structure

```
SEC finetune/
├── src/
│   └── preprocessing/
│       ├── cleaning.py           # Text cleaning module (spaCy-powered)
│       ├── CLEANING_USAGE.md     # Detailed usage guide
│       └── QUICK_REFERENCE.md    # Quick reference card
├── tests/
│   └── test_cleaning.py          # Test suite
├── setup_nlp_models.py           # Automated spaCy model setup
├── check_installation.py         # Installation verification
├── INSTALLATION.md               # Complete installation guide
├── pyproject.toml                # Project configuration
└── README.md                     # This file
```
