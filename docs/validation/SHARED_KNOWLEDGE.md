# Shared Knowledge - SEC Filing Analyzer

> **Purpose:** Capture ground truth learnings, patterns, and gotchas discovered during development to prevent re-discovery and accelerate future work.

---

## 1. SEC Parser Behavior

### 1.1 Section Classification Gotcha

**Problem:** `sec-parser` does not always classify SEC section headers as `TopSectionTitle`.

**Evidence:** (`src/preprocessing/parser.py`)
- Item 1A (Risk Factors) → classified as `TitleElement` (not `TopSectionTitle`)
- Item 7 (MD&A) → classified as `TitleElement` (not `TopSectionTitle`)
- Only some sections (Item 1, Item 2, PART I, PART II) get `TopSectionTitle`

**Root Cause:** The sec-parser library's heuristics for detecting top-level sections don't always match SEC filing formatting variations.

**Solution:** When searching for sections, search ALL title-like elements:
```python
# ❌ WRONG - misses many sections
section_names = filing.get_section_names()  # Only TopSectionTitle

# ✅ CORRECT - search all title elements
for element in filing.elements:
    if element.__class__.__name__ in ['TopSectionTitle', 'TitleElement', 'IntroductorySectionElement']:
        # Check element.text for section patterns
```

**File Reference:** `tests/preprocessing/test_parser_section_recall.py:88-134`

---

### 1.2 HTML Character Encoding

**Problem:** SEC filings contain non-standard characters that break string matching.

**Evidence:**
- `\xa0` (non-breaking space) appears between "Item" and number
- `�` (replacement character) appears in some filings
- Example: `"Item 1A.\xa0\xa0\xa0\xa0Risk Factors"`

**Solution:** Normalize text before comparison:
```python
title_normalized = title.replace('\xa0', ' ').replace('�', ' ')
```

**File Reference:** `tests/preprocessing/test_parser_section_recall.py:124`

---

### 1.3 Deep HTML Nesting Performance

**Problem:** Some SEC filings have deeply nested HTML that causes stack overflow or slow parsing.

**Solution:** The parser includes `_flatten_html_nesting()` that removes redundant wrapper divs. Also temporarily increases recursion limit.

**File Reference:** `src/preprocessing/parser.py:570-625`

---

## 2. Test Suite Patterns

### 2.1 Required 10-K Sections for QA

These sections MUST be found for a 10-K to pass validation:

| Section ID | Section Name | Priority |
|------------|--------------|----------|
| `part1item1` | Item 1. Business | Required |
| `part1item1a` | Item 1A. Risk Factors | **Critical** |
| `part2item7` | Item 7. MD&A | **Critical** |
| `part2item7a` | Item 7A. Quantitative Disclosures | Required |

**Target Recall:** > 99%

**File Reference:** `tests/preprocessing/test_parser_section_recall.py:46-54`

---

### 2.2 Pytest Coverage Dependency

**Problem:** `--cov` flags fail if `pytest-cov` not installed.

**Solution:** Coverage flags removed from `pyproject.toml` defaults. Use explicitly:
```bash
# Install first
pip install pytest-cov

# Then run with coverage
pytest tests/ --cov=src --cov-report=html
```

**File Reference:** `pyproject.toml:181-188`

---

## 3. Configuration Patterns

### 3.1 Pydantic V2 Enforcement

**Rule:** ALL code must use Pydantic V2 patterns.

| ❌ Never Use | ✅ Always Use |
|-------------|--------------|
| `@validator` | `@field_validator` |
| `class Config:` | `model_config = ConfigDict(...)` |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |

**Validation Command:**
```bash
python scripts/utils/validation/validate_pydantic_v2.py src/
```

**File Reference:** `docs/PYDANTIC_V2_ENFORCEMENT.md`

---

### 3.2 Settings Access Pattern

**Pattern:** Use centralized settings from `src/config.py`:
```python
from src.config import settings

# Access paths
raw_dir = settings.paths.raw_data_dir
parsed_dir = settings.paths.parsed_data_dir

# Access model settings
model_name = settings.models.zero_shot_model
```

**File Reference:** `src/config.py`

---

## 4. Data Flow Architecture

```
SEC EDGAR (HTML)
       │
       ▼
┌─────────────────────┐
│  SECFilingParser    │  → ParsedFiling (elements, tree, metadata)
│  parser.py:262      │
└─────────────────────┘
       │
       ▼
┌─────────────────────┐
│  RiskFactorExtractor│  → ExtractedSection (text, subsections)
│  extractor.py       │
└─────────────────────┘
       │
       ▼
┌─────────────────────┐
│  TextCleaner        │  → Cleaned text (no HTML, normalized)
│  cleaning.py        │
└─────────────────────┘
       │
       ▼
┌─────────────────────┐
│  RiskSegmenter      │  → List[str] segments
│  segmenter.py       │
└─────────────────────┘
       │
       ▼
┌─────────────────────┐
│  RiskClassifier     │  → Classification results
│  inference.py       │
└─────────────────────┘
```

---

## 5. Common Gotchas

### 5.1 File Paths on Windows

**Problem:** Path handling differences between Windows and Unix.

**Solution:** Always use `pathlib.Path`:
```python
from pathlib import Path

# ✅ Cross-platform
file_path = Path(__file__).parent / "data" / "file.json"

# ❌ Breaks on Windows
file_path = os.path.join(__file__, "../data/file.json")
```

---

### 5.2 spaCy Model Not Found

**Problem:** `OSError: [E050] Can't find model 'en_core_web_sm'`

**Solution:**
```bash
python -m spacy download en_core_web_sm
```

---

### 5.3 sec-parser Table Bug

**Problem:** `'NoneType' has no attribute 'text'` in table parsing.

**Root Cause:** sec-parser bug where `row.find("td")` returns None for rows with only `<th>` elements.

**Solution:** Monkey-patched in `src/preprocessing/parser.py:26-46`

---

## 6. Verification Commands

```bash
# Run all tests
pytest tests/ -v

# Run parser QA tests
pytest tests/preprocessing/test_parser_section_recall.py -v

# Run with coverage (requires pytest-cov)
pytest tests/ --cov=src --cov-report=html

# Validate Pydantic v2 compliance
python scripts/utils/validation/validate_pydantic_v2.py src/

# Check code style
ruff check src/ scripts/

# Type checking
mypy src/
```

---

## 7. Key File References

| Purpose | File | Key Lines |
|---------|------|-----------|
| Parser implementation | `src/preprocessing/parser.py` | 262-410 |
| Section extraction | `src/preprocessing/extractor.py` | - |
| QA test suite | `tests/preprocessing/test_parser_section_recall.py` | 46-134 |
| Shared fixtures | `tests/conftest.py` | - |
| Settings | `src/config.py` | - |
| Risk taxonomy | `src/analysis/taxonomies/risk_taxonomy.yaml` | - |

---

## 8. Version Pins

| Package | Version | Reason |
|---------|---------|--------|
| `sec-parser` | `==0.54.0` | Reproducibility, tested compatibility |
| `pydantic` | `>=2.12.4` | V2 enforcement |
| Python | `>=3.10` | Required by sec-parser |

---

*Last Updated: 2025-12-03*
