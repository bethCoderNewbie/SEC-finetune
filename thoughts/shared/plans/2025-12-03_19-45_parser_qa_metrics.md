# SEC Filing Parser - QA Metrics & Validation

**Feature:** SEC Filing Parser (`src/preprocessing/parser.py`)
**Purpose:** Evaluate parsing correctness and downstream utility of extracted data

---

## 1. Validation Metrics Overview

### 1.1 Structural Integrity & Completeness

| Metric | Description | Target |
|--------|-------------|--------|
| **Element Recovery Rate** | (Extracted elements / Total DOM elements) * 100 | > 95% |
| **Tree Depth Verification** | Avg/Max depth vs raw HTML DOM | ±10% deviation |
| **Section Hit Rate** | % of standard regulatory sections detected | > 99% |

### 1.2 Semantic Extraction Accuracy

| Metric | Description | Target |
|--------|-------------|--------|
| **Text Cleanliness Score** | Ratio of alphanumeric to noise chars | > 98% clean |
| **Table Reconstruction Fidelity** | Cell-preservation rate | 100% |
| **Title/Header Classification** | Precision/Recall on element types | > 95% |

### 1.3 Performance & Stability

| Metric | Description | Target |
|--------|-------------|--------|
| **Throughput** | MB of HTML processed per second | > 1 MB/s |
| **Parsing Latency** | Time to parse standard 10-K | < 5 seconds |
| **Memory Footprint** | Peak RAM during largest file | < 2 GB |

### 1.4 Regression & Edge Cases

| Metric | Description | Target |
|--------|-------------|--------|
| **Error Rate** | % files returning ParseError or empty | < 1% |
| **Idempotency** | Same file produces identical output | 100% |

---

## 2. Summary Table for QA

| Metric Category | Key Metric | Target / Success Criteria |
|-----------------|------------|---------------------------|
| **Completeness** | Key Section Recall | > 99% (Must find Item 1, 1A, 7, 7A in 10-Ks) |
| **Accuracy** | Table Row Count Match | ±0% deviation from raw HTML |
| **Quality** | Boilerplate Reduction | < 1% HTML artifacts remaining |
| **Performance** | P95 Latency | < 5 seconds per document |

---

## 3. Test Implementation: Key Section Recall

### 3.1 Test File: `tests/test_parser_section_recall.py`

```python
"""
SEC Filing Parser - Key Section Recall Test Suite

Validates that the parser correctly identifies and extracts all required
regulatory sections from 10-K and 10-Q filings.

Target: > 99% recall on standard sections

Usage:
    pytest tests/test_parser_section_recall.py -v
    pytest tests/test_parser_section_recall.py -v --tb=short -k "test_10k"
"""

import pytest
from pathlib import Path
from typing import Dict, List, Set
import json
import time

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.preprocessing.parser import SECFilingParser, ParsedFiling
from src.preprocessing.extractor import SECSectionExtractor
from src.preprocessing.constants import SectionIdentifier
from src.config import settings


# ===========================
# Test Configuration
# ===========================

# Required sections for 10-K filings (must find ALL of these)
REQUIRED_10K_SECTIONS = {
    "part1item1": "Item 1. Business",
    "part1item1a": "Item 1A. Risk Factors",
    "part2item7": "Item 7. Management's Discussion and Analysis",
    "part2item7a": "Item 7A. Quantitative and Qualitative Disclosures",
}

# Required sections for 10-Q filings
REQUIRED_10Q_SECTIONS = {
    "part1item1": "Item 1. Financial Statements",
    "part1item2": "Item 2. Management's Discussion and Analysis",
    "part2item1a": "Item 1A. Risk Factors",
}

# Minimum section recall threshold
MIN_SECTION_RECALL = 0.99  # 99%


# ===========================
# Fixtures
# ===========================

@pytest.fixture(scope="module")
def parser():
    """Initialize parser once for all tests."""
    return SECFilingParser()


@pytest.fixture(scope="module")
def extractor():
    """Initialize extractor once for all tests."""
    return SECSectionExtractor()


@pytest.fixture(scope="module")
def test_10k_files() -> List[Path]:
    """Get all 10-K test files from raw data directory."""
    raw_dir = settings.paths.raw_data_dir
    files = list(raw_dir.glob("*10[Kk]*.html")) + list(raw_dir.glob("*10-[Kk]*.html"))
    return files


@pytest.fixture(scope="module")
def test_10q_files() -> List[Path]:
    """Get all 10-Q test files from raw data directory."""
    raw_dir = settings.paths.raw_data_dir
    files = list(raw_dir.glob("*10[Qq]*.html")) + list(raw_dir.glob("*10-[Qq]*.html"))
    return files


# ===========================
# Helper Functions
# ===========================

def check_section_presence(
    filing: ParsedFiling,
    required_sections: Dict[str, str]
) -> Dict[str, bool]:
    """
    Check which required sections are present in the parsed filing.

    Args:
        filing: Parsed SEC filing
        required_sections: Dict of section_id -> section_name

    Returns:
        Dict of section_id -> found (bool)
    """
    # Get all section names from the filing
    section_names = filing.get_section_names()
    section_names_lower = [s.lower() for s in section_names]

    results = {}
    for section_id, section_name in required_sections.items():
        # Check if section name (or key part) appears in any section
        key_phrase = section_name.lower()

        # Also check for variations (e.g., "Item 1A" vs "Item 1A.")
        found = any(
            key_phrase in s or
            section_id.replace("part1", "").replace("part2", "") in s.replace(" ", "").lower()
            for s in section_names_lower
        )
        results[section_id] = found

    return results


def calculate_recall(
    section_results: Dict[str, bool],
    required_sections: Dict[str, str]
) -> float:
    """
    Calculate section recall rate.

    Returns:
        Recall rate between 0.0 and 1.0
    """
    if not required_sections:
        return 1.0

    found_count = sum(1 for found in section_results.values() if found)
    return found_count / len(required_sections)


# ===========================
# Test Classes
# ===========================

class TestParserSectionRecall:
    """Test suite for Key Section Recall metric."""

    def test_parser_initialization(self, parser):
        """Verify parser initializes correctly."""
        assert parser is not None
        info = parser.get_parser_info()
        assert info['library'] == 'sec-parser'
        assert '10-K' in info['supported_forms']
        assert '10-Q' in info['supported_forms']

    @pytest.mark.parametrize("section_id,section_name", list(REQUIRED_10K_SECTIONS.items()))
    def test_10k_individual_sections(
        self,
        parser,
        test_10k_files,
        section_id,
        section_name
    ):
        """Test that each required 10-K section can be found."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available")

        # Test with first available file
        file_path = test_10k_files[0]
        filing = parser.parse_filing(file_path, form_type="10-K")

        section_results = check_section_presence(filing, {section_id: section_name})

        assert section_results[section_id], (
            f"Section '{section_name}' not found in {file_path.name}. "
            f"Available sections: {filing.get_section_names()}"
        )

    def test_10k_aggregate_recall(self, parser, test_10k_files):
        """Test aggregate section recall across all 10-K files."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available")

        all_recalls = []
        failed_files = []

        for file_path in test_10k_files:
            try:
                filing = parser.parse_filing(file_path, form_type="10-K")
                section_results = check_section_presence(filing, REQUIRED_10K_SECTIONS)
                recall = calculate_recall(section_results, REQUIRED_10K_SECTIONS)
                all_recalls.append(recall)

                if recall < 1.0:
                    missing = [k for k, v in section_results.items() if not v]
                    failed_files.append({
                        'file': file_path.name,
                        'recall': recall,
                        'missing': missing
                    })

            except Exception as e:
                failed_files.append({
                    'file': file_path.name,
                    'recall': 0.0,
                    'error': str(e)
                })

        avg_recall = sum(all_recalls) / len(all_recalls) if all_recalls else 0.0

        # Generate detailed failure report
        if failed_files:
            report = "\n".join([
                f"  - {f['file']}: recall={f.get('recall', 0):.2%}, "
                f"missing={f.get('missing', f.get('error', 'unknown'))}"
                for f in failed_files
            ])
            failure_msg = f"Average recall: {avg_recall:.2%}\nFailed files:\n{report}"
        else:
            failure_msg = f"Average recall: {avg_recall:.2%}"

        assert avg_recall >= MIN_SECTION_RECALL, (
            f"Section recall {avg_recall:.2%} below threshold {MIN_SECTION_RECALL:.0%}.\n"
            f"{failure_msg}"
        )

    @pytest.mark.parametrize("section_id,section_name", list(REQUIRED_10Q_SECTIONS.items()))
    def test_10q_individual_sections(
        self,
        parser,
        test_10q_files,
        section_id,
        section_name
    ):
        """Test that each required 10-Q section can be found."""
        if not test_10q_files:
            pytest.skip("No 10-Q test files available")

        file_path = test_10q_files[0]
        filing = parser.parse_filing(file_path, form_type="10-Q")

        section_results = check_section_presence(filing, {section_id: section_name})

        assert section_results[section_id], (
            f"Section '{section_name}' not found in {file_path.name}. "
            f"Available sections: {filing.get_section_names()}"
        )


class TestParserPerformance:
    """Test suite for parser performance metrics."""

    def test_parsing_latency(self, parser, test_10k_files):
        """Test that parsing completes within latency threshold."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available")

        MAX_LATENCY_SECONDS = 5.0
        file_path = test_10k_files[0]

        start_time = time.time()
        filing = parser.parse_filing(file_path, form_type="10-K")
        elapsed = time.time() - start_time

        assert elapsed < MAX_LATENCY_SECONDS, (
            f"Parsing took {elapsed:.2f}s, exceeds threshold of {MAX_LATENCY_SECONDS}s"
        )
        assert len(filing) > 0, "Parser returned empty result"

    def test_idempotency(self, parser, test_10k_files):
        """Test that parsing the same file twice produces identical results."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available")

        file_path = test_10k_files[0]

        # Parse twice
        filing1 = parser.parse_filing(file_path, form_type="10-K")
        filing2 = parser.parse_filing(file_path, form_type="10-K")

        # Compare key attributes
        assert len(filing1) == len(filing2), "Element count mismatch"
        assert filing1.get_section_names() == filing2.get_section_names(), "Section names mismatch"
        assert filing1.metadata['num_sections'] == filing2.metadata['num_sections'], "Section count mismatch"


class TestParserEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_empty_file_handling(self, parser, tmp_path):
        """Test graceful handling of empty files."""
        empty_file = tmp_path / "empty.html"
        empty_file.write_text("")

        with pytest.raises(ValueError, match="empty"):
            parser.parse_filing(empty_file, form_type="10-K")

    def test_invalid_form_type(self, parser, test_10k_files):
        """Test handling of invalid form type."""
        if not test_10k_files:
            pytest.skip("No test files available")

        with pytest.raises(ValueError, match="Unsupported form type"):
            parser.parse_filing(test_10k_files[0], form_type="INVALID")

    def test_nonexistent_file(self, parser):
        """Test handling of nonexistent file."""
        with pytest.raises(FileNotFoundError):
            parser.parse_filing("nonexistent_file.html", form_type="10-K")


# ===========================
# Metrics Report Generation
# ===========================

class TestMetricsReport:
    """Generate a metrics report for QA review."""

    def test_generate_metrics_report(self, parser, test_10k_files, test_10q_files, tmp_path):
        """Generate comprehensive metrics report."""
        report = {
            "test_date": str(Path(__file__).stat().st_mtime),
            "parser_version": parser.get_parser_info().get('version', 'unknown'),
            "metrics": {}
        }

        # 10-K Metrics
        if test_10k_files:
            recalls = []
            latencies = []

            for file_path in test_10k_files[:10]:  # Limit for speed
                try:
                    start = time.time()
                    filing = parser.parse_filing(file_path, form_type="10-K")
                    latency = time.time() - start
                    latencies.append(latency)

                    section_results = check_section_presence(filing, REQUIRED_10K_SECTIONS)
                    recall = calculate_recall(section_results, REQUIRED_10K_SECTIONS)
                    recalls.append(recall)
                except Exception:
                    recalls.append(0.0)

            report["metrics"]["10k"] = {
                "files_tested": len(test_10k_files),
                "avg_section_recall": sum(recalls) / len(recalls) if recalls else 0,
                "min_section_recall": min(recalls) if recalls else 0,
                "avg_latency_seconds": sum(latencies) / len(latencies) if latencies else 0,
                "max_latency_seconds": max(latencies) if latencies else 0,
            }

        # 10-Q Metrics
        if test_10q_files:
            recalls = []
            for file_path in test_10q_files[:10]:
                try:
                    filing = parser.parse_filing(file_path, form_type="10-Q")
                    section_results = check_section_presence(filing, REQUIRED_10Q_SECTIONS)
                    recall = calculate_recall(section_results, REQUIRED_10Q_SECTIONS)
                    recalls.append(recall)
                except Exception:
                    recalls.append(0.0)

            report["metrics"]["10q"] = {
                "files_tested": len(test_10q_files),
                "avg_section_recall": sum(recalls) / len(recalls) if recalls else 0,
            }

        # Save report
        report_path = tmp_path / "parser_metrics_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n{'='*60}")
        print("PARSER METRICS REPORT")
        print(f"{'='*60}")
        print(json.dumps(report, indent=2))
        print(f"{'='*60}")

        # Assert basic validity
        assert report["metrics"], "No metrics generated"


# ===========================
# Run Configuration
# ===========================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
```

---

## 4. Running the Tests

### 4.1 Basic Execution

```bash
# Run all parser QA tests
pytest tests/test_parser_section_recall.py -v

# Run only section recall tests
pytest tests/test_parser_section_recall.py -v -k "section"

# Run with detailed output on failures
pytest tests/test_parser_section_recall.py -v --tb=long

# Generate coverage report
pytest tests/test_parser_section_recall.py --cov=src/preprocessing --cov-report=html
```

### 4.2 CI/CD Integration

```yaml
# .github/workflows/qa.yml
name: Parser QA Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -e ".[test]"
      - run: pytest tests/test_parser_section_recall.py -v --tb=short
```

---

## 5. Expected Output

### 5.1 Passing Tests

```
tests/test_parser_section_recall.py::TestParserSectionRecall::test_parser_initialization PASSED
tests/test_parser_section_recall.py::TestParserSectionRecall::test_10k_individual_sections[part1item1-Item 1. Business] PASSED
tests/test_parser_section_recall.py::TestParserSectionRecall::test_10k_individual_sections[part1item1a-Item 1A. Risk Factors] PASSED
tests/test_parser_section_recall.py::TestParserSectionRecall::test_10k_individual_sections[part2item7-Item 7. MD&A] PASSED
tests/test_parser_section_recall.py::TestParserSectionRecall::test_10k_aggregate_recall PASSED
tests/test_parser_section_recall.py::TestParserPerformance::test_parsing_latency PASSED
tests/test_parser_section_recall.py::TestParserPerformance::test_idempotency PASSED

============ 7 passed in 12.34s ============
```

### 5.2 Metrics Report Sample

```json
{
  "parser_version": "0.54.0",
  "metrics": {
    "10k": {
      "files_tested": 5,
      "avg_section_recall": 1.0,
      "min_section_recall": 1.0,
      "avg_latency_seconds": 2.34,
      "max_latency_seconds": 4.12
    }
  }
}
```

---

## 6. QA Evaluation Template

# Metrics Evaluation: SEC Filing Parser

**Date:** {{Current Date}}
**Evaluator:** QA Team
**Test Run ID:** {{Commit Hash}}
**Status:** [PASS / FAIL / WARN]

## Executive Summary
* **Verdict:** [Ready to ship / Needs Fixes]
* **Key Findings:** [e.g., Section recall at 100%, latency within threshold]

## Success Criteria Results

| Metric Category | Metric Name | Baseline | Target | **Actual** | Status |
|-----------------|-------------|----------|--------|------------|--------|
| **Completeness** | Key Section Recall (10-K) | 95% | > 99% | **100%** | PASS |
| **Completeness** | Key Section Recall (10-Q) | 95% | > 99% | **100%** | PASS |
| **Performance** | P95 Latency | 8s | < 5s | **3.2s** | PASS |
| **Performance** | Idempotency | 100% | 100% | **100%** | PASS |
| **Stability** | Error Rate | 5% | < 1% | **0%** | PASS |

## Detailed Analysis

### A. Section Recall
* **Observation:** All required sections detected in test filings
* **Evidence:**
    * Item 1A found: 100% (5/5 files)
    * Item 7 found: 100% (5/5 files)

### B. Edge Cases
* **Empty File:** Handled with ValueError (expected)
* **Invalid Form Type:** Handled with ValueError (expected)

## Next Steps
* [ ] Add more test filings for edge case coverage
* [ ] Benchmark against older filings (pre-2015)
* [ ] Monitor production error rates
