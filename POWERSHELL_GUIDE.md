# Complete PowerShell Usage Guide for SEC Filing Preprocessing Pipeline

This guide provides comprehensive PowerShell commands for running the SEC filing preprocessing pipeline on Windows.

## Table of Contents

1. [Environment Setup](#environment-setup)
2. [Quick Start](#quick-start)
3. [Preprocessing Scripts](#preprocessing-scripts)
4. [Common Workflows](#common-workflows)
5. [Advanced Usage](#advanced-usage)
6. [Troubleshooting](#troubleshooting)

---

## Environment Setup

### Initial Setup

```powershell
# Navigate to project directory
cd "C:\Users\bichn\MSBA\SEC finetune"

# Create virtual environment (first time only)
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -e .

# Download spaCy language model (required)
python -m spacy download en_core_web_sm
```

### Activation (Every Session)

```powershell
# Navigate to project directory
cd "C:\Users\bichn\MSBA\SEC finetune"

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Verify activation - you should see (venv) in your prompt
```

### Deactivation

```powershell
# Deactivate virtual environment when done
deactivate
```

### Execution Policy (If Needed)

If you get an error about script execution being disabled:

```powershell
# Check current execution policy
Get-ExecutionPolicy

# Set execution policy for current user (recommended)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or, temporarily bypass for the current session
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

---

## Quick Start

### Verify Installation

```powershell
# Activate environment first
.\venv\Scripts\Activate.ps1

# Run installation check
python scripts/utils/check_installation.py
```

Expected output:
```
✓ Core dependencies installed
✓ spaCy language model loaded
✓ Text cleaning module working
```

### Process Your First Filing

```powershell
# 1. Place HTML file in data/raw/
# Example: data/raw/goog-20241231.html

# 2. Parse the filing
python scripts/02_data_preprocessing/batch_parse.py

# 3. Inspect the results
python scripts/utils/inspection/inspect_parsed.py list
```

---

## Preprocessing Scripts

### 1. Setup NLP Models (`setup_nlp_models.py`)

Downloads spaCy language models with interactive menu.

**Location:** `scripts/utils/setup_nlp_models.py`

**Basic Usage:**
```powershell
python scripts/utils/setup_nlp_models.py
```

**What it does:**
- Presents menu to select model size (sm/md/lg)
- Downloads selected model
- Verifies installation

**When to use:**
- After initial installation
- To switch to larger model for better accuracy
- When setting up new development environment

---

### 2. Check Installation (`check_installation.py`)

Verifies all dependencies are correctly installed.

**Location:** `scripts/utils/check_installation.py`

**Basic Usage:**
```powershell
python scripts/utils/check_installation.py
```

**What it checks:**
- ✓ Core dependencies (spaCy, transformers, torch, pandas)
- ✓ SEC parsing libraries (sec-parser, sec-downloader)
- ✓ spaCy language model
- ✓ Text cleaning module
- ✓ Advanced NLP features

**Exit Codes:**
- `0` = All checks passed
- `1` = Some checks failed

**PowerShell check exit code:**
```powershell
python scripts/utils/check_installation.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Installation verified!" -ForegroundColor Green
} else {
    Write-Host "✗ Installation issues detected" -ForegroundColor Red
}
```

---

### 3. Batch Parse (`batch_parse.py`)

Parse all SEC filings in `data/raw/` and save as JSON files.

**Location:** `scripts/02_data_preprocessing/batch_parse.py`

**Basic Usage:**
```powershell
# Parse all HTML files in data/raw/ (10-K default)
python scripts/02_data_preprocessing/batch_parse.py

# Parse specific form type
python scripts/02_data_preprocessing/batch_parse.py --form-type 10-Q

# Parse from custom directory
python scripts/02_data_preprocessing/batch_parse.py --input-dir "C:\path\to\filings"

# Parse with custom file pattern
python scripts/02_data_preprocessing/batch_parse.py --pattern "AAPL*.html"

# Overwrite existing JSON files
python scripts/02_data_preprocessing/batch_parse.py --overwrite
```

**Options:**
- `--form-type` : `10-K` or `10-Q` (default: `10-K`)
- `--input-dir` : Custom input directory (default: `data/raw`)
- `--pattern` : File pattern to match (default: `*.html`)
- `--overwrite` : Overwrite existing JSON files

**Examples:**

```powershell
# Parse only Apple filings
python scripts/02_data_preprocessing/batch_parse.py --pattern "AAPL*.html"

# Parse 10-Q filings and overwrite existing
python scripts/02_data_preprocessing/batch_parse.py --form-type 10-Q --overwrite

# Process from downloads folder
python scripts/02_data_preprocessing/batch_parse.py --input-dir "C:\Users\bichn\Downloads\SEC_Filings"
```

**Output:**
- Saves to `data/interim/parsed/` as `.json` files
- Shows progress for each file
- Summary statistics at end

---

### 4. Inspect Parsed Filings (`inspect_parsed.py`)

Examine parsed filing JSON files.

**Location:** `scripts/utils/inspection/inspect_parsed.py`

**List all parsed files:**
```powershell
# List parsed files in default directory
python scripts/utils/inspection/inspect_parsed.py list

# List files in custom directory
python scripts/utils/inspection/inspect_parsed.py list "C:\path\to\parsed"
```

**Inspect specific file:**
```powershell
# Basic inspection
python scripts/utils/inspection/inspect_parsed.py inspect data/interim/parsed/AAPL_10K_2023.json

# Show sample content
python scripts/utils/inspection/inspect_parsed.py inspect data/interim/parsed/AAPL_10K_2023.json --samples

# Show more samples
python scripts/utils/inspection/inspect_parsed.py inspect data/interim/parsed/AAPL_10K_2023.json --samples --max-samples 10

# Hide sections
python scripts/utils/inspection/inspect_parsed.py inspect data/interim/parsed/AAPL_10K_2023.json --no-sections

# Hide element counts
python scripts/utils/inspection/inspect_parsed.py inspect data/interim/parsed/AAPL_10K_2023.json --no-elements
```

**Options:**
- `list [directory]` : List all JSON files
- `inspect <file>` : Inspect specific file
- `--samples` : Show sample element content
- `--max-samples N` : Show N samples (default: 5)
- `--no-sections` : Hide section names
- `--no-elements` : Hide element type counts

**Example Output:**
```
Form Type: 10-K
Total Elements: 1,234
File Size: 456.78 KB

--- Section Names ---
  1. ITEM 1A. RISK FACTORS
  2. ITEM 1B. UNRESOLVED STAFF COMMENTS

--- Element Type Counts ---
  TextElement: 890
  TitleElement: 145
  TableElement: 67
```

---

### 5. Run Preprocessing Pipeline (`run_preprocessing_pipeline.py`)

Run complete pipeline: Parse → Extract → Clean → Segment.

**Location:** `scripts/02_data_preprocessing/run_preprocessing_pipeline.py`

**Basic Usage:**
```powershell
# Process first file found in data/raw/
python scripts/02_data_preprocessing/run_preprocessing_pipeline.py

# Process specific file
python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K.html

# Process without saving intermediates
python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --no-save
```

**Options:**
- `--input` : Path to specific HTML file
- `--no-save` : Don't save intermediate results

**Pipeline Steps:**
1. **Parse** - Read and parse SEC filing
2. **Extract** - Extract Risk Factors section (Item 1A)
3. **Clean** - Normalize and clean text
4. **Segment** - Split into individual risk factors

---

## Common Workflows

### Workflow 1: Process Single Filing End-to-End

```powershell
# 1. Activate environment
.\venv\Scripts\Activate.ps1

# 2. Verify installation
python scripts/utils/check_installation.py

# 3. Place HTML file in data/raw/
# Example: AAPL_10K_2023.html

# 4. Run preprocessing pipeline
python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --input data/raw/AAPL_10K_2023.html

# 5. Inspect results
python scripts/utils/inspection/inspect_parsed.py inspect data/interim/parsed/AAPL_10K_2023.json --samples
```

---

### Workflow 2: Batch Process Multiple Filings

```powershell
# 1. Activate environment
.\venv\Scripts\Activate.ps1

# 2. Place multiple HTML files in data/raw/
# Example:
#   data/raw/AAPL_10K_2023.html
#   data/raw/MSFT_10K_2023.html
#   data/raw/GOOGL_10K_2023.html

# 3. Batch parse all files
python scripts/02_data_preprocessing/batch_parse.py

# 4. List all parsed files
python scripts/utils/inspection/inspect_parsed.py list

# 5. Inspect specific filing
python scripts/utils/inspection/inspect_parsed.py inspect data/interim/parsed/AAPL_10K_2023.json
```

---

### Workflow 3: Reprocess with Overwrite

```powershell
# 1. Activate environment
.\venv\Scripts\Activate.ps1

# 2. Reprocess all filings (overwrite existing)
python scripts/02_data_preprocessing/batch_parse.py --overwrite

# 3. Verify new results
python scripts/utils/inspection/inspect_parsed.py list
```

---

### Workflow 4: Process Only Specific Company

```powershell
# 1. Activate environment
.\venv\Scripts\Activate.ps1

# 2. Parse only Apple filings
python scripts/02_data_preprocessing/batch_parse.py --pattern "AAPL*.html"

# 3. Parse only Microsoft filings
python scripts/02_data_preprocessing/batch_parse.py --pattern "MSFT*.html"

# 4. Inspect results
python scripts/utils/inspection/inspect_parsed.py list
```

---

### Workflow 5: Setup New Development Environment

```powershell
# 1. Clone/download project
cd "C:\Users\bichn\MSBA\SEC finetune"

# 2. Create virtual environment
python -m venv venv

# 3. Activate environment
.\venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -e .

# 5. Setup NLP models (interactive)
python scripts/utils/setup_nlp_models.py
# Select: 1 (small model, fastest)

# 6. Verify installation
python scripts/utils/check_installation.py

# 7. Test with sample file
python scripts/02_data_preprocessing/batch_parse.py
```

---

## Advanced Usage

### Combining Commands with PowerShell

**Check if parsing succeeded:**
```powershell
python scripts/02_data_preprocessing/batch_parse.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Parsing completed successfully" -ForegroundColor Green
    python scripts/utils/inspection/inspect_parsed.py list
} else {
    Write-Host "✗ Parsing failed" -ForegroundColor Red
}
```

**Process multiple file patterns:**
```powershell
# Parse Apple, Microsoft, and Google filings
$patterns = @("AAPL*.html", "MSFT*.html", "GOOGL*.html")

foreach ($pattern in $patterns) {
    Write-Host "Processing: $pattern" -ForegroundColor Cyan
    python scripts/02_data_preprocessing/batch_parse.py --pattern $pattern
}
```

**Auto-inspect after parsing:**
```powershell
# Parse files
python scripts/02_data_preprocessing/batch_parse.py

# List all parsed files
python scripts/utils/inspection/inspect_parsed.py list

# Inspect each parsed file with samples
Get-ChildItem "data\interim\parsed\*.json" | ForEach-Object {
    Write-Host "`nInspecting: $($_.Name)" -ForegroundColor Yellow
    python scripts/utils/inspection/inspect_parsed.py inspect $_.FullName --samples --max-samples 3
}
```

**Count parsed files:**
```powershell
$parsedFiles = Get-ChildItem "data\interim\parsed\*.json"
Write-Host "Total parsed files: $($parsedFiles.Count)" -ForegroundColor Green
```

**Clear parsed cache:**
```powershell
# CAUTION: This deletes all parsed files
Remove-Item "data\interim\parsed\*.json" -Confirm
```

---

### Environment Variables

**Set custom paths:**
```powershell
# Set custom raw data directory
$env:RAW_DATA_DIR = "C:\Custom\Path\RawData"

# Set custom parsed data directory
$env:PARSED_DATA_DIR = "C:\Custom\Path\Parsed"

# Run script with custom paths
python scripts/02_data_preprocessing/batch_parse.py
```

**Use .env file (recommended):**

Create `.env` file in project root:
```
RAW_DATA_DIR=C:\Custom\Path\RawData
PARSED_DATA_DIR=C:\Custom\Path\Parsed
```

Then load in PowerShell:
```powershell
# Manually load .env file
Get-Content .env | ForEach-Object {
    $name, $value = $_.split('=')
    Set-Item -Path "env:$name" -Value $value
}
```

---

### Logging and Output Redirection

**Save output to file:**
```powershell
# Save parsing output to log file
python scripts/02_data_preprocessing/batch_parse.py | Tee-Object -FilePath "logs\parse_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# Save both stdout and stderr
python scripts/02_data_preprocessing/batch_parse.py *>&1 | Tee-Object -FilePath "logs\parse.log"
```

**Timestamp logs:**
```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
python scripts/02_data_preprocessing/batch_parse.py | Out-File "logs\batch_parse_$timestamp.log"
```

---

### Batch Processing with Loop

**Process files one at a time:**
```powershell
Get-ChildItem "data\raw\*.html" | ForEach-Object {
    Write-Host "`nProcessing: $($_.Name)" -ForegroundColor Cyan
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --input $_.FullName
}
```

**Process with error handling:**
```powershell
$files = Get-ChildItem "data\raw\*.html"
$successCount = 0
$errorCount = 0

foreach ($file in $files) {
    Write-Host "`nProcessing: $($file.Name)" -ForegroundColor Cyan

    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --input $file.FullName

    if ($LASTEXITCODE -eq 0) {
        $successCount++
        Write-Host "✓ Success" -ForegroundColor Green
    } else {
        $errorCount++
        Write-Host "✗ Failed" -ForegroundColor Red
    }
}

Write-Host "`nSummary:"
Write-Host "  Success: $successCount" -ForegroundColor Green
Write-Host "  Errors: $errorCount" -ForegroundColor Red
Write-Host "  Total: $($files.Count)"
```

---

## Troubleshooting

### Issue: Script execution is disabled

**Error:**
```
.\venv\Scripts\Activate.ps1 : File cannot be loaded because running scripts is disabled
```

**Solution:**
```powershell
# Set execution policy for current user
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or temporarily bypass
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

---

### Issue: Virtual environment not activating

**Symptoms:**
- Prompt doesn't show `(venv)`
- Commands use system Python instead of venv

**Solution:**
```powershell
# Ensure you're in correct directory
cd "C:\Users\bichn\MSBA\SEC finetune"

# Check if venv exists
Test-Path .\venv\Scripts\Activate.ps1

# If false, create venv again
python -m venv venv

# Activate with full path
.\venv\Scripts\Activate.ps1

# Verify activation
Get-Command python | Select-Object Source
# Should show: ...\venv\Scripts\python.exe
```

---

### Issue: Module not found errors

**Error:**
```
ModuleNotFoundError: No module named 'spacy'
```

**Solution:**
```powershell
# Ensure venv is activated
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -e .

# For specific module
pip install spacy

# Verify installation
python scripts/check_installation.py
```

---

### Issue: spaCy model not found

**Error:**
```
Can't find model 'en_core_web_sm'
```

**Solution:**
```powershell
# Download model
python -m spacy download en_core_web_sm

# Or use setup script
python scripts/utils/setup_nlp_models.py

# Verify model is installed
python -m spacy validate
```

---

### Issue: No HTML files found

**Error:**
```
No files matching '*.html' found in: data\raw
```

**Solution:**
```powershell
# Check if data/raw exists
Test-Path "data\raw"

# Create directory if needed
New-Item -ItemType Directory -Force -Path "data\raw"

# List files in directory
Get-ChildItem "data\raw"

# Move HTML files to data/raw
Move-Item "C:\Downloads\*.html" "data\raw\"

# Verify files
Get-ChildItem "data\raw\*.html"
```

---

### Issue: Permission denied on output directory

**Error:**
```
PermissionError: [Errno 13] Permission denied: 'data/interim/parsed'
```

**Solution:**
```powershell
# Create directory with proper permissions
New-Item -ItemType Directory -Force -Path "data\interim\parsed"

# Check directory permissions
Get-Acl "data\interim\parsed" | Format-List

# Run PowerShell as Administrator if needed
Start-Process powershell -Verb runAs
```

---

### Issue: Out of memory during parsing

**Symptoms:**
- Python crashes
- "MemoryError" exceptions

**Solution:**
```powershell
# Process files one at a time instead of batch
Get-ChildItem "data\raw\*.html" | ForEach-Object {
    python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --input $_.FullName
}

# Or process smaller files first
Get-ChildItem "data\raw\*.html" |
    Sort-Object Length |
    ForEach-Object {
        python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --input $_.FullName
    }

# Close other applications to free memory
```

---

### Issue: Path with spaces causing errors

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'C:\Users\bichn\MSBA\SEC'
```

**Solution:**
```powershell
# Always quote paths with spaces
python scripts/02_data_preprocessing/batch_parse.py --input-dir "C:\Users\bichn\MSBA\SEC finetune\data\raw"

# Or use PowerShell variables
$dataPath = "C:\Users\bichn\MSBA\SEC finetune\data\raw"
python scripts/02_data_preprocessing/batch_parse.py --input-dir $dataPath
```

---

## Quick Reference

### Essential Commands

```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Verify installation
python scripts/utils/check_installation.py

# Parse all filings
python scripts/02_data_preprocessing/batch_parse.py

# List parsed files
python scripts/utils/inspection/inspect_parsed.py list

# Inspect specific file
python scripts/utils/inspection/inspect_parsed.py inspect data/interim/parsed/FILE.json --samples

# Run full pipeline
python scripts/02_data_preprocessing/run_preprocessing_pipeline.py
```

### Directory Structure

```
data/
├── raw/              # Place HTML files here
├── interim/
│   └── parsed/       # Parsed JSON files saved here
└── processed/        # Final processed data (future)

scripts/
├── 01_data_collection/           # Data acquisition
├── 02_data_preprocessing/        # Parsing & preprocessing
│   ├── batch_parse.py            # Batch parsing
│   └── run_preprocessing_pipeline.py  # Full pipeline
├── 03_eda/                       # Exploratory data analysis
├── 04_feature_engineering/       # Feature extraction
├── 05_data_splitting/            # Train/test splits
├── 06_training/                  # Model training
├── 07_evaluation/                # Model evaluation
├── 08_inference/                 # Predictions
├── 09_deployment/                # Deployment (planned)
├── 10_monitoring/                # Monitoring (planned)
├── utils/                        # Utilities
│   ├── check_installation.py     # Verify installation
│   ├── setup_nlp_models.py       # Setup spaCy models
│   ├── debugging/                # Debug tools
│   ├── inspection/
│   │   └── inspect_parsed.py     # Inspect parsed files
│   └── testing/
└── README.md                     # Scripts documentation
```

### File Extensions

- **Input**: `.html` (SEC filings in HTML format)
- **Parsed**: `.json` (JSON files with parsed data)
- **Text**: `.txt` (Plain text filings - also supported)

---

## Additional Resources

- **Main README**: `README.md` - Project overview and installation
- **Scripts README**: `scripts/README.md` - Detailed script documentation
- **Configuration**: `src/config.py` - Adjust paths and settings
- **Requirements**: `requirements.txt` - Dependency list

---

## Getting Help

```powershell
# Script help
python scripts/02_data_preprocessing/batch_parse.py --help
python scripts/utils/inspection/inspect_parsed.py --help
python scripts/02_data_preprocessing/run_preprocessing_pipeline.py --help

# Python package help
python -c "from src.preprocessing.parser import SECFilingParser; help(SECFilingParser)"

# Load a parsed JSON file
python -c "from src.preprocessing.parser import ParsedFiling; data = ParsedFiling.load_from_pickle('data/interim/parsed/file.json'); print(data['section_names'])"

# spaCy info
python -m spacy info

# Pip package list
pip list

# Check Python version
python --version
```

---

**Last Updated**: 2024
**PowerShell Version**: 5.1+
**Windows Compatibility**: Windows 10/11
