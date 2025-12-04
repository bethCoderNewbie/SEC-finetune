"""
Shared pytest fixtures for SEC Filing Analyzer test suite.

This module provides common fixtures used across test modules:
- Parser and extractor instances
- Test file paths (10-K, 10-Q)
- Configuration settings
- Mock data helpers

Usage:
    Fixtures are automatically discovered by pytest.
    Import them directly in test files - no explicit import needed.
"""

import pytest
from pathlib import Path
from typing import List, Optional, Generator
import sys
import json

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings


# ===========================
# Path Fixtures
# ===========================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def raw_data_dir() -> Path:
    """Return the raw data directory path."""
    return settings.paths.raw_data_dir


@pytest.fixture(scope="session")
def parsed_data_dir() -> Path:
    """Return the parsed data directory path."""
    return settings.paths.parsed_data_dir


# ===========================
# Test File Discovery Fixtures
# ===========================

@pytest.fixture(scope="module")
def test_10k_files(raw_data_dir: Path) -> List[Path]:
    """
    Get all 10-K test files from raw data directory.

    Returns:
        List of paths to 10-K HTML files
    """
    if not raw_data_dir.exists():
        return []

    files = []
    patterns = ["*10[Kk]*.html", "*10-[Kk]*.html", "*_10K_*.html", "*_10-K_*.html"]
    for pattern in patterns:
        files.extend(raw_data_dir.glob(pattern))

    return sorted(set(files), key=lambda p: p.name)


@pytest.fixture(scope="module")
def test_10q_files(raw_data_dir: Path) -> List[Path]:
    """
    Get all 10-Q test files from raw data directory.

    Returns:
        List of paths to 10-Q HTML files
    """
    if not raw_data_dir.exists():
        return []

    files = []
    patterns = ["*10[Qq]*.html", "*10-[Qq]*.html", "*_10Q_*.html", "*_10-Q_*.html"]
    for pattern in patterns:
        files.extend(raw_data_dir.glob(pattern))

    return sorted(set(files), key=lambda p: p.name)


@pytest.fixture(scope="module")
def sample_10k_file(test_10k_files: List[Path]) -> Optional[Path]:
    """
    Get a single sample 10-K file for testing.

    Returns:
        Path to first available 10-K file, or None if none available
    """
    return test_10k_files[0] if test_10k_files else None


@pytest.fixture(scope="module")
def sample_10q_file(test_10q_files: List[Path]) -> Optional[Path]:
    """
    Get a single sample 10-Q file for testing.

    Returns:
        Path to first available 10-Q file, or None if none available
    """
    return test_10q_files[0] if test_10q_files else None


# ===========================
# Parser Fixtures
# ===========================

@pytest.fixture(scope="module")
def parser():
    """
    Initialize SECFilingParser once for all tests in module.

    Returns:
        SECFilingParser instance
    """
    from src.preprocessing.parser import SECFilingParser
    return SECFilingParser()


@pytest.fixture(scope="module")
def extractor():
    """
    Initialize SECSectionExtractor once for all tests in module.

    Returns:
        SECSectionExtractor instance
    """
    from src.preprocessing.extractor import SECSectionExtractor
    return SECSectionExtractor()


@pytest.fixture(scope="module")
def risk_extractor():
    """
    Initialize RiskFactorExtractor once for all tests in module.

    Returns:
        RiskFactorExtractor instance
    """
    from src.preprocessing.extractor import RiskFactorExtractor
    return RiskFactorExtractor()


# ===========================
# Sample Content Fixtures
# ===========================

@pytest.fixture(scope="session")
def sample_risk_text() -> str:
    """
    Return sample risk factor text for testing.

    Returns:
        Sample risk disclosure text
    """
    return """
    Our business is subject to numerous risks that could materially adversely
    affect our business, financial condition, or results of operations.

    Competition Risk
    We face intense competition in all of our markets. Our competitors may have
    greater financial resources and may be able to respond more quickly to new
    or emerging technologies.

    Regulatory Risk
    Changes in laws and regulations could increase our costs of operations and
    adversely impact our business. We are subject to various federal, state,
    and local laws.

    Cybersecurity Risk
    Security breaches and cyber attacks could compromise our systems and data.
    Unauthorized access to our systems could result in significant costs.
    """


@pytest.fixture(scope="session")
def sample_html_content() -> str:
    """
    Return sample HTML content for testing parser.

    Returns:
        Minimal valid SEC filing HTML structure
    """
    return """
    <!DOCTYPE html>
    <html>
    <head><title>10-K Filing</title></head>
    <body>
        <div>
            <p style="font-weight:bold">Item 1. Business</p>
            <p>Description of the business operations.</p>
        </div>
        <div>
            <p style="font-weight:bold">Item 1A. Risk Factors</p>
            <p>We face various risks including competition, regulatory changes,
            and cybersecurity threats that could adversely affect our business.</p>
        </div>
        <div>
            <p style="font-weight:bold">Item 7. Management's Discussion and Analysis</p>
            <p>The following discussion provides information about our financial
            condition and results of operations.</p>
        </div>
    </body>
    </html>
    """


# ===========================
# Temporary Directory Fixtures
# ===========================

@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """
    Create a temporary output directory for test artifacts.

    Args:
        tmp_path: pytest built-in fixture for temp directory

    Returns:
        Path to temp output directory
    """
    output_dir = tmp_path / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def temp_html_file(tmp_path: Path, sample_html_content: str) -> Path:
    """
    Create a temporary HTML file for testing.

    Args:
        tmp_path: pytest built-in fixture
        sample_html_content: Sample HTML fixture

    Returns:
        Path to temporary HTML file
    """
    html_file = tmp_path / "test_filing.html"
    html_file.write_text(sample_html_content, encoding="utf-8")
    return html_file


# ===========================
# Metrics Fixtures
# ===========================

@pytest.fixture(scope="session")
def required_10k_sections() -> dict:
    """
    Return required sections for 10-K filing validation.

    Returns:
        Dict mapping section_id to section_name
    """
    return {
        "part1item1": "Item 1. Business",
        "part1item1a": "Item 1A. Risk Factors",
        "part2item7": "Item 7. Management's Discussion and Analysis",
        "part2item7a": "Item 7A. Quantitative and Qualitative Disclosures",
    }


@pytest.fixture(scope="session")
def required_10q_sections() -> dict:
    """
    Return required sections for 10-Q filing validation.

    Returns:
        Dict mapping section_id to section_name
    """
    return {
        "part1item1": "Item 1. Financial Statements",
        "part1item2": "Item 2. Management's Discussion and Analysis",
        "part2item1a": "Item 1A. Risk Factors",
    }


# ===========================
# Report Fixtures
# ===========================

@pytest.fixture
def metrics_report_path(tmp_path: Path) -> Path:
    """
    Return path for metrics report output.

    Args:
        tmp_path: pytest built-in fixture

    Returns:
        Path for JSON metrics report
    """
    return tmp_path / "parser_metrics_report.json"


def save_metrics_report(report: dict, path: Path) -> None:
    """
    Helper function to save metrics report to JSON.

    Args:
        report: Metrics report dictionary
        path: Output path
    """
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)


# ===========================
# Skip Condition Markers
# ===========================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "requires_10k_files: mark test to skip if no 10-K files available"
    )
    config.addinivalue_line(
        "markers", "requires_10q_files: mark test to skip if no 10-Q files available"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
