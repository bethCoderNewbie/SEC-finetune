"""
Generate a human-readable QA report for the SEC Section Extractor.

This script:
1. Runs the extractor validation tests (`tests/preprocessing/test_extractor.py`).
2. Parses the test output to determine Pass/Fail/Skip status for key metrics.
3. Generates a comprehensive Markdown report reflecting the current codebase state.
4. Saves the report to the 'reports/' directory.
Source: It runs unit tests (pytest) against the code.
Scope: It validates the logic of the extractor using predefined test cases (often mock data or small samples)
Goal: Provides a "Go/No-Go" status for the codebase's current version based on test passing/failing

Usage:
    python scripts/utils/generate_extractor_qa_report.py
"""

import sys
import json
import datetime
import platform
import subprocess
import os
import re
from pathlib import Path
from typing import Dict, List, Any

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_git_info():
    """Retrieve git metadata safely."""
    def _run_git(args):
        try:
            return subprocess.check_output(["git"] + args, stderr=subprocess.DEVNULL).decode('utf-8').strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    return {
        "commit": _run_git(["rev-parse", "--short", "HEAD"]),
        "branch": _run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "user": _run_git(["config", "user.name"]) or os.environ.get("USERNAME", "unknown")
    }


def get_run_metadata():
    """Gather comprehensive run environment metadata."""
    git = get_git_info()
    return {
        "timestamp": datetime.datetime.now().astimezone().isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git["commit"],
        "git_branch": git["branch"],
        "researcher": git["user"],
        "working_dir": str(Path.cwd()),
    }


def run_extraction_tests() -> str:
    """Run pytest for extractor tests and return stdout."""
    print("Running extractor tests (skipping slow integration tests)...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/preprocessing/test_extractor.py",
        "-v",
        "-k", "not Integration",
        "--tb=short"
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False  # Don't raise error on test failure
        )
        return result.stdout
    except Exception as e:
        return f"Error running tests: {e}"


def parse_test_output(output: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse pytest output to map test functions to metric statuses.
    Returns a dictionary mapping metric keys to status details.
    """
    metrics_map = {
        # Extraction Accuracy
        "test_extracted_sections_have_valid_identifier": "section_start_precision",
        "test_item_pattern_matches_real_titles": "key_item_recall",
        # "section_end_precision" - No direct test, mapped manually or inferred
        
        # Content Quality
        "test_no_page_headers_in_subsections": "page_header_filtering",
        "test_subsections_are_meaningful": "subsection_classification",
        
        # Benchmarking
        "test_extracted_text_length_in_range": "char_count_range",
        "test_risk_keyword_density": "keyword_density",
        
        # Integration
        "test_extract_risk_factors_from_real_file": "real_file_extraction"
    }

    results = {
        key: {"status": "UNKNOWN", "details": "Test not found in output"}
        for key in metrics_map.values()
    }
    
    # Add manual/missing metrics
    results["section_end_precision"] = {"status": "UNKNOWN", "details": "No direct test coverage"}
    results["toc_noise_filtering"] = {"status": "UNKNOWN", "details": "No direct test coverage"}
    results["heading_level_accuracy"] = {"status": "UNKNOWN", "details": "No direct test coverage"}

    # Regex to match pytest output lines:
    # tests/preprocessing/test_extractor.py::TestClass::test_name PASSED/FAILED/SKIPPED [ %]
    test_pattern = re.compile(r"::(test_\w+)\s+(PASSED|FAILED|SKIPPED|XFAIL|XPASS)")

    for line in output.splitlines():
        match = test_pattern.search(line)
        if match:
            test_name, status = match.groups()
            
            if test_name in metrics_map:
                metric_key = metrics_map[test_name]
                results[metric_key]["status"] = status
                results[metric_key]["details"] = f"Test `{test_name}` {status}"

    return results


def determine_go_no_go(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate overall status and Go/No-Go decisions."""
    
    # Logic to translate test status to Go/No-Go
    def get_decision(status):
        if status == "PASSED": return "GO"
        if status in ["FAILED", "XPASS"]: return "NO-GO"
        if status == "SKIPPED": return "NO-GO (No Data)"
        if status == "XFAIL": return "NO-GO (Known Issue)"
        return "UNKNOWN"

    for key, data in results.items():
        data["go_no_go"] = get_decision(data["status"])

    return results


def generate_markdown_report(results, metadata, raw_output):
    """Generate the Markdown content for the Extractor QA Report."""
    
    # Count stats
    passed = sum(1 for r in results.values() if r["status"] == "PASSED")
    failed = sum(1 for r in results.values() if r["status"] in ["FAILED", "XPASS"])
    skipped = sum(1 for r in results.values() if r["status"] == "SKIPPED")
    xfail = sum(1 for r in results.values() if r["status"] == "XFAIL")

    md = f"""# SEC Section Extractor QA Report

**Status**: `GENERATED (From Test Run)`
**Test Suite**: `tests/preprocessing/test_extractor.py`

## 0. Run Environment (Metadata)

| Key | Value |
|-----|-------|
| **Timestamp** | `{metadata['timestamp']}` |
| **Researcher** | `{metadata['researcher']}` |
| **Git Commit** | `{metadata['git_commit']}` (Branch: `{metadata['git_branch']}`) |
| **Python** | `{metadata['python_version']}` |
| **Platform** | `{metadata['platform']}` |

---

## 1. Executive Summary

This report is generated dynamically by running the extraction test suite.

**Test Summary**:
*   ✅ **Passed**: {passed}
*   ❌ **Failed**: {failed}
*   ⏭️ **Skipped**: {skipped}
*   ⚠️ **Known Issues (XFail)**: {xfail}

### Go/No-Go Validation Table

| Metric Category | Metric Name | Test Status | Go/No-Go | Details |
|-----------------|-------------|-------------|----------|---------|
| **Extraction Accuracy** | Section Start Precision | {results["section_start_precision"]["status"]} | {results["section_start_precision"]["go_no_go"]} | {results["section_start_precision"]["details"]} |
| **Extraction Accuracy** | Section End Precision | {results["section_end_precision"]["status"]} | {results["section_end_precision"]["go_no_go"]} | {results["section_end_precision"]["details"]} |
| **Extraction Accuracy** | Key Item Recall | {results["key_item_recall"]["status"]} | {results["key_item_recall"]["go_no_go"]} | {results["key_item_recall"]["details"]} |
| **Content Quality** | Page Header Filtering | {results["page_header_filtering"]["status"]} | {results["page_header_filtering"]["go_no_go"]} | {results["page_header_filtering"]["details"]} |
| **Content Quality** | Subsection Classification | {results["subsection_classification"]["status"]} | {results["subsection_classification"]["go_no_go"]} | {results["subsection_classification"]["details"]} |
| **Content Quality** | ToC Noise Filtering | {results["toc_noise_filtering"]["status"]} | {results["toc_noise_filtering"]["go_no_go"]} | {results["toc_noise_filtering"]["details"]} |
| **Benchmarking** | Char Count Range | {results["char_count_range"]["status"]} | {results["char_count_range"]["go_no_go"]} | {results["char_count_range"]["details"]} |
| **Benchmarking** | Keyword Density | {results["keyword_density"]["status"]} | {results["keyword_density"]["go_no_go"]} | {results["keyword_density"]["details"]} |
| **Integration** | Real File Extraction | {results["real_file_extraction"]["status"]} | {results["real_file_extraction"]["go_no_go"]} | {results["real_file_extraction"]["details"]} |

---

## 2. Detailed Findings

### 2.1 Extraction Accuracy
*   **Section Start Precision**: {results["section_start_precision"]["details"]}
*   **Key Item Recall**: {results["key_item_recall"]["details"]}
*   **Section End Precision**: {results["section_end_precision"]["details"]} (Requires manual verification or new test case).

### 2.2 Content Quality
*   **Page Header Filtering**: {results["page_header_filtering"]["details"]}
    *   *Note*: If XFAIL, this confirms known page header pollution issues.
*   **Subsection Classification**: {results["subsection_classification"]["details"]}
*   **ToC Noise Filtering**: {results["toc_noise_filtering"]["details"]} (Not currently covered by automated tests).

### 2.3 Benchmarking & Integration
*   **Character Counts**: {results["char_count_range"]["details"]}
*   **Keyword Density**: {results["keyword_density"]["details"]}
*   **Real File Extraction**: {results["real_file_extraction"]["details"]}
    *   *Note*: If this passes while others skip, it means raw data is present but extracted interim data is missing.

---

## 3. Raw Test Output

```text
{raw_output}
```
"""
    return md


def main():
    metadata = get_run_metadata()
    print(f"Run Environment: {metadata['platform']} | Python {metadata['python_version']}")
    
    # 1. Run Tests
    raw_output = run_extraction_tests()
    
    # 2. Parse Results
    parsed_results = parse_test_output(raw_output)
    
    # 3. Analyze
    final_results = determine_go_no_go(parsed_results)
    
    # 4. Generate Report
    report_content = generate_markdown_report(final_results, metadata, raw_output)
    
    output_dir = PROJECT_ROOT / "reports"
    output_dir.mkdir(exist_ok=True)
    
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    output_path = output_dir / f"extractor_qa_report_{today}.md"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"\nReport generated successfully: {output_path}")


if __name__ == "__main__":
    main()