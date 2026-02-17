# Changes Summary

## 2025-12-12: HTML Sanitizer for Pre-Parser Cleaning

### Overview

Added `HTMLSanitizer` to clean raw HTML **before** sec-parser processing. This improves `ParsedFiling` quality by removing noise while preserving metadata and structure needed for section extraction.

### New Pipeline Flow

```
1. SANITIZE → HTMLSanitizer       → cleaned HTML (NEW)
2. PARSE    → SECFilingParser     → ParsedFiling (with metadata)
3. EXTRACT  → SECSectionExtractor → ExtractedSection (metadata preserved)
4. CLEAN    → TextCleaner         → cleaned text
5. SEGMENT  → RiskSegmenter       → SegmentedRisks (metadata preserved)
```

### New Files

| File | Purpose |
|------|---------|
| `src/preprocessing/sanitizer.py` | `HTMLSanitizer` class with 8 configurable cleaning steps |

### Modified Files

| File | Changes |
|------|---------|
| `configs/config.yaml` | Added `sanitizer` section under `preprocessing` |
| `src/config/preprocessing.py` | Added `SanitizerConfig` class with settings |
| `src/preprocessing/pipeline.py` | Integrated sanitizer as Step 1/5 |
| `src/preprocessing/__init__.py` | Exported `HTMLSanitizer`, `SanitizerConfig`, `sanitize_html` |

### Sanitization Options

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `true` | Enable pre-parser HTML sanitization |
| `remove_edgar_header` | `false` | Remove EDGAR header (WARNING: disables metadata) |
| `remove_edgar_tags` | `false` | Remove `<PAGE>`, `<S>` tags (WARNING: breaks structure) |
| `decode_entities` | `true` | `&amp;` → `&`, `&nbsp;` → space |
| `normalize_unicode` | `true` | NFKC normalization (`ﬁ` → `fi`) |
| `remove_invisible_chars` | `true` | Remove zero-width spaces, control chars |
| `normalize_quotes` | `true` | Curly → straight quotes |
| `fix_encoding` | `false` | Fix mojibake (requires `ftfy` library) |
| `flatten_nesting` | `true` | Remove redundant nested tags |

### Safe Defaults

Two options are disabled by default because they break functionality:

1. **`remove_edgar_header: false`** - EDGAR header contains CIK, SIC, company name metadata
2. **`remove_edgar_tags: false`** - `<PAGE>` tags are used by sec-parser for section structure

### Usage

```python
# Default (sanitizer enabled with safe defaults)
from src.preprocessing import process_filing
result = process_filing("data/raw/AAPL_10K.html")

# With custom config
from src.preprocessing import SECPreprocessingPipeline, PipelineConfig
from src.preprocessing.sanitizer import SanitizerConfig

config = PipelineConfig(
    pre_sanitize=True,
    sanitizer_config=SanitizerConfig(
        decode_entities=True,
        normalize_unicode=True,
        normalize_quotes=True,
    )
)
pipeline = SECPreprocessingPipeline(config)
result = pipeline.process_risk_factors("data/raw/AAPL_10K.html")

# Standalone sanitization
from src.preprocessing import HTMLSanitizer, sanitize_html

sanitizer = HTMLSanitizer()
clean_html = sanitizer.sanitize(raw_html)
stats = sanitizer.get_stats(raw_html, clean_html)
print(f"Reduction: {stats['reduction_percent']:.1f}%")
```

### Test Results

With safe defaults on AAPL_10K_2021.html:
- **1.9% HTML reduction** (10.5MB → 10.3MB)
- **Metadata preserved**: CIK, SIC code, company name
- **54 segments extracted** successfully
- **Cleaner text**: No mojibake, normalized quotes

### Configuration in `configs/config.yaml`

```yaml
preprocessing:
  sanitizer:
    enabled: true
    remove_edgar_header: false  # Preserves metadata
    remove_edgar_tags: false    # Preserves sec-parser structure
    decode_entities: true
    normalize_unicode: true
    remove_invisible_chars: true
    normalize_quotes: true
    fix_encoding: false
    flatten_nesting: true
```

---

## 2025-12-12: Preprocessing Pipeline Restructure

### Overview

Complete restructure of the preprocessing pipeline to ensure metadata preservation throughout the entire flow. Added new `pipeline.py` orchestrator and `SegmentedRisks` model.

### New Pipeline Flow

```
1. PARSE   → SECFilingParser    → ParsedFiling (with metadata)
2. CLEAN   → TextCleaner        → cleaned text
3. EXTRACT → SECSectionExtractor → ExtractedSection (metadata preserved)
4. SEGMENT → RiskSegmenter      → SegmentedRisks (metadata preserved)
```

### Key Changes

#### New Files
| File | Purpose |
|------|---------|
| `src/preprocessing/pipeline.py` | Pipeline orchestrator with `SECPreprocessingPipeline` class |

#### Modified Files
| File | Changes |
|------|---------|
| `src/preprocessing/parser.py` | Added `_extract_sic_name()` method to extract SIC industry name |
| `src/preprocessing/extractor.py` | Added filing metadata fields to `ExtractedSection` model |
| `src/preprocessing/segmenter.py` | Added `RiskSegment`, `SegmentedRisks` models with metadata preservation |
| `src/preprocessing/cleaning.py` | Fixed `deep_clean` logic with lazy spaCy initialization |
| `src/preprocessing/__init__.py` | Updated exports for new classes and pipeline |

#### New Models

**ExtractedSection** (updated):
```python
class ExtractedSection(BaseModel):
    text: str
    identifier: str
    title: str
    subsections: List[str]
    elements: List[Dict]
    metadata: Dict
    # NEW: Filing-level metadata
    sic_code: Optional[str]
    sic_name: Optional[str]      # e.g., "PHARMACEUTICAL PREPARATIONS"
    cik: Optional[str]
    ticker: Optional[str]
    company_name: Optional[str]
    form_type: Optional[str]
```

**SegmentedRisks** (new):
```python
class SegmentedRisks(BaseModel):
    segments: List[RiskSegment]
    sic_code: Optional[str]
    sic_name: Optional[str]
    cik: Optional[str]
    ticker: Optional[str]
    company_name: Optional[str]
    form_type: Optional[str]
    section_title: Optional[str]
    total_segments: int
    metadata: Dict
```

**RiskSegment** (new):
```python
class RiskSegment(BaseModel):
    index: int
    text: str
    word_count: int
    char_count: int
```

#### New Pipeline Usage

```python
# Simple usage
from src.preprocessing import process_filing

result = process_filing("data/raw/AAPL_10K.html")
print(f"Company: {result.company_name}")
print(f"SIC: {result.sic_code} - {result.sic_name}")
print(f"Segments: {len(result)}")

# With configuration
from src.preprocessing import SECPreprocessingPipeline, PipelineConfig

config = PipelineConfig(
    deep_clean=True,
    use_lemmatization=True,
)
pipeline = SECPreprocessingPipeline(config)
result = pipeline.process_risk_factors("data/raw/AAPL_10K.html")

# Save to JSON
result.save_to_json("output/AAPL_risks.json")
```

#### Output JSON Structure

```json
{
  "segments": [
    {"index": 0, "text": "...", "word_count": 150, "char_count": 890},
    {"index": 1, "text": "...", "word_count": 200, "char_count": 1200}
  ],
  "sic_code": "2834",
  "sic_name": "PHARMACEUTICAL PREPARATIONS",
  "cik": "0000320193",
  "ticker": null,
  "company_name": "APPLE INC",
  "form_type": "10-K",
  "section_title": "Item 1A. Risk Factors",
  "total_segments": 45
}
```

### Script Updates

#### `scripts/data_preprocessing/run_preprocessing_pipeline.py`

Updated to use new pipeline flow with metadata preservation:

| Change | Description |
|--------|-------------|
| Output version | `"version": "2.0"` with new JSON structure |
| Metadata fields | `sic_code`, `sic_name`, `cik`, `ticker`, `company_name` at top level |
| Imports | Added `SegmentedRisks`, `RiskSegment` from segmenter |
| Type hints | Full typing with `List`, `Dict`, `Any`, `Tuple`, `Optional` |
| Segmentation | Uses `segment_extracted_section()` method |
| Batch results | Include metadata (`sic_code`, `sic_name`, `cik`) per file |

**New Output Structure (v2.0):**
```json
{
  "version": "2.0",
  "filing_name": "AAPL_10K.html",
  "sic_code": "3571",
  "sic_name": "ELECTRONIC COMPUTERS",
  "cik": "0000320193",
  "ticker": "AAPL",
  "company_name": "APPLE INC",
  "form_type": "10-K",
  "section_title": "Item 1A. Risk Factors",
  "num_segments": 45,
  "segments": [...]
}
```

### Pydantic V2 Compliance

#### `src/preprocessing/pipeline.py`

Converted `PipelineConfig` from `@dataclass` to Pydantic V2 `BaseModel`:

```python
# Before (dataclass)
@dataclass
class PipelineConfig:
    remove_html: bool = True
    similarity_threshold: float = 0.5

# After (Pydantic V2)
class PipelineConfig(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid',
    )

    remove_html: bool = Field(default=True, description="Remove HTML tags")
    similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold"
    )
```

**Benefits:**
- Validation on assignment (`validate_assignment=True`)
- Error on unknown fields (`extra='forbid'`)
- Range validation (`ge=0.0, le=1.0`)
- Self-documenting via `Field(description=...)`
- JSON serialization via `model_dump_json()`

### Bug Fixes

1. **cleaning.py**: Fixed `deep_clean=True` not working when spaCy wasn't pre-initialized
   - Added lazy initialization of spaCy when `deep_clean=True` is called

2. **segmenter.py**: Replaced `print()` statements with proper `logging` module

### Benefits

| Aspect | Before | After |
|--------|--------|-------|
| Metadata flow | Lost after parsing | Preserved throughout |
| SIC Name | Not extracted | Extracted (e.g., "PHARMACEUTICAL PREPARATIONS") |
| Output format | List of strings | Structured `SegmentedRisks` with metadata |
| Pipeline orchestration | Manual chaining | `SECPreprocessingPipeline` class |
| Serialization | None | JSON save/load methods |

---

## 2025-12-03: Configuration Modularization

### Overview

Complete refactor of `src/config.py` (1,126 lines) into a modular `src/config/` package with 16 domain-specific modules.

### Key Changes

#### New Package Structure
```
src/config/
├── __init__.py          # Main Settings class + global instance
├── _loader.py           # Single cached YAML loader (replaces 5 duplicates)
├── paths.py             # PathsConfig
├── sec_parser.py        # SecParserConfig
├── models.py            # ModelsConfig
├── preprocessing.py     # PreprocessingConfig
├── extraction.py        # ExtractionConfig
├── sec_sections.py      # SecSectionsConfig
├── testing.py           # TestingConfig + ReproducibilityConfig
├── run_context.py       # RunContext
├── legacy.py            # Deprecation warnings for old imports
└── features/
    ├── __init__.py
    ├── sentiment.py     # SentimentConfig (6 sub-configs)
    ├── topic_modeling.py# TopicModelingConfig (7 sub-configs)
    ├── readability.py   # ReadabilityConfig (5 sub-configs)
    └── risk_analysis.py # RiskAnalysisConfig
```

#### Files Modified
| File | Change |
|------|--------|
| `src/config.py` | **Deleted** (was 1,126 lines) |
| `src/config/` | **Created** (16 new files) |
| `src/preprocessing/segmenter.py` | Migrated to use `settings` object |
| `src/preprocessing/parser.py` | Migrated to use `settings` object |
| `pyproject.toml` | Added `filterwarnings` for deprecation enforcement |

#### API Changes

**No breaking changes** - existing imports work unchanged:

```python
# This still works (unchanged)
from src.config import settings
settings.paths.data_dir
settings.models.default_model
```

**Legacy imports now emit warnings**:
```python
# Old (deprecated, emits DeprecationWarning)
from src.config import DATA_DIR

# New (recommended)
from src.config import settings
settings.paths.data_dir
```

#### Benefits

| Metric | Before | After |
|--------|--------|-------|
| Lines in config | 1,126 (single file) | ~65 avg per file (16 files) |
| YAML loader functions | 5 (duplicated) | 1 (cached) |
| Module-level I/O | 5 calls | 0 (lazy loading) |
| Testability | Hard (import-time I/O) | Easy (mockable) |

#### Migration Guide

No immediate migration required. Legacy imports continue to work but emit deprecation warnings. To suppress warnings:

```bash
# Suppress deprecation warnings (not recommended)
export PYTHONWARNINGS="ignore::DeprecationWarning"
```

To migrate existing code:
```python
# Before
from src.config import DATA_DIR, MIN_SEGMENT_LENGTH

# After
from src.config import settings
data_dir = settings.paths.data_dir
min_length = settings.preprocessing.min_segment_length
```

---

# Changes Summary - sec-parser Integration

## Overview

Complete refactor to integrate sec-parser library for robust SEC filing parsing.

## Files Updated

### 1. pyproject.toml (MAJOR UPDATE)

#### Changed:
- **Python version**: `>=3.8` → `>=3.10` (required for sec-parser)
- **Description**: Added "sec-parser" to description
- **Keywords**: Added "10-Q" and "sec-parser"
- **Classifiers**: Updated Python versions (3.10, 3.11, 3.12)

#### Added Dependencies:
```toml
# Core (PINNED for reproducibility)
sec-parser==0.54.0        # SEC filing semantic parser
sec-downloader>=0.10.0    # SEC EDGAR downloader
python-dotenv>=1.0.0      # Environment variable management
pydantic>=2.0.0           # Data validation

# Development
pytest-cov>=4.1.0         # Test coverage
pytest-mock>=3.12.0       # Mocking for tests
ipykernel>=6.0.0          # Jupyter kernel
nbformat>=5.0.0           # Notebook format
```

#### Added Tool Configurations:
- `[tool.coverage.run]` - Coverage settings
- `[tool.coverage.report]` - Coverage reporting
- `[tool.ruff]` - Modern linter configuration
- `[tool.isort]` - Import sorting

#### Enhanced Tool Configurations:
- `[tool.black]` - Updated target versions, added more exclusions
- `[tool.pytest.ini_options]` - Added coverage, markers, detailed options
- `[tool.mypy]` - Enhanced type checking rules

### 2. requirements.txt (REWRITTEN)

**Before:**
- Basic dependencies only
- No version pinning strategy
- Included optional dependencies

**After:**
- Structured sections with comments
- **sec-parser pinned** to exact version (0.54.0)
- Clear separation of required vs optional
- Installation instructions in comments
- Removed optional dependencies (moved to requirements-dev.txt)

### 3. requirements-dev.txt (NEW)

Created comprehensive development dependencies:
- Testing tools (pytest, pytest-cov, pytest-mock)
- Code quality (black, flake8, mypy, ruff, isort)
- Jupyter ecosystem (jupyter, jupyterlab, ipykernel)
- Documentation (mkdocs, mkdocs-material)
- Optional features (fine-tuning, external services)

### 4. .env.example (NEW)

Created environment variables template:
- SEC parser configuration
- Extraction settings
- Model configuration
- Database configuration (MongoDB, PostgreSQL)
- MinIO/S3 configuration
- Development settings
- Path overrides

### 5. src/config.py (ENHANCED)

**Added:**
```python
# SEC Parser Configuration
SUPPORTED_FORM_TYPES = ["10-K", "10-Q"]
DEFAULT_FORM_TYPE = "10-K"
PARSE_TABLES = True
PARSE_IMAGES = False

# Logs directory
LOGS_DIR = PROJECT_ROOT / "logs"
EXTRACTION_LOGS_DIR = LOGS_DIR / "extractions"

# Extraction Configuration
MIN_EXTRACTION_CONFIDENCE = 0.7
ENABLE_AUDIT_LOGGING = True/False

# Reproducibility
RANDOM_SEED = 42
SEC_PARSER_VERSION = "0.54.0"

# Golden dataset validation
GOLDEN_DATASET_PATH = ...
ENABLE_GOLDEN_VALIDATION = True/False
```

**Enhanced:**
- Environment variable loading via python-dotenv
- More structured configuration sections
- Audit and logging capabilities
- Reproducibility settings

### 6. src/preprocessing/parser.py (COMPLETE REWRITE)

**Old Approach:**
- Simple file reader
- No structure preservation
- Basic encoding handling

**New Approach:**
```python
class SECFilingParser:
    - Uses sec-parser library
    - Returns ParsedFiling dataclass
    - Semantic element extraction
    - Tree structure preservation
    - Robust encoding (UTF-8 → latin-1 → ignore)
    - Metadata extraction
    - Support for 10-K and 10-Q

class ParsedFiling:
    - elements: List of semantic elements
    - tree: Hierarchical structure
    - form_type: Enum
    - metadata: Rich metadata
    - Helper methods
```

### 7. src/preprocessing/extractor.py (COMPLETE REWRITE)

**Old Approach:**
- Regex pattern matching
- No structure awareness
- Returns plain text

**New Approach:**
```python
class SECSectionExtractor:
    - Semantic tree navigation
    - Section identification by identifier or title
    - Returns ExtractedSection dataclass
    - Subsection extraction
    - Element type preservation

class ExtractedSection:
    - text: Full content
    - identifier: Section ID
    - title: Human-readable title
    - subsections: List of subsections
    - elements: Semantic elements
    - metadata: Rich metadata
    - Helper methods (get_tables, get_paragraphs)

class RiskFactorExtractor:
    - Specialized for Risk Factors
    - Convenience methods
    - Backward-compatible API
```

### 8. examples/01_basic_extraction.py (NEW)

Complete working example:
- Step-by-step extraction
- Error handling
- Metadata access
- Output saving

### 9. examples/02_complete_pipeline.py (NEW)

Full pipeline demonstration:
- Parse → Extract → Clean → Segment
- JSON output
- Metadata tracking
- Results saving

### 10. docs/USAGE_GUIDE.md (NEW)

Comprehensive API documentation:
- Quick start examples
- API reference for all classes
- Section identifiers table
- Complete pipeline example
- Error handling
- Best practices
- Troubleshooting

### 11. docs/INSTALLATION.md (NEW)

Complete installation guide:
- Prerequisites
- Step-by-step installation
- Verification steps
- Common issues and solutions
- Development setup
- Docker setup (optional)
- Troubleshooting

## Key Changes Summary

### Reproducibility
1. **Exact version pinning**: `sec-parser==0.54.0`
2. **Version tracking**: Environment variable `SEC_PARSER_VERSION`
3. **Random seed**: `RANDOM_SEED = 42`
4. **Python version**: Minimum 3.10

### Maintainability
1. **Clean architecture**: Parser → Extractor → Downstream
2. **Type hints**: Throughout codebase
3. **Dataclasses**: Structured data objects
4. **Comprehensive docs**: Usage guide, installation guide
5. **Code quality tools**: black, ruff, mypy, isort configured

### Scalability
1. **Modular design**: Easy to extend
2. **Section identifiers**: Enum-based
3. **Tree structure**: Efficient navigation
4. **Metadata tracking**: Rich information

### Auditability
1. **Audit logging**: Optional logging of all extractions
2. **Metadata**: Comprehensive extraction metadata
3. **Element tracking**: Type and count tracking
4. **Configuration**: Environment-based settings

## Migration Path

### For Existing Code:

**Old Code:**
```python
from src.preprocessing.parser import FilingParser
from src.preprocessing.extractor import RiskFactorExtractor

parser = FilingParser()
content = parser.parse_filing("file.txt")

extractor = RiskFactorExtractor()
risk_text = extractor.find_risk_section(content)
```

**New Code:**
```python
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor

parser = SECFilingParser()
filing = parser.parse_filing("file.html", form_type="10-K")

extractor = RiskFactorExtractor()
risk_section = extractor.extract(filing)

# Access data
risk_text = risk_section.text
subsections = risk_section.subsections
elements = risk_section.elements
```

### Breaking Changes:

1. **Input format**: Now requires HTML (not TXT)
   - Use sec-downloader to get HTML filings

2. **Return types**: Returns dataclasses (not strings)
   - Access `.text` for raw text
   - Access `.subsections`, `.elements` for structure

3. **Python version**: Requires 3.10+ (was 3.8+)

4. **Dependencies**: Must install sec-parser
   ```bash
   pip install sec-parser==0.54.0
   ```

## Installation Commands

### Fresh Install:
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt

# Verify
python -c "import sec_parser; print(sec_parser.__version__)"
```

### Update Existing:
```bash
# Update dependencies
pip install -r requirements.txt --upgrade

# Verify sec-parser version
pip show sec-parser
# Should show: Version: 0.54.0
```

## Testing

Run examples to verify:
```bash
# Basic extraction
python examples/01_basic_extraction.py

# Complete pipeline
python examples/02_complete_pipeline.py
```

## Next Steps

1. Install new dependencies
2. Download HTML filing for testing
3. Run example scripts
4. Update your code to use new API
5. Review documentation in `docs/`

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Parsing** | Regex patterns | Semantic parser |
| **Structure** | Flat text | Hierarchical tree |
| **Subsections** | Manual parsing | Auto-detected |
| **Tables** | Lost | Preserved |
| **Metadata** | Minimal | Comprehensive |
| **Reproducibility** | No version pinning | Exact versions |
| **Type Safety** | No types | Full type hints |
| **Documentation** | Minimal | Extensive |

## Version Information

- **sec-parser**: 0.54.0 (pinned)
- **Python**: >=3.10
- **Project version**: 0.1.0

## Documentation

- `docs/INSTALLATION.md` - Installation guide
- `docs/USAGE_GUIDE.md` - API reference and examples
- `examples/` - Working code examples
- `pyproject.toml` - Package configuration
- `.env.example` - Environment variables template

## Support

For issues or questions:
1. Check `docs/` directory
2. Review `examples/`
3. Read sec-parser docs: https://sec-parser.readthedocs.io/
