# Extraction Output Best Practices

## Overview
This document outlines best practices for saving, loading, and managing extracted SEC filing sections in a maintainable and scalable way.

## Directory Structure

```
data/
├── raw/                    # Original HTML/TXT filings
├── interim/
│   ├── parsed/            # Parsed filings (JSON)
│   └── extracted/         # Extracted sections (JSON)
└── processed/             # Final processed data for modeling
```

## Saving Outputs

### 1. Basic Usage

```python
from src.preprocessing.extractor import SECSectionExtractor
from src.preprocessing.parser import SECFilingParser

# Parse filing
parser = SECFilingParser()
filing = parser.parse_filing("data/raw/AAPL_10K.html", form_type="10-K")

# Extract section
extractor = SECSectionExtractor()
risk_section = extractor.extract_risk_factors(filing)

# Save to JSON
risk_section.save_to_json("data/interim/extracted/AAPL_risks.json")
```

### 2. Naming Conventions

**Recommended file naming:**
- `{TICKER}_{FORM_TYPE}_{YEAR}_{SECTION}.json`
- Examples:
  - `AAPL_10K_2024_risks.json`
  - `GOOGL_10Q_Q3_2024_mdna.json`
  - `MSFT_10K_2024_business.json`

### 3. Output Format Structure

```json
{
  "version": "1.0",
  "text": "Full section text...",
  "identifier": "part1item1a",
  "title": "Item 1A. Risk Factors",
  "subsections": ["Market Risks", "Operational Risks", ...],
  "elements": [
    {"type": "TextElement", "text": "...", "level": 0},
    {"type": "TableElement", "text": "...", "level": 0}
  ],
  "metadata": {
    "form_type": "10-K",
    "num_subsections": 15,
    "num_elements": 342,
    "element_type_counts": {"TextElement": 320, "TableElement": 22}
  },
  "stats": {
    "text_length": 45678,
    "num_subsections": 15,
    "num_elements": 342,
    "num_tables": 22,
    "num_paragraphs": 320
  }
}
```

## Loading Outputs

### 1. Load Extracted Section

```python
from src.preprocessing.extractor import ExtractedSection

# Load from JSON
section = ExtractedSection.load_from_json("data/interim/extracted/AAPL_risks.json")

# Access data
print(section.title)
print(f"Length: {len(section)} characters")
print(f"Subsections: {section.subsections}")
```

### 2. Batch Loading

```python
from pathlib import Path
from src.config import EXTRACTED_DATA_DIR

# Load all extracted sections
sections = []
for json_file in EXTRACTED_DATA_DIR.glob("*_risks.json"):
    section = ExtractedSection.load_from_json(json_file)
    sections.append(section)

print(f"Loaded {len(sections)} risk sections")
```

## Advanced: Multiple Output Formats

### 1. JSON + Parquet for Analytics

```python
# Save as JSON (human-readable)
risk_section.save_to_json("data/interim/extracted/AAPL_risks.json")

# Also save as Parquet for fast querying (recommended for large datasets)
import pandas as pd

df = pd.DataFrame([{
    'ticker': 'AAPL',
    'form_type': risk_section.metadata['form_type'],
    'section': risk_section.identifier,
    'title': risk_section.title,
    'text': risk_section.text,
    'num_subsections': len(risk_section.subsections),
    'subsections': risk_section.subsections,
    'year': 2024,
}])

df.to_parquet("data/interim/extracted/AAPL_risks.parquet")
```

### 2. Environment-Based Format Selection

```bash
# In .env file
EXTRACTION_OUTPUT_FORMAT=both  # Options: json, parquet, both
```

```python
from src.config import EXTRACTION_OUTPUT_FORMAT

if EXTRACTION_OUTPUT_FORMAT in ['json', 'both']:
    risk_section.save_to_json(json_path)

if EXTRACTION_OUTPUT_FORMAT in ['parquet', 'both']:
    save_as_parquet(risk_section, parquet_path)
```

## Configuration Management

### 1. Centralized Section Definitions

All section identifiers are defined in `src/config.py`:

```python
# src/config.py
SEC_10K_SECTIONS = {
    "part1item1": "Item 1. Business",
    "part1item1a": "Item 1A. Risk Factors",
    # ... add new sections here
}

# To extract a custom section, just add it to the config!
```

### 2. Extensibility

**Adding new sections:**

1. Update `src/config.py`:
```python
SEC_10K_SECTIONS = {
    # ... existing sections
    "part2item9a": "Item 9A. Controls and Procedures",  # NEW
}
```

2. Create enum value (optional, for type safety):
```python
# src/preprocessing/extractor.py
class SectionIdentifier(Enum):
    # ... existing identifiers
    ITEM_9A_CONTROLS = "part2item9a"  # NEW
```

3. Use immediately:
```python
controls = extractor.extract_section(filing, SectionIdentifier.ITEM_9A_CONTROLS)
```

### 3. Environment-Based Defaults

```bash
# .env
DEFAULT_SECTIONS_TO_EXTRACT=part1item1a,part2item7,part2item7a
```

```python
# config.py
DEFAULT_SECTIONS_TO_EXTRACT = os.getenv(
    "DEFAULT_SECTIONS_TO_EXTRACT",
    "part1item1a"
).split(",")
```

## Data Versioning

### 1. Track Processing Versions

```python
# Enhanced metadata
metadata = {
    'form_type': '10-K',
    'extraction_version': '1.0',
    'sec_parser_version': os.getenv('SEC_PARSER_VERSION'),
    'extraction_date': datetime.now().isoformat(),
    'source_file': str(input_file),
}
```

### 2. Schema Evolution

When changing the output format:
1. Increment version number in `save_to_json()`
2. Update `load_from_json()` to handle both versions
3. Consider migration script for old files

```python
def load_from_json(file_path):
    data = json.load(f)
    version = data.get('version', '0.0')

    if version == '0.0':
        # Migrate old format
        data = migrate_v0_to_v1(data)

    return ExtractedSection(**data)
```

## Performance Optimization

### 1. Lazy Loading for Large Datasets

```python
class ExtractedSection:
    def __init__(self, ..., lazy_load=False):
        if lazy_load:
            self._text = None  # Load on demand
        else:
            self._text = text

    @property
    def text(self):
        if self._text is None:
            self._text = self._load_text()
        return self._text
```

### 2. Caching

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def load_extracted_section(file_path: str):
    return ExtractedSection.load_from_json(file_path)
```

## Testing

### 1. Golden Dataset Validation

```python
# tests/test_extraction.py
def test_extraction_format():
    section = extract_test_section()

    # Validate structure
    assert 'version' in section.__dict__
    assert 'metadata' in section.__dict__
    assert len(section.text) > 0

    # Validate save/load roundtrip
    section.save_to_json(tmp_path / "test.json")
    loaded = ExtractedSection.load_from_json(tmp_path / "test.json")

    assert loaded.text == section.text
    assert loaded.identifier == section.identifier
```

## Summary

✅ **DO:**
- Use JSON for human-readable storage
- Add versioning to all outputs
- Centralize config in `src/config.py`
- Use environment variables for runtime config
- Follow consistent naming conventions
- Include metadata and statistics

❌ **DON'T:**
- Hardcode section identifiers in multiple places
- Skip versioning in output format
- Store extracted data in `raw/` directory
- Use pickle for long-term storage (use JSON)
- Forget to validate save/load roundtrips

## References

- `src/config.py` - All configuration settings
- `src/preprocessing/extractor.py` - Extraction logic
- `src/preprocessing/parser.py` - Parsing logic (similar patterns)
