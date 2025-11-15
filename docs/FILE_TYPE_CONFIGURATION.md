# File Type Configuration Guide

## Overview

The SEC Filing Analyzer supports flexible input file types through the `INPUT_FILE_EXTENSIONS` configuration in `src/config.py`.

## Current Configuration

**Location:** `src/config.py`

```python
# Input file types
# Options: ["html"], ["txt"], or ["html", "txt"] for both
INPUT_FILE_EXTENSIONS = ["html"]
```

## Supported Configurations

### Option 1: HTML Files Only (Default - RECOMMENDED)

```python
INPUT_FILE_EXTENSIONS = ["html"]
```

**Use when:**
- You have SEC EDGAR HTML filings (downloaded directly from SEC EDGAR)
- You want full semantic parsing with section detection
- You need table extraction and structured data

**Advantages:**
- ✅ Full semantic structure preservation
- ✅ Accurate section identification (Item 1A, Item 7, etc.)
- ✅ Table extraction capabilities
- ✅ Works seamlessly with `sec-parser` library

**Example files:**
- `goog-20241231.html` (from SEC EDGAR)
- `AAPL_10K_2023.htm`

---

### Option 2: Text Files Only

```python
INPUT_FILE_EXTENSIONS = ["txt"]
```

**Use when:**
- You have plain text SEC filings
- You've pre-processed filings to remove HTML

**Limitations:**
- ⚠️ **sec-parser library requires HTML** - will not work with plain text
- ⚠️ Loses semantic structure (sections, tables, formatting)
- ⚠️ Requires custom text parser implementation

**Status:** Requires additional development to support `.txt` files properly.

---

### Option 3: Both HTML and Text Files

```python
INPUT_FILE_EXTENSIONS = ["html", "txt"]
```

**Use when:**
- You have a mix of HTML and text filings
- You want maximum flexibility

**Requirements:**
- Custom logic to detect file type and use appropriate parser
- Separate parsing pipeline for `.txt` files

**Status:** Requires file type detection and dual parser implementation.

---

## How to Change Configuration

### Step 1: Edit `src/config.py`

Open `C:\Users\bichn\MSBA\SEC finetune\src\config.py` and modify:

```python
# For HTML files only (recommended)
INPUT_FILE_EXTENSIONS = ["html"]

# For TXT files only (requires custom parser)
INPUT_FILE_EXTENSIONS = ["txt"]

# For both HTML and TXT files
INPUT_FILE_EXTENSIONS = ["html", "txt"]
```

### Step 2: Place Files in `data/raw/`

Based on your configuration:

```bash
# For HTML
data/raw/
├── company1_10k.html
├── company2_10k.htm
└── goog-20241231.html

# For TXT
data/raw/
├── company1_10k.txt
└── GOOGL_10K_2024.txt

# For both
data/raw/
├── company1_10k.html
├── company2_10k.txt
└── goog-20241231.html
```

### Step 3: Restart the Application

The configuration is loaded when the app starts:

```bash
streamlit run src/visualization/app.py
```

---

## Implementation Details

### File Discovery

The `get_filing_files()` function in `app.py` automatically discovers files based on the configuration:

```python
def get_filing_files():
    """Get list of SEC filing files in data/raw/"""
    raw_dir = Path(RAW_DATA_DIR)
    all_files = []
    for ext in INPUT_FILE_EXTENSIONS:
        ext = ext.lstrip('.')  # Normalize extension
        pattern = f"*.{ext}"
        all_files.extend(raw_dir.glob(pattern))
    return sorted([f.name for f in all_files])
```

### Extension Normalization

Extensions are automatically normalized to handle:
- With dot: `.html` → `html`
- Without dot: `html` → `html`

Both formats work in the configuration.

---

## Parser Compatibility

### sec-parser Library Requirements

The `sec-parser` library used in `src/preprocessing/parser.py` **requires HTML format**:

```python
# From parser.py
def __init__(self):
    # sec-parser only provides Edgar10QParser for HTML parsing
    self.parsers = {
        FormType.FORM_10K: sp.Edgar10QParser(),  # Expects HTML
        FormType.FORM_10Q: sp.Edgar10QParser(),   # Expects HTML
    }
```

**HTML Input:**
- ✅ Parses semantic elements (sections, tables, paragraphs)
- ✅ Builds hierarchical tree structure
- ✅ Identifies section types (Item 1A, etc.)

**TXT Input:**
- ❌ Will fail - parser expects HTML tags
- ❌ Cannot extract semantic structure from plain text

---

## Future Enhancements

To support `.txt` files, implement:

1. **Text-based parser** in `src/preprocessing/parser.py`:
   ```python
   class TextFilingParser:
       """Parser for plain text SEC filings"""
       def parse_filing(self, file_path):
           # Read text file
           # Use regex to find sections
           # Return simplified structure
   ```

2. **File type detection** in `app.py`:
   ```python
   def run_analysis_pipeline(file_path: Path):
       file_ext = file_path.suffix.lower()
       if file_ext in ['.html', '.htm']:
           parser = SECFilingParser()
       elif file_ext == '.txt':
           parser = TextFilingParser()
       # ...
   ```

3. **Unified interface** for both parser types

---

## Examples

### Example 1: Switch to HTML-only mode

```python
# config.py
INPUT_FILE_EXTENSIONS = ["html"]
```

App will show:
```
✓ Found 1 file(s) in data/raw/
📄 Select a 10-K filing: goog-20241231.html
```

### Example 2: Enable both file types

```python
# config.py
INPUT_FILE_EXTENSIONS = ["html", "txt"]
```

App will show:
```
✓ Found 2 file(s) in data/raw/
📄 Select a 10-K filing:
  - goog-20241231.html
  - GOOGL_10K_2024.txt
```

---

## Troubleshooting

### Issue: "No .html files found"

**Cause:** No HTML files in `data/raw/` or wrong configuration

**Solution:**
1. Check `data/raw/` directory has `.html` files
2. Verify `INPUT_FILE_EXTENSIONS = ["html"]` in `config.py`
3. Restart the Streamlit app

### Issue: "Error during analysis: module 'sec_parser' has no attribute 'Edgar10KParser'"

**Cause:** Fixed in recent update - `sec-parser` only has `Edgar10QParser`

**Solution:** Already resolved - parser now uses `Edgar10QParser` for all form types

### Issue: Parser fails on .txt files

**Cause:** `sec-parser` requires HTML markup

**Solution:** Either:
1. Use HTML files instead (recommended)
2. Implement custom text parser (requires development)

---

## Summary

**Current Recommendation:** Use `INPUT_FILE_EXTENSIONS = ["html"]`

This provides the best compatibility with the existing `sec-parser` infrastructure and enables full semantic analysis of SEC filings.

For questions or to add `.txt` support, see the parser implementation in:
- `src/preprocessing/parser.py`
- `src/preprocessing/extractor.py`
