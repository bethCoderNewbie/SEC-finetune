# Quick Start Guide

## Repository Overview

This is a clean, well-organized Python project for SEC 10-K filing analysis using NLP.

## 📁 Directory Structure

```
sec-filing-analyzer/
├── 📚 docs/           → All documentation
├── 🛠️  scripts/        → Utility scripts (setup, validation)
├── 📦 src/            → Production code
│   └── preprocessing/ → Text cleaning (spaCy-powered)
├── 🧪 tests/          → Unit & integration tests
├── 📓 notebooks/      → Jupyter notebooks
├── ⚙️  configs/        → YAML configurations
└── 📊 data/           → Sample data (small files only)
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install all packages (includes spaCy)
pip install -e .
```

### 2. Download spaCy Model

```bash
# Option A: Automated (recommended)
python scripts/setup_nlp_models.py

# Option B: Manual
python -m spacy download en_core_web_sm
```

### 3. Verify Installation

```bash
python scripts/check_installation.py
```

Expected output:
```
[SUCCESS] ALL CHECKS PASSED - Installation is complete!
```

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| [INSTALLATION.md](INSTALLATION.md) | Complete installation guide |
| [CLEANING_SUMMARY.md](CLEANING_SUMMARY.md) | Text cleaning implementation |
| [FILE_ORGANIZATION.md](FILE_ORGANIZATION.md) | Where to put files |
| [code_guidance.md](code_guidance.md) | Coding standards |

## 🔧 Utility Scripts

Located in `scripts/`:

```bash
# Setup spaCy models (interactive)
python scripts/setup_nlp_models.py

# Verify installation
python scripts/check_installation.py
```

## 💻 Usage Example

### Basic Text Cleaning

```python
from src.preprocessing.cleaning import clean_filing_text

html_text = "<p>The company's revenue increased by 15%.</p>"
cleaned = clean_filing_text(html_text, remove_html=True)
print(cleaned)  # "The company's revenue increased by 15%."
```

### Advanced Preprocessing

```python
from src.preprocessing.cleaning import TextCleaner

# Initialize with all NLP features
cleaner = TextCleaner(
    use_lemmatization=True,
    remove_stopwords=True,
    remove_punctuation=True
)

# Clean HTML
text = cleaner.remove_html_tags(raw_html)

# Apply deep cleaning
cleaned = cleaner.clean_text(text, deep_clean=True)
```

More examples: [src/preprocessing/CLEANING_USAGE.md](../src/preprocessing/CLEANING_USAGE.md)

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/

# Run specific module tests
python tests/test_cleaning.py

# Run with coverage
pytest tests/ --cov=src
```

## 📝 Development Workflow

### 1. Prototyping
Use Jupyter notebooks in `notebooks/`:
```bash
jupyter notebook notebooks/02_preprocessing_dev.ipynb
```

### 2. Implementing
Write production code in `src/`:
```python
# Example: src/preprocessing/my_module.py
```

### 3. Testing
Add tests in `tests/`:
```python
# Example: tests/test_my_module.py
```

### 4. Documenting
Update docs in `docs/`:
```markdown
# Example: docs/MY_FEATURE.md
```

## 🗂️ File Organization Rules

| File Type | Location | Example |
|-----------|----------|---------|
| Production code | `src/` | `src/preprocessing/cleaning.py` |
| Utility scripts | `scripts/` | `scripts/check_installation.py` |
| Documentation | `docs/` | `docs/INSTALLATION.md` |
| Tests | `tests/` | `tests/test_cleaning.py` |
| Configs | `configs/` | `configs/model/llm_base.yaml` |
| Notebooks | `notebooks/` | `notebooks/01_exploration.ipynb` |

See [FILE_ORGANIZATION.md](FILE_ORGANIZATION.md) for details.

## 🔍 Key Features

### Text Cleaning Module

**Location**: `src/preprocessing/cleaning.py`

**Features**:
- ✅ HTML tag removal
- ✅ Text normalization
- ✅ Lemmatization (spaCy)
- ✅ Stop word removal
- ✅ Punctuation removal
- ✅ Number removal

**Documentation**:
- Usage guide: [src/preprocessing/CLEANING_USAGE.md](../src/preprocessing/CLEANING_USAGE.md)
- Quick reference: [src/preprocessing/QUICK_REFERENCE.md](../src/preprocessing/QUICK_REFERENCE.md)
- Summary: [CLEANING_SUMMARY.md](CLEANING_SUMMARY.md)

## 🆘 Troubleshooting

### Can't find spaCy model
```bash
python -m spacy download en_core_web_sm
```

### Import errors
```bash
pip install -e .
python scripts/check_installation.py
```

### Want detailed help
See [INSTALLATION.md](INSTALLATION.md) for complete troubleshooting.

## 📚 Learning More

1. **Start here**: This file (Quick Start)
2. **Installation**: [INSTALLATION.md](INSTALLATION.md)
3. **File organization**: [FILE_ORGANIZATION.md](FILE_ORGANIZATION.md)
4. **Text cleaning**: [CLEANING_SUMMARY.md](CLEANING_SUMMARY.md)
5. **Coding standards**: [code_guidance.md](code_guidance.md)

## 🎯 Common Tasks

### Add a new preprocessing module

```bash
# 1. Create module in src/preprocessing/
touch src/preprocessing/my_module.py

# 2. Add tests
touch tests/test_my_module.py

# 3. Document it
touch src/preprocessing/MY_MODULE_USAGE.md
```

### Add a new utility script

```bash
# 1. Create script
touch scripts/my_script.py

# 2. Update scripts README
# Add entry to scripts/README.md

# 3. Make executable (optional)
chmod +x scripts/my_script.py
```

### Update dependencies

```bash
# Edit pyproject.toml, then:
pip install -e .
```

## 🔗 Quick Links

- Main README: [../README.md](../README.md)
- Project structure: [../CURRENT_STRUCTURE.md](../CURRENT_STRUCTURE.md)
- Reorganization history: [../REORGANIZATION_SUMMARY.md](../REORGANIZATION_SUMMARY.md)
- Repository blueprint: [../repository.txt](../repository.txt)

---

**Welcome to the SEC Filing Analyzer!**

For questions or issues, check the documentation or run:
```bash
python scripts/check_installation.py
```

Last Updated: 2025-11-14
