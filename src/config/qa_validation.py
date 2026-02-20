"""
QA Validation configuration for flexible test thresholds.

This module provides:
1. Schema-based threshold definitions loaded from configs/qa_validation/*.yaml
2. ThresholdRegistry for querying thresholds by category/name
3. ValidationResult for comparing actual values against thresholds
4. Auto-generation of Go/No-Go validation tables

Configuration files:
    configs/qa_validation/
    ├── extraction.yaml   # Section extractor and content quality thresholds
    ├── parsing.yaml      # SEC parser performance and stability thresholds
    ├── cleaning.yaml     # Cleaner and segmenter thresholds
    ├── features.yaml     # Sentiment and readability analysis thresholds
    └── health_check.yaml # Data health check thresholds (identity, cleanliness, substance)

Usage:
    from src.config.qa_validation import (
        ThresholdRegistry,
        ValidationResult,
        qa_validation_config
    )

    # Get a threshold definition
    threshold = ThresholdRegistry.get("key_item_recall")

    # Validate an actual measurement
    result = ValidationResult.from_threshold(threshold, actual=0.98)
    print(result.status)  # "PASS"
    print(result.go_no_go)  # "GO"

    # Get all thresholds in a category
    accuracy_thresholds = ThresholdRegistry.by_category("extraction_accuracy")
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


# QA validation config files to load
_QA_VALIDATION_FILES = [
    "qa_validation/extraction.yaml",
    "qa_validation/parsing.yaml",
    "qa_validation/cleaning.yaml",
    "qa_validation/features.yaml",
    "qa_validation/health_check.yaml",
]


def _get_config() -> dict:
    """
    Load and merge all QA validation config files.

    Loads from configs/qa_validation/*.yaml and merges categories and thresholds.
    """
    merged = {
        "schema_version": "1.0.0",
        "categories": {},
        "thresholds": {},
    }

    for config_file in _QA_VALIDATION_FILES:
        data = load_yaml_section(config_file)
        if not data:
            continue

        # Merge categories
        for cat_name, cat_config in data.get("categories", {}).items():
            merged["categories"][cat_name] = cat_config

        # Merge thresholds
        for cat_name, thresholds in data.get("thresholds", {}).items():
            if cat_name not in merged["thresholds"]:
                merged["thresholds"][cat_name] = {}
            merged["thresholds"][cat_name].update(thresholds)

    return merged


# =============================================================================
# Enums
# =============================================================================

class MetricType(str, Enum):
    """Supported metric value types for threshold validation."""
    RATE = "rate"           # 0.0 - 1.0 (precision, recall, success_rate)
    COUNT = "count"         # Integer counts (segment_count, word_count)
    SCORE = "score"         # 0 - 100 scale (gini, obfuscation_score)
    LATENCY = "latency"     # Seconds (p95_latency, avg_processing_time)
    BOOLEAN = "boolean"     # True/False (is_implemented, is_idempotent)
    RANGE = "range"         # Min-max bounded (char_count, fk_grade)


class ThresholdOperator(str, Enum):
    """Comparison operators for threshold validation."""
    GTE = ">="      # Greater than or equal (for rates, recall)
    GT = ">"        # Greater than
    LTE = "<="      # Less than or equal (for latency, error_rate)
    LT = "<"        # Less than
    EQ = "=="       # Equal (for booleans)
    BETWEEN = "[]"  # Between min and max (for ranges)


class ValidationStatus(str, Enum):
    """Status values for validation results."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    NA = "N/A"


class GoNoGo(str, Enum):
    """Go/No-Go decision values."""
    GO = "GO"
    NO_GO = "NO-GO"
    CONDITIONAL = "CONDITIONAL"
    NA = "N/A"


# =============================================================================
# Pydantic Models
# =============================================================================

class ThresholdDefinition(BaseModel):
    """Schema for defining a single QA threshold."""

    # Identity
    name: str = Field(..., description="Unique threshold identifier")
    display_name: str = Field(..., description="Human-readable name")
    category: str = Field(default="", description="Category (set by registry)")

    # Type and validation
    metric_type: MetricType = Field(
        default=MetricType.RATE,
        description="Value type for validation"
    )
    unit: Optional[str] = Field(None, description="Unit of measurement")

    # Thresholds
    target: Union[float, int, bool, None] = Field(
        None,
        description="Target value for pass/fail"
    )
    operator: ThresholdOperator = Field(
        default=ThresholdOperator.GTE,
        description="Comparison operator"
    )
    min_value: Optional[float] = Field(
        None,
        description="Minimum acceptable value (for RANGE type)"
    )
    max_value: Optional[float] = Field(
        None,
        description="Maximum acceptable value (for RANGE type)"
    )
    warn_threshold: Optional[float] = Field(
        None,
        description="Threshold for WARN status (between pass and fail)"
    )

    # Metadata
    description: str = Field(default="", description="Threshold description")
    blocking: bool = Field(
        default=True,
        description="Is this a Go/No-Go blocker?"
    )
    tags: List[str] = Field(default_factory=list, description="Search tags")

    # Versioning
    added_version: str = Field(
        default="1.0.0",
        description="Version threshold was added"
    )
    deprecated_version: Optional[str] = Field(
        None,
        description="Version threshold was deprecated"
    )

    @classmethod
    def from_config(
        cls,
        name: str,
        config: Dict[str, Any],
        category: str = ""
    ) -> "ThresholdDefinition":
        """Create a ThresholdDefinition from config dictionary."""
        return cls(
            name=name,
            display_name=config.get("display_name", name),
            category=category,
            metric_type=MetricType(config.get("metric_type", "rate")),
            unit=config.get("unit"),
            target=config.get("target"),
            operator=ThresholdOperator(config.get("operator", ">=")),
            min_value=config.get("min_value"),
            max_value=config.get("max_value"),
            warn_threshold=config.get("warn_threshold"),
            description=config.get("description", ""),
            blocking=config.get("blocking", True),
            tags=config.get("tags", []),
            added_version=config.get("added_version", "1.0.0"),
            deprecated_version=config.get("deprecated_version"),
        )


class CategoryDefinition(BaseModel):
    """Schema for a threshold category."""

    name: str = Field(..., description="Category identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="Category description")

    @classmethod
    def from_config(cls, name: str, config: Dict[str, Any]) -> "CategoryDefinition":
        """Create a CategoryDefinition from config dictionary."""
        return cls(
            name=name,
            display_name=config.get("display_name", name),
            description=config.get("description", ""),
        )


class ValidationResult(BaseModel):
    """Result of validating a measurement against a threshold."""

    threshold_name: str = Field(..., description="Name of the threshold")
    category: str = Field(default="", description="Category of the threshold")
    display_name: str = Field(default="", description="Human-readable name")
    actual: Union[float, int, bool, None] = Field(
        ...,
        description="Measured value"
    )
    target: Union[float, int, bool, None] = Field(
        None,
        description="Target value"
    )
    status: ValidationStatus = Field(..., description="Validation status")
    go_no_go: GoNoGo = Field(..., description="Go/No-Go decision")
    message: Optional[str] = Field(None, description="Additional context")
    measured_at: datetime = Field(
        default_factory=datetime.now,
        description="When measurement was taken"
    )

    @classmethod
    def from_threshold(
        cls,
        threshold: ThresholdDefinition,
        actual: Union[float, int, bool, None],
        message: Optional[str] = None
    ) -> "ValidationResult":
        """
        Create a ValidationResult by comparing actual value to threshold.

        Args:
            threshold: The threshold definition to validate against
            actual: The measured value
            message: Optional message/context

        Returns:
            ValidationResult with status and go_no_go determined
        """
        status = cls._evaluate_status(threshold, actual)
        go_no_go = cls._determine_go_no_go(threshold, status)

        return cls(
            threshold_name=threshold.name,
            category=threshold.category,
            display_name=threshold.display_name,
            actual=actual,
            target=threshold.target,
            status=status,
            go_no_go=go_no_go,
            message=message,
        )

    @staticmethod
    def _evaluate_status(
        threshold: ThresholdDefinition,
        actual: Union[float, int, bool, None]
    ) -> ValidationStatus:
        """Evaluate validation status based on threshold and actual value."""
        if actual is None:
            return ValidationStatus.SKIP

        target = threshold.target
        operator = threshold.operator
        warn = threshold.warn_threshold

        # Handle boolean type
        if threshold.metric_type == MetricType.BOOLEAN:
            if actual == target:
                return ValidationStatus.PASS
            return ValidationStatus.FAIL

        # Handle range type
        if threshold.metric_type == MetricType.RANGE:
            min_val = threshold.min_value
            max_val = threshold.max_value
            if min_val is not None and actual < min_val:
                return ValidationStatus.FAIL
            if max_val is not None and actual > max_val:
                return ValidationStatus.FAIL
            return ValidationStatus.PASS

        # Handle numeric comparisons
        if target is None:
            return ValidationStatus.NA

        # Determine if passing
        passed = False
        if operator == ThresholdOperator.GTE:
            passed = actual >= target
        elif operator == ThresholdOperator.GT:
            passed = actual > target
        elif operator == ThresholdOperator.LTE:
            passed = actual <= target
        elif operator == ThresholdOperator.LT:
            passed = actual < target
        elif operator == ThresholdOperator.EQ:
            passed = actual == target

        if passed:
            return ValidationStatus.PASS

        # Check for warn threshold
        if warn is not None:
            warn_passed = False
            if operator in (ThresholdOperator.GTE, ThresholdOperator.GT):
                warn_passed = actual >= warn
            elif operator in (ThresholdOperator.LTE, ThresholdOperator.LT):
                warn_passed = actual <= warn

            if warn_passed:
                return ValidationStatus.WARN

        return ValidationStatus.FAIL

    @staticmethod
    def _determine_go_no_go(
        threshold: ThresholdDefinition,
        status: ValidationStatus
    ) -> GoNoGo:
        """Determine Go/No-Go based on status and blocking flag."""
        if status == ValidationStatus.PASS:
            return GoNoGo.GO
        if status == ValidationStatus.SKIP:
            return GoNoGo.NA
        if status == ValidationStatus.NA:
            return GoNoGo.NA
        if status == ValidationStatus.WARN:
            return GoNoGo.CONDITIONAL
        # FAIL status
        if threshold.blocking:
            return GoNoGo.NO_GO
        return GoNoGo.CONDITIONAL


# =============================================================================
# Threshold Registry
# =============================================================================

class ThresholdRegistry:
    """
    Central registry for all QA threshold definitions.

    Loads thresholds from config.yaml and provides query methods.

    Usage:
        # Get a specific threshold
        threshold = ThresholdRegistry.get("key_item_recall")

        # Get all thresholds in a category
        accuracy = ThresholdRegistry.by_category("extraction_accuracy")

        # Get all registered thresholds
        all_thresholds = ThresholdRegistry.all_thresholds()
    """

    _thresholds: Dict[str, ThresholdDefinition] = {}
    _categories: Dict[str, CategoryDefinition] = {}
    _by_category: Dict[str, List[str]] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_loaded(cls) -> None:
        """Ensure thresholds are loaded from config."""
        if cls._initialized:
            return

        config = _get_config()

        # Load categories
        for cat_name, cat_config in config.get("categories", {}).items():
            cls._categories[cat_name] = CategoryDefinition.from_config(
                cat_name, cat_config
            )
            cls._by_category[cat_name] = []

        # Load thresholds
        for cat_name, thresholds in config.get("thresholds", {}).items():
            if cat_name not in cls._by_category:
                cls._by_category[cat_name] = []

            for thresh_name, thresh_config in thresholds.items():
                threshold = ThresholdDefinition.from_config(
                    thresh_name, thresh_config, category=cat_name
                )
                cls._thresholds[thresh_name] = threshold
                cls._by_category[cat_name].append(thresh_name)

        cls._initialized = True

    @classmethod
    def get(cls, name: str) -> Optional[ThresholdDefinition]:
        """Get a threshold definition by name."""
        cls._ensure_loaded()
        return cls._thresholds.get(name)

    @classmethod
    def by_category(cls, category: str) -> List[ThresholdDefinition]:
        """Get all thresholds in a category."""
        cls._ensure_loaded()
        names = cls._by_category.get(category, [])
        return [cls._thresholds[n] for n in names if n in cls._thresholds]

    @classmethod
    def all_thresholds(cls) -> List[ThresholdDefinition]:
        """Get all registered thresholds."""
        cls._ensure_loaded()
        return list(cls._thresholds.values())

    @classmethod
    def all_categories(cls) -> List[CategoryDefinition]:
        """Get all registered categories."""
        cls._ensure_loaded()
        return list(cls._categories.values())

    @classmethod
    def category_names(cls) -> List[str]:
        """Get list of category names."""
        cls._ensure_loaded()
        return list(cls._by_category.keys())

    @classmethod
    def by_tag(cls, tag: str) -> List[ThresholdDefinition]:
        """Get all thresholds with a specific tag."""
        cls._ensure_loaded()
        return [t for t in cls._thresholds.values() if tag in t.tags]

    @classmethod
    def blocking_thresholds(cls) -> List[ThresholdDefinition]:
        """Get all blocking (Go/No-Go) thresholds."""
        cls._ensure_loaded()
        return [t for t in cls._thresholds.values() if t.blocking]

    @classmethod
    def reload(cls) -> None:
        """Reload thresholds from config (clears cache)."""
        cls._thresholds.clear()
        cls._categories.clear()
        cls._by_category.clear()
        cls._initialized = False
        cls._ensure_loaded()


# =============================================================================
# Pydantic Settings Config
# =============================================================================

class QAValidationConfig(BaseSettings):
    """QA validation configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix='QA_VALIDATION_',
        case_sensitive=False
    )

    schema_version: str = Field(
        default_factory=lambda: _get_config().get('schema_version', '1.0.0')
    )

    @property
    def registry(self) -> type[ThresholdRegistry]:
        """Access the threshold registry."""
        return ThresholdRegistry


# =============================================================================
# Report Generation Helpers
# =============================================================================

def generate_validation_table(
    results: List[ValidationResult]
) -> List[Dict[str, Any]]:
    """
    Generate a Go/No-Go validation table from results.

    Args:
        results: List of ValidationResult objects

    Returns:
        List of dicts suitable for JSON serialization
    """
    return [
        {
            "category": r.category,
            "metric": r.threshold_name,
            "display_name": r.display_name,
            "target": r.target,
            "actual": r.actual,
            "status": r.status.value,
            "go_no_go": r.go_no_go.value,
        }
        for r in results
    ]


def generate_blocking_summary(results: List[ValidationResult]) -> Dict[str, Any]:
    """
    Generate summary of blocking threshold results.

    Args:
        results: List of ValidationResult objects

    Returns:
        Summary dict with pass/fail counts
    """
    blocking_results = [
        r for r in results
        if ThresholdRegistry.get(r.threshold_name)
        and ThresholdRegistry.get(r.threshold_name).blocking
    ]

    passed = sum(1 for r in blocking_results if r.status == ValidationStatus.PASS)
    failed = sum(1 for r in blocking_results if r.status == ValidationStatus.FAIL)
    warned = sum(1 for r in blocking_results if r.status == ValidationStatus.WARN)

    return {
        "total_blocking": len(blocking_results),
        "passed": passed,
        "failed": failed,
        "warned": warned,
        "all_pass": failed == 0,
    }


def determine_overall_status(results: List[ValidationResult]) -> ValidationStatus:
    """
    Determine overall status from a list of results.

    Returns FAIL if any blocking threshold failed, WARN if any warned,
    PASS otherwise.
    """
    for r in results:
        threshold = ThresholdRegistry.get(r.threshold_name)
        if threshold and threshold.blocking:
            if r.status == ValidationStatus.FAIL:
                return ValidationStatus.FAIL

    for r in results:
        if r.status == ValidationStatus.WARN:
            return ValidationStatus.WARN

    return ValidationStatus.PASS


# =============================================================================
# Module-level config instance
# =============================================================================

qa_validation_config = QAValidationConfig()


# =============================================================================
# Health Check Validator (Data Quality Checks)
# =============================================================================

import hashlib
import json
import re


class HealthCheckValidator:
    """
    Unified validator for preprocessing output data health.

    Follows the 4-check framework:
    1. Completeness: Identity fields present (CIK, company name)
    2. Cleanliness: No HTML/page number artifacts
    3. Substance: Meaningful content (segment length, word count)
    4. Consistency: No duplicates, proper segmentation

    Usage:
        from src.config.qa_validation import HealthCheckValidator

        validator = HealthCheckValidator()
        report = validator.check_run(Path("data/processed/20251212_..."))
        print(report["status"])  # "PASS" or "FAIL"
    """

    # Artifact detection patterns
    HTML_PATTERN = re.compile(r'<[^>]+>')
    PAGE_NUMBER_PATTERN = re.compile(
        r'\b(Page\s+\d+|\d+\s+of\s+\d+)\b',
        re.IGNORECASE
    )

    # Domain validation
    RISK_KEYWORDS = {
        "risk", "adverse", "material", "uncertain",
        "may", "could", "might", "potential"
    }
    REQUIRED_IDENTITY_FIELDS = ["cik", "company_name"]
    RECOMMENDED_IDENTITY_FIELDS = ["sic_code", "ticker", "form_type"]

    # Substance thresholds
    MIN_SEGMENT_LENGTH = 50
    MAX_SEGMENT_WORDS = 380  # RFC-003 Option A ceiling; ~512 tokens at 1.35 tok/word

    def __init__(self):
        """Initialize the validator with threshold registry."""
        self.registry = ThresholdRegistry

    def check_single(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single in-memory data object (inline validation).

        This method enables inline validation during processing to support
        the quarantine pattern. Files that fail validation are quarantined
        instead of being written to production directories.

        Args:
            data: Dictionary containing preprocessed data (e.g., SegmentedRisks.model_dump())

        Returns:
            Report dict with status ("PASS" or "FAIL"), blocking_summary, and validation_table

        Usage:
            from src.config.qa_validation import HealthCheckValidator

            validator = HealthCheckValidator()
            result = filing.to_dict()  # or segmented_risks.model_dump()
            report = validator.check_single(result)

            if report["status"] == "FAIL":
                # Quarantine the file
                quarantine_file(result, report)
        """
        # Wrap single file in list for consistency with check_run
        file_data = [data]

        # Collect all validation results
        results: List[ValidationResult] = []

        # 1. Identity completeness
        results.extend(self._check_identity(file_data))

        # 2. Cleanliness
        results.extend(self._check_cleanliness(file_data))

        # 3. Substance
        results.extend(self._check_substance(file_data))

        # 4. Domain rules (duplicates, keywords)
        results.extend(self._check_domain(file_data))

        # Generate report using existing infrastructure
        overall_status = determine_overall_status(results)
        blocking_summary = generate_blocking_summary(results)

        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "blocking_summary": blocking_summary,
            "validation_table": generate_validation_table(results),
        }

    def check_run(self, run_dir: Path) -> Dict[str, Any]:
        """
        Run all health checks on a preprocessing run directory.

        Args:
            run_dir: Path to directory containing JSON output files

        Returns:
            Report dict with status, summary, and validation table
        """
        files = list(run_dir.glob("*.json"))
        if not files:
            return {"status": "ERROR", "message": "No JSON files found"}

        # Load all file data
        file_data = []
        for f in files:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                data["_source_file"] = str(f)
                file_data.append(data)

        # Collect all validation results
        results: List[ValidationResult] = []

        # 1. Identity completeness
        results.extend(self._check_identity(file_data))

        # 2. Cleanliness
        results.extend(self._check_cleanliness(file_data))

        # 3. Substance
        results.extend(self._check_substance(file_data))

        # 4. Domain rules (duplicates, keywords)
        results.extend(self._check_domain(file_data))

        # Generate report using existing infrastructure
        overall_status = determine_overall_status(results)
        blocking_summary = generate_blocking_summary(results)

        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "run_directory": str(run_dir),
            "files_checked": len(files),
            "blocking_summary": blocking_summary,
            "validation_table": generate_validation_table(results),
        }

    def _check_identity(self, file_data: List[Dict]) -> List[ValidationResult]:
        """Check identity field completeness."""
        results = []
        total = len(file_data)
        if total == 0:
            return results

        cik_present = sum(1 for f in file_data if f.get("cik"))
        company_present = sum(1 for f in file_data if f.get("company_name"))
        sic_present = sum(1 for f in file_data if f.get("sic_code"))

        # CIK rate
        threshold = self.registry.get("cik_present_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, cik_present / total
            ))

        # Company name rate
        threshold = self.registry.get("company_name_present_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, company_present / total
            ))

        # SIC code rate
        threshold = self.registry.get("sic_code_present_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, sic_present / total
            ))

        return results

    def _check_cleanliness(self, file_data: List[Dict]) -> List[ValidationResult]:
        """Check for HTML and page number artifacts."""
        results = []
        total_segments = 0
        html_artifacts = 0
        page_artifacts = 0

        for data in file_data:
            for seg in data.get("segments", []):
                total_segments += 1
                text = seg.get("text", "")
                if self.HTML_PATTERN.search(text):
                    html_artifacts += 1
                if self.PAGE_NUMBER_PATTERN.search(text):
                    page_artifacts += 1

        if total_segments == 0:
            return results

        # HTML artifact rate
        threshold = self.registry.get("html_artifact_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, html_artifacts / total_segments
            ))

        # Page number artifact rate
        threshold = self.registry.get("page_number_artifact_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, page_artifacts / total_segments
            ))

        return results

    def _check_substance(self, file_data: List[Dict]) -> List[ValidationResult]:
        """Check content substance (segment length, word count)."""
        results = []
        total_segments = 0
        empty_segments = 0
        short_segments = 0
        over_limit_segments = 0

        for data in file_data:
            for seg in data.get("segments", []):
                total_segments += 1
                length = seg.get("length", len(seg.get("text", "")))
                if length == 0:
                    empty_segments += 1
                elif length < self.MIN_SEGMENT_LENGTH:
                    short_segments += 1
                if seg.get("word_count", 0) > self.MAX_SEGMENT_WORDS:
                    over_limit_segments += 1

        if total_segments == 0:
            return results

        # Empty segment rate
        threshold = self.registry.get("empty_segment_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, empty_segments / total_segments
            ))

        # Short segment rate
        threshold = self.registry.get("short_segment_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, short_segments / total_segments
            ))

        # Over-limit word rate (RFC-003 Option A token-safety gate)
        threshold = self.registry.get("over_limit_word_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, over_limit_segments / total_segments
            ))

        # Smart Integrity Check - File Size Validation
        for data in file_data:
            file_size_bytes = data.get("file_size_bytes")
            sic_code = data.get("sic_code")

            if file_size_bytes:
                # Convert bytes to KB and MB
                file_size_kb = file_size_bytes / 1024
                file_size_mb = file_size_bytes / (1024 * 1024)

                # Check minimum file size (strict floor - blocking)
                threshold = self.registry.get("min_file_size_kb")
                if threshold:
                    results.append(ValidationResult.from_threshold(
                        threshold, file_size_kb
                    ))

                # Check maximum file size with SIC code exemption (flexible ceiling)
                # Financials/REITs (SIC 6000-6799) get 150 MB limit
                # Others get 50 MB limit
                if sic_code and 6000 <= int(sic_code) <= 6799:
                    threshold = self.registry.get("max_file_size_mb_financial")
                else:
                    threshold = self.registry.get("max_file_size_mb_standard")

                if threshold:
                    results.append(ValidationResult.from_threshold(
                        threshold, file_size_mb
                    ))

                # Calculate extraction yield (PPM)
                # Ratio of extracted text chars to raw file bytes
                extracted_chars = sum(len(seg.get("text", "")) for seg in data.get("segments", []))
                if file_size_bytes > 0:
                    yield_ppm = (extracted_chars / file_size_bytes) * 1_000_000
                    threshold = self.registry.get("extraction_yield_ppm")
                    if threshold:
                        results.append(ValidationResult.from_threshold(
                            threshold, yield_ppm
                        ))

        return results

    def _check_domain(self, file_data: List[Dict]) -> List[ValidationResult]:
        """Check SEC-specific domain rules."""
        results = []

        if not file_data:
            return results

        # Duplicate detection via content hash
        hashes: Dict[str, List[str]] = {}
        for data in file_data:
            text = "".join(s.get("text", "") for s in data.get("segments", []))
            normalized = re.sub(r'\s+', ' ', text.lower().strip())
            content_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]

            file_name = data.get("filing_name", data.get("_source_file", "unknown"))
            if content_hash not in hashes:
                hashes[content_hash] = []
            hashes[content_hash].append(file_name)

        duplicate_groups = sum(1 for files in hashes.values() if len(files) > 1)
        duplicate_rate = duplicate_groups / len(file_data)

        threshold = self.registry.get("duplicate_rate")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, duplicate_rate
            ))

        # Risk keyword presence
        total_risk_words = 0
        for data in file_data:
            text = " ".join(s.get("text", "") for s in data.get("segments", []))
            words = re.findall(r'\b\w+\b', text.lower())
            total_risk_words += sum(1 for w in words if w in self.RISK_KEYWORDS)

        threshold = self.registry.get("risk_keyword_present")
        if threshold:
            results.append(ValidationResult.from_threshold(
                threshold, total_risk_words >= 10
            ))

        return results
