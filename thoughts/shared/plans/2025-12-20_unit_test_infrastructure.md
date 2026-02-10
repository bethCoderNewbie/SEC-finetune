---
date: 2025-12-20T15:58:49-06:00
researcher: bethCoderNewbie
git_commit: 1843e0d
branch: main
repository: SEC finetune
topic: "Unit Test Infrastructure for Preprocessing Modules"
tags: [plan, testing, unit-tests, preprocessing]
status: approved
sources:
  - thoughts/shared/research/2025-12-15_12-30_mitigate_test_change_strategy.md
  - thoughts/shared/research/2025-12-15_18-26_flexible_test_metrics_architecture.md
---

# Plan: Unit Test Infrastructure for SEC Finetune

## Problem Statement

The existing `tests/preprocessing/` tests are QA/integration tests that validate output quality using real data. The project needs fast, isolated unit tests that verify code logic without file I/O dependencies.

## Desired End State

After implementation:
1. `tests/unit/preprocessing/` directory with isolated unit tests
2. Lightweight `tests/unit/conftest.py` with mock-only fixtures
3. Unit tests run in <1 second with zero real data dependencies
4. Existing QA tests in `tests/preprocessing/` remain untouched

## Anti-Scope (NOT Doing)

- NOT modifying existing `tests/preprocessing/` files
- NOT modifying `tests/conftest.py`
- NOT adding integration tests
- NOT requiring external libraries (spaCy, sentence-transformers) for unit tests

---

## Directory Structure to Create

```
tests/unit/
├── __init__.py
├── conftest.py                    # Lightweight mock fixtures
└── preprocessing/
    ├── __init__.py
    ├── test_constants_unit.py     # SectionIdentifier, patterns
    ├── test_sanitizer_unit.py     # HTMLSanitizer methods
    ├── test_cleaning_unit.py      # TextCleaner methods
    ├── test_parser_unit.py        # SECFilingParser methods
    ├── test_extractor_unit.py     # SECSectionExtractor methods
    └── test_segmenter_unit.py     # RiskSegmenter methods
```

---

## Implementation Steps

### Step 1: Create Directory Structure
```
mkdir tests/unit
mkdir tests/unit/preprocessing
touch tests/unit/__init__.py
touch tests/unit/preprocessing/__init__.py
```

### Step 2: Create `tests/unit/conftest.py`

Lightweight fixtures (no file I/O):

```python
import pytest

@pytest.fixture
def sample_sic_html() -> str:
    """HTML with SIC code for testing _extract_sic_code."""
    return """STANDARD INDUSTRIAL CLASSIFICATION: SERVICES-PREPACKAGED SOFTWARE [7372]"""

@pytest.fixture
def sample_curly_quotes_text() -> str:
    """Text with curly quotes for _normalize_punctuation."""
    return "The company\u2019s revenue increased \u201csignificantly\u201d."

@pytest.fixture
def sample_page_artifacts_text() -> str:
    """Text with page numbers for _remove_page_artifacts."""
    return "Some content\n-12-\nMore content\nPage 45\n"

@pytest.fixture
def sample_invisible_chars_html() -> str:
    """HTML with invisible Unicode chars."""
    return "Text\u200bwith\ufeffzero-width\u00adchars"

@pytest.fixture
def sample_risk_paragraphs() -> str:
    """Multiple paragraphs for segmentation testing."""
    return """Competition Risk: We face intense competition.

Regulatory Risk: We are subject to various regulations.

Cybersecurity Risk: Security breaches could harm us."""

@pytest.fixture
def sample_nested_html() -> str:
    """Deeply nested HTML for flattening tests."""
    return "<div><div><div><p>Content</p></div></div></div>"
```

### Step 3: Create Unit Test Files

**Priority order** (based on dependency chain):

| Order | File | Tests For | Key Methods |
|-------|------|-----------|-------------|
| 1 | `test_constants_unit.py` | `constants.py` | SectionIdentifier, SECTION_PATTERNS |
| 2 | `test_sanitizer_unit.py` | `sanitizer.py` | _remove_edgar_header, _normalize_quotes |
| 3 | `test_cleaning_unit.py` | `cleaning.py` | _normalize_whitespace, _remove_page_artifacts |
| 4 | `test_parser_unit.py` | `parser.py` | _extract_sic_code, _validate_form_type |
| 5 | `test_extractor_unit.py` | `extractor.py` | _matches_section_pattern, _normalize_title |
| 6 | `test_segmenter_unit.py` | `segmenter.py` | _segment_by_headers, _filter_segments |

### Step 4: Key Test Cases Per File

#### test_constants_unit.py
- `TestSectionIdentifier`: enum values, uniqueness
- `TestSectionPatterns`: regex pattern matching for Item 1A, Item 7, etc.
- `TestElementTypeSets`: frozenset contents

#### test_sanitizer_unit.py
- `TestRemoveEdgarHeader`: SEC-HEADER removal
- `TestNormalizeQuotes`: curly quote → straight quote
- `TestRemoveInvisibleChars`: zero-width chars, BOM, soft hyphen
- `TestDecodeEntities`: &amp;, &nbsp;, numeric entities

#### test_cleaning_unit.py
- `TestNormalizeWhitespace`: collapse spaces, newlines
- `TestRemovePageArtifacts`: -12-, Page 45, TOC dots
- `TestNormalizePunctuation`: curly quotes, duplicate punctuation
- `TestRemoveHtmlTags`: simple tags, script removal, entity decode

#### test_parser_unit.py
- `TestExtractSicCode`: [7372] format, ASSIGNED-SIC format, None case
- `TestValidateFormType`: 10-K, 10K, 10-Q variations, invalid raises
- `TestFlattenHtmlNesting`: empty tag removal, single-child unwrap

#### test_extractor_unit.py
- `TestMatchesSectionPattern`: parametrized pattern matching
- `TestNormalizeTitle`: punctuation, lowercase, whitespace
- `TestExtractedSectionMethods`: __len__, get_tables, get_paragraphs

#### test_segmenter_unit.py
- `TestSegmentByHeaders`: bullet points, numbered items, ALL CAPS
- `TestFilterSegments`: min_length, header-only removal
- `TestIsNonRiskContent`: TOC detection, page references
- `TestSegmentRisksEdgeCases`: empty string, whitespace-only

---

## Files to Create

| File | Purpose |
|------|---------|
| `tests/unit/__init__.py` | Package marker |
| `tests/unit/conftest.py` | Mock fixtures |
| `tests/unit/preprocessing/__init__.py` | Package marker |
| `tests/unit/preprocessing/test_constants_unit.py` | Constants tests |
| `tests/unit/preprocessing/test_sanitizer_unit.py` | Sanitizer tests |
| `tests/unit/preprocessing/test_cleaning_unit.py` | Cleaning tests |
| `tests/unit/preprocessing/test_parser_unit.py` | Parser tests |
| `tests/unit/preprocessing/test_extractor_unit.py` | Extractor tests |
| `tests/unit/preprocessing/test_segmenter_unit.py` | Segmenter tests |

## Files to Read (for implementation reference)

| File | Line References |
|------|-----------------|
| `src/preprocessing/constants.py` | SectionIdentifier, SECTION_PATTERNS |
| `src/preprocessing/sanitizer.py` | Lines 189-403 (helper methods) |
| `src/preprocessing/cleaning.py` | Lines 123-318 (helper methods) |
| `src/preprocessing/parser.py` | Lines 467-686 (helper methods) |
| `src/preprocessing/extractor.py` | Lines 504-709 (helper methods) |
| `src/preprocessing/segmenter.py` | Lines 265-440 (helper methods) |

---

## Verification

```bash
# Run unit tests only
pytest tests/unit/ -v --tb=short

# Verify speed (<1 second)
pytest tests/unit/ -v --durations=0

# Verify isolation (no data directory needed)
pytest tests/unit/ -v --collect-only

# Run both suites independently
pytest tests/unit/ -v && pytest tests/preprocessing/ -v
```

---

## Phase 2: CI/CD Configuration

### Step 1: Create `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install ruff
      - run: ruff check .

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pytest pydantic pydantic-settings
      - run: pytest tests/unit/ -v --tb=short
```

### Step 2: Validate Workflow Syntax

```bash
# Install GitHub CLI if needed, then validate
gh workflow view ci.yml
```

---

## Phase 3: Run & Verify

### Local Verification

```bash
# 1. Run unit tests
pytest tests/unit/ -v --tb=short

# 2. Run linter
ruff check .

# 3. Verify speed
pytest tests/unit/ -v --durations=0
```

### CI Verification

```bash
# Commit and push to trigger CI
git add tests/unit/ .github/workflows/ci.yml
git commit -m "Add unit test infrastructure and CI"
git push
```

---

## Success Criteria

1. [ ] `pytest tests/unit/` runs in <1 second
2. [ ] No `pytest.skip()` calls referencing missing data
3. [ ] All unit tests pass with empty `data/` directory
4. [ ] Existing `tests/preprocessing/` tests still pass unchanged
5. [ ] `ruff check .` passes with no errors
6. [ ] CI workflow runs successfully on push
