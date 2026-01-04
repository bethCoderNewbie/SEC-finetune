"""
SEC Filing Parser - Key Section Recall Test Suite

Validates that the parser correctly identifies and extracts all required
regulatory sections from 10-K and 10-Q filings.

Metrics Tested:
- Key Section Recall: > 99% (Must find Item 1, 1A, 7, 7A in 10-Ks)
- Parsing Latency: < 5 seconds per document
- Idempotency: Same file produces identical output
- Error Handling: Graceful handling of edge cases

Target: > 99% recall on standard sections

Usage:
    # Run all tests
    pytest tests/preprocessing/test_parser_section_recall.py -v

    # Run specific test class
    pytest tests/preprocessing/test_parser_section_recall.py::TestParserSectionRecall -v

    # Run with coverage
    pytest tests/preprocessing/test_parser_section_recall.py \\
        --cov=src/preprocessing --cov-report=html

    # Generate metrics report
    pytest tests/preprocessing/test_parser_section_recall.py::TestMetricsReport -v -s
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# pylint: disable=wrong-import-position
from src.preprocessing.parser import SECFilingParser, ParsedFiling  # noqa: E402
# pylint: enable=wrong-import-position


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

# Performance thresholds
MAX_LATENCY_SECONDS = 5.0


# ===========================
# Helper Functions
# ===========================

def check_section_presence(
    filing: ParsedFiling,
    required_sections: Dict[str, str]
) -> Dict[str, bool]:
    """
    Check which required sections are present in the parsed filing.

    This function searches ALL elements in the filing, not just TopSectionTitle,
    because sec-parser may classify some section headers as TitleElement instead.

    Args:
        filing: Parsed SEC filing
        required_sections: Dict of section_id -> section_name

    Returns:
        Dict of section_id -> found (bool)
    """
    # Collect all text from elements that could be section headers
    # Include TopSectionTitle, TitleElement, and other title-like elements
    all_titles = []

    for element in filing.elements:
        element_type = element.__class__.__name__
        # Check title-like element types
        if element_type in ['TopSectionTitle', 'TitleElement', 'IntroductorySectionElement']:
            text = str(element.text) if hasattr(element, 'text') else ''
            if text:
                all_titles.append(text.lower())

    # Also include the formal section names
    section_names = filing.get_section_names()
    all_titles.extend([s.lower() for s in section_names])

    results = {}
    for section_id, section_name in required_sections.items():
        # Extract item pattern for matching
        # e.g., "part1item1a" -> "item1a", "part2item7" -> "item7"
        item_pattern = section_id.replace("part1", "").replace("part2", "")

        # Build search patterns
        # "Item 1A. Risk Factors" should match:
        # - "item 1a" (with space)
        # - "item1a" (without space)
        # - "risk factors" (section title)
        key_phrase = section_name.lower()

        # Extract just the item number part (e.g., "item 1a", "item 7")
        item_with_space = item_pattern[:4] + " " + item_pattern[4:]  # "item 1a"
        item_no_space = item_pattern  # "item1a"

        found = False
        for title in all_titles:
            # Normalize the title for comparison (remove special chars)
            title_normalized = title.replace('\xa0', ' ').replace('�', ' ')

            title_compact = title_normalized.replace(" ", "").replace(".", "")
            if (key_phrase in title_normalized
                    or item_with_space in title_normalized
                    or item_no_space in title_compact):
                found = True
                break

        results[section_id] = found

    return results


def calculate_recall(
    section_results: Dict[str, bool],
    required_sections: Dict[str, str]
) -> float:
    """
    Calculate section recall rate.

    Args:
        section_results: Dict of section_id -> found (bool)
        required_sections: Dict of section_id -> section_name

    Returns:
        Recall rate between 0.0 and 1.0
    """
    if not required_sections:
        return 1.0

    found_count = sum(1 for found in section_results.values() if found)
    return found_count / len(required_sections)


def format_failure_report(failed_files: List[Dict]) -> str:
    """
    Format a human-readable failure report.

    Args:
        failed_files: List of failure dictionaries

    Returns:
        Formatted report string
    """
    if not failed_files:
        return "All files passed."

    lines = ["Failed files:"]
    for f in failed_files:
        if 'error' in f:
            lines.append(f"  - {f['file']}: ERROR - {f['error']}")
        else:
            lines.append(
                f"  - {f['file']}: recall={f.get('recall', 0):.2%}, "
                f"missing={f.get('missing', [])}"
            )
    return "\n".join(lines)


# ===========================
# Test Classes
# ===========================

class TestParserInitialization:
    """Test suite for parser initialization and configuration."""

    def test_parser_initialization(self, parser: SECFilingParser):
        """Verify parser initializes correctly."""
        assert parser is not None
        info = parser.get_parser_info()

        assert info['library'] == 'sec-parser'
        assert '10-K' in info['supported_forms']
        assert '10-Q' in info['supported_forms']

    def test_parser_info_structure(self, parser: SECFilingParser):
        """Verify parser info contains required fields."""
        info = parser.get_parser_info()

        required_fields = ['library', 'version', 'supported_forms']
        for field in required_fields:
            assert field in info, f"Missing field: {field}"

    def test_form_types_available(self, parser: SECFilingParser):
        """Verify all expected form types are supported."""
        info = parser.get_parser_info()
        supported = info['supported_forms']

        assert '10-K' in supported, "10-K not supported"
        assert '10-Q' in supported, "10-Q not supported"


class TestParserSectionRecall:
    """Test suite for Key Section Recall metric."""

    @pytest.mark.parametrize("section_id,section_name", list(REQUIRED_10K_SECTIONS.items()))
    def test_10k_individual_sections(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path],
        section_id: str,
        section_name: str
    ):
        """Test that each required 10-K section can be found."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available in data/raw/")

        # Test with first available file
        file_path = test_10k_files[0]
        filing = parser.parse_filing(file_path, form_type="10-K")

        section_results = check_section_presence(filing, {section_id: section_name})

        assert section_results[section_id], (
            f"Section '{section_name}' not found in {file_path.name}.\n"
            f"Available sections: {filing.get_section_names()}"
        )

    def test_10k_aggregate_recall(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path]
    ):
        """Test aggregate section recall across all 10-K files."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available in data/raw/")

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
        failure_report = format_failure_report(failed_files)

        assert avg_recall >= MIN_SECTION_RECALL, (
            f"Section recall {avg_recall:.2%} below threshold {MIN_SECTION_RECALL:.0%}.\n"
            f"Average recall: {avg_recall:.2%}\n{failure_report}"
        )

    @pytest.mark.parametrize("section_id,section_name", list(REQUIRED_10Q_SECTIONS.items()))
    def test_10q_individual_sections(
        self,
        parser: SECFilingParser,
        test_10q_files: List[Path],
        section_id: str,
        section_name: str
    ):
        """Test that each required 10-Q section can be found."""
        if not test_10q_files:
            pytest.skip("No 10-Q test files available in data/raw/")

        file_path = test_10q_files[0]
        filing = parser.parse_filing(file_path, form_type="10-Q")

        section_results = check_section_presence(filing, {section_id: section_name})

        assert section_results[section_id], (
            f"Section '{section_name}' not found in {file_path.name}.\n"
            f"Available sections: {filing.get_section_names()}"
        )

    def test_10q_aggregate_recall(
        self,
        parser: SECFilingParser,
        test_10q_files: List[Path]
    ):
        """Test aggregate section recall across all 10-Q files."""
        if not test_10q_files:
            pytest.skip("No 10-Q test files available in data/raw/")

        all_recalls = []
        failed_files = []

        for file_path in test_10q_files:
            try:
                filing = parser.parse_filing(file_path, form_type="10-Q")
                section_results = check_section_presence(filing, REQUIRED_10Q_SECTIONS)
                recall = calculate_recall(section_results, REQUIRED_10Q_SECTIONS)
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
        failure_report = format_failure_report(failed_files)

        assert avg_recall >= MIN_SECTION_RECALL, (
            f"10-Q section recall {avg_recall:.2%} below threshold {MIN_SECTION_RECALL:.0%}.\n"
            f"{failure_report}"
        )


class TestParserPerformance:
    """Test suite for parser performance metrics."""

    def test_parsing_latency(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path]
    ):
        """Test that parsing completes within latency threshold."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available")

        file_path = test_10k_files[0]

        start_time = time.time()
        filing = parser.parse_filing(file_path, form_type="10-K")
        elapsed = time.time() - start_time

        assert elapsed < MAX_LATENCY_SECONDS, (
            f"Parsing took {elapsed:.2f}s, exceeds threshold of {MAX_LATENCY_SECONDS}s"
        )
        assert len(filing) > 0, "Parser returned empty result"

    def test_idempotency(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path]
    ):
        """Test that parsing the same file twice produces identical results."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available")

        file_path = test_10k_files[0]

        # Parse twice
        filing1 = parser.parse_filing(file_path, form_type="10-K")
        filing2 = parser.parse_filing(file_path, form_type="10-K")

        # Compare key attributes
        assert len(filing1) == len(filing2), (
            f"Element count mismatch: {len(filing1)} vs {len(filing2)}"
        )
        assert filing1.get_section_names() == filing2.get_section_names(), (
            "Section names mismatch between parses"
        )
        assert filing1.metadata['num_sections'] == filing2.metadata['num_sections'], (
            "Section count mismatch in metadata"
        )

    @pytest.mark.slow
    def test_batch_performance(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path]
    ):
        """Test parsing performance across multiple files."""
        if len(test_10k_files) < 2:
            pytest.skip("Need at least 2 files for batch test")

        # Limit to 5 files for reasonable test time
        test_files = test_10k_files[:5]
        latencies = []

        for file_path in test_files:
            start_time = time.time()
            try:
                parser.parse_filing(file_path, form_type="10-K")
            except Exception:
                pass  # Track timing even on failure
            latencies.append(time.time() - start_time)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        assert avg_latency < MAX_LATENCY_SECONDS, (
            f"Average latency {avg_latency:.2f}s exceeds threshold"
        )
        print(f"\nBatch performance: avg={avg_latency:.2f}s, max={max_latency:.2f}s")


class TestParserEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_empty_file_handling(self, parser: SECFilingParser, tmp_path: Path):
        """Test graceful handling of empty files."""
        empty_file = tmp_path / "empty.html"
        empty_file.write_text("")

        with pytest.raises(ValueError, match="empty"):
            parser.parse_filing(empty_file, form_type="10-K")

    def test_invalid_form_type(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path]
    ):
        """Test handling of invalid form type."""
        if not test_10k_files:
            pytest.skip("No test files available")

        with pytest.raises(ValueError, match="Unsupported form type"):
            parser.parse_filing(test_10k_files[0], form_type="INVALID")

    def test_nonexistent_file(self, parser: SECFilingParser):
        """Test handling of nonexistent file."""
        with pytest.raises(FileNotFoundError):
            parser.parse_filing("nonexistent_file_12345.html", form_type="10-K")

    def test_minimal_html(self, parser: SECFilingParser, tmp_path: Path):
        """Test parsing of minimal valid HTML."""
        minimal_html = """
        <html><body>
            <p>Item 1. Business</p>
            <p>Description of operations.</p>
        </body></html>
        """
        html_file = tmp_path / "minimal.html"
        html_file.write_text(minimal_html)

        # Should not raise - minimal HTML should be parseable
        filing = parser.parse_filing(html_file, form_type="10-K")
        assert len(filing) > 0

    def test_deeply_nested_html(self, parser: SECFilingParser, tmp_path: Path):
        """Test handling of deeply nested HTML structures."""
        # Create deeply nested HTML (common in SEC filings)
        nested = "<div>" * 50 + "Content" + "</div>" * 50
        html_content = f"<html><body>{nested}</body></html>"

        html_file = tmp_path / "nested.html"
        html_file.write_text(html_content)

        # Should handle without stack overflow
        filing = parser.parse_filing(html_file, form_type="10-K")
        assert filing is not None


class TestParserMetadata:
    """Test suite for metadata extraction."""

    def test_metadata_fields(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path]
    ):
        """Test that metadata contains expected fields."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available")

        filing = parser.parse_filing(test_10k_files[0], form_type="10-K")
        metadata = filing.metadata

        required_fields = ['total_elements', 'num_sections', 'element_types', 'html_size']
        for field in required_fields:
            assert field in metadata, f"Missing metadata field: {field}"

    def test_element_count_positive(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path]
    ):
        """Test that element count is positive."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available")

        filing = parser.parse_filing(test_10k_files[0], form_type="10-K")

        assert filing.metadata['total_elements'] > 0
        assert len(filing) > 0
        assert len(filing) == filing.metadata['total_elements']

    def test_sic_code_extraction(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path]
    ):
        """Test SIC code extraction from filing."""
        if not test_10k_files:
            pytest.skip("No 10-K test files available")

        filing = parser.parse_filing(test_10k_files[0], form_type="10-K")

        # SIC code may or may not be present depending on file
        # Just verify the field exists
        assert 'sic_code' in filing.metadata


class TestMetricsReport:
    """Generate a comprehensive metrics report for QA review."""

    def test_generate_metrics_report(
        self,
        parser: SECFilingParser,
        test_10k_files: List[Path],
        test_10q_files: List[Path],
        save_test_artifact,
        test_artifact_dir: Path
    ):
        """Generate comprehensive metrics report.

        Saves report to persistent test output directory for validation and review.
        """
        report = {
            "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "parser_info": parser.get_parser_info(),
            "thresholds": {
                "min_section_recall": MIN_SECTION_RECALL,
                "max_latency_seconds": MAX_LATENCY_SECONDS,
            },
            "metrics": {}
        }

        # 10-K Metrics
        if test_10k_files:
            recalls = []
            latencies = []
            errors = []

            for file_path in test_10k_files[:10]:  # Limit for speed
                try:
                    start = time.time()
                    filing = parser.parse_filing(file_path, form_type="10-K")
                    latency = time.time() - start
                    latencies.append(latency)

                    section_results = check_section_presence(filing, REQUIRED_10K_SECTIONS)
                    recall = calculate_recall(section_results, REQUIRED_10K_SECTIONS)
                    recalls.append(recall)
                except Exception as e:
                    recalls.append(0.0)
                    errors.append({'file': file_path.name, 'error': str(e)})

            # Calculate p95 latency
            if len(latencies) > 1:
                p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
            else:
                p95_latency = latencies[0] if latencies else 0

            report["metrics"]["10k"] = {
                "files_tested": len(test_10k_files),
                "files_sampled": min(10, len(test_10k_files)),
                "avg_section_recall": sum(recalls) / len(recalls) if recalls else 0,
                "min_section_recall": min(recalls) if recalls else 0,
                "max_section_recall": max(recalls) if recalls else 0,
                "avg_latency_seconds": (
                    sum(latencies) / len(latencies) if latencies else 0
                ),
                "max_latency_seconds": max(latencies) if latencies else 0,
                "p95_latency_seconds": p95_latency,
                "error_count": len(errors),
                "errors": errors[:5] if errors else [],
            }

        # 10-Q Metrics
        if test_10q_files:
            recalls = []
            latencies = []

            for file_path in test_10q_files[:10]:
                try:
                    start = time.time()
                    filing = parser.parse_filing(file_path, form_type="10-Q")
                    latency = time.time() - start
                    latencies.append(latency)

                    section_results = check_section_presence(filing, REQUIRED_10Q_SECTIONS)
                    recall = calculate_recall(section_results, REQUIRED_10Q_SECTIONS)
                    recalls.append(recall)
                except Exception:
                    recalls.append(0.0)

            report["metrics"]["10q"] = {
                "files_tested": len(test_10q_files),
                "files_sampled": min(10, len(test_10q_files)),
                "avg_section_recall": sum(recalls) / len(recalls) if recalls else 0,
                "avg_latency_seconds": sum(latencies) / len(latencies) if latencies else 0,
            }

        # Overall status
        status = "PASS"
        if report["metrics"].get("10k", {}).get("avg_section_recall", 1.0) < MIN_SECTION_RECALL:
            status = "FAIL"
        if report["metrics"].get("10k", {}).get("max_latency_seconds", 0) > MAX_LATENCY_SECONDS:
            status = "WARN" if status != "FAIL" else status
        report["status"] = status

        # Save report to persistent test output directory
        report_path = save_test_artifact("parser_metrics_report.json", report)

        # Print report
        print(f"\n{'='*60}")
        print("PARSER METRICS REPORT")
        print(f"{'='*60}")
        print(json.dumps(report, indent=2))
        print(f"{'='*60}")
        print(f"Report saved to: {report_path}")
        print(f"Artifact directory: {test_artifact_dir}")

        # Assert basic validity
        assert report["status"] in ["PASS", "WARN", "FAIL"]


# ===========================
# Run Configuration
# ===========================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
