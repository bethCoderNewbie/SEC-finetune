# Current Repository Structure

**Last Updated**: 2025-11-14

This document reflects the **actual current state** of the repository after reorganization.

## Directory Tree

```
sec-filing-analyzer/
├── .github/              # GitHub-specific files (CI/CD workflows)
│   └── workflows/
│       ├── test.yml
│       └── train.yml
│
├── configs/              # Hydra/YAML configs for experiments
│   ├── data/
│   │   └── finetune_dataset.yaml
│   ├── model/
│   │   └── llm_base.yaml
│   └── core/
│       └── services.yaml
│
├── data/                 # Data versioned by DVC (small samples only)
│   ├── external/         # Third-party data sources
│   ├── interim/          # Transformed data
│   ├── processed/        # Final datasets for training
│   ├── raw/              # Original, immutable data
│   └── README.md         # Explains that large data lives in cloud storage
│
├── docs/                 # ✓ REORGANIZED - Project documentation
│   ├── requirements/     # Historical requirements files
│   │   └── requirements_cleaning.txt
│   ├── architecture.md              # Pipeline diagram breakdown
│   ├── setup.md                     # Installation and setup guide
│   ├── INSTALLATION.md              # ✓ Complete installation guide
│   ├── CLEANING_SUMMARY.md          # ✓ Text cleaning implementation summary
│   ├── PYPROJECT_UPDATE_SUMMARY.md  # ✓ Dependency management docs
│   ├── README_INSTALLATION_SECTION.md # ✓ README template
│   ├── code_guidance.md             # ✓ Coding standards
│   ├── USAGE_GUIDE_SEC_PARSER.md    # SEC parser usage guide
│   ├── FILE_ORGANIZATION.md         # ✓ File organization guide
│   └── data_schema.md               # DB schema (auto-generated)
│
├── llm_finetuning/       # Code for training the LLM (optional directory)
│   ├── synthesize_dataset.py
│   ├── data_prep.py
│   ├── train.py
│   ├── evaluate.py
│   └── configs/
│
├── models/               # Model checkpoints (versioned by Git LFS or DVC)
│   ├── my-finetuned-model/
│   └── README.md         # Explains where trained models are stored
│
├── notebooks/            # Jupyter notebooks for exploration
│   ├── 01_data_exploration.ipynb
│   ├── 02_preprocessing_dev.ipynb
│   ├── 03_llm_finetuning_prototype.ipynb
│   └── 04_results_analysis.ipynb
│
├── prompts/              # LLM prompt templates (versioned)
│   ├── categorize_risk.prompt
│   ├── summarize.prompt
│   └── qa_agent.prompt
│
├── reports/              # Generated analysis and figures
│   └── figures/
│
├── scripts/              # ✓ NEW - Utility scripts for development
│   ├── README.md                    # ✓ Scripts documentation
│   ├── setup_nlp_models.py          # ✓ spaCy model downloader
│   ├── check_installation.py        # ✓ Installation verification
│   └── generate_schema_docs.py      # (PLANNED) Schema doc generator
│
├── src/                  # Main source code (production code)
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
│   │       ├── __init__.py
│   │       ├── mongo_schemas.py
│   │       └── postgres_schemas.py
│   │
│   ├── preprocessing/    # 2. ✓ ENHANCED - Text preprocessing
│   │   ├── __init__.py
│   │   ├── parser.py                # HTML/XML parsing
│   │   ├── extractor.py             # Section extraction
│   │   ├── cleaning.py              # ✓ Text cleaning (spaCy-powered)
│   │   ├── segmenter.py             # Text segmentation
│   │   ├── CLEANING_USAGE.md        # ✓ Detailed cleaning module docs
│   │   └── QUICK_REFERENCE.md       # ✓ Quick reference for cleaning
│   │
│   ├── analysis/         # 3. NLP and analysis
│   │   ├── __init__.py
│   │   ├── taxonomies/
│   │   │   ├── __init__.py
│   │   │   └── risk_taxonomy.yaml
│   │   ├── inference.py
│   │   └── insights.py
│   │
│   ├── visualization/    # 4. Visualization layer
│   │   ├── __init__.py
│   │   ├── app.py        # Streamlit application
│   │   └── api.py        # FastAPI endpoints
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
├── .gitattributes        # Git LFS configuration
├── CHANGES.md            # Changelog
├── CURRENT_STRUCTURE.md  # ✓ This file
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Multi-container setup
├── Makefile              # Convenience commands
├── pyproject.toml        # ✓ UPDATED - Project metadata & dependencies
├── README.md             # Project overview
├── repository.txt        # Repository structure blueprint (reference)
├── requirements.txt      # Legacy requirements (backwards compatibility)
└── requirements-dev.txt  # Legacy dev requirements
```

## Recent Changes (2025-11-14)

### ✓ Files Reorganized

#### Moved to `scripts/`:
- `setup_nlp_models.py` (from root)
- `check_installation.py` (from root)

#### Moved to `docs/`:
- `CLEANING_SUMMARY.md` (from root)
- `PYPROJECT_UPDATE_SUMMARY.md` (from root)
- `README_INSTALLATION_SECTION.md` (from root)
- `code_guidance.md` (from root)

#### Moved to `docs/requirements/`:
- `requirements_cleaning.txt` (from root)

#### Removed (Duplicates):
- `INSTALLATION.md` (from root - kept in docs/)

### ✓ Files Created

#### In `scripts/`:
- `README.md` - Documentation for utility scripts

#### In `docs/`:
- `FILE_ORGANIZATION.md` - File organization guide
- (Existing files consolidated here)

#### In `src/preprocessing/`:
- Enhanced `cleaning.py` with spaCy support
- `CLEANING_USAGE.md` - Detailed usage guide
- `QUICK_REFERENCE.md` - Quick reference card

#### In `tests/`:
- `test_cleaning.py` - Comprehensive tests for cleaning module

#### In root:
- `CURRENT_STRUCTURE.md` - This file

### ✓ Files Updated

- `pyproject.toml` - Added spaCy dependencies, installation instructions
- `repository.txt` - Updated with current docs/ structure

## File Organization Principles

### Production Code → `src/`
All code that runs in production or is imported by production code.

**Examples**:
- Data processing: `src/preprocessing/`
- Analysis: `src/analysis/`
- APIs: `src/visualization/api.py`

### Utility Scripts → `scripts/`
Standalone scripts for development, setup, and maintenance.

**Examples**:
- Installation helpers
- Validation tools
- Code generators
- Database initialization

### Documentation → `docs/`
All written documentation (except README.md which stays in root).

**Examples**:
- Installation guides
- Architecture documentation
- Implementation summaries
- Usage guides

**Exception**: Module-specific docs can stay with the module (e.g., `src/preprocessing/CLEANING_USAGE.md`).

### Tests → `tests/`
All pytest unit and integration tests.

**Examples**:
- `test_<module>.py` for unit tests
- `integration/` subdirectory for integration tests

### Configuration → `configs/`
YAML/JSON configuration files organized by type.

**Examples**:
- Model configs: `configs/model/`
- Dataset configs: `configs/data/`
- Service configs: `configs/core/`

## Clean Codebase Status

✅ All production code in `src/`
✅ All utility scripts in `scripts/`
✅ All documentation in `docs/` (except module-specific)
✅ All tests in `tests/`
✅ All configs in `configs/`
✅ No duplicate files
✅ Clear separation of concerns
✅ Each major directory has README.md
✅ Dependencies centralized in `pyproject.toml`

## Next Steps

### Documentation TODOs:
- [ ] Create `data/README.md` - Explain data versioning
- [ ] Create `models/README.md` - Explain model storage
- [ ] Create `configs/README.md` - Explain configuration system
- [ ] Create `tests/README.md` - Explain testing approach

### Directory Structure TODOs:
- [ ] Create `llm_finetuning/` directory if needed
- [ ] Set up alembic for database migrations
- [ ] Configure DVC for data versioning

### Code TODOs:
- [ ] Implement remaining preprocessing modules
- [ ] Set up database schemas
- [ ] Configure CI/CD workflows

## References

- **Blueprint**: `repository.txt` (idealized structure)
- **Current**: `CURRENT_STRUCTURE.md` (this file - actual state)
- **Organization Guide**: `docs/FILE_ORGANIZATION.md` (detailed guidelines)
- **Installation**: `docs/INSTALLATION.md` (setup instructions)

---

**Maintained By**: Development Team
**Last Reorganization**: 2025-11-14
**Status**: Clean and Organized ✓
