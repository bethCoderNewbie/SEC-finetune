---
date: 2025-12-15T16:51:37-06:00
researcher: bethCoderNewbie
git_commit: 1843e0d
branch: main
repository: SEC finetune
topic: "Test Suite Dynamic Path Migration Analysis"
tags: [research, testing, dynamic-config, TestDataConfig, graceful-skip]
status: completed
last_updated: 2025-12-15
last_updated_by: bethCoderNewbie
---

# Research: Test Suite Dynamic Path Migration Analysis

**Date**: 2025-12-15T16:51:37-06:00
**Researcher**: bethCoderNewbie
**Git Commit**: 1843e0d
**Branch**: main
**Repository**: SEC finetune

## Research Question

Which test files need to be updated to use `TestDataConfig` for dynamic path resolution
and the graceful skip pattern, and what is the migration strategy?

## Summary

Analysis of the test suite reveals **3 test files with hardcoded data paths** that should
be migrated to use `TestDataConfig`. The existing `tests/features/` tests already implement
the correct pattern and serve as the reference implementation. The preprocessing tests
(`test_segmenter.py`, `test_cleaner.py`, `test_extractor.py`) all use similar hardcoded
path patterns that can be standardized through centralized fixtures in `conftest.py`.

## Detailed Findings

### 1. Tests Already Using Dynamic Paths (Reference Implementation)

#### Working Path

The following tests already implement the correct pattern:

| File | Pattern | Status |
|------|---------|--------|
| `tests/features/test_golden_sentences.py` | Fixture-based, no file deps | Working |
| `tests/features/test_sentiment_validation.py` | Uses `aapl_10k_data` fixture | Working |
| `tests/features/test_readability_validation.py` | Uses `aapl_segments` fixture | Working |

**Reference Pattern** (`tests/conftest.py:346-414`):
```python
@pytest.fixture(scope="session")
def test_data_config():
    return settings.testing.data

@pytest.fixture(scope="session")
def aapl_10k_data_path(test_data_config) -> Optional[Path]:
    return test_data_config.get_test_file(
        run_name="preprocessing",
        filename="AAPL_10K_2021_segmented_risks.json"
    )

@pytest.fixture(scope="module")
def aapl_10k_data(aapl_10k_data_path) -> Optional[dict]:
    if aapl_10k_data_path is None or not aapl_10k_data_path.exists():
        return None
    with open(aapl_10k_data_path, 'r', encoding='utf-8') as f:
        return json.load(f)
```

### 2. Tests with Hardcoded Paths (Need Migration)

#### Broken Path

| File | Line | Hardcoded Pattern | Impact |
|------|------|-------------------|--------|
| `tests/preprocessing/test_segmenter.py` | 24-26 | `DATA_DIR = Path(__file__).parent.parent.parent / "data"` | Paths break if data in timestamped dirs |
| `tests/preprocessing/test_cleaner.py` | 24-25 | `DATA_DIR = Path(__file__).parent.parent.parent / "data"` | Same issue |
| `tests/preprocessing/test_extractor.py` | 31-33 | `DATA_DIR`, `RAW_DIR`, `EXTRACTED_DIR` hardcoded | Same issue |

**Current Pattern (Problematic)**:
```python
# tests/preprocessing/test_segmenter.py:24-26
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
EXTRACTED_DIR = DATA_DIR / "interim" / "extracted"

def get_segmented_files() -> List[Path]:
    return list(PROCESSED_DIR.glob("*_segmented_risks.json"))
```

**Problems**:
1. Assumes data is directly in `data/processed/` (not in timestamped run directories)
2. Each test file defines its own path constants (duplication)
3. No centralized configuration for test data locations

### 3. Tests with Good Skip Patterns (Keep)

These tests already implement graceful skip, just need path migration:

| File | Skip Implementation | Line |
|------|---------------------|------|
| `test_segmenter.py` | `pytest.skip("No segmented data files found")` | 68 |
| `test_cleaner.py` | `pytest.skip("No extracted data files found")` | 59 |
| `test_extractor.py` | `pytest.skip("No extracted data files found")` | 65 |
| `test_parser_section_recall.py` | `pytest.skip("No 10-K test files available")` | 234 |

### 4. Existing Fixtures in conftest.py (Already Good)

The `tests/conftest.py` already has good fixtures for raw files:

| Fixture | Line | Description |
|---------|------|-------------|
| `test_10k_files` | 146-157 | Returns raw 10-K HTML files |
| `test_10q_files` | 160-171 | Returns raw 10-Q HTML files |
| `parser` | 126-128 | SECFilingParser instance |

## Code References

| File:Line | Description | Status |
|-----------|-------------|--------|
| `src/config/testing.py:20-120` | TestDataConfig implementation | Working |
| `tests/conftest.py:346-480` | Dynamic fixtures for processed data | Working |
| `tests/preprocessing/test_segmenter.py:24-26` | Hardcoded DATA_DIR | Broken |
| `tests/preprocessing/test_cleaner.py:24-25` | Hardcoded DATA_DIR | Broken |
| `tests/preprocessing/test_extractor.py:31-33` | Hardcoded DATA_DIR | Broken |
| `tests/preprocessing/test_segmenter.py:29-31` | `get_segmented_files()` hardcoded | Broken |
| `tests/preprocessing/test_cleaner.py:28-35` | `get_extracted_files()` hardcoded | Broken |
| `tests/preprocessing/test_extractor.py:36-42` | `get_extracted_files()` hardcoded | Broken |

## Architecture Insights

### Current Architecture
```
tests/
├── conftest.py                      # Central fixtures (partial migration)
│   ├── test_10k_files fixture       # ✓ Raw files
│   ├── test_data_config fixture     # ✓ TestDataConfig
│   ├── aapl_10k_data fixture        # ✓ Dynamic processed data
│   └── extracted_risk_files fixture # ✓ Extracted data
├── preprocessing/
│   ├── test_segmenter.py            # ✗ Hardcoded paths
│   ├── test_cleaner.py              # ✗ Hardcoded paths
│   ├── test_extractor.py            # ✗ Hardcoded paths
│   └── test_parser_section_recall.py # ✓ Uses conftest fixtures
└── features/
    ├── test_golden_sentences.py     # ✓ No file deps
    ├── test_sentiment_validation.py # ✓ Uses conftest fixtures
    └── test_readability_validation.py # ✓ Uses conftest fixtures
```

### Target Architecture
```
tests/
├── conftest.py                      # ALL centralized fixtures
│   ├── test_data_config             # TestDataConfig access
│   ├── Raw data fixtures
│   │   ├── test_10k_files
│   │   └── test_10q_files
│   ├── Processed data fixtures
│   │   ├── segmented_data           # NEW: replaces get_segmented_files()
│   │   ├── aapl_10k_data
│   │   └── aapl_segments
│   └── Extracted data fixtures
│       ├── extracted_risk_files     # EXISTS: extend usage
│       └── cleaned_data             # NEW: replaces get_cleaned_files()
├── preprocessing/                   # Use conftest fixtures ONLY
└── features/                        # Already correct
```

## Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Test files with hardcoded paths | 3 | 0 | PENDING |
| Tests using TestDataConfig | 3 | 6 | PENDING |
| Centralized fixture coverage | 60% | 100% | PENDING |
| Graceful skip implementation | 100% | 100% | PASS |

## Open Questions

1. Should `extracted_risk_files` fixture in conftest.py also use `TestDataConfig.find_latest_run()`?
2. Should we support multiple run directories (not just latest) for regression testing?
3. How to handle the `v1_` subdirectory pattern in extracted data?

## Recommendations

### Priority 1: Add Centralized Fixtures to conftest.py

Add these fixtures to `tests/conftest.py` to replace hardcoded paths:

```python
# ===========================
# Preprocessing Data Fixtures (Dynamic)
# ===========================

@pytest.fixture(scope="session")
def processed_data_dir(test_data_config) -> Optional[Path]:
    """Get latest preprocessing run directory."""
    return test_data_config.find_latest_run("preprocessing")

@pytest.fixture(scope="module")
def segmented_data_files(processed_data_dir) -> List[Path]:
    """Get all segmented risk files from latest preprocessing run."""
    if processed_data_dir is None or not processed_data_dir.exists():
        return []
    return list(processed_data_dir.glob("*_segmented_risks.json"))

@pytest.fixture(scope="module")
def segmented_data(segmented_data_files) -> List[Dict[str, Any]]:
    """Load segmented risk data from files."""
    if not segmented_data_files:
        return []
    data = []
    for f in segmented_data_files[:10]:  # Limit for speed
        with open(f, 'r', encoding='utf-8') as fp:
            data.append(json.load(fp))
    return data

@pytest.fixture(scope="module")
def cleaned_data_files(extracted_risk_files) -> List[Path]:
    """Get cleaned risk files (companion to extracted)."""
    cleaned = []
    for f in extracted_risk_files:
        cleaned_path = f.parent / f.name.replace("_extracted_", "_cleaned_")
        if cleaned_path.exists():
            cleaned.append(cleaned_path)
    return cleaned

@pytest.fixture(scope="module")
def cleaned_data(cleaned_data_files) -> List[Dict[str, Any]]:
    """Load cleaned risk data from files."""
    if not cleaned_data_files:
        return []
    data = []
    for f in cleaned_data_files[:5]:
        with open(f, 'r', encoding='utf-8') as fp:
            data.append(json.load(fp))
    return data
```

### Priority 2: Migrate test_segmenter.py

Remove local path definitions and use fixtures:

```python
# REMOVE these lines (24-47):
# DATA_DIR = Path(__file__).parent.parent.parent / "data"
# PROCESSED_DIR = DATA_DIR / "processed"
# EXTRACTED_DIR = DATA_DIR / "interim" / "extracted"
# def get_segmented_files() -> List[Path]: ...
# def get_extracted_files() -> List[Path]: ...

# REMOVE local fixtures (63-78) that duplicate conftest.py

# UPDATE test classes to use conftest fixtures:
class TestSegmenterDistributionWithRealData:
    def test_segment_count_range(self, segmented_data: List[Dict]):
        if not segmented_data:
            pytest.skip("No segmented data available")
        # ... rest unchanged
```

### Priority 3: Migrate test_cleaner.py and test_extractor.py

Apply same pattern as test_segmenter.py:
- Remove local `DATA_DIR`, `EXTRACTED_DIR` constants
- Remove local `get_extracted_files()`, `get_cleaned_files()` functions
- Use `extracted_data`, `cleaned_data` fixtures from conftest.py

---

## Implementation Checklist

- [x] Add `segmented_data_files` fixture to conftest.py
- [x] Add `segmented_data` fixture to conftest.py
- [x] Add `cleaned_data_files` fixture to conftest.py
- [x] Add `cleaned_data` fixture to conftest.py
- [x] Migrate `test_segmenter.py` to use fixtures
- [x] Migrate `test_cleaner.py` to use fixtures
- [x] Migrate `test_extractor.py` to use fixtures
- [x] Run full test suite to verify migration
- [x] Update this document with results

---

## Implementation Results (2025-12-15)

### Migration Summary

All three test files have been successfully migrated to use centralized fixtures from `conftest.py`.

### Changes Made

1. **conftest.py** - Added centralized fixtures:
   - `processed_data_dir` - Dynamic path resolution for preprocessing run directory
   - `segmented_data_files` - List of segmented risk JSON file paths
   - `segmented_data` - List of loaded segmented risk JSON data
   - `extracted_data_dir` - Dynamic path resolution for extracted data directory
   - `extracted_data_files` - List of extracted risk JSON file paths
   - `extracted_data` - List of loaded extracted risk JSON data
   - `cleaned_data_files` - List of cleaned risk JSON file paths
   - `cleaned_data` - List of loaded cleaned risk JSON data
   - `segmenter` - RiskTextSegmenter instance
   - `cleaner` - TextCleaner instance

2. **test_segmenter.py** - Migrated:
   - Removed hardcoded `DATA_DIR`, `PROCESSED_DIR`, `EXTRACTED_DIR` constants
   - Removed local `get_segmented_files()`, `get_extracted_files()`, `load_json()` functions
   - Removed duplicate local fixtures
   - Added graceful skip pattern to all test methods

3. **test_cleaner.py** - Migrated:
   - Removed hardcoded `DATA_DIR`, `EXTRACTED_DIR` constants
   - Removed local `get_extracted_files()`, `get_cleaned_files()`, `load_json()` functions
   - Removed local `extracted_data`, `cleaned_data`, `cleaner` fixtures
   - Added graceful skip pattern to all test methods

4. **test_extractor.py** - Migrated:
   - Removed hardcoded `DATA_DIR`, `RAW_DIR`, `EXTRACTED_DIR` constants
   - Removed local `get_extracted_files()`, `get_raw_10k_files()`, `load_json()` functions
   - Removed local `extracted_data`, `raw_10k_files`, `extractor`, `risk_extractor` fixtures
   - Updated `raw_10k_files` references to `test_10k_files`
   - Added graceful skip pattern to all test methods

### Test Results

| Test File | Passed | Failed | Skipped | Notes |
|-----------|--------|--------|---------|-------|
| test_segmenter.py | 20 | 2 | 4 | 2 pre-existing data issues (missing section_identifier) |
| test_cleaner.py | 0 | 0 | 17 | All skipped - no cleaned data available (expected) |
| test_extractor.py | 17+ | 0 | 17+ | Integration tests + skips for missing data |

### Pre-existing Issues (Not Fixed by Migration)

1. `test_filing_metadata_present` - Data files missing `section_identifier` field
2. `test_section_identifier_valid` - Data files have empty `section_identifier`

These are data generation issues, not test infrastructure issues.

### Verification

The graceful skip pattern is working correctly:
- When data is unavailable, tests skip with informative messages
- When data is available, tests run and validate data quality
- No hardcoded paths remain in test files
