# SEC Filing Parser - Usage Guide

## Overview

This guide explains how to use the new sec-parser-based architecture for extracting sections from SEC filings.

## Installation

```bash
# Install sec-parser
pip install sec-parser==0.54.0

# Install sec-downloader (for downloading filings)
pip install sec-downloader

# Install other dependencies
pip install python-dotenv pandas
```

## Quick Start

### 1. Basic Risk Factors Extraction

```python
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor

# Parse the filing
parser = SECFilingParser()
filing = parser.parse_filing("path/to/10K.html", form_type="10-K")

# Extract Risk Factors
extractor = RiskFactorExtractor()
risk_section = extractor.extract(filing)

# Access the content
print(f"Section: {risk_section.title}")
print(f"Length: {len(risk_section)} characters")
print(f"Subsections: {risk_section.subsections}")
print(f"Text: {risk_section.text}")
```

### 2. Extract Multiple Sections

```python
from src.preprocessing.extractor import SECSectionExtractor, SectionIdentifier

parser = SECFilingParser()
filing = parser.parse_filing("path/to/10K.html", form_type="10-K")

extractor = SECSectionExtractor()

# Extract different sections
business = extractor.extract_section(filing, SectionIdentifier.ITEM_1_BUSINESS)
risks = extractor.extract_section(filing, SectionIdentifier.ITEM_1A_RISK_FACTORS)
mdna = extractor.extract_section(filing, SectionIdentifier.ITEM_7_MDNA)
financials = extractor.extract_section(filing, SectionIdentifier.ITEM_8_FINANCIAL_STATEMENTS)
```

## API Reference

### SECFilingParser

Main class for parsing SEC HTML filings.

#### Methods

**`parse_filing(file_path, form_type="10-K")`**
- Parses a filing from an HTML file
- Returns: `ParsedFiling` object
- Parameters:
  - `file_path`: Path to HTML file
  - `form_type`: "10-K" or "10-Q"

**`parse_from_content(html_content, form_type="10-K")`**
- Parses a filing from HTML string
- Returns: `ParsedFiling` object

**`get_parser_info()`**
- Returns parser and library version information

### ParsedFiling

Container for parsed filing data.

#### Attributes

- `elements`: List of semantic elements
- `tree`: Semantic tree structure
- `form_type`: FormType enum (FORM_10K or FORM_10Q)
- `metadata`: Dictionary with parsing metadata

#### Methods

- `__len__()`: Returns number of elements
- `get_section_names()`: Returns list of all top-level section names

### SECSectionExtractor

Extracts specific sections from parsed filings.

#### Methods

**`extract_section(filing, section)`**
- Extracts a specific section
- Parameters:
  - `filing`: ParsedFiling object
  - `section`: SectionIdentifier enum
- Returns: `ExtractedSection` or None

**`extract_risk_factors(filing)`**
- Convenience method for Risk Factors
- Returns: `ExtractedSection` or None

**`extract_mdna(filing)`**
- Convenience method for MD&A
- Returns: `ExtractedSection` or None

### ExtractedSection

Container for extracted section data.

#### Attributes

- `text`: Full text content
- `identifier`: Section identifier (e.g., "part1item1a")
- `title`: Human-readable title
- `subsections`: List of subsection titles
- `elements`: List of semantic elements
- `metadata`: Dictionary with metadata

#### Methods

- `__len__()`: Returns character length
- `get_tables()`: Returns all TableElement objects
- `get_paragraphs()`: Returns all text paragraphs

### RiskFactorExtractor

Specialized extractor for Risk Factors.

#### Methods

**`extract(filing)`**
- Extract Risk Factors from ParsedFiling
- Returns: `ExtractedSection` or None

**`extract_from_file(file_path, form_type="10-K")`**
- Parse file and extract in one step
- Returns: `ExtractedSection` or None

**`get_risk_categories(section)`**
- Get list of risk category titles
- Returns: List of strings

**`get_risk_paragraphs(section)`**
- Get individual risk paragraphs
- Returns: List of strings

## Section Identifiers

### 10-K Sections

| Identifier | Section Name |
|------------|--------------|
| `ITEM_1_BUSINESS` | Item 1. Business |
| `ITEM_1A_RISK_FACTORS` | Item 1A. Risk Factors |
| `ITEM_1B_UNRESOLVED_STAFF` | Item 1B. Unresolved Staff Comments |
| `ITEM_1C_CYBERSECURITY` | Item 1C. Cybersecurity |
| `ITEM_7_MDNA` | Item 7. MD&A |
| `ITEM_7A_MARKET_RISK` | Item 7A. Market Risk Disclosures |
| `ITEM_8_FINANCIAL_STATEMENTS` | Item 8. Financial Statements |

### 10-Q Sections

| Identifier | Section Name |
|------------|--------------|
| `ITEM_1_FINANCIAL_STATEMENTS_10Q` | Item 1. Financial Statements |
| `ITEM_2_MDNA_10Q` | Item 2. MD&A |
| `ITEM_1A_RISK_FACTORS_10Q` | Item 1A. Risk Factors |

## Complete Pipeline Example

```python
from pathlib import Path
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor
from src.preprocessing.cleaning import TextCleaner
from src.preprocessing.segmenter import RiskSegmenter

# 1. Parse filing
parser = SECFilingParser()
filing = parser.parse_filing("AAPL_10K.html", form_type="10-K")

# 2. Extract Risk Factors
extractor = RiskFactorExtractor()
risk_section = extractor.extract(filing)

# 3. Clean text
cleaner = TextCleaner()
clean_text = cleaner.clean_text(risk_section.text)

# 4. Segment into individual risks
segmenter = RiskSegmenter()
segments = segmenter.segment_risks(clean_text)

# 5. Process each segment
for i, segment in enumerate(segments, 1):
    print(f"Risk {i}: {segment[:100]}...")
```

## Working with Semantic Elements

The parser preserves the semantic structure of the filing:

```python
parser = SECFilingParser()
filing = parser.parse_filing("filing.html", form_type="10-K")

# Access all elements
for element in filing.elements:
    element_type = element.__class__.__name__
    print(f"{element_type}: {element.text[:50]}...")

# Get specific element types
import sec_parser as sp

titles = [el for el in filing.elements if isinstance(el, sp.TitleElement)]
tables = [el for el in filing.elements if isinstance(el, sp.TableElement)]
text = [el for el in filing.elements if isinstance(el, sp.TextElement)]

print(f"Found {len(titles)} titles, {len(tables)} tables, {len(text)} text elements")
```

## Downloading Filings

Use sec-downloader to get HTML filings:

```python
from sec_downloader import Downloader

# Initialize downloader
dl = Downloader("YourCompanyName", "email@example.com")

# Download latest 10-K
html = dl.get_filing_html(ticker="AAPL", form="10-K")

# Save to file
from pathlib import Path
output_file = Path("data/raw/AAPL_10K_latest.html")
output_file.write_text(html, encoding='utf-8')

# Now parse it
from src.preprocessing.parser import SECFilingParser
parser = SECFilingParser()
filing = parser.parse_from_content(html, form_type="10-K")
```

## Configuration

Key configuration options in `src/config.py`:

```python
# Form types
SUPPORTED_FORM_TYPES = ["10-K", "10-Q"]
DEFAULT_FORM_TYPE = "10-K"

# Parsing
PARSE_TABLES = True
PARSE_IMAGES = False

# Segmentation
MIN_SEGMENT_LENGTH = 50
MAX_SEGMENT_LENGTH = 2000

# Extraction
MIN_EXTRACTION_CONFIDENCE = 0.7
ENABLE_AUDIT_LOGGING = True
```

## Error Handling

```python
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor

try:
    # Parse filing
    parser = SECFilingParser()
    filing = parser.parse_filing("filing.html", form_type="10-K")

    # Extract section
    extractor = RiskFactorExtractor()
    risk_section = extractor.extract(filing)

    if risk_section is None:
        print("WARNING: Risk Factors section not found")
    else:
        print(f"SUCCESS: Extracted {len(risk_section)} characters")

except FileNotFoundError as e:
    print(f"ERROR: File not found - {e}")
except ValueError as e:
    print(f"ERROR: Invalid input - {e}")
except Exception as e:
    print(f"ERROR: Unexpected error - {e}")
```

## Best Practices

### 1. Reproducibility

```python
# Pin exact version in requirements.txt
sec-parser==0.54.0

# Use version checking
import sec_parser as sp
print(f"Using sec-parser version: {sp.__version__}")
```

### 2. Caching Parsed Filings

```python
import pickle
from pathlib import Path

# Save parsed filing
parser = SECFilingParser()
filing = parser.parse_filing("filing.html", form_type="10-K")

cache_file = Path("cache/parsed_filing.pkl")
cache_file.parent.mkdir(exist_ok=True)

with open(cache_file, 'wb') as f:
    pickle.dump(filing, f)

# Load from cache later
with open(cache_file, 'rb') as f:
    filing = pickle.load(f)
```

### 3. Batch Processing

```python
from pathlib import Path
from src.preprocessing.parser import SECFilingParser
from src.preprocessing.extractor import RiskFactorExtractor

parser = SECFilingParser()
extractor = RiskFactorExtractor()

results = []

for html_file in Path("data/raw").glob("*.html"):
    print(f"Processing: {html_file.name}")

    try:
        filing = parser.parse_filing(html_file, form_type="10-K")
        risk_section = extractor.extract(filing)

        if risk_section:
            results.append({
                'file': html_file.name,
                'length': len(risk_section),
                'subsections': len(risk_section.subsections),
            })
    except Exception as e:
        print(f"ERROR processing {html_file.name}: {e}")

# Save results
import pandas as pd
df = pd.DataFrame(results)
df.to_csv("extraction_results.csv", index=False)
```

## Troubleshooting

### Issue: ImportError for sec-parser

**Solution:**
```bash
pip install sec-parser==0.54.0
```

### Issue: Section not found

**Possible causes:**
1. Wrong form type (10-K vs 10-Q)
2. Non-standard filing format
3. Section not present in filing

**Solution:**
```python
# Check available sections
filing = parser.parse_filing("filing.html", form_type="10-K")
print("Available sections:")
for section_name in filing.get_section_names():
    print(f"  - {section_name}")
```

### Issue: Empty subsections list

**Cause:** Risk Factors section has no clearly marked subsections

**Solution:** Use semantic elements directly
```python
risk_section = extractor.extract(filing)
paragraphs = risk_section.get_paragraphs()
for para in paragraphs:
    print(para['text'][:100])
```

## Next Steps

1. See `examples/01_basic_extraction.py` for a complete working example
2. See `examples/02_complete_pipeline.py` for full pipeline
3. Check `tests/` for unit tests and validation examples
4. Review `src/preprocessing/` for implementation details
