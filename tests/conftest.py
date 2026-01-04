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
from typing import Any, Callable, Dict, List, Optional, Generator
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
# Extracted Data Fixtures
# ===========================

@pytest.fixture(scope="module")
def extracted_risk_files(project_root: Path) -> List[Path]:
    """
    Get all extracted risk JSON files from data/interim/extracted.
    
    Returns:
        List of Path objects for extracted risk files.
    """
    extracted_dir = project_root / "data" / "interim" / "extracted"
    if not extracted_dir.exists():
        return []
        
    return list(extracted_dir.glob("*_extracted_risks.json"))

@pytest.fixture(scope="module")
def extracted_risk_sections(extracted_risk_files: List[Path]) -> List['ExtractedSection']:
    """
    Load ExtractedSection objects from JSON files.
    
    Returns:
        List of ExtractedSection objects.
    """
    from src.preprocessing.extractor import ExtractedSection
    
    sections = []
    for file_path in extracted_risk_files:
        try:
            section = ExtractedSection.load_from_json(file_path)
            sections.append(section)
        except Exception as e:
            print(f"Warning: Failed to load {file_path}: {e}")
            
    return sections


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
    config.addinivalue_line(
        "markers", "requires_preprocessing_data: mark test to skip if no preprocessing data available"
    )


# ===========================
# Dynamic Test Data Fixtures
# ===========================

@pytest.fixture(scope="session")
def test_data_config():
    """
    Get test data configuration for dynamic path resolution.

    Returns:
        TestDataConfig instance for finding run directories
    """
    return settings.testing.data


@pytest.fixture(scope="session")
def latest_preprocessing_run(test_data_config) -> Optional[Path]:
    """
    Get the latest preprocessing run directory.

    Returns:
        Path to latest preprocessing run, or None if not found
    """
    return test_data_config.find_latest_run("preprocessing")


@pytest.fixture(scope="session")
def aapl_10k_data_path(test_data_config) -> Optional[Path]:
    """
    Get path to AAPL 10-K segmented risks file.

    Dynamically resolves from latest preprocessing run.

    Returns:
        Path to AAPL_10K_2021_segmented_risks.json, or None if not found
    """
    return test_data_config.get_test_file(
        run_name="preprocessing",
        filename="AAPL_10K_2021_segmented_risks.json"
    )


@pytest.fixture(scope="module")
def aapl_10k_data(aapl_10k_data_path) -> Optional[dict]:
    """
    Load actual AAPL 10-K 2021 segmented risk factors.

    Returns None if file not available (allows graceful skip).

    Returns:
        Dict with segments and aggregate_sentiment, or None
    """
    if aapl_10k_data_path is None or not aapl_10k_data_path.exists():
        return None

    with open(aapl_10k_data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(scope="module")
def aapl_segments(aapl_10k_data) -> List[dict]:
    """
    Get list of segment dictionaries from AAPL 10-K data.

    Returns empty list if data unavailable.

    Returns:
        List of 54 segment dictionaries, or empty list
    """
    if aapl_10k_data is None:
        return []
    return aapl_10k_data.get("segments", [])


@pytest.fixture(scope="module")
def aapl_aggregate_sentiment(aapl_10k_data) -> Optional[dict]:
    """
    Get aggregate sentiment statistics from AAPL 10-K data.

    Returns:
        Dict with avg_negative_ratio, avg_positive_ratio, etc., or None
    """
    if aapl_10k_data is None:
        return None
    return aapl_10k_data.get("aggregate_sentiment")


# ===========================
# Golden Sentence Fixtures (No File Dependency)
# ===========================

@pytest.fixture(scope="session")
def golden_sentence() -> str:
    """
    Deterministic test sentence with known LM word matches.

    This sentence contains verified LM dictionary words for exact testing.

    Returns:
        Test sentence with known sentiment word composition
    """
    return "The company anticipates potential litigation and catastrophic losses."


@pytest.fixture(scope="session")
def golden_sentence_expected() -> dict:
    """
    Expected feature values for golden sentence (verified).

    Verified against LM dictionary:
    - anticipates: Uncertainty
    - litigation: Litigious, Negative, Complexity
    - catastrophic: Negative
    - losses: Negative

    Returns:
        Dict with expected counts for each category
    """
    return {
        'negative_count': 3,       # catastrophic, losses, litigation
        'positive_count': 0,
        'uncertainty_count': 1,    # anticipates
        'litigious_count': 1,      # litigation
        'total_sentiment_words': 5,
        'word_count': 8,
    }


@pytest.fixture(scope="module")
def long_segment_texts(aapl_segments) -> List[str]:
    """
    Get segments with >200 chars for readability analysis.

    Short segments don't provide reliable readability metrics.

    Returns:
        List of text strings from segments with sufficient length
    """
    return [seg["text"] for seg in aapl_segments if len(seg["text"]) > 200]


# ===========================
# Preprocessing Data Fixtures (Dynamic)
# ===========================

@pytest.fixture(scope="session")
def processed_data_dir(test_data_config) -> Optional[Path]:
    """
    Get latest preprocessing run directory.

    Uses TestDataConfig for dynamic path resolution.

    Returns:
        Path to latest preprocessing run directory, or None if not found
    """
    return test_data_config.find_latest_run("preprocessing")


@pytest.fixture(scope="module")
def segmented_data_files(processed_data_dir) -> List[Path]:
    """
    Get all segmented risk files from latest preprocessing run.

    Returns:
        List of Path objects for segmented risk JSON files
    """
    if processed_data_dir is None or not processed_data_dir.exists():
        return []
    return list(processed_data_dir.glob("*_segmented_risks.json"))


@pytest.fixture(scope="module")
def segmented_data(segmented_data_files) -> List[dict]:
    """
    Load segmented risk data from files.

    Limits to 10 files for test speed.

    Returns:
        List of loaded JSON data dictionaries
    """
    if not segmented_data_files:
        return []
    data = []
    for f in segmented_data_files[:10]:
        with open(f, 'r', encoding='utf-8') as fp:
            data.append(json.load(fp))
    return data


@pytest.fixture(scope="module")
def extracted_data_dir(project_root: Path) -> Path:
    """
    Get the extracted data directory path.

    Returns:
        Path to data/interim/extracted directory
    """
    return project_root / "data" / "interim" / "extracted"


@pytest.fixture(scope="module")
def extracted_data_files(extracted_data_dir: Path) -> List[Path]:
    """
    Get all extracted risk JSON files.

    Includes files from v1_ subdirectory if present.

    Returns:
        List of Path objects for extracted risk JSON files
    """
    if not extracted_data_dir.exists():
        return []

    files = list(extracted_data_dir.glob("*_extracted_risks.json"))

    # Also check v1_ subdirectory
    v1_dir = extracted_data_dir / "v1_"
    if v1_dir.exists():
        files.extend(v1_dir.glob("*_extracted_risks.json"))

    return files


@pytest.fixture(scope="module")
def extracted_data(extracted_data_files: List[Path]) -> List[dict]:
    """
    Load extracted risk data from files.

    Limits to 5 files for test speed.

    Returns:
        List of loaded JSON data dictionaries
    """
    if not extracted_data_files:
        return []
    data = []
    for f in extracted_data_files[:5]:
        with open(f, 'r', encoding='utf-8') as fp:
            data.append(json.load(fp))
    return data


@pytest.fixture(scope="module")
def cleaned_data_files(extracted_data_dir: Path) -> List[Path]:
    """
    Get all cleaned risk JSON files.

    Includes files from v1_ subdirectory if present.

    Returns:
        List of Path objects for cleaned risk JSON files
    """
    if not extracted_data_dir.exists():
        return []

    files = list(extracted_data_dir.glob("*_cleaned_risks.json"))

    # Also check v1_ subdirectory
    v1_dir = extracted_data_dir / "v1_"
    if v1_dir.exists():
        files.extend(v1_dir.glob("*_cleaned_risks.json"))

    return files


@pytest.fixture(scope="module")
def cleaned_data(cleaned_data_files: List[Path]) -> List[dict]:
    """
    Load cleaned risk data from files.

    Limits to 5 files for test speed.

    Returns:
        List of loaded JSON data dictionaries
    """
    if not cleaned_data_files:
        return []
    data = []
    for f in cleaned_data_files[:5]:
        with open(f, 'r', encoding='utf-8') as fp:
            data.append(json.load(fp))
    return data


@pytest.fixture
def segmenter():
    """
    Initialize RiskSegmenter for tests.

    Returns:
        RiskSegmenter instance
    """
    from src.preprocessing.segmenter import RiskSegmenter
    return RiskSegmenter()


@pytest.fixture
def cleaner():
    """
    Initialize TextCleaner for tests.

    Returns:
        TextCleaner instance
    """
    from src.preprocessing.cleaning import TextCleaner
    return TextCleaner()


# ===========================
# Test Output Persistence Fixtures
# ===========================

# Global test run context - shared across all tests in a session
_test_output_run = None


def pytest_configure(config):
    """
    Initialize test output run at pytest startup.

    Creates a timestamped output directory for this test session.
    """
    global _test_output_run

    from src.config.testing import TestOutputConfig

    output_config = TestOutputConfig()
    _test_output_run = output_config.create_test_run(name="pytest")
    _test_output_run.create()

    # Save initial metadata
    _test_output_run.save_metadata({
        "pytest_args": list(config.invocation_params.args) if hasattr(config, 'invocation_params') else [],
        "rootdir": str(config.rootdir) if hasattr(config, 'rootdir') else None,
    })


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Capture test results after each test phase.

    Records pass/fail/skip status with timing information.
    """
    outcome = yield
    report = outcome.get_result()

    # Only capture 'call' phase (not setup/teardown)
    if report.when == "call" and _test_output_run is not None:
        error_msg = None
        skip_reason = None

        if report.failed:
            if hasattr(report, 'longrepr') and report.longrepr:
                error_msg = str(report.longrepr)[:500]  # Truncate long errors

        if report.skipped:
            if hasattr(report, 'longrepr') and report.longrepr:
                # Skip reason is in longrepr tuple
                if isinstance(report.longrepr, tuple) and len(report.longrepr) > 2:
                    skip_reason = str(report.longrepr[2])
                else:
                    skip_reason = str(report.longrepr)

        _test_output_run.add_test_result(
            nodeid=item.nodeid,
            outcome=report.outcome,
            duration=report.duration,
            error=error_msg,
            reason=skip_reason
        )


def pytest_sessionfinish(session, exitstatus):
    """
    Save final results when test session completes.

    Creates test_results.json with summary and details of all tests.
    """
    global _test_output_run

    if _test_output_run is not None:
        _test_output_run.finalize()

        # Print output location
        print(f"\n{'='*60}")
        print(f"Test outputs saved to: {_test_output_run.run_dir}")
        print(f"{'='*60}\n")


@pytest.fixture(scope="session")
def test_output_run():
    """
    Get the current test output run context.

    This session-scoped fixture provides access to the test run context
    for saving artifacts and results.

    Usage:
        def test_example(test_output_run):
            # Save an artifact
            test_output_run.save_artifact(
                "test_module", "test_name", "output.json", {"key": "value"}
            )

    Returns:
        TestRunContext instance for the current test session
    """
    global _test_output_run
    return _test_output_run


@pytest.fixture(scope="function")
def test_artifact_dir(request, test_output_run) -> Path:
    """
    Get artifact directory for the current test.

    Creates a directory specific to this test for storing artifacts.
    Directory structure: artifacts/{module}/{test_name}/

    Usage:
        def test_example(test_artifact_dir):
            output_path = test_artifact_dir / "results.json"
            with open(output_path, 'w') as f:
                json.dump(results, f)

    Returns:
        Path to the test-specific artifact directory
    """
    if test_output_run is None:
        # Fallback to tmp_path if no output run (e.g., in isolation)
        return request.getfixturevalue('tmp_path')

    # Extract module and test name from node
    module_name = request.node.module.__name__.split(".")[-1] if request.node.module else "unknown"
    test_name = request.node.name

    return test_output_run.get_artifact_dir(module_name, test_name)


@pytest.fixture(scope="function")
def save_test_artifact(request, test_output_run) -> Callable:
    """
    Helper fixture to save test artifacts easily.

    Provides a callable that saves data to the test's artifact directory.

    Usage:
        def test_example(save_test_artifact):
            # Save JSON artifact
            save_test_artifact("output.json", {"result": 42})

            # Save text artifact
            save_test_artifact("debug.txt", "Some debug info", format="text")

    Args:
        filename: Name of the artifact file
        data: Data to save (dict for JSON, str for text)
        format: "json" (default) or "text"

    Returns:
        Callable that saves artifacts
    """
    def _save(filename: str, data: Any, format: str = "json") -> Optional[Path]:
        if test_output_run is None:
            return None

        module_name = request.node.module.__name__.split(".")[-1] if request.node.module else "unknown"
        test_name = request.node.name

        return test_output_run.save_artifact(
            test_module=module_name,
            test_name=test_name,
            filename=filename,
            data=data,
            format=format
        )

    return _save
