"""Tests for data health check validation.

Tests the HealthCheckValidator class and related threshold definitions.
"""

import json
import pytest
from pathlib import Path

from src.config.qa_validation import (
    HealthCheckValidator,
    ThresholdRegistry,
    ValidationStatus,
)


class TestHealthCheckThresholds:
    """Test that health check thresholds are properly loaded."""

    def test_health_check_thresholds_exist(self):
        """Health check thresholds should be available in registry."""
        # Force reload to pick up new config
        ThresholdRegistry.reload()

        # Identity thresholds
        assert ThresholdRegistry.get("cik_present_rate") is not None
        assert ThresholdRegistry.get("company_name_present_rate") is not None
        assert ThresholdRegistry.get("sic_code_present_rate") is not None

        # Cleanliness thresholds
        assert ThresholdRegistry.get("html_artifact_rate") is not None
        assert ThresholdRegistry.get("page_number_artifact_rate") is not None

        # Substance thresholds
        assert ThresholdRegistry.get("empty_segment_rate") is not None
        assert ThresholdRegistry.get("short_segment_rate") is not None

        # Domain thresholds
        assert ThresholdRegistry.get("duplicate_rate") is not None
        assert ThresholdRegistry.get("risk_keyword_present") is not None

    def test_blocking_thresholds_marked_correctly(self):
        """Critical thresholds should be marked as blocking."""
        ThresholdRegistry.reload()

        # These should be blocking
        cik = ThresholdRegistry.get("cik_present_rate")
        assert cik is not None
        assert cik.blocking is True

        company = ThresholdRegistry.get("company_name_present_rate")
        assert company is not None
        assert company.blocking is True

        html = ThresholdRegistry.get("html_artifact_rate")
        assert html is not None
        assert html.blocking is True

        # These should NOT be blocking
        sic = ThresholdRegistry.get("sic_code_present_rate")
        assert sic is not None
        assert sic.blocking is False

    def test_health_check_tag_query(self):
        """Should be able to query thresholds by health_check tag."""
        ThresholdRegistry.reload()

        health_check_thresholds = ThresholdRegistry.by_tag("health_check")
        assert len(health_check_thresholds) >= 8  # We defined 8 thresholds


class TestHealthCheckValidator:
    """Test HealthCheckValidator functionality."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        ThresholdRegistry.reload()
        return HealthCheckValidator()

    @pytest.fixture
    def sample_valid_data(self, tmp_path):
        """Create valid sample data that should pass all checks."""
        # Ensure we have >= 10 risk keywords: risk, adverse, may, could, might,
        # material, uncertain, potential (need 10+ total occurrences)
        data = {
            "cik": "0000320193",
            "company_name": "Apple Inc.",
            "sic_code": "3571",
            "ticker": "AAPL",
            "form_type": "10-K",
            "filing_name": "AAPL_10K_2021.json",
            "segments": [
                {
                    "id": 1,
                    "text": "This is a risk factor about market conditions. The risk may be material and could have adverse effects. There is potential for uncertain outcomes.",
                    "length": 150,
                    "word_count": 28
                },
                {
                    "id": 2,
                    "text": "The company may face material risk and uncertainty. Adverse conditions might affect operations and could result in potential losses.",
                    "length": 140,
                    "word_count": 22
                },
            ]
        }
        file_path = tmp_path / "valid_file.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return tmp_path

    @pytest.fixture
    def sample_missing_cik(self, tmp_path):
        """Create data with missing CIK (should fail)."""
        data = {
            "company_name": "Test Corp",
            "sic_code": "1234",
            "segments": [
                {"id": 1, "text": "This is a valid segment with enough content.", "length": 100}
            ]
        }
        with open(tmp_path / "missing_cik.json", 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return tmp_path

    @pytest.fixture
    def sample_html_artifact(self, tmp_path):
        """Create data with HTML artifacts (should fail cleanliness)."""
        data = {
            "cik": "123456",
            "company_name": "Test Corp",
            "segments": [
                {"id": 1, "text": "<div>This segment has HTML tags</div>", "length": 40}
            ]
        }
        with open(tmp_path / "html_artifact.json", 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return tmp_path

    @pytest.fixture
    def sample_empty_segment(self, tmp_path):
        """Create data with empty segment (should fail substance)."""
        data = {
            "cik": "123456",
            "company_name": "Test Corp",
            "segments": [
                {"id": 1, "text": "", "length": 0},
                {"id": 2, "text": "This is a valid segment.", "length": 100}
            ]
        }
        with open(tmp_path / "empty_segment.json", 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return tmp_path

    def test_valid_data_passes(self, validator, sample_valid_data):
        """Valid data should pass all checks."""
        report = validator.check_run(sample_valid_data)

        assert report["status"] == "PASS"
        assert report["files_checked"] == 1
        assert report["blocking_summary"]["failed"] == 0

    def test_missing_cik_fails(self, validator, sample_missing_cik):
        """Missing CIK should fail blocking check."""
        report = validator.check_run(sample_missing_cik)

        assert report["status"] == "FAIL"
        assert report["blocking_summary"]["failed"] > 0

        # Find the CIK result
        cik_result = next(
            (r for r in report["validation_table"] if r["metric"] == "cik_present_rate"),
            None
        )
        assert cik_result is not None
        assert cik_result["status"] == "FAIL"
        assert cik_result["actual"] == 0.0

    def test_html_artifacts_detected(self, validator, sample_html_artifact):
        """HTML artifacts should be flagged."""
        report = validator.check_run(sample_html_artifact)

        # Find the HTML artifact result
        html_result = next(
            (r for r in report["validation_table"] if r["metric"] == "html_artifact_rate"),
            None
        )
        assert html_result is not None
        assert html_result["actual"] > 0  # Should detect the artifact

    def test_empty_segment_detected(self, validator, sample_empty_segment):
        """Empty segments should be flagged."""
        report = validator.check_run(sample_empty_segment)

        # Find the empty segment result
        empty_result = next(
            (r for r in report["validation_table"] if r["metric"] == "empty_segment_rate"),
            None
        )
        assert empty_result is not None
        assert empty_result["actual"] == 0.5  # 1 of 2 segments empty

    def test_empty_directory_returns_error(self, validator, tmp_path):
        """Empty directory should return error status."""
        report = validator.check_run(tmp_path)

        assert report["status"] == "ERROR"
        assert "No JSON files found" in report.get("message", "")

    def test_duplicate_detection(self, validator, tmp_path):
        """Duplicate content should be detected."""
        # Create two files with identical content
        data = {
            "cik": "123456",
            "company_name": "Test Corp",
            "segments": [
                {"id": 1, "text": "This is the exact same content.", "length": 100}
            ]
        }

        with open(tmp_path / "file1.json", 'w', encoding='utf-8') as f:
            json.dump(data, f)

        with open(tmp_path / "file2.json", 'w', encoding='utf-8') as f:
            json.dump(data, f)

        report = validator.check_run(tmp_path)

        # Find the duplicate result
        dup_result = next(
            (r for r in report["validation_table"] if r["metric"] == "duplicate_rate"),
            None
        )
        assert dup_result is not None
        assert dup_result["actual"] > 0  # Should detect duplicates

    def test_risk_keywords_detected(self, validator, sample_valid_data):
        """Risk keywords should be detected in valid data."""
        report = validator.check_run(sample_valid_data)

        # Find the risk keyword result
        risk_result = next(
            (r for r in report["validation_table"] if r["metric"] == "risk_keyword_present"),
            None
        )
        assert risk_result is not None
        assert risk_result["actual"] is True  # Keywords found


class TestHealthCheckValidatorWithRealData:
    """Test with real preprocessing output if available."""

    @pytest.fixture
    def processed_data_dir(self):
        """Find existing processed data directory."""
        processed_root = Path("data/processed")
        if not processed_root.exists():
            pytest.skip("No processed data directory found")

        # Find first directory with JSON files
        for run_dir in processed_root.iterdir():
            if run_dir.is_dir():
                json_files = list(run_dir.glob("*.json"))
                if json_files:
                    return run_dir

        pytest.skip("No processed data runs found")

    def test_real_data_validation(self, processed_data_dir):
        """Validate real preprocessing output."""
        ThresholdRegistry.reload()
        validator = HealthCheckValidator()

        report = validator.check_run(processed_data_dir)

        # Should complete without error
        assert report["status"] in ["PASS", "WARN", "FAIL"]
        assert report["files_checked"] > 0
        assert "validation_table" in report
        assert "blocking_summary" in report

        # Print summary for debugging
        print(f"\nReal data validation:")
        print(f"  Directory: {processed_data_dir}")
        print(f"  Files: {report['files_checked']}")
        print(f"  Status: {report['status']}")
        print(f"  Blocking passed: {report['blocking_summary']['passed']}/{report['blocking_summary']['total_blocking']}")
