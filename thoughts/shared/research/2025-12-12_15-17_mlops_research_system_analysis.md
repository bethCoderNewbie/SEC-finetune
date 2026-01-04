---
date: 2025-12-12T15:17:08-06:00
researcher: bethCoderNewbie
git_commit: ea45dd2
branch: main
repository: SEC finetune
topic: "MLOps Research System & Data Versioning Best Practices"
tags: [research, mlops, data-versioning, templates, best-practices, documentation, preprocessing, pipeline]
status: complete
last_updated: 2025-12-12
last_updated_by: bethCoderNewbie
---

# Research: MLOps Research System & Data Versioning Best Practices

**Date**: 2025-12-12T15:17:08-06:00
**Researcher**: bethCoderNewbie
**Git Commit**: ea45dd2
**Branch**: main
**Repository**: SEC finetune

## Research Question

Analyze the existing `thoughts/shared/research` system and document best practices for:
1. Saving outputs and checkpoints in ML pipelines
2. Data versioning strategies
3. Research documentation templates
4. Experiment tracking patterns
5. **Preprocessing pipeline architecture** (`src/preprocessing/`)
6. **Data directory structure and versioning** (`data/`)

## Summary

The SEC finetune codebase implements a **comprehensive MLOps system** with:
- **Structured research documents** using YAML frontmatter for metadata tracking
- **Git-integrated versioning** via `hack/spec_metadata.sh` for reproducibility
- **Staged data pipeline** (raw → interim → processed) for clear data lineage
- **RunContext class** for timestamped experiment outputs with config preservation
- **Pydantic-based preprocessing pipeline** with 4-stage flow: Parse → Clean → Extract → Segment
- **Version-tagged data directories** (`v1_`, `v1_parser_basic`, etc.) for checkpoint isolation

This system enables **full reproducibility** by linking research findings to specific git commits, data versions, and configuration states.

---

## Part 1: Documentation Architecture

### 1.1 Directory Structure
```
thoughts/
├── searchable/              # (Excluded from paths)
└── shared/
    ├── research/            # Investigation & analysis documents
    │   └── YYYY-MM-DD_HH-MM_topic.md
    ├── plans/               # Implementation blueprints
    │   └── YYYY-MM-DD_HH-MM_topic.md
    ├── prs/                 # Pull request documentation
    │   └── YYYY-MM-DD_HH-MM_description.md
    └── templates/           # Reusable document templates
        ├── research_template.md
        ├── plan_template.md
        └── experiment_template.md
```

### 1.2 Naming Convention
- Format: `YYYY-MM-DD_HH-MM_descriptive_topic.md`
- Example: `2025-12-03_21-32_sentiment_readability_qa_metrics.md`
- Rationale: Chronological sorting + human-readable descriptions

### 1.3 YAML Frontmatter Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `date` | ISO 8601 | Yes | Creation timestamp with timezone |
| `researcher` | string | Yes | Author identity |
| `git_commit` | string | Yes | Short SHA for reproducibility |
| `branch` | string | Yes | Git branch name |
| `repository` | string | Yes | Project identifier |
| `topic` | string | Yes | Descriptive title |
| `tags` | list | Yes | Categorization labels |
| `status` | enum | Yes | `in_progress`, `complete`, `ready_for_review` |
| `last_updated` | date | Yes | Most recent modification date |
| `last_updated_by` | string | Yes | Last modifier identity |
| `related_research` | path | Plans only | Link to source research document |

### 1.4 Metadata Generation Script

**File**: `hack/spec_metadata.sh`

```bash
# Generate YAML frontmatter
./hack/spec_metadata.sh --yaml

# Generate JSON for programmatic use
./hack/spec_metadata.sh --json

# Override researcher name
RESEARCHER_NAME="custom_name" ./hack/spec_metadata.sh --yaml
```

---

## Part 2: Preprocessing Pipeline Architecture

### 2.1 Module Overview

**Location**: `src/preprocessing/`

```
src/preprocessing/
├── __init__.py      # Public API exports
├── pipeline.py      # Orchestration (SECPreprocessingPipeline)
├── parser.py        # SEC HTML parsing (SECFilingParser)
├── cleaning.py      # Text cleaning (TextCleaner)
├── extractor.py     # Section extraction (SECSectionExtractor)
├── segmenter.py     # Risk segmentation (RiskSegmenter)
└── constants.py     # Section identifiers (SectionIdentifier)
```

### 2.2 Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SECPreprocessingPipeline                         │
│                    (pipeline.py:79-294)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. PARSE         2. EXTRACT        3. CLEAN         4. SEGMENT    │
│  ─────────        ──────────        ─────────        ──────────    │
│  SECFilingParser  SECSectionExtractor TextCleaner   RiskSegmenter  │
│  parser.py        extractor.py        cleaning.py   segmenter.py   │
│                                                                     │
│  HTML → ParsedFiling → ExtractedSection → cleaned text → Segments  │
│                                                                     │
│  Metadata preserved throughout: sic_code, sic_name, cik, ticker    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 Pipeline Configuration (Pydantic V2)

**File**: `pipeline.py:29-76` - `PipelineConfig`

```python
class PipelineConfig(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid',  # Raise error on unknown fields
    )

    # Cleaning options
    remove_html: bool = True
    deep_clean: bool = False
    use_lemmatization: bool = False
    remove_stopwords: bool = False

    # Segmentation options
    min_segment_length: Optional[int] = None  # From settings
    max_segment_length: Optional[int] = None  # From settings
    semantic_model_name: str = "all-MiniLM-L6-v2"
    similarity_threshold: float = 0.5
```

### 2.4 Stage 1: Parser

**File**: `parser.py:262-598` - `SECFilingParser`

| Feature | Implementation | Line Reference |
|---------|----------------|----------------|
| HTML Parsing | `sec_parser` library | `parser.py:391-397` |
| Metadata Extraction | Regex for SIC, CIK, Company | `parser.py:457-512` |
| Nesting Optimization | `_flatten_html_nesting()` | `parser.py:599-652` |
| JSON Serialization | `save_to_pickle()` (saves JSON) | `parser.py:95-144` |

**Output Naming**: `{TICKER}_10K_{YEAR}_{FORM}_{TIMESTAMP}_parsed.json`
- Example: `AAPL_10K_2021_10-K_20251202_135817_parsed.json`

### 2.5 Stage 2: Extractor

**File**: `extractor.py` - `SECSectionExtractor`

Extracts specific sections (Item 1A Risk Factors) with metadata preservation.

### 2.6 Stage 3: Cleaner

**File**: `cleaning.py` - `TextCleaner`

| Method | Purpose |
|--------|---------|
| `remove_html_tags()` | Strip HTML markup |
| `clean_text()` | Normalize whitespace, remove noise |
| `deep_clean()` | NLP-based cleaning (optional) |

### 2.7 Stage 4: Segmenter

**File**: `segmenter.py:135-488` - `RiskSegmenter`

| Segmentation Method | Trigger | Line Reference |
|---------------------|---------|----------------|
| **Semantic** (primary) | SentenceTransformer available | `segmenter.py:442-488` |
| **Header-based** (fallback) | < 2 semantic segments | `segmenter.py:265-289` |
| **Paragraph-based** (fallback) | < 3 header segments | `segmenter.py:291-320` |

**Output Schema** (`SegmentedRisks`):
```python
{
    "segments": [{"index": 0, "text": "...", "word_count": 134}],
    "sic_code": "7372",
    "sic_name": "PREPACKAGED SOFTWARE",
    "cik": "0000320193",
    "ticker": "AAPL",
    "company_name": "APPLE INC",
    "form_type": "10-K",
    "section_title": "Item 1A. Risk Factors",
    "total_segments": 54
}
```

### 2.8 Quick Start Usage

```python
from src.preprocessing import process_filing

# Single file processing
result = process_filing("data/raw/AAPL_10K_2021.html")
print(f"Company: {result.company_name}, SIC: {result.sic_name}")
print(f"Segments: {len(result)}")

# Save output
result.save_to_json("data/processed/AAPL_10K_2021_segmented.json")
```

---

## Part 3: Data Directory Structure & Versioning

### 3.1 Complete Directory Layout

```
data/
├── dictionary/                          # Reference data
│   ├── lm_dictionary_cache.pkl          # Preprocessed LM dictionary
│   └── Loughran-McDonald_MasterDictionary_1993-2024.csv
│
├── raw/                                 # IMMUTABLE source data
│   ├── AAPL_10K_2021.html              # 100+ SEC filings
│   ├── AAPL_10K_2022.html
│   ├── GOOGL_10K_2021.html
│   └── ... (95 files across 20+ tickers)
│
├── interim/                             # Intermediate processing stages
│   ├── parsed/                          # Parser output (JSON)
│   │   ├── v1_parser_basic/             # Version tag: basic parser
│   │   ├── v1_parser_semetic/           # Version tag: semantic parser
│   │   ├── AAPL_10K_2021_10-K_20251202_135817_parsed.json
│   │   └── ... (timestamped outputs)
│   │
│   └── extracted/                       # Extractor output
│       ├── v1_/                         # Version tag: extraction v1
│       │   ├── AAPL_10K_2021_cleaned_risks.json
│       │   └── AAPL_10K_2021_extracted_risks.json
│       └── AAPL_10K_2021_extracted_risks.json  # Current version
│
└── processed/                           # ML-ready outputs
    ├── AAPL_10K_2021_segmented_risks.json  # Final segmented data
    ├── AAPL_10K_2022_segmented_risks.json
    ├── ... (50+ processed files)
    │
    ├── features/                        # Feature engineering output
    │   └── example_sentiment.json
    │
    └── labeled/                         # Training datasets
        └── {YYYYMMDD_HHMMSS}_{experiment}/
            └── run_config.yaml
```

### 3.2 Versioning Patterns

| Pattern | Location | Purpose | Example |
|---------|----------|---------|---------|
| **Version Prefix** | `interim/*/v1_/` | Isolate algorithm versions | `v1_parser_basic/`, `v1_parser_semetic/` |
| **Timestamp Suffix** | Parsed files | Track processing time | `_20251202_135817_parsed.json` |
| **Run ID Directory** | `processed/labeled/` | Experiment isolation | `20251212_151708_sentiment_baseline/` |

### 3.3 File Naming Conventions

| Stage | Pattern | Example |
|-------|---------|---------|
| Raw | `{TICKER}_10K_{YEAR}.html` | `AAPL_10K_2021.html` |
| Parsed | `{TICKER}_10K_{YEAR}_{FORM}_{TIMESTAMP}_parsed.json` | `AAPL_10K_2021_10-K_20251202_135817_parsed.json` |
| Extracted | `{TICKER}_10K_{YEAR}_{type}_risks.json` | `AAPL_10K_2021_extracted_risks.json` |
| Processed | `{TICKER}_10K_{YEAR}_segmented_risks.json` | `AAPL_10K_2021_segmented_risks.json` |

### 3.4 Data Lineage Example

```
data/raw/AAPL_10K_2021.html (7.5MB HTML)
    │
    ├─── Parser (sec_parser + monkey patches)
    ▼
data/interim/parsed/AAPL_10K_2021_10-K_20251202_135817_parsed.json (7.5MB JSON)
    │   - elements: 2,847 semantic elements
    │   - metadata: {sic_code: "3571", cik: "0000320193", ...}
    │
    ├─── Extractor (Item 1A only)
    ▼
data/interim/extracted/AAPL_10K_2021_extracted_risks.json
    │   - section_title: "Item 1A. Risk Factors"
    │   - text: ~50KB cleaned text
    │
    ├─── Cleaner + Segmenter
    ▼
data/processed/AAPL_10K_2021_segmented_risks.json
    │   - segments: 54 risk paragraphs
    │   - sentiment: pre-computed per segment
    │   - aggregate_sentiment: {avg_negative_ratio: 0.0454, ...}
```

### 3.5 Processed Output Schema

**File**: `data/processed/AAPL_10K_2021_segmented_risks.json`

```json
{
  "filing_name": "AAPL_10K_2021.html",
  "ticker": "AAPL",
  "section_title": "Item 1A. Risk Factors",
  "section_identifier": "part1item1a",
  "num_segments": 54,
  "segmentation_settings": {
    "min_segment_length": 50,
    "max_segment_length": 999999999999
  },
  "sentiment_analysis_enabled": true,
  "aggregate_sentiment": {
    "avg_negative_ratio": 0.0454,
    "avg_uncertainty_ratio": 0.0326,
    "avg_positive_ratio": 0.0054,
    "avg_sentiment_word_ratio": 0.1085
  },
  "segments": [
    {
      "id": 1,
      "text": "Item 1A. Risk Factors...",
      "length": 897,
      "word_count": 134,
      "sentiment": {
        "negative_count": 1,
        "positive_count": 0,
        "uncertainty_count": 5,
        "negative_ratio": 0.0072,
        "total_sentiment_words": 6
      }
    }
  ]
}
```

---

## Part 4: RunContext for Experiment Tracking

### 4.1 Implementation

**File**: `src/config.py:183-243`

```python
from src.config import RunContext

# Create versioned experiment directory
run = RunContext(name="sentiment_baseline")
run.create()

# Output path: data/processed/labeled/20251212_151708_sentiment_baseline/
output_path = run.output_dir

# Preserve experiment configuration
run.save_config({
    "model": "finbert",
    "learning_rate": 2e-5,
    "seed": 42,
    "data_version": "ea45dd2",  # Link to git commit
    "preprocessing": {
        "min_segment_length": 50,
        "max_segment_length": 2000
    }
})
```

### 4.2 Properties

| Property | Description | Example |
|----------|-------------|---------|
| `run_id` | Timestamp identifier | `20251212_151708` |
| `output_dir` | Full path | `labeled/20251212_151708_sentiment_baseline/` |
| `save_config()` | Writes `run_config.yaml` | Preserves full experiment state |

---

## Part 5: Configuration Versioning

### 5.1 Pydantic Settings Structure

**File**: `src/config.py:1000-1037`

| Config Section | Purpose | File Reference |
|----------------|---------|----------------|
| `paths` | Directory structure | `config.py:51-177` |
| `sec_parser` | Parser settings | `config.py:250-274` |
| `preprocessing` | Text cleaning | `config.py:300-321` |
| `extraction` | Section extraction | `config.py:328-346` |
| `sentiment` | Sentiment analysis | `config.py:426-577` |
| `readability` | Readability features | `config.py:797-950` |
| `reproducibility` | Random seeds | `config.py:410-419` |

### 5.2 YAML Config Files

```
configs/
├── config.yaml                    # Main settings
└── features/
    ├── sentiment.yaml             # LM dictionary categories
    ├── readability.yaml           # Readability thresholds
    ├── topic_modeling.yaml        # Topic model params
    └── risk_analysis.yaml         # Risk classification
```

---

## Part 6: Existing Research Documents Inventory

| Document | Topic | Status |
|----------|-------|--------|
| `2025-12-03_17-51-31_config_restructure.md` | Config code quality analysis | complete |
| `2025-12-03_18-13-00_legacy_imports_audit.md` | Legacy import patterns | complete |
| `2025-12-03_19-16_extractor_qa_metrics.md` | Extractor QA evaluation | complete |
| `2025-12-03_19-45_parser_qa_metrics.md` | Parser QA evaluation | complete |
| `2025-12-03_20-23_cleaner_segmenter_qa_metrics.md` | Cleaning/segmenting QA | complete |
| `2025-12-03_21-32_sentiment_readability_qa_metrics.md` | Sentiment/readability QA | complete |
| `2025-12-03_21-45_sentiment_readability_validation_plan.md` | Validation test plan | ready_for_review |

---

## Code References

### Documentation System
| File:Line | Description |
|-----------|-------------|
| `hack/spec_metadata.sh:22-58` | Metadata gathering functions |
| `hack/spec_metadata.sh:72-84` | YAML frontmatter output |
| `CLAUDE.md:1-50` | Research workflow instructions |

### Preprocessing Pipeline
| File:Line | Description |
|-----------|-------------|
| `src/preprocessing/__init__.py:1-62` | Public API exports |
| `src/preprocessing/pipeline.py:29-76` | PipelineConfig (Pydantic V2) |
| `src/preprocessing/pipeline.py:79-216` | SECPreprocessingPipeline class |
| `src/preprocessing/parser.py:262-410` | SECFilingParser.parse_filing() |
| `src/preprocessing/parser.py:457-512` | Metadata extraction (SIC, CIK) |
| `src/preprocessing/segmenter.py:42-133` | SegmentedRisks schema |
| `src/preprocessing/segmenter.py:135-224` | RiskSegmenter.segment_risks() |
| `src/preprocessing/segmenter.py:442-488` | Semantic segmentation |

### Configuration
| File:Line | Description |
|-----------|-------------|
| `src/config.py:183-243` | RunContext class |
| `src/config.py:1000-1037` | Settings composition |

---

## Architecture Insights

### Design Principles
1. **Immutable Raw Data**: Never modify files in `data/raw/`
2. **Staged Processing**: Clear checkpoints at interim/processed stages
3. **Version Tagging**: Subdirectories (`v1_/`) for algorithm versions
4. **Timestamp Suffixes**: Every output traceable to processing time
5. **Git-Linked Metadata**: Every document references a specific commit
6. **Config Preservation**: Experiment configs saved with outputs
7. **Metadata Propagation**: SIC, CIK, company preserved through pipeline

### Integration Flow
```
CLAUDE.md (workflow)
    ↓ instructs
hack/spec_metadata.sh (metadata)
    ↓ populates
thoughts/shared/research/*.md (documentation)
    ↓ informs
thoughts/shared/plans/*.md (implementation)
    ↓ guides
src/preprocessing/ (pipeline code)
    ↓ processes
data/raw/ → data/interim/ → data/processed/ (versioned outputs)
```

---

## MLOps Best Practices Checklist

| Practice | Implementation | Status |
|----------|----------------|--------|
| **Data Versioning** | Staged directories + version prefixes + timestamps | IMPLEMENTED |
| **Config Management** | Pydantic models + YAML files | IMPLEMENTED |
| **Experiment Tracking** | RunContext + run_config.yaml | IMPLEMENTED |
| **Reproducibility** | Seeds + git SHA + config snapshots | IMPLEMENTED |
| **Documentation** | Structured markdown + YAML frontmatter | IMPLEMENTED |
| **Data Lineage** | Directory structure + metadata propagation | IMPLEMENTED |
| **Pipeline Orchestration** | SECPreprocessingPipeline (4 stages) | IMPLEMENTED |
| **Schema Validation** | Pydantic V2 models throughout | IMPLEMENTED |
| **Model Registry** | `models/registry/` directory exists | PARTIAL |
| **Metrics Logging** | Manual JSON files | COULD IMPROVE |

---

## Recommendations

### Priority 1: Template Files (COMPLETED)
Created reusable templates at:
- `thoughts/shared/templates/research_template.md`
- `thoughts/shared/templates/plan_template.md`
- `thoughts/shared/templates/experiment_template.md`

### Priority 2: Automated Metrics Logging
Consider adding to RunContext:
```python
run.save_metrics({
    "accuracy": 0.87,
    "f1_score": 0.84,
    "loss": 0.23
})
```

### Priority 3: DVC Integration
For large data versioning beyond git:
```yaml
# dvc.yaml
stages:
  parse:
    cmd: python scripts/01_parse.py
    deps:
      - data/raw/
    outs:
      - data/interim/parsed/
```

### Priority 4: Version Consistency
Standardize version tagging:
- Current: `v1_`, `v1_parser_basic`, `v1_parser_semetic` (inconsistent)
- Proposed: `v{MAJOR}.{MINOR}/` (e.g., `v1.0/`, `v1.1/`)

---

## Open Questions

1. Should `models/registry/` follow a specific schema (MLflow, custom)?
2. Should research documents be auto-indexed for searchability?
3. Should RunContext integrate with experiment tracking tools (MLflow, W&B)?
4. Should version prefixes include git SHA for data-code linkage?

Read C:\Users\bichn\MSBA\SEC finetune\thoughts\shared\plans\2025-12-12_mlops_improvements.md for more information | DONE
---

## Appendix A: Document Relationship Graph

```
research/config_restructure.md
    └─→ plans/config_restructure.md
        └─→ src/config/ (implementation)

research/sentiment_qa_metrics.md
    └─→ plans/sentiment_validation_plan.md
        └─→ tests/features/ (implementation)

research/mlops_research_system_analysis.md (this document)
    └─→ templates/research_template.md
    └─→ templates/plan_template.md
    └─→ templates/experiment_template.md
```

## Appendix B: Data Inventory Summary

| Category | Count | Size Range |
|----------|-------|------------|
| Raw HTML files | ~100 | 2-20 MB each |
| Parsed JSON files | ~100 | 5-16 MB each |
| Extracted JSON files | ~100 | 10-50 KB each |
| Processed JSON files | ~50 | 20-100 KB each |
| Tickers covered | 20+ | AAPL, GOOGL, MSFT, etc. |
| Years covered | 2020-2025 | 5-year span |
