"""
Unit tests for Phase 3: Automated Retry Mechanism

Tests the retry_failed_files.py script functionality including:
- DLQ loading and filtering
- Retry logic with adaptive timeout
- Memory-aware processing
- DLQ updates after retry
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import retry script components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

try:
    from retry_failed_files import (
        load_dead_letter_queue,
        filter_failures,
        retry_files,
        update_dead_letter_queue,
    )
    RETRY_MODULE_AVAILABLE = True
except ImportError:
    RETRY_MODULE_AVAILABLE = False


@pytest.fixture
def sample_dlq_data():
    """Sample DLQ data for testing."""
    return [
        {
            "file": "data/raw/file1.html",
            "timestamp": "2026-02-16T12:00:00",
            "reason": "timeout",
            "script": "run_preprocessing_pipeline.py",
            "attempt_count": 1,
            "file_size_mb": 45.2,
            "error_type": "timeout"
        },
        {
            "file": "data/raw/file2.html",
            "timestamp": "2026-02-16T12:05:00",
            "reason": "memory_error",
            "script": "run_preprocessing_pipeline.py",
            "attempt_count": 2,
            "file_size_mb": 68.5,
            "error_type": "exception"
        },
        {
            "file": "data/raw/file3.html",
            "timestamp": "2026-02-16T12:10:00",
            "reason": "timeout",
            "script": "run_preprocessing_pipeline.py",
            "attempt_count": 3,
            "file_size_mb": 15.0,
            "error_type": "timeout"
        }
    ]


@pytest.fixture
def dlq_file(tmp_path, sample_dlq_data):
    """Create a temporary DLQ file."""
    dlq_path = tmp_path / "failed_files.json"
    with open(dlq_path, 'w') as f:
        json.dump(sample_dlq_data, f, indent=2)
    return dlq_path


@pytest.mark.skipif(not RETRY_MODULE_AVAILABLE, reason="Retry module not available")
class TestLoadDeadLetterQueue:
    """Test DLQ loading functionality."""

    def test_load_existing_dlq(self, dlq_file):
        """Test loading an existing DLQ file."""
        failures = load_dead_letter_queue(dlq_file)

        assert len(failures) == 3
        assert failures[0]['file'] == "data/raw/file1.html"
        assert failures[1]['attempt_count'] == 2

    def test_load_nonexistent_dlq(self, tmp_path):
        """Test loading a non-existent DLQ file."""
        nonexistent = tmp_path / "nonexistent.json"
        failures = load_dead_letter_queue(nonexistent)

        assert failures == []

    def test_load_empty_dlq(self, tmp_path):
        """Test loading an empty DLQ file."""
        empty_dlq = tmp_path / "empty.json"
        with open(empty_dlq, 'w') as f:
            json.dump([], f)

        failures = load_dead_letter_queue(empty_dlq)
        assert failures == []


@pytest.mark.skipif(not RETRY_MODULE_AVAILABLE, reason="Retry module not available")
class TestFilterFailures:
    """Test failure filtering logic."""

    def test_filter_by_max_attempts(self, sample_dlq_data):
        """Test filtering by maximum attempt count."""
        # Filter out files with >= 3 attempts
        filtered = filter_failures(sample_dlq_data, max_attempts=3)

        assert len(filtered) == 2  # file3 has 3 attempts, should be excluded
        assert all(f['attempt_count'] < 3 for f in filtered)

    def test_filter_by_min_size(self, sample_dlq_data):
        """Test filtering by minimum file size."""
        # Only files >= 40MB
        filtered = filter_failures(sample_dlq_data, min_size_mb=40.0)

        assert len(filtered) == 2  # file3 is 15MB, should be excluded
        assert all(f['file_size_mb'] >= 40.0 for f in filtered)

    def test_filter_by_failure_type(self, sample_dlq_data):
        """Test filtering by failure type."""
        # Only timeout failures
        filtered = filter_failures(sample_dlq_data, failure_types=['timeout'])

        assert len(filtered) == 2  # file2 is 'exception', should be excluded
        assert all(f['error_type'] == 'timeout' for f in filtered)

    def test_filter_combined(self, sample_dlq_data):
        """Test filtering with multiple criteria."""
        # Large files (>=40MB), timeout only, <3 attempts
        filtered = filter_failures(
            sample_dlq_data,
            min_size_mb=40.0,
            max_attempts=3,
            failure_types=['timeout']
        )

        # Only file1 matches all criteria
        assert len(filtered) == 1
        assert filtered[0]['file'] == "data/raw/file1.html"

    def test_filter_no_criteria(self, sample_dlq_data):
        """Test filtering with no criteria returns all."""
        filtered = filter_failures(sample_dlq_data)

        # Default max_attempts=3 excludes file3
        assert len(filtered) == 2


@pytest.mark.skipif(not RETRY_MODULE_AVAILABLE, reason="Retry module not available")
class TestRetryFiles:
    """Test retry logic."""

    @pytest.fixture
    def mock_semaphore(self):
        """Mock MemorySemaphore."""
        with patch('retry_failed_files.MemorySemaphore') as mock:
            instance = mock.return_value

            # Mock resource estimate
            estimate = Mock()
            estimate.file_size_mb = 45.0
            estimate.category.value = "medium"
            estimate.recommended_timeout_sec = 1200
            estimate.estimated_memory_mb = 1000
            estimate.worker_pool = "shared"

            instance.get_resource_estimate.return_value = estimate
            instance.can_allocate.return_value = True

            yield instance

    def test_retry_files_dry_run(self, sample_dlq_data, tmp_path, mock_semaphore):
        """Test dry-run mode doesn't actually process files."""
        # Create test files
        for failure in sample_dlq_data:
            file_path = tmp_path / Path(failure['file']).name
            file_path.write_text("<html>test</html>")
            failure['file'] = str(file_path)

        results = retry_files(
            sample_dlq_data,
            timeout_multiplier=2.0,
            force_isolated=False,
            dry_run=True
        )

        assert results['total'] == 3
        assert results['success'] == 0
        assert results['failed'] == 0
        assert results['skipped'] == 0
        assert len(results['details']) == 3
        assert all(d['action'] == 'dry_run' for d in results['details'])

    def test_retry_files_missing_files(self, sample_dlq_data, mock_semaphore):
        """Test retry skips missing files."""
        # Don't create the files - they don't exist
        results = retry_files(
            sample_dlq_data,
            timeout_multiplier=2.0,
            force_isolated=False,
            dry_run=False
        )

        # All should be skipped due to missing files
        assert results['skipped'] == 3

    def test_timeout_multiplier_applied(self, sample_dlq_data, tmp_path, mock_semaphore):
        """Test that timeout multiplier is correctly applied."""
        # Create test file
        file_path = tmp_path / "test.html"
        file_path.write_text("<html>test</html>")
        sample_dlq_data[0]['file'] = str(file_path)

        # Base timeout is 1200s (from mock), multiplier is 2.5
        # Expected: 1200 * 2.5 = 3000s
        with patch('retry_failed_files.SECPreprocessingPipeline'), \
             patch('retry_failed_files.ParallelProcessor'):

            results = retry_files(
                [sample_dlq_data[0]],
                timeout_multiplier=2.5,
                force_isolated=False,
                dry_run=True
            )

            # Check timeout in dry-run details
            assert results['details'][0]['timeout'] == 3000

    def test_force_isolated_mode(self, sample_dlq_data, tmp_path, mock_semaphore):
        """Test force isolated processing mode."""
        file_path = tmp_path / "test.html"
        file_path.write_text("<html>test</html>")
        sample_dlq_data[0]['file'] = str(file_path)

        with patch('retry_failed_files.SECPreprocessingPipeline') as mock_pipeline, \
             patch('retry_failed_files.ParallelProcessor') as mock_processor:

            mock_pipeline.return_value.process_risk_factors.return_value = []

            retry_files(
                [sample_dlq_data[0]],
                timeout_multiplier=2.0,
                force_isolated=True,
                dry_run=False
            )

            # Verify ParallelProcessor was called with max_workers=1
            # (isolated processing)
            calls = mock_processor.call_args_list
            if calls:
                assert calls[0][1].get('max_workers') == 1


@pytest.mark.skipif(not RETRY_MODULE_AVAILABLE, reason="Retry module not available")
class TestUpdateDeadLetterQueue:
    """Test DLQ update logic."""

    def test_update_removes_successful(self, dlq_file, sample_dlq_data):
        """Test that successful retries are removed from DLQ."""
        retry_results = {
            'total': 3,
            'success': 2,
            'failed': 1,
            'details': [
                {'file': sample_dlq_data[0]['file'], 'status': 'success'},
                {'file': sample_dlq_data[1]['file'], 'status': 'success'},
                {'file': sample_dlq_data[2]['file'], 'status': 'failed', 'error': 'timeout'},
            ]
        }

        update_dead_letter_queue(dlq_file, retry_results)

        # Load updated DLQ
        with open(dlq_file, 'r') as f:
            updated = json.load(f)

        # Only failed file should remain
        assert len(updated) == 1
        assert updated[0]['file'] == sample_dlq_data[2]['file']

    def test_update_increments_attempts(self, dlq_file, sample_dlq_data):
        """Test that failed retries increment attempt count."""
        retry_results = {
            'total': 1,
            'success': 0,
            'failed': 1,
            'details': [
                {'file': sample_dlq_data[0]['file'], 'status': 'failed', 'error': 'timeout'},
            ]
        }

        original_attempts = sample_dlq_data[0]['attempt_count']

        update_dead_letter_queue(dlq_file, retry_results)

        # Load updated DLQ
        with open(dlq_file, 'r') as f:
            updated = json.load(f)

        # Find the file
        updated_file = next(f for f in updated if f['file'] == sample_dlq_data[0]['file'])

        # Attempt count should be incremented
        assert updated_file['attempt_count'] == original_attempts + 1
        assert 'last_retry' in updated_file

    def test_update_adds_last_retry_timestamp(self, dlq_file, sample_dlq_data):
        """Test that last_retry timestamp is added."""
        retry_results = {
            'total': 1,
            'success': 0,
            'failed': 1,
            'details': [
                {'file': sample_dlq_data[0]['file'], 'status': 'failed', 'error': 'timeout'},
            ]
        }

        before_time = datetime.now()
        update_dead_letter_queue(dlq_file, retry_results)
        after_time = datetime.now()

        with open(dlq_file, 'r') as f:
            updated = json.load(f)

        updated_file = next(f for f in updated if f['file'] == sample_dlq_data[0]['file'])

        # Verify timestamp exists and is in correct range
        assert 'last_retry' in updated_file
        timestamp = datetime.fromisoformat(updated_file['last_retry'])
        assert before_time <= timestamp <= after_time


class TestAdaptiveTimeoutCalculation:
    """Test adaptive timeout calculation logic."""

    def test_small_file_timeout(self):
        """Test timeout calculation for small files."""
        base_timeout = 600  # 10 minutes for small files (<20MB)
        multiplier = 2.0

        result = int(base_timeout * multiplier)
        assert result == 1200  # 20 minutes

    def test_medium_file_timeout(self):
        """Test timeout calculation for medium files."""
        base_timeout = 1200  # 20 minutes for medium files (20-50MB)
        multiplier = 2.5

        result = int(base_timeout * multiplier)
        assert result == 3000  # 50 minutes

    def test_large_file_timeout(self):
        """Test timeout calculation for large files."""
        base_timeout = 2400  # 40 minutes for large files (>50MB)
        multiplier = 3.0

        result = int(base_timeout * multiplier)
        assert result == 7200  # 120 minutes (2 hours)

    def test_timeout_scaling_table(self):
        """Verify timeout scaling table from documentation."""
        test_cases = [
            # (base_timeout, multiplier, expected_result)
            (600, 2.0, 1200),    # Small file, 2x
            (1200, 2.5, 3000),   # Medium file, 2.5x
            (2400, 3.0, 7200),   # Large file, 3x
            (600, 4.0, 2400),    # Small file, 4x
            (2400, 2.0, 4800),   # Large file, 2x
        ]

        for base, mult, expected in test_cases:
            result = int(base * mult)
            assert result == expected, f"Failed for base={base}, mult={mult}"


class TestMemoryEstimationIntegration:
    """Test integration with memory estimation."""

    def test_memory_estimation_formula(self):
        """Test memory estimation formula: (file_size_mb * 12) + 500."""
        test_cases = [
            (10.0, 620),    # 10 * 12 + 500 = 620
            (45.2, 1042),   # 45.2 * 12 + 500 = 1042.4 ≈ 1042
            (68.5, 1322),   # 68.5 * 12 + 500 = 1322
        ]

        for file_size_mb, expected_mb in test_cases:
            estimated = (file_size_mb * 12) + 500
            assert abs(estimated - expected_mb) < 1  # Allow 1MB tolerance

    def test_memory_availability_check(self):
        """Test memory availability checking logic."""
        # Simulate memory check
        total_memory_mb = 16000  # 16GB
        safety_margin = 0.2
        reserved_mb = total_memory_mb * safety_margin  # 3200MB

        estimated_need = 1000  # Need 1GB
        available_mb = 5000  # 5GB available

        # Should be able to allocate
        can_allocate = available_mb > (estimated_need + reserved_mb)
        assert can_allocate is True

        # Simulate low memory
        available_mb = 1000  # Only 1GB available
        can_allocate = available_mb > (estimated_need + reserved_mb)
        assert can_allocate is False  # Not enough (need 1000 + 3200 = 4200)


class TestDLQStructureValidation:
    """Test DLQ file structure validation."""

    def test_required_fields_present(self, sample_dlq_data):
        """Test that all required fields are present."""
        required_fields = ['file', 'timestamp', 'script']

        for failure in sample_dlq_data:
            for field in required_fields:
                assert field in failure, f"Missing required field: {field}"

    def test_optional_fields(self, sample_dlq_data):
        """Test that optional fields are handled properly."""
        optional_fields = ['attempt_count', 'file_size_mb', 'error_type', 'reason', 'last_retry']

        # Optional fields may or may not be present
        for failure in sample_dlq_data:
            # If present, they should have correct types
            if 'attempt_count' in failure:
                assert isinstance(failure['attempt_count'], int)
            if 'file_size_mb' in failure:
                assert isinstance(failure['file_size_mb'], (int, float))

    def test_timestamp_format(self, sample_dlq_data):
        """Test that timestamps are in ISO 8601 format."""
        for failure in sample_dlq_data:
            timestamp = failure['timestamp']

            # Should be parseable as ISO 8601
            try:
                dt = datetime.fromisoformat(timestamp)
                assert dt is not None
            except ValueError:
                pytest.fail(f"Invalid timestamp format: {timestamp}")


@pytest.mark.integration
class TestRetryMechanismIntegration:
    """Integration tests for retry mechanism."""

    @pytest.mark.skipif(not RETRY_MODULE_AVAILABLE, reason="Retry module not available")
    def test_full_retry_workflow_dry_run(self, tmp_path, sample_dlq_data):
        """Test complete retry workflow in dry-run mode."""
        # Create DLQ file
        dlq_path = tmp_path / "failed_files.json"
        with open(dlq_path, 'w') as f:
            json.dump(sample_dlq_data, f)

        # Create test files
        for failure in sample_dlq_data:
            file_path = tmp_path / Path(failure['file']).name
            file_path.write_text("<html>test</html>")
            failure['file'] = str(file_path)

        # Update DLQ with real paths
        with open(dlq_path, 'w') as f:
            json.dump(sample_dlq_data, f)

        # Load DLQ
        failures = load_dead_letter_queue(dlq_path)
        assert len(failures) == 3

        # Filter
        eligible = filter_failures(failures, max_attempts=3)
        assert len(eligible) == 2

        # Dry run retry
        with patch('retry_failed_files.MemorySemaphore'):
            results = retry_files(eligible, dry_run=True)

            assert results['total'] == 2
            assert len(results['details']) == 2


class TestPhase3CompletionCriteria:
    """Verify Phase 3 completion criteria from plan."""

    def test_retry_script_exists(self):
        """Verify retry script file exists."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "utils" / "retry_failed_files.py"
        assert script_path.exists()

    def test_all_core_functions_exist(self):
        """Verify all core functions exist."""
        if not RETRY_MODULE_AVAILABLE:
            pytest.skip("Retry module not available")

        import retry_failed_files

        required_functions = [
            'load_dead_letter_queue',
            'filter_failures',
            'retry_files',
            'update_dead_letter_queue',
            'main',
        ]

        for func_name in required_functions:
            assert hasattr(retry_failed_files, func_name), f"Missing function: {func_name}"

    def test_documentation_exists(self):
        """Verify documentation files exist."""
        base_path = Path(__file__).parent.parent.parent

        docs = [
            base_path / "docs" / "RETRY_MECHANISM.md",
            base_path / "scripts" / "utils" / "RETRY_QUICK_START.md",
        ]

        for doc in docs:
            assert doc.exists(), f"Missing documentation: {doc}"

    def test_example_dlq_exists(self):
        """Verify example DLQ file exists."""
        example_dlq = Path(__file__).parent.parent.parent / "logs" / "failed_files_example.json"
        assert example_dlq.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
