---
title: Parser and Test Unit Analysis Using Real Data
date: 2025-12-15T19:22:00
researcher: Claude (Opus 4.5)
git_commit: 1843e0d
git_branch: main
status: completed
---

# Parser and Test Unit Analysis Using Real Data

## Executive Summary

This research analyzes `src/preprocessing/parser.py` and its test suite `tests/preprocessing/test_parser_section_recall.py` using real SEC 10-K filing data. Key findings reveal a significant performance gap between test thresholds and real-world parsing times, along with architectural insights into how sec-parser classifies section elements.

## Files Analyzed

| File | Purpose | Lines |
|------|---------|-------|
| `src/preprocessing/parser.py` | SEC Filing Parser using sec-parser library | 789 |
| `tests/preprocessing/test_parser_section_recall.py` | Key Section Recall Test Suite | 662 |
| `tests/conftest.py` | Shared pytest fixtures | 861 |

## Real Data Characteristics

### Available Test Data
- **Total 10-K files**: 887 HTML files
- **Size range**: 6.35 MB to 68.25 MB
- **10-Q files**: None available (tests skip 10-Q)

### Sample File Sizes (sorted smallest to largest)
| File | Size |
|------|------|
| COST_10K_2023.html | 6.35 MB |
| ROST_10K_2023.html | 6.80 MB |
| INTC_10K_2021.html | 60.31 MB |
| JPM_10K_2021.html | 67.95 MB |
| WELL_10K_2025.html | 68.25 MB |

## Key Findings

### 1. Performance Gap: Test Threshold vs Reality

**Test threshold defined**: `MAX_LATENCY_SECONDS = 5.0` (line 68)

**Actual parsing time** (COST_10K_2023.html, 6.35 MB - smallest file):
- **Measured: 34.52 seconds**
- **7x over threshold** even on the smallest file

This means **100% of test files will fail the latency threshold** when using real data.

### 2. Section Classification Architecture

The parser correctly identifies all required sections, but sec-parser classifies them differently:

**TopSectionTitle** (returned by `get_section_names()`):
- Item 1 Business
- Item 2 Properties
- Item 3 Legal Proceedings
- Item 4 Mine Safety
- Item 5 Market for Stock
- Item 6 Reserved

**TitleElement** (NOT returned by `get_section_names()`):
- Item 1A Risk Factors
- Item 7 MD&A
- Item 7A Quantitative Disclosures
- Item 8 Financial Statements
- Item 9, 9A, 9B, 9C
- Items 10-16

**Implication**: The test's `check_section_presence()` function (lines 75-139) correctly searches ALL title-like elements, not just `TopSectionTitle`. This is a **critical design decision** that allows 100% recall despite sec-parser's classification.

### 3. Section Recall Results

On COST_10K_2023.html:
- **Recall: 100%** (4/4 required sections found)
- Item 1. Business: FOUND (TopSectionTitle)
- Item 1A. Risk Factors: FOUND (TitleElement)
- Item 7. MD&A: FOUND (TitleElement)
- Item 7A. Quantitative: FOUND (TitleElement)

### 4. Element Type Distribution (COST_10K_2023.html)

| Element Type | Count |
|--------------|-------|
| TableElement | 667 |
| TextElement | 347 |
| PageHeaderElement | 340 |
| EmptyElement | 339 |
| TitleElement | 198 |
| PageNumberElement | 134 |
| IntroductorySectionElement | 68 |
| SupplementaryText | 17 |
| TopSectionTitle | 8 |

### 5. Test Suite Structure

**Test Classes and Coverage:**

| Class | Tests | Uses Real Data | Status |
|-------|-------|----------------|--------|
| TestParserInitialization | 3 | No | PASS |
| TestParserSectionRecall | 6 | Yes (10-K/10-Q) | Times out |
| TestParserPerformance | 3 | Yes | Times out |
| TestParserEdgeCases | 5 | No (tmp_path) | PASS |
| TestParserMetadata | 3 | Yes | Times out |
| TestMetricsReport | 1 | Yes | Times out |

**Tests that pass without real data:**
- All 3 initialization tests
- All 5 edge case tests (use mock/minimal HTML)

### 6. Test Fixture Discovery Logic

The conftest.py discovers test files via patterns (lines 53-69):
```python
patterns = ["*10[Kk]*.html", "*10-[Kk]*.html", "*_10K_*.html", "*_10-K_*.html"]
```

This matches all 887 files in `data/raw/`.

## Working Paths vs Broken Paths

### Working
1. **Parser initialization**: `SECFilingParser()` works correctly
2. **Section recall logic**: `check_section_presence()` properly handles multiple element types
3. **Metadata extraction**: SIC code, company name, CIK all extract correctly
4. **Edge case handling**: Empty files, invalid types, nested HTML handled gracefully

### Broken/Problematic
1. **Latency threshold** (`parser.py:68`): 5-second threshold is unrealistic
   - Even smallest file (6.35 MB) takes 34+ seconds
   - Auto-scaling recursion limit (`parser.py:354-358`) helps but doesn't solve timing

2. **Test timeout** in CI: Real data tests timeout during pytest execution
   - Batch tests at line 404-431 are particularly problematic

## Recommendations

### Immediate Actions
1. **Adjust latency threshold** to realistic values:
   - Small files (<10 MB): ~60 seconds
   - Medium files (10-30 MB): ~120 seconds
   - Large files (>30 MB): ~300 seconds

2. **Add file size limits** in test fixtures:
   ```python
   # Filter to files under 10MB for latency tests
   files = [f for f in files if f.stat().st_size < 10 * 1024 * 1024]
   ```

3. **Split test modes**:
   - Quick mode: Use smallest files only
   - Full mode: Test all files (CI-only, with extended timeout)

### Architecture Improvements
1. **Cache parsed results** to avoid re-parsing in multiple tests
2. **Add progress callbacks** for long-running parses
3. **Document the TopSectionTitle vs TitleElement behavior** in parser.py docstring

## Verification Commands

```bash
# Run tests that pass with real data
pytest tests/preprocessing/test_parser_section_recall.py::TestParserInitialization -v
pytest tests/preprocessing/test_parser_section_recall.py::TestParserEdgeCases -v

# Test single file parsing (expect ~35s for smallest)
python -c "
from src.preprocessing.parser import SECFilingParser
from pathlib import Path
import time
p = SECFilingParser()
start = time.time()
f = p.parse_filing('data/raw/COST_10K_2023.html', form_type='10-K', quiet=True)
print(f'Time: {time.time()-start:.2f}s, Elements: {len(f)}')
"
```

## Appendix: Test Configuration Constants

From `test_parser_section_recall.py`:

```python
REQUIRED_10K_SECTIONS = {
    "part1item1": "Item 1. Business",
    "part1item1a": "Item 1A. Risk Factors",
    "part2item7": "Item 7. Management's Discussion and Analysis",
    "part2item7a": "Item 7A. Quantitative and Qualitative Disclosures",
}

MIN_SECTION_RECALL = 0.99  # 99%
MAX_LATENCY_SECONDS = 5.0  # UNREALISTIC for real data
```
