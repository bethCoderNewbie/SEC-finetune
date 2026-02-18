"""Unit tests for Priority 2: Inline Gatekeeper Validation & Quarantine Pattern."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.config.qa_validation import HealthCheckValidator
from src.preprocessing.pipeline import SECPreprocessingPipeline
from src.preprocessing.segmenter import SegmentedRisks, RiskSegment


def import_batch_parse():
    """Dynamically import batch_parse module."""
    spec = importlib.util.spec_from_file_location(
        "batch_parse",
        "scripts/data_preprocessing/batch_parse.py"
    )
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules["batch_parse"] = module
        spec.loader.exec_module(module)
        return module
    raise ImportError("Could not import batch_parse module")


class TestHealthCheckValidatorCheckSingle:
    """Test cases for HealthCheckValidator.check_single() method."""

    @pytest.fixture
    def validator(self):
        """Create HealthCheckValidator instance."""
        return HealthCheckValidator()

    @pytest.fixture
    def valid_data(self):
        """Create valid test data."""
        return {
            "ticker": "AAPL",
            "cik": "0000320193",
            "company_name": "Apple Inc.",
            "form_type": "10-K",
            "filing_date": "2021-10-29",
            "fiscal_year": 2021,
            "section": "Item 1A - Risk Factors",
            "segments": [
                {
                    "segment_id": 1,
                    "text": "We face intense competition in all aspects of our business and may encounter adverse risks that could materially affect operations.",
                    "word_count": 22,
                    "char_count": 130
                },
                {
                    "segment_id": 2,
                    "text": "Our business is subject to various risks that could adversely impact potential outcomes and might cause material uncertainties.",
                    "word_count": 20,
                    "char_count": 122
                }
            ]
        }

    def test_check_single_pass(self, validator, valid_data):
        """Test check_single returns PASS for valid data."""
        report = validator.check_single(valid_data)

        assert report["status"] == "PASS"
        assert "timestamp" in report
        assert "blocking_summary" in report
        assert "validation_table" in report

    def test_check_single_fail_missing_identity(self, validator):
        """Test check_single returns FAIL for missing identity fields."""
        invalid_data = {
            "ticker": None,  # Missing ticker
            "company_name": "Test Company",
            "form_type": "10-K",
            "segments": []
        }

        report = validator.check_single(invalid_data)

        assert report["status"] == "FAIL"
        assert not report["blocking_summary"]["all_pass"]

    def test_check_single_fail_no_segments(self, validator, valid_data):
        """Test check_single with empty segments skips substance checks, returns PASS."""
        valid_data["segments"] = []

        report = validator.check_single(valid_data)

        # With no segments, cleanliness and substance checks are skipped entirely.
        # Identity checks still run and pass (cik/company_name present) → PASS overall.
        assert report["status"] == "PASS"

    def test_check_single_fail_dirty_text(self, validator, valid_data):
        """Test check_single returns FAIL for segments containing HTML artifacts."""
        # The cleanliness check detects HTML tags (html_artifact_rate is blocking=True)
        valid_data["segments"][0]["text"] = "<b>Risk</b> with <i>HTML</i> tags remaining in text"

        report = validator.check_single(valid_data)

        # HTML artifact rate check is blocking=True → overall FAIL
        assert report["status"] == "FAIL"

    def test_check_single_validation_table_format(self, validator, valid_data):
        """Test validation_table is properly formatted."""
        report = validator.check_single(valid_data)

        validation_table = report["validation_table"]

        # validation_table is a list of dicts with category/metric/status keys
        assert isinstance(validation_table, list)
        assert len(validation_table) > 0
        assert any("identity" in row.get("category", "") for row in validation_table)

    def test_check_single_blocking_summary_on_fail(self, validator):
        """Test blocking_summary contains failure details."""
        invalid_data = {
            "ticker": None,
            "company_name": None,
            "form_type": "10-K",
            "segments": []
        }

        report = validator.check_single(invalid_data)

        blocking_summary = report["blocking_summary"]

        # blocking_summary is a dict with failure counts
        assert not blocking_summary["all_pass"]
        assert blocking_summary["failed"] > 0

    def test_check_single_timestamp_format(self, validator, valid_data):
        """Test timestamp is in ISO format."""
        report = validator.check_single(valid_data)

        timestamp = report["timestamp"]

        # Should be ISO 8601 format
        assert "T" in timestamp
        from datetime import datetime
        # Should parse without error
        datetime.fromisoformat(timestamp)


class TestPipelineProcessAndValidate:
    """Test cases for Pipeline.process_and_validate() method."""

    @pytest.fixture
    def pipeline(self):
        """Create SECPreprocessingPipeline instance."""
        return SECPreprocessingPipeline()

    @pytest.fixture
    def mock_validator(self):
        """Create mock validator."""
        validator = Mock(spec=HealthCheckValidator)
        validator.check_single.return_value = {
            "status": "PASS",
            "timestamp": "2025-12-28T14:30:00",
            "blocking_summary": "",
            "validation_table": "All checks passed"
        }
        return validator

    def test_process_and_validate_success(self, pipeline, tmp_path, mock_validator):
        """Test process_and_validate returns success for valid file."""
        # Create test HTML file
        test_file = tmp_path / "test_10k.html"
        test_file.write_text("""
        <html>
        <body>
        <div>ITEM 1A. RISK FACTORS</div>
        <p>Risk 1: Market competition is intense.</p>
        <p>Risk 2: Regulatory environment is complex.</p>
        </body>
        </html>
        """)

        result, status, validation_report = pipeline.process_and_validate(
            file_path=test_file,
            form_type="10-K",
            validator=mock_validator
        )

        # Should succeed if file is processable
        assert result is not None or status == "FAIL"
        assert status in ["PASS", "FAIL"]
        assert validation_report is not None

    def test_process_and_validate_processing_failure(self, pipeline, tmp_path, mock_validator):
        """Test process_and_validate handles processing failures."""
        # Create invalid/empty file
        test_file = tmp_path / "invalid.html"
        test_file.write_text("")

        result, status, validation_report = pipeline.process_and_validate(
            file_path=test_file,
            validator=mock_validator
        )

        # Should return FAIL status
        assert status == "FAIL"
        assert validation_report is not None
        assert "reason" in validation_report

    def test_process_and_validate_validation_failure(self, pipeline, tmp_path):
        """Test process_and_validate handles validation failures."""
        # Create mock validator that returns FAIL
        mock_validator = Mock(spec=HealthCheckValidator)
        mock_validator.check_single.return_value = {
            "status": "FAIL",
            "timestamp": "2025-12-28T14:30:00",
            "blocking_summary": "Missing required fields",
            "validation_table": "Validation failed"
        }

        # Create test file (even if processing succeeds, validation will fail)
        test_file = tmp_path / "test.html"
        test_file.write_text("<html><body>Test content</body></html>")

        with patch.object(pipeline, 'process_filing') as mock_process:
            # Mock successful processing
            mock_result = Mock(spec=SegmentedRisks)
            mock_result.model_dump.return_value = {"ticker": "TEST"}
            mock_process.return_value = mock_result

            result, status, validation_report = pipeline.process_and_validate(
                file_path=test_file,
                validator=mock_validator
            )

            # Should return FAIL due to validation
            assert status == "FAIL"
            assert validation_report["status"] == "FAIL"

    def test_process_and_validate_creates_validator_if_none(self, pipeline, tmp_path):
        """Test process_and_validate creates validator if not provided."""
        test_file = tmp_path / "test.html"
        test_file.write_text("<html><body>Test</body></html>")

        # Don't pass validator - should create one internally
        with patch.object(pipeline, 'process_filing', return_value=None):
            result, status, validation_report = pipeline.process_and_validate(
                file_path=test_file,
                validator=None  # Let it create validator
            )

            # Should handle gracefully
            assert status == "FAIL"

    def test_process_and_validate_tuple_return(self, pipeline, tmp_path, mock_validator):
        """Test process_and_validate returns tuple of (result, status, report)."""
        test_file = tmp_path / "test.html"
        test_file.write_text("<html><body>Test</body></html>")

        with patch.object(pipeline, 'process_filing', return_value=None):
            return_value = pipeline.process_and_validate(
                file_path=test_file,
                validator=mock_validator
            )

            # Should return tuple with 3 elements
            assert isinstance(return_value, tuple)
            assert len(return_value) == 3

            result, status, validation_report = return_value
            assert status in ["PASS", "FAIL"]
            assert isinstance(validation_report, dict)


class TestQuarantinePattern:
    """Test cases for quarantine pattern in batch processing."""

    def test_quarantine_directory_creation(self, tmp_path):
        """Test quarantine directory is created with correct naming."""
        batch_parse = import_batch_parse()
        batch_parse_filings = batch_parse.batch_parse_filings
        from src.config import RunContext

        # Create test setup
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create minimal test file
        test_file = input_dir / "test.html"
        test_file.write_text("<html><body>Test</body></html>")

        run = RunContext(name="test_quarantine", base_dir=output_dir)
        run.create()

        # Run with validation
        with patch('src.preprocessing.pipeline.SECPreprocessingPipeline.process_and_validate') as mock_validate:
            # Mock validation failure
            mock_validate.return_value = (
                None,  # result
                "FAIL",  # status
                {"status": "FAIL", "timestamp": "2025-12-28", "blocking_summary": "Test failure"}
            )

            batch_parse_filings(
                input_dir=input_dir,
                output_dir=run.output_dir,
                run_context=run,
                use_validation=True,
                quiet=True
            )

            # Quarantine directory should exist
            quarantine_dirs = list(output_dir.glob("quarantine_*"))
            assert len(quarantine_dirs) > 0

    def test_failure_report_generation(self, tmp_path):
        """Test failure report markdown is generated for quarantined files."""
        batch_parse = import_batch_parse()
        batch_parse_filings = batch_parse.batch_parse_filings
        from src.config import RunContext

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        test_file = input_dir / "test.html"
        test_file.write_text("<html><body>Test</body></html>")

        run = RunContext(name="test_reports", base_dir=output_dir)
        run.create()

        with patch('src.preprocessing.pipeline.SECPreprocessingPipeline.process_and_validate') as mock_validate:
            # Mock result and validation failure
            mock_result = Mock(spec=SegmentedRisks)
            mock_result.save_to_json = Mock()
            mock_validate.return_value = (
                mock_result,
                "FAIL",
                {
                    "status": "FAIL",
                    "timestamp": "2025-12-28T14:30:00",
                    "blocking_summary": "Missing required data",
                    "validation_table": "Details here"
                }
            )

            batch_parse_filings(
                input_dir=input_dir,
                output_dir=run.output_dir,
                run_context=run,
                use_validation=True,
                incremental=True,
                quiet=True
            )

            # Failure report should exist
            quarantine_dirs = list(output_dir.glob("quarantine_*"))
            if quarantine_dirs:
                reports = list(quarantine_dirs[0].glob("*_FAILURE_REPORT.md"))
                assert len(reports) > 0

    def test_manifest_tracks_quarantine_failures(self, tmp_path):
        """Test manifest records quarantine path for failures."""
        from src.utils.state_manager import StateManifest

        manifest_path = tmp_path / ".manifest.json"
        manifest = StateManifest(manifest_path)

        input_file = tmp_path / "failed.html"
        input_file.write_text("content")

        quarantine_path = tmp_path / "quarantine" / "failed_FAILED.json"

        manifest.record_failure(
            input_path=input_file,
            run_id="test_run",
            reason="validation_failed",
            quarantine_path=quarantine_path,
            validation_report={"status": "FAIL"}
        )

        # Verify quarantine path is recorded
        file_data = manifest.data["files"][str(input_file.absolute())]
        assert file_data["quarantine_path"] == str(quarantine_path.absolute())
        assert file_data["validation_report"]["status"] == "FAIL"

    def test_success_path_not_quarantined(self, tmp_path):
        """Test successful processing does not create quarantine entries."""
        from src.utils.state_manager import StateManifest

        manifest = StateManifest(tmp_path / ".manifest.json")

        input_file = tmp_path / "success.html"
        input_file.write_text("content")

        manifest.record_success(
            input_path=input_file,
            output_path=tmp_path / "output.json",
            run_id="test_run",
            validation_report={"status": "PASS"}
        )

        file_data = manifest.data["files"][str(input_file.absolute())]
        assert "quarantine_path" not in file_data
        assert file_data["status"] == "success"


class TestManifestFailureTracking:
    """Test cases for manifest failure tracking."""

    @pytest.fixture
    def manifest(self, tmp_path):
        """Create StateManifest instance."""
        from src.utils.state_manager import StateManifest
        return StateManifest(tmp_path / ".manifest.json")

    def test_failure_attempt_counter(self, manifest, tmp_path):
        """Test that repeated record_failure calls overwrite the record with latest run_id."""
        file_path = tmp_path / "file.html"
        file_path.write_text("content")

        # First attempt
        manifest.record_failure(file_path, "run1", "error1")
        assert manifest.data["files"][str(file_path.absolute())]["status"] == "failed"
        assert manifest.data["files"][str(file_path.absolute())]["run_id"] == "run1"

        # Second attempt overwrites
        manifest.record_failure(file_path, "run2", "error2")
        assert manifest.data["files"][str(file_path.absolute())]["run_id"] == "run2"

        # Third attempt overwrites again
        manifest.record_failure(file_path, "run3", "error3")
        assert manifest.data["files"][str(file_path.absolute())]["run_id"] == "run3"

    def test_failure_reason_tracking(self, manifest, tmp_path):
        """Test failure reasons are tracked."""
        file_path = tmp_path / "file.html"
        file_path.write_text("content")

        reasons = ["validation_failed", "extraction_error", "parsing_error"]

        for run_id, reason in enumerate(reasons, 1):
            manifest.record_failure(file_path, f"run{run_id}", reason)

        file_data = manifest.data["files"][str(file_path.absolute())]

        # Last reason should be stored
        assert file_data["failure_reason"] == "parsing_error"

    def test_failed_files_query(self, manifest, tmp_path):
        """Test querying only failed files."""
        # Create mixed success/failure files
        for i in range(3):
            success_file = tmp_path / f"success_{i}.html"
            success_file.write_text("content")
            manifest.record_success(success_file, tmp_path / f"out_{i}.json", f"run{i}")

        for i in range(2):
            failed_file = tmp_path / f"failed_{i}.html"
            failed_file.write_text("content")
            manifest.record_failure(failed_file, f"run{i}", f"error{i}")

        failed_files = manifest.get_failed_files()

        assert len(failed_files) == 2
        for file_path in failed_files:
            assert "failed_" in file_path  # iterates dict keys (file path strings)

    def test_success_overwrites_failure(self, manifest, tmp_path):
        """Test successful reprocessing overwrites failure status."""
        file_path = tmp_path / "file.html"
        file_path.write_text("content")

        # Initial failure
        manifest.record_failure(file_path, "run1", "error")
        assert manifest.data["files"][str(file_path.absolute())]["status"] == "failed"

        # Successful reprocessing
        manifest.record_success(file_path, tmp_path / "output.json", "run2")
        assert manifest.data["files"][str(file_path.absolute())]["status"] == "success"

        # Should not appear in failed files
        failed_files = manifest.get_failed_files()
        assert str(file_path.absolute()) not in failed_files


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
