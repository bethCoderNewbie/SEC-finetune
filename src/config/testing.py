"""Testing and reproducibility configuration."""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_testing_config() -> dict:
    return load_yaml_section("config.yaml").get("testing", {})


def _get_reproducibility_config() -> dict:
    return load_yaml_section("config.yaml").get("reproducibility", {})


# =============================================================================
# Test Metrics Configuration
# =============================================================================

class TestMetricsConfig:
    """
    Standard configuration for test metrics collection and reporting.

    Provides consistent field names, templates, and helper methods for
    generating test metrics across all test modules.

    Usage:
        from src.config.testing import TestMetricsConfig

        # Create a metrics report
        metrics = TestMetricsConfig.create_report(
            test_name="segmentation_quality",
            summary={"total_items": 100, "success_rate": 0.95}
        )

        # Add performance metrics
        metrics.update(TestMetricsConfig.performance_metrics(
            latencies=[0.1, 0.2, 0.15],
            label="parsing"
        ))

        # Save using fixture
        save_test_artifact("metrics.json", metrics)
    """

    # ===================
    # Standard Field Names
    # ===================

    # Metadata fields
    FIELD_TEST_NAME = "test_name"
    FIELD_TEST_DATE = "test_date"
    FIELD_GIT_SHA = "git_sha"
    FIELD_STATUS = "status"

    # Summary fields
    FIELD_TOTAL = "total"
    FIELD_PASSED = "passed"
    FIELD_FAILED = "failed"
    FIELD_SKIPPED = "skipped"
    FIELD_SUCCESS_RATE = "success_rate"

    # Performance fields
    FIELD_LATENCY_AVG = "latency_avg_seconds"
    FIELD_LATENCY_MIN = "latency_min_seconds"
    FIELD_LATENCY_MAX = "latency_max_seconds"
    FIELD_LATENCY_P50 = "latency_p50_seconds"
    FIELD_LATENCY_P95 = "latency_p95_seconds"
    FIELD_LATENCY_P99 = "latency_p99_seconds"
    FIELD_THROUGHPUT = "throughput_per_second"

    # Quality fields
    FIELD_PRECISION = "precision"
    FIELD_RECALL = "recall"
    FIELD_F1_SCORE = "f1_score"
    FIELD_ACCURACY = "accuracy"

    # Count fields
    FIELD_TOTAL_ITEMS = "total_items"
    FIELD_PROCESSED = "processed"
    FIELD_ERRORS = "errors"
    FIELD_WARNINGS = "warnings"

    # Status values
    STATUS_PASS = "PASS"
    STATUS_FAIL = "FAIL"
    STATUS_WARN = "WARN"
    STATUS_SKIP = "SKIP"

    # ===================
    # Helper Methods
    # ===================

    @classmethod
    def create_report(
        cls,
        test_name: str,
        summary: Optional[Dict[str, Any]] = None,
        status: str = "PASS",
        git_sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a standard metrics report structure.

        Args:
            test_name: Name of the test generating metrics
            summary: Summary metrics dictionary
            status: Overall status (PASS/FAIL/WARN/SKIP)
            git_sha: Git commit SHA (auto-detected if None)

        Returns:
            Structured metrics report dictionary

        Example:
            metrics = TestMetricsConfig.create_report(
                test_name="parser_recall",
                summary={"files_tested": 10, "avg_recall": 0.95},
                status="PASS"
            )
        """
        report = {
            cls.FIELD_TEST_NAME: test_name,
            cls.FIELD_TEST_DATE: datetime.now().isoformat(),
            cls.FIELD_STATUS: status,
        }

        if git_sha:
            report[cls.FIELD_GIT_SHA] = git_sha
        else:
            # Auto-detect git SHA
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    report[cls.FIELD_GIT_SHA] = result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        if summary:
            report["summary"] = summary

        return report

    @classmethod
    def performance_metrics(
        cls,
        latencies: List[float],
        label: str = "operation"
    ) -> Dict[str, Any]:
        """
        Calculate standard performance metrics from latency measurements.

        Args:
            latencies: List of latency values in seconds
            label: Label for the metrics (e.g., "parsing", "extraction")

        Returns:
            Dictionary with performance metrics

        Example:
            perf = TestMetricsConfig.performance_metrics(
                latencies=[0.1, 0.2, 0.15, 0.3],
                label="parsing"
            )
            # Returns: {"parsing_latency_avg_seconds": 0.1875, ...}
        """
        if not latencies:
            return {}

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        def percentile(p: float) -> float:
            idx = int(n * p)
            return sorted_latencies[min(idx, n - 1)]

        prefix = f"{label}_" if label else ""

        return {
            f"{prefix}{cls.FIELD_LATENCY_AVG}": sum(latencies) / n,
            f"{prefix}{cls.FIELD_LATENCY_MIN}": sorted_latencies[0],
            f"{prefix}{cls.FIELD_LATENCY_MAX}": sorted_latencies[-1],
            f"{prefix}{cls.FIELD_LATENCY_P50}": percentile(0.50),
            f"{prefix}{cls.FIELD_LATENCY_P95}": percentile(0.95),
            f"{prefix}{cls.FIELD_LATENCY_P99}": percentile(0.99),
        }

    @classmethod
    def quality_metrics(
        cls,
        true_positives: int,
        false_positives: int,
        false_negatives: int,
        true_negatives: int = 0
    ) -> Dict[str, Any]:
        """
        Calculate standard quality metrics (precision, recall, F1).

        Args:
            true_positives: Count of true positives
            false_positives: Count of false positives
            false_negatives: Count of false negatives
            true_negatives: Count of true negatives (for accuracy)

        Returns:
            Dictionary with quality metrics

        Example:
            quality = TestMetricsConfig.quality_metrics(
                true_positives=90,
                false_positives=5,
                false_negatives=10,
                true_negatives=95
            )
        """
        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0 else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0 else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0 else 0.0
        )

        total = true_positives + false_positives + false_negatives + true_negatives
        accuracy = (
            (true_positives + true_negatives) / total
            if total > 0 else 0.0
        )

        return {
            cls.FIELD_PRECISION: precision,
            cls.FIELD_RECALL: recall,
            cls.FIELD_F1_SCORE: f1,
            cls.FIELD_ACCURACY: accuracy,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "true_negatives": true_negatives,
        }

    @classmethod
    def count_metrics(
        cls,
        total: int,
        processed: int,
        errors: int = 0,
        warnings: int = 0
    ) -> Dict[str, Any]:
        """
        Create standard count/processing metrics.

        Args:
            total: Total items to process
            processed: Successfully processed items
            errors: Number of errors
            warnings: Number of warnings

        Returns:
            Dictionary with count metrics

        Example:
            counts = TestMetricsConfig.count_metrics(
                total=100, processed=95, errors=3, warnings=2
            )
        """
        success_rate = processed / total if total > 0 else 0.0

        return {
            cls.FIELD_TOTAL_ITEMS: total,
            cls.FIELD_PROCESSED: processed,
            cls.FIELD_ERRORS: errors,
            cls.FIELD_WARNINGS: warnings,
            cls.FIELD_SUCCESS_RATE: success_rate,
        }

    @classmethod
    def determine_status(
        cls,
        success_rate: float,
        pass_threshold: float = 0.95,
        warn_threshold: float = 0.80
    ) -> str:
        """
        Determine status based on success rate thresholds.

        Args:
            success_rate: Success rate (0.0 to 1.0)
            pass_threshold: Minimum rate for PASS (default: 0.95)
            warn_threshold: Minimum rate for WARN (default: 0.80)

        Returns:
            Status string: PASS, WARN, or FAIL

        Example:
            status = TestMetricsConfig.determine_status(0.92)  # Returns "WARN"
        """
        if success_rate >= pass_threshold:
            return cls.STATUS_PASS
        elif success_rate >= warn_threshold:
            return cls.STATUS_WARN
        else:
            return cls.STATUS_FAIL

    @classmethod
    def stats_summary(cls, values: List[float], label: str = "") -> Dict[str, Any]:
        """
        Calculate summary statistics for a list of values.

        Args:
            values: List of numeric values
            label: Optional prefix for field names

        Returns:
            Dictionary with min, max, avg, count statistics

        Example:
            stats = TestMetricsConfig.stats_summary(
                [10, 20, 30, 40, 50],
                label="segment_length"
            )
        """
        if not values:
            return {}

        prefix = f"{label}_" if label else ""

        return {
            f"{prefix}count": len(values),
            f"{prefix}min": min(values),
            f"{prefix}max": max(values),
            f"{prefix}avg": sum(values) / len(values),
            f"{prefix}total": sum(values),
        }


class TestDataConfig(BaseSettings):
    """
    Dynamic test data discovery for timestamped run directories.

    Handles path resolution for test data stored in RunContext-created directories.
    Paths follow the pattern: {run_id}_{name}_{git_sha}/

    Usage:
        from src.config import settings

        # Get latest preprocessing run directory
        run_dir = settings.testing.data.find_latest_run("preprocessing")

        # Get specific file from latest run
        path = settings.testing.data.get_test_file(
            run_name="preprocessing",
            filename="AAPL_10K_2021_segmented_risks.json"
        )

        # Find all preprocessing runs
        runs = settings.testing.data.find_runs("preprocessing")
    """
    model_config = SettingsConfigDict(
        env_prefix='TEST_DATA_',
        case_sensitive=False,
        arbitrary_types_allowed=True
    )

    # Pattern: YYYYMMDD_HHMMSS_name[_sha]
    run_folder_pattern: str = Field(
        default=r"^\d{8}_\d{6}_(.+)$",
        description="Regex pattern to match run folder names"
    )

    @computed_field
    @property
    def processed_data_dir(self) -> Path:
        """Get processed data directory from settings."""
        from src.config import settings
        return settings.paths.processed_data_dir

    def find_runs(self, name_contains: str) -> List[Path]:
        """
        Find all run directories matching a name pattern.

        Args:
            name_contains: Substring to match in run folder name
                          (e.g., "preprocessing", "labeling", "features")

        Returns:
            List of matching directories, sorted by name descending (newest first)
        """
        if not self.processed_data_dir.exists():
            return []

        pattern = re.compile(self.run_folder_pattern)
        matching_dirs = []

        for item in self.processed_data_dir.iterdir():
            if item.is_dir() and pattern.match(item.name):
                if name_contains.lower() in item.name.lower():
                    matching_dirs.append(item)

        # Sort descending by name (timestamp prefix ensures chronological order)
        return sorted(matching_dirs, key=lambda p: p.name, reverse=True)

    def find_latest_run(self, name_contains: str) -> Optional[Path]:
        """
        Find the most recent run directory matching a name pattern.

        Args:
            name_contains: Substring to match (e.g., "preprocessing", "labeling")

        Returns:
            Path to latest matching run directory, or None if not found

        Example:
            >>> settings.testing.data.find_latest_run("preprocessing")
            Path('.../20251212_161906_preprocessing_ea45dd2')
        """
        runs = self.find_runs(name_contains)
        return runs[0] if runs else None

    def get_test_file(
        self,
        run_name: str,
        filename: str,
        require_exists: bool = True
    ) -> Optional[Path]:
        """
        Get path to a specific file within the latest run directory.

        Args:
            run_name: Run type to search for (e.g., "preprocessing")
            filename: Name of file to find
            require_exists: If True, return None if file doesn't exist

        Returns:
            Path to file, or None if not found

        Example:
            >>> settings.testing.data.get_test_file(
            ...     "preprocessing",
            ...     "AAPL_10K_2021_segmented_risks.json"
            ... )
            Path('.../20251212_161906_preprocessing_ea45dd2/AAPL_10K_2021_segmented_risks.json')
        """
        run_dir = self.find_latest_run(run_name)
        if run_dir is None:
            return None

        file_path = run_dir / filename

        if require_exists and not file_path.exists():
            return None

        return file_path

    def list_files_in_run(
        self,
        run_name: str,
        pattern: str = "*.json"
    ) -> List[Path]:
        """
        List all files matching a pattern in the latest run directory.

        Args:
            run_name: Run type to search for
            pattern: Glob pattern for files (default: "*.json")

        Returns:
            List of matching file paths
        """
        run_dir = self.find_latest_run(run_name)
        if run_dir is None:
            return []

        return list(run_dir.glob(pattern))


class TestRunContext:
    """
    Context for a single test run with timestamped output directory.

    Manages the creation and population of test output directories following
    the pattern: {YYYYMMDD_HHMMSS}_pytest_{git_sha}/

    Usage:
        run = TestRunContext(output_dir=Path("tests/outputs"), name="pytest")
        run.create()

        # Save test metadata
        run.save_metadata({"pytest_version": "7.0.0"})

        # Get artifact path for a specific test
        artifact_path = run.get_artifact_path("test_segmenter", "test_count", "output.json")

        # Save final results
        run.save_results({"passed": 10, "failed": 2})
    """

    def __init__(
        self,
        output_dir: Path,
        name: str = "pytest",
        git_sha: Optional[str] = None
    ):
        """
        Initialize a test run context.

        Args:
            output_dir: Base directory for test outputs
            name: Name identifier for this run (default: "pytest")
            git_sha: Git commit SHA (auto-detected if not provided)
        """
        self.output_dir = Path(output_dir)
        self.name = name
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.git_sha = git_sha or self._get_git_sha()

        # Build run ID: YYYYMMDD_HHMMSS_name_sha
        if self.git_sha:
            self.run_id = f"{self.timestamp}_{name}_{self.git_sha}"
        else:
            self.run_id = f"{self.timestamp}_{name}"

        self.run_dir = self.output_dir / self.run_id
        self.artifacts_dir = self.run_dir / "artifacts"
        self.logs_dir = self.run_dir / "logs"

        # Track test results
        self._results: Dict[str, List[Dict[str, Any]]] = {
            "passed": [],
            "failed": [],
            "skipped": [],
            "errors": [],
        }

    def _get_git_sha(self) -> Optional[str]:
        """Get current git commit SHA (short form)."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def create(self) -> Path:
        """
        Create the run directory structure.

        Returns:
            Path to the created run directory

        Creates:
            {run_dir}/
            ├── artifacts/
            └── logs/
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Update latest pointer (Windows-compatible: use a text file)
        latest_file = self.output_dir / ".latest"
        latest_file.write_text(self.run_id, encoding="utf-8")

        return self.run_dir

    def get_artifact_path(
        self,
        test_module: str,
        test_name: str,
        filename: str
    ) -> Path:
        """
        Get the path for a test artifact.

        Args:
            test_module: Test module name (e.g., "test_segmenter")
            test_name: Test function name (e.g., "test_segment_count")
            filename: Artifact filename (e.g., "output.json")

        Returns:
            Path to the artifact file (parent dirs created if needed)
        """
        # Clean module name (remove 'tests.' prefix if present)
        clean_module = test_module.replace("tests.", "").replace(".", "/")
        artifact_dir = self.artifacts_dir / clean_module / test_name

        if filename:
            return artifact_dir / filename
        return artifact_dir

    def get_artifact_dir(self, test_module: str, test_name: str) -> Path:
        """
        Get and create the artifact directory for a test.

        Args:
            test_module: Test module name
            test_name: Test function name

        Returns:
            Path to the artifact directory (created if not exists)
        """
        artifact_dir = self.get_artifact_path(test_module, test_name, "")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    def save_metadata(self, metadata: Dict[str, Any]) -> Path:
        """
        Save run metadata to run_metadata.json.

        Args:
            metadata: Dictionary of metadata to save

        Returns:
            Path to the saved metadata file
        """
        full_metadata = {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
            "name": self.name,
            "python_version": sys.version,
            "platform": sys.platform,
            **metadata
        }

        metadata_path = self.run_dir / "run_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(full_metadata, f, indent=2, default=str)

        return metadata_path

    def save_results(self, results: Dict[str, Any]) -> Path:
        """
        Save test results to test_results.json.

        Args:
            results: Dictionary of test results

        Returns:
            Path to the saved results file
        """
        full_results = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            **results
        }

        results_path = self.run_dir / "test_results.json"
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(full_results, f, indent=2, default=str)

        return results_path

    def save_artifact(
        self,
        test_module: str,
        test_name: str,
        filename: str,
        data: Any,
        format: str = "json"
    ) -> Path:
        """
        Save an artifact for a specific test.

        Args:
            test_module: Test module name
            test_name: Test function name
            filename: Artifact filename
            data: Data to save
            format: Output format ("json" or "text")

        Returns:
            Path to the saved artifact
        """
        artifact_path = self.get_artifact_path(test_module, test_name, filename)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(artifact_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        elif format == "text":
            with open(artifact_path, 'w', encoding='utf-8') as f:
                f.write(str(data))
        else:
            raise ValueError(f"Unknown format: {format}. Use 'json' or 'text'.")

        return artifact_path

    def add_test_result(
        self,
        nodeid: str,
        outcome: str,
        duration: float,
        error: Optional[str] = None,
        reason: Optional[str] = None
    ) -> None:
        """
        Add a test result to the internal tracker.

        Args:
            nodeid: Pytest node ID (e.g., "tests/test_foo.py::test_bar")
            outcome: Test outcome ("passed", "failed", "skipped", "error")
            duration: Test duration in seconds
            error: Error message if failed
            reason: Skip reason if skipped
        """
        result = {
            "nodeid": nodeid,
            "duration": duration,
            "outcome": outcome,
        }
        if error:
            result["error"] = error
        if reason:
            result["reason"] = reason

        if outcome in self._results:
            self._results[outcome].append(result)

    def finalize(self) -> Path:
        """
        Finalize the test run by saving collected results.

        Returns:
            Path to the saved results file
        """
        total = sum(len(v) for v in self._results.values())
        return self.save_results({
            "total": total,
            "passed": len(self._results["passed"]),
            "failed": len(self._results["failed"]),
            "skipped": len(self._results["skipped"]),
            "errors": len(self._results["errors"]),
            "details": self._results,
        })


class TestOutputConfig(BaseSettings):
    """
    Configuration for test output persistence.

    Manages persistent test output directories for validation, debugging,
    and reporting. Test outputs are stored in timestamped directories
    following the pattern: tests/outputs/{YYYYMMDD_HHMMSS}_pytest_{git_sha}/

    Usage:
        from src.config.testing import TestOutputConfig

        config = TestOutputConfig()
        run = config.create_test_run()
        run.create()

        # Save artifacts
        run.save_artifact("test_segmenter", "test_count", "output.json", {"count": 10})

        # Finalize
        run.finalize()
    """
    model_config = SettingsConfigDict(
        env_prefix='TEST_OUTPUT_',
        case_sensitive=False,
        arbitrary_types_allowed=True
    )

    output_dir: Path = Field(
        default_factory=lambda: Path("tests/outputs"),
        description="Base directory for persistent test outputs"
    )

    # Pattern: YYYYMMDD_HHMMSS_name[_sha]
    run_folder_pattern: str = Field(
        default=r"^\d{8}_\d{6}_(.+)$",
        description="Regex pattern to match test run folder names"
    )

    def create_test_run(self, name: str = "pytest") -> TestRunContext:
        """
        Create a new test run context.

        Args:
            name: Name identifier for the run (default: "pytest")

        Returns:
            TestRunContext instance (call .create() to create directories)
        """
        return TestRunContext(output_dir=self.output_dir, name=name)

    def find_runs(self, name_contains: Optional[str] = None) -> List[Path]:
        """
        Find all test run directories.

        Args:
            name_contains: Optional filter for run names

        Returns:
            List of run directories, sorted newest first
        """
        if not self.output_dir.exists():
            return []

        pattern = re.compile(self.run_folder_pattern)
        matching_dirs = []

        for item in self.output_dir.iterdir():
            if item.is_dir() and pattern.match(item.name):
                if name_contains is None or name_contains.lower() in item.name.lower():
                    matching_dirs.append(item)

        return sorted(matching_dirs, key=lambda p: p.name, reverse=True)

    def find_latest_run(self, name_contains: Optional[str] = None) -> Optional[Path]:
        """
        Find the most recent test run directory.

        Args:
            name_contains: Optional filter for run names

        Returns:
            Path to latest run, or None if no runs exist
        """
        runs = self.find_runs(name_contains)
        return runs[0] if runs else None

    def get_run_metadata(self, run_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Load metadata from a test run.

        Args:
            run_dir: Path to the run directory

        Returns:
            Metadata dictionary, or None if not found
        """
        metadata_path = run_dir / "run_metadata.json"
        if not metadata_path.exists():
            return None

        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_run_results(self, run_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Load test results from a test run.

        Args:
            run_dir: Path to the run directory

        Returns:
            Results dictionary, or None if not found
        """
        results_path = run_dir / "test_results.json"
        if not results_path.exists():
            return None

        with open(results_path, 'r', encoding='utf-8') as f:
            return json.load(f)


class TestingConfig(BaseSettings):
    """Testing and validation configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='TESTING_',
        case_sensitive=False
    )

    enable_golden_validation: bool = Field(
        default_factory=lambda: _get_testing_config().get('enable_golden_validation', False)
    )

    # Dynamic test data discovery
    data: TestDataConfig = Field(default_factory=TestDataConfig)

    # Persistent test output management
    output: TestOutputConfig = Field(default_factory=TestOutputConfig)


class ReproducibilityConfig(BaseSettings):
    """Reproducibility configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='REPRODUCIBILITY_',
        case_sensitive=False
    )

    random_seed: int = Field(
        default_factory=lambda: _get_reproducibility_config().get('random_seed', 42)
    )
