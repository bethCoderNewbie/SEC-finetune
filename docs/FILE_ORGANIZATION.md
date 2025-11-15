# File Organization Guide

## Current Repository Structure

This document describes the actual file organization of the SEC Filing Analyzer project and explains where different types of files should be placed.

## Directory Structure

```
sec-filing-analyzer/
├── .github/              # GitHub-specific files (CI/CD)
├── configs/              # Hydra/YAML configs for experiments
├── data/                 # Data versioned by DVC (small samples only)
│   ├── external/         # Third-party data sources
│   ├── interim/          # Transformed data
│   ├── processed/        # Final datasets for training
│   └── raw/              # Original, immutable data
│
├── docs/                 # ✓ PROJECT DOCUMENTATION
│   ├── requirements/     # Historical requirements files
│   │   └── requirements_cleaning.txt
│   ├── INSTALLATION.md             # Complete installation guide
│   ├── CLEANING_SUMMARY.md         # Text cleaning implementation summary
│   ├── PYPROJECT_UPDATE_SUMMARY.md # Dependency management documentation
│   ├── README_INSTALLATION_SECTION.md  # Template for README
│   ├── code_guidance.md            # Coding standards and guidelines
│   ├── USAGE_GUIDE_SEC_PARSER.md   # SEC parser usage guide
│   └── FILE_ORGANIZATION.md        # This file
│
├── models/               # Serialized model checkpoints
│
├── notebooks/            # Jupyter notebooks for exploration
│   ├── 01_data_exploration.ipynb
│   ├── 02_preprocessing_dev.ipynb
│   └── ...
│
├── prompts/              # LLM prompt templates (versioned)
│
├── reports/              # Generated analysis and figures
│
├── scripts/              # ✓ UTILITY SCRIPTS
│   ├── README.md                   # Scripts documentation
│   ├── setup_nlp_models.py         # spaCy model downloader
│   └── check_installation.py       # Installation verification
│
├── src/                  # ✓ MAIN SOURCE CODE
│   ├── __init__.py
│   │
│   ├── acquisition/      # 1. Data acquisition from EDGAR
│   │   ├── __init__.py
│   │   └── edgar_client.py
│   │
│   ├── storage/          # Database and data lake I/O
│   │   ├── __init__.py
│   │   ├── db_clients.py
│   │   ├── mongo_repo.py
│   │   ├── postgres_repo.py
│   │   └── schemas/
│   │
│   ├── preprocessing/    # 2. Text preprocessing and extraction
│   │   ├── __init__.py
│   │   ├── parser.py             # HTML/XML parsing
│   │   ├── extractor.py          # Section extraction
│   │   ├── cleaning.py           # ✓ Text cleaning (spaCy-powered)
│   │   ├── segmenter.py          # Text segmentation
│   │   ├── CLEANING_USAGE.md     # Detailed cleaning module docs
│   │   └── QUICK_REFERENCE.md    # Quick reference for cleaning
│   │
│   ├── analysis/         # 3. NLP and analysis
│   │   ├── __init__.py
│   │   ├── taxonomies/
│   │   ├── inference.py
│   │   └── insights.py
│   │
│   ├── visualization/    # 4. Visualization layer
│   │   ├── __init__.py
│   │   ├── app.py        # Streamlit app
│   │   └── api.py        # FastAPI
│   │
│   ├── main.py           # Main pipeline script
│   └── config.py         # Global configuration
│
├── tests/                # Unit and integration tests
│   ├── test_acquisition.py
│   ├── test_preprocessing.py
│   ├── test_analysis.py
│   ├── test_storage.py
│   └── test_cleaning.py  # ✓ Text cleaning tests
│
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore patterns
├── CHANGES.md            # Changelog
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Multi-container setup
├── Makefile              # Convenience commands
├── pyproject.toml        # ✓ Project metadata & dependencies
├── README.md             # Project overview
├── repository.txt        # Repository structure blueprint
├── requirements.txt      # Legacy requirements (use pyproject.toml)
└── requirements-dev.txt  # Legacy dev requirements
```

## File Placement Guidelines

### Where Should I Put This File?

#### ✅ Production Code
**Location**: `src/`

Examples:
- Data processing modules → `src/preprocessing/`
- Analysis algorithms → `src/analysis/`
- Database utilities → `src/storage/`
- API endpoints → `src/visualization/api.py`

**Rule**: If it runs in production or is imported by production code, it goes in `src/`.

---

#### ✅ Utility Scripts
**Location**: `scripts/`

Examples:
- Installation helpers (`setup_nlp_models.py`)
- Validation tools (`check_installation.py`)
- Code generators (`generate_schema_docs.py`)
- Database initialization (`init_database.py`)

**Rule**: If it's a standalone script for development/setup/maintenance, it goes in `scripts/`.

---

#### ✅ Documentation
**Location**: `docs/`

Examples:
- Installation guides (`INSTALLATION.md`)
- Architecture documentation (`architecture.md`)
- API documentation
- Implementation summaries (`CLEANING_SUMMARY.md`)
- Usage guides (`USAGE_GUIDE_*.md`)

**Rule**: If it's primarily text documentation, it goes in `docs/`.

**Exception**: Module-specific docs can stay with the module (e.g., `src/preprocessing/CLEANING_USAGE.md`).

---

#### ✅ Configuration Files
**Location**: `configs/`

Examples:
- Model configs → `configs/model/llm_base.yaml`
- Dataset configs → `configs/data/finetune_dataset.yaml`
- Service configs → `configs/core/services.yaml`

**Rule**: YAML/JSON configuration files go in `configs/`, organized by type.

---

#### ✅ Tests
**Location**: `tests/`

Examples:
- Unit tests → `tests/test_<module_name>.py`
- Integration tests → `tests/integration/`
- Fixtures → `tests/conftest.py`

**Rule**: All pytest tests go in `tests/`, mirroring the `src/` structure.

---

#### ✅ Notebooks
**Location**: `notebooks/`

Examples:
- Data exploration → `01_data_exploration.ipynb`
- Prototyping → `02_preprocessing_dev.ipynb`
- Results analysis → `04_results_analysis.ipynb`

**Rule**: Jupyter notebooks for experimentation and analysis. Use numbered prefixes for ordering.

---

#### ✅ Data Files
**Location**: `data/`

**Important**: Only small sample files! Large data goes to cloud storage or databases.

Examples:
- Raw samples → `data/raw/sample_10k.txt`
- Processed examples → `data/processed/sample_risks.jsonl`

**Rule**: Keep it minimal. Add `README.md` explaining where real data lives.

---

#### ✅ Model Checkpoints
**Location**: `models/`

**Important**: Don't commit large files! Use Git LFS or cloud storage.

Examples:
- Fine-tuned models → `models/my-finetuned-model/`
- Model configs → `models/my-model/config.json`

**Rule**: Add `.gitignore` entries and `README.md` pointing to storage location.

---

#### ✅ Generated Reports
**Location**: `reports/`

Examples:
- Figures → `reports/figures/risk_distribution.png`
- Analysis results → `reports/evaluation_results.json`
- Model cards → `reports/model_card.md`

**Rule**: Generated output goes here. Usually git-ignored except for key results.

---

## Special Cases

### Module-Specific Documentation

**Where**: Next to the module (e.g., `src/preprocessing/CLEANING_USAGE.md`)

**Why**: Keeps implementation and its detailed docs together.

**Also**: Link from main docs (`docs/`) for discoverability.

Example:
```
src/preprocessing/
├── cleaning.py
├── CLEANING_USAGE.md      # Detailed usage (stays with code)
└── QUICK_REFERENCE.md     # Quick reference (stays with code)

docs/
└── CLEANING_SUMMARY.md    # High-level summary (links to detailed docs)
```

---

### Requirements Files

**Current**:
- `pyproject.toml` - **PRIMARY** dependency specification
- `requirements.txt` - Legacy, for backwards compatibility
- `requirements-dev.txt` - Legacy dev dependencies
- `docs/requirements/requirements_cleaning.txt` - Historical reference

**Best Practice**: Use `pyproject.toml` for all dependencies. Keep `requirements*.txt` only if needed for compatibility.

---

### Root-Level Files

**Keep in root**:
- `README.md` - Project overview (ALWAYS in root)
- `pyproject.toml` - Python project config (ALWAYS in root)
- `Makefile` - Build commands
- `.env.example` - Environment template
- `Dockerfile` - Container config
- `docker-compose.yml` - Multi-container config
- `.gitignore` - Git ignore patterns
- `CHANGES.md` / `CHANGELOG.md` - Version history

**Move to docs/**:
- Installation guides
- Architecture docs
- Implementation summaries
- Usage guides

---

## Migration Rules

If you find a file in the wrong place:

1. **Identify type** (code/docs/script/config/test)
2. **Check table above** for correct location
3. **Move file** to appropriate directory
4. **Update imports** if it's Python code
5. **Update links** in documentation
6. **Test** that everything still works

---

## Clean Codebase Checklist

✅ All production code in `src/`
✅ All utility scripts in `scripts/`
✅ All documentation in `docs/` (except module-specific)
✅ All tests in `tests/`
✅ All configs in `configs/`
✅ No duplicate files
✅ No large data files committed (use `.gitignore`)
✅ Each directory has a `README.md`
✅ Dependencies in `pyproject.toml`
✅ Clear separation of concerns

---

## Directory README Requirements

Each major directory should have a `README.md` explaining:

- **Purpose**: What goes in this directory
- **Structure**: How it's organized
- **Usage**: How to use files in this directory
- **Examples**: Sample files or patterns

**Completed**:
- ✅ `scripts/README.md`
- ✅ `src/preprocessing/CLEANING_USAGE.md`

**TODO**:
- `data/README.md` - Explain data versioning and storage
- `models/README.md` - Explain model storage location
- `configs/README.md` - Explain configuration system
- `tests/README.md` - Explain testing approach

---

## Anti-Patterns to Avoid

❌ **Don't**: Put utility scripts in root
✅ **Do**: Put them in `scripts/`

❌ **Don't**: Put documentation in root (except README.md)
✅ **Do**: Put it in `docs/`

❌ **Don't**: Mix production code with scripts
✅ **Do**: Keep `src/` for production, `scripts/` for utilities

❌ **Don't**: Duplicate requirements across multiple files
✅ **Do**: Use `pyproject.toml` as single source of truth

❌ **Don't**: Commit large data or model files
✅ **Do**: Use Git LFS or cloud storage, commit small samples

❌ **Don't**: Leave files without documentation
✅ **Do**: Add README.md in each directory

---

## Quick Reference

| File Type | Location | Example |
|-----------|----------|---------|
| Production code | `src/` | `src/preprocessing/cleaning.py` |
| Utility script | `scripts/` | `scripts/check_installation.py` |
| General docs | `docs/` | `docs/INSTALLATION.md` |
| Module docs | `src/<module>/` | `src/preprocessing/CLEANING_USAGE.md` |
| Tests | `tests/` | `tests/test_cleaning.py` |
| Config | `configs/` | `configs/model/llm_base.yaml` |
| Notebook | `notebooks/` | `notebooks/01_exploration.ipynb` |
| Data sample | `data/` | `data/raw/sample.txt` |
| Model | `models/` | `models/my-model/` |
| Report | `reports/` | `reports/figures/plot.png` |

---

**Last Updated**: 2025-11-14
**Maintained By**: Development Team
**Reference**: `repository.txt` (blueprint)
