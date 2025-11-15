# Utility Scripts

This directory contains utility scripts for development, debugging, and testing.

## Directory Structure

```
utils/
├── check_installation.py     # Validate environment setup
├── setup_nlp_models.py       # Download required NLP models
├── debugging/                # Debugging and diagnostic tools
│   ├── diagnose_extraction.py
│   └── debug_node_structure.py
├── inspection/               # Data inspection tools
│   └── inspect_parsed.py
└── testing/                  # Testing utilities
    └── test_extractor_fix.py
```

## Scripts Overview

### Environment Setup

**check_installation.py**
- Validates that all dependencies are correctly installed
- Checks core libraries, SEC-specific packages, and NLP models
- Run after initial setup to verify installation

```bash
python scripts/utils/check_installation.py
```

**setup_nlp_models.py**
- Downloads required spaCy language models
- Interactive script to choose model size
- Run post-installation

```bash
python scripts/utils/setup_nlp_models.py
```

### Debugging Tools (`debugging/`)

**diagnose_extraction.py**
- Comprehensive diagnostic for extraction failures
- Performs "5 Whys" analysis on parsing issues
- Examines tree structure, identifiers, and text matching

```bash
python scripts/utils/debugging/diagnose_extraction.py
```

**debug_node_structure.py**
- Debug semantic element tree structure
- Inspect node types and relationships

```bash
python scripts/utils/debugging/debug_node_structure.py
```

### Inspection Tools (`inspection/`)

**inspect_parsed.py**
- Inspect parsed SEC filings saved as JSON
- List available files or examine specific filings
- View sections, elements, and sample content

```bash
# List all parsed files
python scripts/utils/inspection/inspect_parsed.py list

# Inspect specific file
python scripts/utils/inspection/inspect_parsed.py inspect data/interim/AAPL_parsed.json
```

### Testing Tools (`testing/`)

**test_extractor_fix.py**
- Test extractor fixes and improvements
- Validate extraction logic

```bash
python scripts/utils/testing/test_extractor_fix.py
```

## Usage Guidelines

1. **Environment Setup**: Run `check_installation.py` after setting up the project
2. **Debugging**: Use debugging tools when encountering parsing or extraction issues
3. **Inspection**: Use inspection tools to verify data at each pipeline stage
4. **Testing**: Use testing tools to validate fixes before committing

## Adding New Utilities

When adding new utility scripts:
1. Place them in the appropriate subdirectory
2. Include a docstring with purpose and usage
3. Update this README
4. Follow the existing naming conventions
