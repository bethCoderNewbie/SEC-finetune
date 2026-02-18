# Installation Guide

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git (optional, for version control)

## Quick Start

### 1. Clone or Download the Repository

```bash
cd "C:\Users\bichn\MSBA\SEC finetune"
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
# source venv/bin/activate
```

### 3. Install Dependencies

#### Option A: Using pip with requirements.txt (Recommended)

```bash
# Install main dependencies
pip install -r requirements.txt

# For development (includes testing, code quality tools)
pip install -r requirements-dev.txt
```

#### Option B: Using pyproject.toml

```bash
# Install main package
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"

# Install with all optional dependencies
pip install -e ".[all]"
```

### 4. Verify Installation

```bash
# Verify sec-parser is installed
python -c "import sec_parser; print(f'sec-parser version: {sec_parser.__version__}')"

# Expected output: sec-parser version: 0.54.0
```

### 5. Set Up Environment Variables

```bash
# Copy template
cp .env.example .env

# Edit .env file with your configuration
# (optional - defaults will work for basic usage)
```

### 6. Create Required Directories

```bash
python -c "from src.config import ensure_directories; ensure_directories()"
```

This will create:
- `data/raw/`
- `data/interim/`
- `data/processed/`
- `models/`
- `logs/`
- `logs/extractions/`

## Verify Installation

Run the test script:

```bash
# Test parser import
python src/preprocessing/parser.py

# Test extractor import
python src/preprocessing/extractor.py

# Test config
python src/config.py
```

Expected output: No errors, informational messages about available sections and configuration.

## Download Sample Filing

To test the installation with real data:

```python
from sec_downloader import Downloader
from pathlib import Path

# Initialize downloader
dl = Downloader("YourCompanyName", "your@email.com")

# Download Apple's latest 10-K
html = dl.get_filing_html(ticker="AAPL", form="10-K")

# Save to data directory
output_file = Path("data/raw/AAPL_10K_latest.html")
output_file.write_text(html, encoding='utf-8')

print(f"Downloaded: {output_file}")
```

Or use the command line:

```bash
python -c "
from sec_downloader import Downloader
from pathlib import Path

dl = Downloader('MyCompany', 'email@example.com')
html = dl.get_filing_html(ticker='AAPL', form='10-K')
Path('data/raw/AAPL_10K.html').write_text(html, encoding='utf-8')
print('Downloaded AAPL 10-K')
"
```

## Run Example Scripts

```bash
# Run basic extraction example
python examples/01_basic_extraction.py

# Run complete pipeline example
python examples/02_complete_pipeline.py
```

## Common Installation Issues

### Issue 1: sec-parser not found

**Error:**
```
ModuleNotFoundError: No module named 'sec_parser'
```

**Solution:**
```bash
pip install sec-parser==0.54.0
```

### Issue 2: Torch installation issues

**Error:**
```
Could not find a version that satisfies the requirement torch
```

**Solution (Windows with CUDA):**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

**Solution (CPU only):**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Issue 3: Python version too old

**Error:**
```
requires-python = ">=3.10" but you have Python 3.9
```

**Solution:**
Install Python 3.10 or higher:
- Download from https://www.python.org/downloads/
- Or use pyenv: `pyenv install 3.10.0`

### Issue 4: Permission errors on Windows

**Error:**
```
PermissionError: [WinError 5] Access is denied
```

**Solution:**
Run terminal as Administrator or install packages with `--user` flag:
```bash
pip install -r requirements.txt --user
```

## Development Setup

For contributors and developers:

### 1. Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

### 2. Set Up Pre-commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install
```

### 3. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### 4. Code Quality Checks

```bash
# Format code with black
black src/ tests/

# Sort imports
isort src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type checking with mypy
mypy src/
```

## Updating Dependencies

### Update sec-parser

```bash
# Check current version
pip show sec-parser

# Update to specific version (update requirements.txt first)
pip install sec-parser==0.55.0

# Update pyproject.toml
# Edit: sec-parser==0.55.0
```

### Update All Dependencies

```bash
# Update to latest compatible versions
pip install --upgrade -r requirements.txt
```

## Uninstallation

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment
rm -rf venv

# Or on Windows
rmdir /s venv
```

## Docker Installation (Optional)

If you prefer using Docker:

```bash
# Build image
docker build -t sec-filing-analyzer .

# Run container
docker run -it -v $(pwd)/data:/app/data sec-filing-analyzer

# Run examples in container
docker run -it sec-filing-analyzer python examples/01_basic_extraction.py
```

## Troubleshooting

### Check Python Version

```bash
python --version
# Should be 3.10.0 or higher
```

### Check pip Version

```bash
pip --version
# Should be recent version
```

### List Installed Packages

```bash
pip list | grep sec
# Should show:
# sec-downloader  x.x.x
# sec-parser      0.54.0
```

### Verify Import Paths

```python
import sys
print('\n'.join(sys.path))
```

### Clear pip Cache

```bash
pip cache purge
```

### Reinstall from Scratch

```bash
# Remove virtual environment
deactivate
rm -rf venv

# Create new environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Reinstall
pip install -r requirements.txt
```

## Next Steps

1. Review `docs/USAGE_GUIDE_SEC_PARSER.md` for API documentation
2. Run examples in `examples/` directory
3. Check `notebooks/` for interactive tutorials
4. Read `README.md` for project overview

## Support

- Check documentation in `docs/`
- Review examples in `examples/`
- Open issue on GitHub (if applicable)
- Check sec-parser docs: https://sec-parser.readthedocs.io/
