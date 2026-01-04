#!/usr/bin/env python
"""
Generate batch extractor QA report with parallel processing and checkpointing.

This script:
1. Loads all extracted risk JSON files from a run directory
2. Validates each file against extractor QA metrics in parallel
3. Generates a consolidated report with per-file and aggregate results
4. Supports checkpoint/resume for crash recovery

Usage:
    # Basic usage (sequential)
    python scripts/validation/extraction_quality/check_extractor_batch.py \
        --run-dir data/interim/extracted/20251212_extract_batch

    # Parallel processing with 8 workers
    python scripts/validation/extraction_quality/check_extractor_batch.py \
        --run-dir data/interim/extracted/20251212_extract_batch \
        --max-workers 8

    # With checkpointing and resume
    python scripts/validation/extraction_quality/check_extractor_batch.py \
        --run-dir data/interim/extracted/20251212_extract_batch \
        --max-workers 8 \
        --checkpoint-interval 20 \
        --resume

    # Generate markdown report
    python scripts/validation/extraction_quality/check_extractor_batch.py \
        --run-dir data/interim/extracted/20251212_extract_batch \
        --output reports/extractor_qa_batch_20251227.md \
        --format markdown

Exit Codes:
    0 - All checks passed (or acceptable failure rate)
    1 - Critical failures detected
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.constants import PAGE_HEADER_PATTERN, SectionIdentifier, TOC_PATTERNS_COMPILED
from src.utils.checkpoint import CheckpointManager
from src.utils.parallel import ParallelProcessor
from src.utils.metadata import RunMetadata
from src.utils.naming import parse_run_dir_metadata, format_output_filename
from src.config.qa_validation import (
    ThresholdRegistry,
    ValidationResult,
    ValidationStatus,
    determine_overall_status,
    ThresholdDefinition
)
from src.config import settings


# =============================================================================
# QA Metrics and Validation Logic
# =============================================================================

def _load_metrics_from_config() -> Dict[str, ThresholdDefinition]:
    """
    Load extractor QA metrics from config registry.

    Returns:
        Dict mapping metric names to ThresholdDefinition objects
    """
    metrics = {}

    # Load extraction_accuracy category
    for threshold in ThresholdRegistry.by_category("extraction_accuracy"):
        metrics[threshold.name] = threshold

    # Load content_quality category
    for threshold in ThresholdRegistry.by_category("content_quality"):
        metrics[threshold.name] = threshold

    # Add legacy script-specific metrics not in config
    # These maintain backwards compatibility with existing reports
    legacy_metrics = {
        "valid_identifier": ThresholdDefinition(
            name="valid_identifier",
            display_name="Valid Section Identifier",
            category="boundary_detection_legacy",
            metric_type="boolean",
            target=True,
            operator="==",
            blocking=True,
            description="Section has valid identifier (Item 1A or Part1Item1A)",
            tags=["extractor", "legacy"]
        ),
        "has_title": ThresholdDefinition(
            name="has_title",
            display_name="Section Has Title",
            category="boundary_detection_legacy",
            metric_type="boolean",
            target=True,
            operator="==",
            blocking=True,
            description="Section has non-empty title",
            tags=["extractor", "legacy"]
        ),
        "title_mentions_risk": ThresholdDefinition(
            name="title_mentions_risk",
            display_name="Title Mentions Risk",
            category="content_quality_legacy",
            metric_type="boolean",
            target=True,
            operator="==",
            blocking=False,
            description="Title contains 'risk' keyword",
            tags=["extractor", "legacy"]
        ),
        "substantial_content": ThresholdDefinition(
            name="substantial_content",
            display_name="Substantial Content (>1000 chars)",
            category="content_quality_legacy",
            metric_type="rate",
            target=1.0,
            operator=">=",
            blocking=True,
            description="Text length greater than 1000 characters",
            tags=["extractor", "legacy"]
        ),
        "char_count_in_range": ThresholdDefinition(
            name="char_count_in_range",
            display_name="Character Count in Range (5k-50k)",
            category="benchmarking_legacy",
            metric_type="boolean",
            target=True,
            operator="==",
            blocking=False,
            description="Character count between 5000 and 50000",
            tags=["extractor", "benchmarking", "legacy"]
        ),
        "has_subsections": ThresholdDefinition(
            name="has_subsections",
            display_name="Has Subsections",
            category="content_quality_legacy",
            metric_type="boolean",
            target=True,
            operator="==",
            blocking=False,
            description="Section has subsections",
            tags=["extractor", "legacy"]
        ),
        "keyword_density": ThresholdDefinition(
            name="keyword_density",
            display_name="Risk Keyword Density (>0.5%)",
            category="benchmarking_legacy",
            metric_type="rate",
            target=0.005,
            operator=">=",
            blocking=False,
            description="Risk keyword density above 0.5%",
            tags=["extractor", "benchmarking", "legacy"]
        ),
    }

    metrics.update(legacy_metrics)
    return metrics


# Risk keywords for density check
RISK_KEYWORDS = {
    "risk", "risks", "adverse", "adversely", "material", "materially",
    "uncertain", "uncertainty", "may", "could", "might", "potential"
}

# Load metrics from config at module level
METRICS_CONFIG = _load_metrics_from_config()


# =============================================================================
# New Metric Validation Functions (Config-Based)
# =============================================================================

def _check_section_boundary_precision_start(data: Dict, text: str) -> Optional[ValidationResult]:
    """
    Check if section start boundary is correctly detected.

    Validation: Check if extracted text starts with the expected section title
    (e.g., "Item 1A. Risk Factors" or similar) rather than premature content.

    A correct start should:
    1. Begin with section identifier (Item 1A, ITEM 1A, etc.)
    2. NOT start mid-sentence or with continuation text
    3. NOT have leading artifacts (page numbers, headers, etc.)
    """
    threshold = METRICS_CONFIG.get("section_boundary_precision_start")
    if not threshold:
        return None

    # Get first 500 chars for start boundary check
    text_start = text[:500].strip()

    # Valid start patterns: Should begin with Item identifier
    valid_start_patterns = [
        r'^Item\s+\d+[A-Z]?[\s\.]',  # "Item 1A. " or "Item 1A "
        r'^ITEM\s+\d+[A-Z]?[\s\.]',  # "ITEM 1A. " or "ITEM 1A "
        r'^Part\s+[IVX]+',           # "Part I" or "Part IV"
    ]

    # Invalid start patterns: Should NOT start with these
    invalid_start_patterns = [
        r'^\d+\s*$',                 # Starts with standalone page number
        r'^Page\s+\d+',              # Starts with "Page X"
        r'^\w+\s+Inc\.\s+\|',        # Starts with page header
        r'^[a-z]',                   # Starts with lowercase (mid-sentence)
    ]

    # Check for valid start
    has_valid_start = any(re.search(pat, text_start, re.MULTILINE) for pat in valid_start_patterns)

    # Check for invalid start
    has_invalid_start = any(re.search(pat, text_start, re.MULTILINE) for pat in invalid_start_patterns)

    # Pass if valid start AND no invalid patterns
    precision = 1.0 if (has_valid_start and not has_invalid_start) else 0.0

    return ValidationResult.from_threshold(threshold, precision)


def _check_section_boundary_precision_end(data: Dict, text: str) -> Optional[ValidationResult]:
    """
    Check if section end boundary is correctly detected.

    Detects if next section content (Item 1B, 1C, 2, etc.) leaked into extraction.

    Research: 2025-12-30_17-43_section_end_precision_investigation.md
    Finding: Previous pattern had 52.8% false positive rate from:
      - Case-sensitive matching (only lowercase "Item")
      - Matching section header "Item 1A. Risk Factors"
      - Matching cross-references "see Item 7. MD&A"

    Fix: Exclude header region, case-insensitive pattern, filter cross-refs.
    """
    threshold = METRICS_CONFIG.get("section_boundary_precision_end")
    if not threshold:
        return None

    # Exclude header region (first 300 chars) to avoid matching section title
    text_body = text[300:] if len(text) > 300 else ""

    # Detect boundary overshoot patterns
    # Pattern: Item 1B/1C/2+ at line start (not cross-references)
    # Excludes Item 1A (current section)
    # Requires newline before "Item" to distinguish headers from in-text references
    overshoot_pattern = r'(\n|^)(Item|ITEM)\s+(?!1A)[1-9]+[A-Z]?\s*\.\s+[A-Z]'
    has_overshoot = bool(re.search(overshoot_pattern, text_body))

    # Pass if NO overshoot detected
    precision = 0.0 if has_overshoot else 1.0

    return ValidationResult.from_threshold(threshold, precision)


def _check_key_item_recall(data: Dict) -> Optional[ValidationResult]:
    """
    Check if extracted section identifier matches expected key items.

    This is a file-level check - aggregate across batch for recall metric.
    Key items from research (line 78-87): Item 1, 1A, 7, 7A.
    """
    threshold = METRICS_CONFIG.get("key_item_recall")
    if not threshold:
        return None

    identifier = data.get("identifier", "").lower()

    # Key items from research
    key_items = ["part1item1", "part1item1a", "part2item7", "part2item7a"]

    # Check if this file represents a key item
    is_key_item = any(ki in identifier for ki in key_items)

    # Return 1.0 if key item found, 0.0 otherwise
    # Aggregate recall computed in batch_generate_extractor_qa_report()
    return ValidationResult.from_threshold(threshold, 1.0 if is_key_item else 0.0)


def _check_toc_filtering_rate(text: str) -> Optional[ValidationResult]:
    """
    Check if ToC patterns are present in extracted text.

    Uses comprehensive ToC patterns from src/preprocessing/constants.py:
    - Standard format: "Item 1A. Risk Factors..... 25"
    - Roman numerals: "Part IV Item 15..... 89"
    - Spaced dots: "Item 1A . . . . . 25"
    - Middle-dot leaders: "Item 1A · · · · · 25"
    - Alternative separators: "Item 1A ━━━━━ 25"
    - Subsection numbering: "Item 1A.1..... 45"
    - No period after Item: "Item 1A Risk Factors..... 25"
    - Leader-only: "Item 1A....."
    - Table of Contents headers
    - Sequential page numbers
    """
    threshold = METRICS_CONFIG.get("toc_filtering_rate")
    if not threshold:
        return None

    # Use comprehensive ToC patterns from constants.py
    has_toc = False

    # Check our new compiled patterns
    for pattern in TOC_PATTERNS_COMPILED:
        if pattern.search(text):
            has_toc = True
            break

    # Additional legacy patterns not in constants
    if not has_toc:
        legacy_toc_patterns = [
            r'Table\s+of\s+Contents',
            r'Page\s+\d+\s+Page\s+\d+\s+Page\s+\d+',  # Sequential pages
        ]
        has_toc = any(re.search(pat, text, re.IGNORECASE) for pat in legacy_toc_patterns)

    # Pass if NO ToC patterns found (filtering worked)
    filtering_rate = 0.0 if has_toc else 1.0

    return ValidationResult.from_threshold(threshold, filtering_rate)


def _check_page_header_filtering_rate(data: Dict, text: str) -> Optional[ValidationResult]:
    """
    Check rate of page headers filtered from content.

    Research finding (line 114-128): Page headers like "Apple Inc. | 2021 Form 10-K | 6"
    incorrectly captured as subsections.

    Check both text content AND subsections list.
    """
    threshold = METRICS_CONFIG.get("page_header_filtering_rate")
    if not threshold:
        return None

    # Pattern from research (line 246-248)
    page_header_pattern = re.compile(r'.+\|\s*\d{4}\s+Form\s+\d+-[KQ]\s*\|\s*\d+')

    # Check text content
    text_has_headers = bool(page_header_pattern.search(text))

    # Check subsections
    subsections = data.get("subsections", [])
    subsection_headers = sum(1 for sub in subsections if page_header_pattern.match(sub))

    total_checks = 1 + len(subsections)  # Text + each subsection
    failed_checks = (1 if text_has_headers else 0) + subsection_headers

    filtering_rate = 1.0 - (failed_checks / total_checks) if total_checks > 0 else 1.0

    return ValidationResult.from_threshold(threshold, filtering_rate)


def _check_subsection_classification_accuracy(data: Dict) -> Optional[ValidationResult]:
    """
    Check accuracy of subsection vs page header classification.

    Research finding (line 114-128): ~60% accuracy due to page headers
    incorrectly classified as subsections.

    Evidence: 17 subsections, 10 invalid (page headers) = 41% valid.
    """
    threshold = METRICS_CONFIG.get("subsection_classification_accuracy")
    if not threshold:
        return None

    subsections = data.get("subsections", [])
    if not subsections:
        return ValidationResult.from_threshold(threshold, 1.0)

    # Page header pattern
    page_header_pattern = re.compile(r'.+\|\s*\d{4}\s+Form\s+\d+-[KQ]\s*\|\s*\d+')

    # Count valid subsections (NOT page headers)
    valid_subsections = sum(
        1 for sub in subsections
        if not page_header_pattern.match(sub)
    )

    accuracy = valid_subsections / len(subsections) if subsections else 1.0

    return ValidationResult.from_threshold(threshold, accuracy)


def _check_noise_to_signal_ratio(text: str) -> Optional[ValidationResult]:
    """
    Compute ratio of noise artifacts to meaningful content.

    Noise indicators:
    - Page headers
    - HTML artifacts (should be 0 after cleaning)
    - Excessive whitespace
    - Page numbers
    """
    threshold = METRICS_CONFIG.get("noise_to_signal_ratio")
    if not threshold:
        return None

    # Count noise characters
    noise_chars = 0

    # Page headers
    page_headers = re.findall(r'.+\|\s*\d{4}\s+Form\s+\d+-[KQ]\s*\|\s*\d+', text)
    noise_chars += sum(len(h) for h in page_headers)

    # HTML artifacts
    html_tags = re.findall(r'<[^>]+>', text)
    noise_chars += sum(len(tag) for tag in html_tags)

    # Excessive whitespace (more than 3 consecutive spaces/newlines)
    excess_ws = re.findall(r'\s{4,}', text)
    noise_chars += sum(len(ws) - 1 for ws in excess_ws)  # 1 space is legitimate

    total_chars = len(text)
    ratio = noise_chars / total_chars if total_chars > 0 else 0.0

    return ValidationResult.from_threshold(threshold, ratio)


def validate_single_extraction(file_path: Path) -> Dict[str, Any]:
    """
    Validate a single extracted risk JSON file against QA metrics from config.

    Args:
        file_path: Path to extracted risk JSON file

    Returns:
        Validation result dict with per-metric ValidationResult objects
    """
    start_time = time.time()

    try:
        # Load JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Initialize results
        metrics_results = {}

        # Metric 1: Valid identifier
        identifier = data.get("identifier", "").lower()
        valid_identifiers = {"part1item1a", "item1a", "part2item1a"}
        has_valid_id = any(vid in identifier for vid in valid_identifiers)
        metrics_results["valid_identifier"] = {
            "status": "PASS" if has_valid_id else "FAIL",
            "actual": identifier,
            "expected": "Contains one of: " + ", ".join(valid_identifiers)
        }

        # Metric 2: Has title
        title = data.get("title", "")
        has_title = len(title) > 0
        metrics_results["has_title"] = {
            "status": "PASS" if has_title else "FAIL",
            "actual": f"'{title[:50]}...'" if title else "(empty)",
            "expected": "Non-empty title"
        }

        # Metric 3: Title mentions risk
        mentions_risk = "risk" in title.lower() if title else False
        metrics_results["title_mentions_risk"] = {
            "status": "PASS" if mentions_risk else "WARN",
            "actual": f"'{title}'",
            "expected": "Title contains 'risk'"
        }

        # Metric 4: Substantial content
        text = data.get("text", "")
        text_length = len(text)
        has_substance = text_length > 1000
        metrics_results["substantial_content"] = {
            "status": "PASS" if has_substance else "FAIL",
            "actual": f"{text_length} chars",
            "expected": ">1000 chars"
        }

        # Metric 5: Character count in reasonable range
        in_range = 5000 <= text_length <= 50000
        metrics_results["char_count_in_range"] = {
            "status": "PASS" if in_range else "WARN",
            "actual": f"{text_length} chars",
            "expected": "5,000 - 50,000 chars"
        }

        # Metric 6: No page headers
        # PAGE_HEADER_PATTERN is already a compiled pattern from constants
        page_headers_found = bool(PAGE_HEADER_PATTERN.search(text))
        metrics_results["no_page_headers"] = {
            "status": "FAIL" if page_headers_found else "PASS",
            "actual": "Found page headers" if page_headers_found else "No page headers",
            "expected": "No page header patterns in text"
        }

        # Metric 7: Has subsections
        subsections = data.get("subsections", [])
        has_subsections = len(subsections) > 0
        metrics_results["has_subsections"] = {
            "status": "PASS" if has_subsections else "WARN",
            "actual": f"{len(subsections)} subsections",
            "expected": ">0 subsections"
        }

        # Metric 8: Keyword density
        words = text.lower().split()
        risk_word_count = sum(1 for w in words if w in RISK_KEYWORDS)
        density = (risk_word_count / len(words) * 100) if words else 0
        good_density = density > 0.5
        metrics_results["keyword_density"] = {
            "status": "PASS" if good_density else "WARN",
            "actual": f"{density:.2f}%",
            "expected": ">0.5%"
        }

        # === NEW CONFIG-BASED METRICS ===

        # Metric 9: Section boundary precision (start)
        vr = _check_section_boundary_precision_start(data, text)
        if vr:
            metrics_results["section_boundary_precision_start"] = {
                "status": vr.status.value,
                "actual": vr.actual,
                "expected": vr.target
            }

        # Metric 10: Section boundary precision (end)
        vr = _check_section_boundary_precision_end(data, text)
        if vr:
            metrics_results["section_boundary_precision_end"] = {
                "status": vr.status.value,
                "actual": vr.actual,
                "expected": vr.target
            }

        # Metric 11: Key item recall
        vr = _check_key_item_recall(data)
        if vr:
            metrics_results["key_item_recall"] = {
                "status": vr.status.value,
                "actual": vr.actual,
                "expected": vr.target
            }

        # Metric 12: ToC filtering rate
        vr = _check_toc_filtering_rate(text)
        if vr:
            metrics_results["toc_filtering_rate"] = {
                "status": vr.status.value,
                "actual": vr.actual,
                "expected": vr.target
            }

        # Metric 13: Page header filtering rate
        vr = _check_page_header_filtering_rate(data, text)
        if vr:
            metrics_results["page_header_filtering_rate"] = {
                "status": vr.status.value,
                "actual": vr.actual,
                "expected": vr.target
            }

        # Metric 13: Subsection classification accuracy
        vr = _check_subsection_classification_accuracy(data)
        if vr:
            metrics_results["subsection_classification_accuracy"] = {
                "status": vr.status.value,
                "actual": vr.actual,
                "expected": vr.target
            }

        # Metric 14: Noise to signal ratio
        vr = _check_noise_to_signal_ratio(text)
        if vr:
            metrics_results["noise_to_signal_ratio"] = {
                "status": vr.status.value,
                "actual": vr.actual,
                "expected": vr.target
            }

        # Determine overall status using METRICS_CONFIG
        blocking_failures = [
            k for k, v in metrics_results.items()
            if k in METRICS_CONFIG and METRICS_CONFIG[k].blocking and v["status"] == "FAIL"
        ]
        warnings = [k for k, v in metrics_results.items() if v["status"] == "WARN"]

        if blocking_failures:
            overall_status = "FAIL"
        elif warnings:
            overall_status = "WARN"
        else:
            overall_status = "PASS"

        return {
            "file": file_path.name,
            "file_path": str(file_path),
            "status": "success",
            "overall_status": overall_status,
            "metrics": metrics_results,
            "blocking_failures": blocking_failures,
            "warnings": warnings,
            "elapsed_time": time.time() - start_time,
            "error": None
        }

    except Exception as e:
        return {
            "file": file_path.name,
            "file_path": str(file_path),
            "status": "error",
            "overall_status": "ERROR",
            "metrics": {},
            "blocking_failures": [],
            "warnings": [],
            "elapsed_time": time.time() - start_time,
            "error": str(e)
        }


# =============================================================================
# Global worker state
# =============================================================================

_worker_initialized = False


def _init_worker() -> None:
    """Initialize worker process (if needed for future extensions)."""
    global _worker_initialized
    _worker_initialized = True


def validate_single_extraction_worker(args: Tuple[Path, bool]) -> Dict[str, Any]:
    """Worker function for parallel validation."""
    file_path, verbose = args
    return validate_single_extraction(file_path)


# =============================================================================
# Report Generation
# =============================================================================

def generate_consolidated_json_report(
    run_dir: Path,
    per_file_results: List[Dict],
    metadata: Dict
) -> Dict[str, Any]:
    """Generate consolidated JSON report."""
    # Count statuses
    passed = sum(1 for r in per_file_results if r['overall_status'] == 'PASS')
    warned = sum(1 for r in per_file_results if r['overall_status'] == 'WARN')
    failed = sum(1 for r in per_file_results if r['overall_status'] == 'FAIL')
    errors = sum(1 for r in per_file_results if r['status'] == 'error')

    # Aggregate metric statistics using METRICS_CONFIG
    metric_stats = {}
    for metric_key in METRICS_CONFIG:
        metric_passes = sum(
            1 for r in per_file_results
            if r['status'] == 'success' and r['metrics'].get(metric_key, {}).get('status') == 'PASS'
        )
        metric_fails = sum(
            1 for r in per_file_results
            if r['status'] == 'success' and r['metrics'].get(metric_key, {}).get('status') == 'FAIL'
        )
        metric_warns = sum(
            1 for r in per_file_results
            if r['status'] == 'success' and r['metrics'].get(metric_key, {}).get('status') == 'WARN'
        )
        total_validated = len([r for r in per_file_results if r['status'] == 'success'])

        threshold = METRICS_CONFIG[metric_key]
        metric_stats[metric_key] = {
            "display_name": threshold.display_name,
            "category": threshold.category,
            "blocking": threshold.blocking,
            "passed": metric_passes,
            "failed": metric_fails,
            "warned": metric_warns,
            "pass_rate": metric_passes / total_validated if total_validated > 0 else 0
        }

    # Determine overall status
    if failed > 0:
        overall_status = "FAIL"
    elif warned > 0:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        "status": overall_status,
        "timestamp": datetime.datetime.now().isoformat(),
        "run_directory": str(run_dir),
        "metadata": metadata,
        "total_files": len(per_file_results),
        "files_validated": len([r for r in per_file_results if r['status'] == 'success']),
        "overall_summary": {
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "errors": errors
        },
        "metric_statistics": metric_stats,
        "per_file_results": per_file_results
    }


def generate_markdown_report(report: Dict) -> str:
    """Generate markdown QA report from consolidated JSON report."""
    meta = report["metadata"]
    summary = report["overall_summary"]
    metric_stats = report["metric_statistics"]

    md = f"""# SEC Section Extractor QA Report (Batch)

**Status**: `{report['status']}`
**Source**: Batch validation of extracted risk files

## 0. Run Environment (Metadata)

| Key | Value |
|-----|-------|
| **Timestamp** | `{meta['timestamp']}` |
| **Researcher** | `{meta['researcher']}` |
| **Git Commit** | `{meta['git_commit']}` (Branch: `{meta['git_branch']}`) |
| **Python** | `{meta['python_version']}` |
| **Platform** | `{meta['platform']}` |
| **Run Directory** | `{report['run_directory']}` |

---

## 1. Executive Summary

This report validates {report['total_files']} extracted risk factor files against QA metrics.

**File Status Summary**:
*   ✅ **Passed**: {summary['passed']}
*   ⚠️ **Warned**: {summary['warned']}
*   ❌ **Failed**: {summary['failed']}
*   🔴 **Errors**: {summary['errors']}

### Metric Performance

| Metric Category | Metric Name | Pass Rate | Passed | Failed | Warned | Blocking |
|-----------------|-------------|-----------|--------|--------|--------|----------|
"""

    # Add metric rows grouped by category
    categories = {}
    for metric_key, stats in metric_stats.items():
        cat = stats["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((metric_key, stats))

    for category in ["Boundary Detection", "Content Quality", "Benchmarking"]:
        if category in categories:
            for metric_key, stats in categories[category]:
                blocking_icon = "🔒" if stats["blocking"] else ""
                pass_rate = f"{stats['pass_rate']*100:.1f}%"
                md += f"| **{stats['category']}** | {stats['display_name']} {blocking_icon} | {pass_rate} | {stats['passed']} | {stats['failed']} | {stats['warned']} | {'Yes' if stats['blocking'] else 'No'} |\n"

    md += f"""
---

## 2. Detailed Findings

### 2.1 Critical Metrics (Blocking)

"""

    # Add critical metrics details
    for metric_key, stats in metric_stats.items():
        if stats["blocking"]:
            status_icon = "✅" if stats["pass_rate"] == 1.0 else "❌"
            md += f"*   {status_icon} **{stats['display_name']}**: {stats['passed']}/{report['files_validated']} files passed ({stats['pass_rate']*100:.1f}%)\n"

    md += f"""
### 2.2 Quality Metrics (Non-Blocking)

"""

    # Add non-blocking metrics
    for metric_key, stats in metric_stats.items():
        if not stats["blocking"]:
            status_icon = "✅" if stats["pass_rate"] > 0.8 else "⚠️"
            md += f"*   {status_icon} **{stats['display_name']}**: {stats['passed']}/{report['files_validated']} files passed ({stats['pass_rate']*100:.1f}%)\n"

    md += f"""
---

## 3. Failed Files

"""

    failed_files = [r for r in report['per_file_results'] if r['overall_status'] in ['FAIL', 'ERROR']]
    if failed_files:
        md += f"Total failed files: {len(failed_files)}\n\n"
        for result in failed_files[:20]:  # Limit to first 20
            md += f"### {result['file']}\n\n"
            md += f"**Status**: {result['overall_status']}\n\n"
            if result['status'] == 'error':
                md += f"**Error**: {result['error']}\n\n"
            else:
                md += "**Failed Metrics**:\n"
                for metric_key in result.get('blocking_failures', []):
                    metric_result = result['metrics'][metric_key]
                    threshold = METRICS_CONFIG.get(metric_key)
                    display_name = threshold.display_name if threshold else metric_key
                    md += f"*   ❌ {display_name}: {metric_result['actual']} (Expected: {metric_result['expected']})\n"
                md += "\n"
    else:
        md += "No failed files! All extractions passed QA checks.\n\n"

    md += f"""
---

## 4. Summary

**Overall Status**: `{report['status']}`

"""

    if report['status'] == 'PASS':
        md += "All extractions passed QA validation. The extraction pipeline is performing well.\n"
    elif report['status'] == 'WARN':
        md += f"{summary['warned']} files have warnings but no blocking failures. Review non-critical metrics for potential improvements.\n"
    else:
        md += f"{summary['failed']} files failed QA validation. Review failed metrics and fix extraction issues before proceeding.\n"

    return md


def print_summary(report: Dict, verbose: bool = False) -> None:
    """Print human-readable summary."""
    print(f"\n{'='*60}")
    print(f"Extractor QA Report: {report['status']}")
    print(f"{'='*60}")
    print(f"  Run directory: {report['run_directory']}")
    print(f"  Total files: {report['total_files']}")
    print(f"  Validated: {report['files_validated']}")

    summary = report['overall_summary']
    print(f"\n  File Status:")
    print(f"    Passed: {summary['passed']}")
    print(f"    Warned: {summary['warned']}")
    print(f"    Failed: {summary['failed']}")
    print(f"    Errors: {summary['errors']}")

    print(f"\n  Top Metrics:")
    metric_stats = report['metric_statistics']
    for metric_key in ["valid_identifier", "substantial_content", "has_title"]:
        stats = metric_stats[metric_key]
        print(f"    {stats['display_name']}: {stats['pass_rate']*100:.1f}% pass rate")

    if verbose and report.get('per_file_results'):
        print(f"\n{'='*60}")
        print("Per-File Results:")
        print(f"{'='*60}")
        for result in report['per_file_results'][:50]:  # Limit output
            status_icon = {
                'PASS': '[PASS]',
                'WARN': '[WARN]',
                'FAIL': '[FAIL]',
                'ERROR': '[ERR ]'
            }.get(result['overall_status'], '[----]')

            print(f"  {status_icon} {result['file']}")
            if result['status'] == 'error':
                print(f"         Error: {result['error']}")

    print(f"\n{'='*60}")
    if report['status'] == 'PASS':
        print("Result: ALL CHECKS PASSED")
    elif report['status'] == 'WARN':
        print("Result: PASSED WITH WARNINGS")
    else:
        print("Result: CHECKS FAILED")
    print(f"{'='*60}")


# =============================================================================
# Batch Orchestrator (REFACTORED to use shared utilities)
# =============================================================================

def batch_generate_extractor_qa_report(
    run_dir: Path,
    output_path: Optional[Path] = None,
    output_format: str = "json",
    max_workers: Optional[int] = None,
    checkpoint_interval: int = 10,
    resume: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Generate batch extractor QA report with parallel processing.

    Args:
        run_dir: Directory containing extracted risk JSON files
        output_path: Output path for report
        output_format: "json" or "markdown"
        max_workers: Number of parallel workers
        checkpoint_interval: Save checkpoint every N files
        resume: Resume from checkpoint
        verbose: Verbose output

    Returns:
        Consolidated report dict
    """
    # Gather metadata
    metadata = RunMetadata.gather()

    # Parse run_dir metadata for naming convention
    run_metadata = parse_run_dir_metadata(run_dir)

    # Setup paths using naming convention
    if output_path is None:
        ext = "json" if output_format == "json" else "md"

        # Generate output filename following naming convention
        # Pattern: extractor_qa_report_{run_id}_{name}_{git_sha}.{ext}
        filename = format_output_filename("extractor_qa_report", run_metadata, ext)
        output_path = run_dir / filename

    checkpoint = CheckpointManager(run_dir / "_extractor_qa_checkpoint.json")

    # Find all extracted risk JSON files
    json_files = sorted([
        f for f in run_dir.glob("*extracted*.json")
        if not f.name.startswith("_")
    ])

    if not json_files:
        return {
            "status": "ERROR",
            "message": f"No extracted risk JSON files found in: {run_dir}",
            "timestamp": datetime.datetime.now().isoformat(),
            "run_directory": str(run_dir),
            "metadata": metadata
        }

    total_files_found = len(json_files)
    print(f"Found {total_files_found} extracted risk files in: {run_dir}")

    # Resume from checkpoint if requested
    processed_files = []
    all_results = []
    current_metrics = {}

    if resume and checkpoint.exists():
        validated_set, all_results, current_metrics = checkpoint.load()
        processed_files = list(validated_set)
        json_files = [f for f in json_files if f.name not in validated_set]
        if validated_set:
            print(f"Resuming: {len(processed_files)} files already validated, {len(json_files)} remaining")

    if not json_files:
        print("All files already validated!")
        if all_results:
            report = generate_consolidated_json_report(run_dir, all_results, metadata)
            if output_format == "markdown":
                md_content = generate_markdown_report(report)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            else:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, default=str)
            return report

    # Create parallel processor
    processor = ParallelProcessor(
        max_workers=max_workers,
        initializer=_init_worker,
        max_tasks_per_child=50
    )

    # Determine processing mode
    use_parallel = processor.should_use_parallel(len(json_files), max_workers)
    if use_parallel:
        workers = max_workers or min(os.cpu_count() or 4, len(json_files))
        print(f"Using {workers} parallel workers")
    else:
        print("Using sequential processing")

    # Process files with checkpoint callback
    start_time = time.time()

    def checkpoint_callback(idx: int, result: Dict):
        """Save checkpoint periodically."""
        all_results.append(result)
        processed_files.append(result['file'])

        if idx % checkpoint_interval == 0:
            current_metrics = {
                "total_files": total_files_found,
                "processed": len(processed_files)
            }
            checkpoint.save(processed_files, all_results, current_metrics)

    # Prepare task arguments
    task_args = [(f, verbose) for f in json_files]

    # Process batch
    results = processor.process_batch(
        items=task_args,
        worker_func=validate_single_extraction_worker,
        progress_callback=checkpoint_callback,
        verbose=verbose
    )

    # Ensure all results are captured
    for result in results:
        if result['file'] not in processed_files:
            all_results.append(result)
            processed_files.append(result['file'])

    elapsed_time = time.time() - start_time
    print(f"\nCompleted in {elapsed_time:.2f} seconds")

    # Generate report
    report = generate_consolidated_json_report(run_dir, all_results, metadata)

    # Save report
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_format == "markdown":
        md_content = generate_markdown_report(report)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
    else:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)

    print(f"Report saved to: {output_path}")

    # Clean up checkpoint
    checkpoint.cleanup()

    return report


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate batch extractor QA report with parallel processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Directory containing extracted risk JSON files"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path for report (default: {run-dir}/extractor_qa_report.{ext})"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format: json or markdown (default: json)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        help="Number of parallel workers (default: CPU count, use 1 for sequential)"
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Save checkpoint every N files (default: 10)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if exists"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress per file"
    )

    args = parser.parse_args()

    # Validate run directory
    if not args.run_dir.exists():
        print(f"Error: Directory not found: {args.run_dir}")
        sys.exit(1)

    if not args.run_dir.is_dir():
        print(f"Error: Not a directory: {args.run_dir}")
        sys.exit(1)

    # Run batch QA report generation
    print(f"Starting batch extractor QA report on: {args.run_dir}")
    report = batch_generate_extractor_qa_report(
        run_dir=args.run_dir,
        output_path=args.output,
        output_format=args.format,
        max_workers=args.max_workers,
        checkpoint_interval=args.checkpoint_interval,
        resume=args.resume,
        verbose=args.verbose
    )

    # Handle error case
    if report.get("status") == "ERROR":
        print(f"Error: {report.get('message', 'Unknown error')}")
        sys.exit(1)

    # Print summary
    print_summary(report, verbose=args.verbose)

    # Exit code: fail if critical failures
    if report['status'] == 'FAIL':
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
