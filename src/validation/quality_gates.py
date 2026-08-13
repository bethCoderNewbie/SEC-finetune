"""
Boundary quality validation gates for filing and classification data.

Per-filing and per-record validation at system boundaries between
preprocessing, storage, analysis, and export layers. Reuses existing
HealthCheckValidator thresholds and segment_annotator constants.

See ADR-019 for architectural rationale.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class FilingValidationResult:
    """Result of a per-filing or per-record quality gate check."""

    is_valid: bool  # True only when no blocking failures
    status: str  # "PASS" | "WARN" | "FAIL"
    blocking_failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)


def validate_filing(data: Dict[str, Any]) -> FilingValidationResult:
    """Per-filing quality gate for segmented JSON data.

    Checks structural pre-conditions (ticker, fiscal_year, filed_as_of_date)
    then delegates to HealthCheckValidator.check_single() for rate-based
    checks (identity, cleanliness, substance, domain).

    Args:
        data: Raw dict from a segmented JSON file (supports both v1 and v2 schemas).

    Returns:
        FilingValidationResult with blocking_failures and warnings.
    """
    blocking_failures: List[str] = []
    warnings: List[str] = []
    details: List[Dict[str, Any]] = []

    # --- Structural pre-condition checks (not in YAML) ---

    # Handle both v1 (flat) and v2 (document_info nested) schema
    if "document_info" in data:
        di = data["document_info"]
    else:
        di = data

    # ticker: required (DB unique key)
    ticker = di.get("ticker")
    ticker_ok = bool(ticker and str(ticker).strip())
    details.append({
        "check": "ticker_present",
        "blocking": True,
        "passed": ticker_ok,
    })
    if not ticker_ok:
        blocking_failures.append("ticker_present")

    # fiscal_year: required, must be 4 digits
    fiscal_year = di.get("fiscal_year")
    fy_ok = bool(
        fiscal_year
        and isinstance(fiscal_year, (str, int))
        and re.fullmatch(r"\d{4}", str(fiscal_year))
    )
    details.append({
        "check": "fiscal_year_valid",
        "blocking": True,
        "passed": fy_ok,
    })
    if not fy_ok:
        blocking_failures.append("fiscal_year_valid")

    # filed_as_of_date: recommended (annotator needs it for filing_date)
    filed_date = di.get("filed_as_of_date")
    filed_date_ok = bool(filed_date and str(filed_date).strip())
    details.append({
        "check": "filed_as_of_date_present",
        "blocking": False,
        "passed": filed_date_ok,
    })
    if not filed_date_ok:
        warnings.append("filed_as_of_date_present")

    # If structural pre-conditions already failed, skip the heavier
    # HealthCheckValidator call — we know this filing is invalid.
    if blocking_failures:
        return FilingValidationResult(
            is_valid=False,
            status="FAIL",
            blocking_failures=blocking_failures,
            warnings=warnings,
            details=details,
        )

    # --- Delegate to HealthCheckValidator for rate-based checks ---
    from src.config.qa_validation import HealthCheckValidator

    validator = HealthCheckValidator()
    report = validator.check_single(data)

    # Extract blocking failures and warnings from the validation table
    for row in report.get("validation_table", []):
        detail_entry = {
            "check": row["metric"],
            "blocking": row["go_no_go"] == "NO-GO",
            "passed": row["status"] == "PASS",
            "status": row["status"],
            "actual": row.get("actual"),
            "target": row.get("target"),
        }
        details.append(detail_entry)

        if row["status"] == "FAIL" and row["go_no_go"] == "NO-GO":
            blocking_failures.append(row["metric"])
        elif row["status"] == "WARN":
            warnings.append(row["metric"])

    is_valid = len(blocking_failures) == 0
    if not is_valid:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    return FilingValidationResult(
        is_valid=is_valid,
        status=status,
        blocking_failures=blocking_failures,
        warnings=warnings,
        details=details,
    )


def validate_classification_record(record: Dict[str, Any]) -> FilingValidationResult:
    """Per-record quality gate for annotator output (classification records).

    Validates PRD-002 section 2.2 required fields and ADR-015/ADR-016
    value constraints. Imports constants from segment_annotator to avoid
    hardcoded lists.

    Args:
        record: Single flat dict from SegmentAnnotator.annotate() output.

    Returns:
        FilingValidationResult with blocking_failures and warnings.
    """
    from src.analysis.segment_annotator import (
        ARCHETYPE_LABEL_MAP,
        ARCHETYPE_NAMES,
        _VALID_LABEL_SOURCES,
    )
    from src.config.qa_validation import HealthCheckValidator

    blocking_failures: List[str] = []
    warnings: List[str] = []
    details: List[Dict[str, Any]] = []

    def _check(name: str, passed: bool, blocking: bool = True) -> None:
        details.append({"check": name, "blocking": blocking, "passed": passed})
        if not passed:
            if blocking:
                blocking_failures.append(name)
            else:
                warnings.append(name)

    # --- Blocking checks (PRD-002 §2.2) ---

    # text: non-empty string
    text = record.get("text")
    _check("text_non_empty", bool(text and isinstance(text, str) and text.strip()))

    # label: int in {0..5}
    label = record.get("label")
    valid_labels = set(ARCHETYPE_LABEL_MAP.values())
    _check("label_valid", isinstance(label, int) and label in valid_labels)

    # risk_label: in ARCHETYPE_NAMES
    risk_label = record.get("risk_label")
    _check("risk_label_valid", risk_label in ARCHETYPE_NAMES)

    # confidence: float in [0.0, 1.0]
    confidence = record.get("confidence")
    _check(
        "confidence_in_range",
        isinstance(confidence, (int, float))
        and 0.0 <= float(confidence) <= 1.0,
    )

    # label_source: in _VALID_LABEL_SOURCES
    label_source = record.get("label_source")
    _check("label_source_valid", label_source in _VALID_LABEL_SOURCES)

    # word_count: int > 0
    word_count = record.get("word_count")
    _check(
        "word_count_positive",
        isinstance(word_count, int) and word_count > 0,
    )

    # char_count: int > 0
    char_count = record.get("char_count")
    _check(
        "char_count_positive",
        isinstance(char_count, int) and char_count > 0,
    )

    # ticker: non-empty
    ticker = record.get("ticker")
    _check("ticker_non_empty", bool(ticker and str(ticker).strip()))

    # --- Warning checks ---

    # cik: non-empty (some old filings lack CIK)
    cik = record.get("cik")
    _check("cik_present", bool(cik and str(cik).strip()), blocking=False)

    # word_count in [MIN_SEGMENT_WORDS, MAX_SEGMENT_WORDS]
    if isinstance(word_count, int) and word_count > 0:
        min_words = HealthCheckValidator.MIN_SEGMENT_WORDS
        max_words = HealthCheckValidator.MAX_SEGMENT_WORDS
        _check(
            "word_count_in_range",
            min_words <= word_count <= max_words,
            blocking=False,
        )

    # filing_date: present (needed for time-series analysis)
    filing_date = record.get("filing_date")
    _check(
        "filing_date_present",
        bool(filing_date and str(filing_date).strip()),
        blocking=False,
    )

    # --- Result ---

    is_valid = len(blocking_failures) == 0
    if not is_valid:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    return FilingValidationResult(
        is_valid=is_valid,
        status=status,
        blocking_failures=blocking_failures,
        warnings=warnings,
        details=details,
    )
