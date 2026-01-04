"""Unit tests for Priority 1: State Management & Incremental Processing."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.utils.state_manager import StateManifest, compute_file_hash
from src.config.run_context import RunContext


class TestComputeFileHash:
    """Test cases for compute_file_hash function."""

    def test_hash_computation_basic(self, tmp_path):
        """Test basic hash computation for a file."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        # Compute hash
        hash_value = compute_file_hash(test_file)

        # Verify hash format and consistency
        assert hash_value.startswith("sha256:")
        assert len(hash_value) == 71  # "sha256:" + 64 hex chars

        # Verify same content produces same hash
        hash_value2 = compute_file_hash(test_file)
        assert hash_value == hash_value2

    def test_hash_changes_with_content(self, tmp_path):
        """Test that hash changes when file content changes."""
        test_file = tmp_path / "test.txt"

        # Initial content
        test_file.write_text("Version 1")
        hash1 = compute_file_hash(test_file)

        # Modified content
        test_file.write_text("Version 2")
        hash2 = compute_file_hash(test_file)

        # Hashes should differ
        assert hash1 != hash2

    def test_hash_large_file(self, tmp_path):
        """Test hash computation for large file (>1MB)."""
        test_file = tmp_path / "large.txt"

        # Create 2MB file
        content = "x" * (2 * 1024 * 1024)
        test_file.write_text(content)

        # Should complete without error
        hash_value = compute_file_hash(test_file)
        assert hash_value.startswith("sha256:")

    def test_hash_binary_file(self, tmp_path):
        """Test hash computation for binary file."""
        test_file = tmp_path / "binary.dat"

        # Write binary data
        test_file.write_bytes(b"\x00\x01\x02\x03\xFF\xFE")

        hash_value = compute_file_hash(test_file)
        assert hash_value.startswith("sha256:")

    def test_hash_empty_file(self, tmp_path):
        """Test hash computation for empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        hash_value = compute_file_hash(test_file)
        assert hash_value.startswith("sha256:")


class TestStateManifest:
    """Test cases for StateManifest class."""

    @pytest.fixture
    def manifest_path(self, tmp_path):
        """Create temporary manifest path."""
        return tmp_path / ".manifest.json"

    @pytest.fixture
    def manifest(self, manifest_path):
        """Create StateManifest instance."""
        return StateManifest(manifest_path)

    def test_initialization(self, manifest):
        """Test StateManifest initialization."""
        assert manifest.data == {"files": {}, "metadata": {}, "run_configs": {}}
        assert manifest.data["metadata"]["version"] == "1.0"

    def test_load_creates_new_manifest(self, manifest, manifest_path):
        """Test load creates new manifest if file doesn't exist."""
        manifest.load()

        # Manifest file should be created
        assert manifest_path.exists()

        # Should have default structure
        assert "files" in manifest.data
        assert "metadata" in manifest.data
        assert manifest.data["metadata"]["version"] == "1.0"

    def test_save_creates_manifest_file(self, manifest, manifest_path):
        """Test save creates manifest file."""
        manifest.save()

        assert manifest_path.exists()

        # Verify content
        with open(manifest_path) as f:
            data = json.load(f)
        assert data["metadata"]["version"] == "1.0"

    def test_atomic_save(self, manifest, manifest_path):
        """Test that save operation is atomic."""
        # Add some data
        manifest.data["files"]["test.txt"] = {"hash": "abc123", "status": "success"}

        # Save
        manifest.save()

        # Verify data persisted
        manifest2 = StateManifest(manifest_path)
        manifest2.load()
        assert "test.txt" in manifest2.data["files"]

    def test_backup_recovery(self, manifest, manifest_path):
        """Test automatic backup recovery on corrupted manifest."""
        # Create valid backup
        backup_path = manifest_path.with_suffix(".json.bak")
        backup_data = {"files": {"backup.txt": {}}, "metadata": {"version": "1.0"}, "run_configs": {}}
        backup_path.write_text(json.dumps(backup_data))

        # Create corrupted main manifest
        manifest_path.write_text("{invalid json")

        # Load should recover from backup
        manifest.load()

        assert "backup.txt" in manifest.data["files"]

    def test_should_process_new_file(self, manifest, tmp_path):
        """Test should_process returns True for new file."""
        test_file = tmp_path / "new.txt"
        test_file.write_text("content")

        assert manifest.should_process(test_file) is True

    def test_should_process_unchanged_file(self, manifest, tmp_path):
        """Test should_process returns False for unchanged file."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("content")

        # Record file in manifest
        file_hash = compute_file_hash(test_file)
        manifest.data["files"][str(test_file.absolute())] = {
            "hash": file_hash,
            "status": "success"
        }

        assert manifest.should_process(test_file) is False

    def test_should_process_changed_file(self, manifest, tmp_path):
        """Test should_process returns True for changed file."""
        test_file = tmp_path / "changed.txt"
        test_file.write_text("version 1")

        # Record original hash
        original_hash = compute_file_hash(test_file)
        manifest.data["files"][str(test_file.absolute())] = {
            "hash": original_hash,
            "status": "success"
        }

        # Modify file
        test_file.write_text("version 2")

        assert manifest.should_process(test_file) is True

    def test_should_process_force_override(self, manifest, tmp_path):
        """Test should_process with force=True always returns True."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Record file as processed
        file_hash = compute_file_hash(test_file)
        manifest.data["files"][str(test_file.absolute())] = {
            "hash": file_hash,
            "status": "success"
        }

        # Force should override
        assert manifest.should_process(test_file, force=True) is True

    def test_record_success(self, manifest, tmp_path):
        """Test recording successful processing."""
        input_file = tmp_path / "input.txt"
        input_file.write_text("content")
        output_file = tmp_path / "output.json"

        manifest.record_success(
            input_path=input_file,
            output_path=output_file,
            run_id="20251228_143022"
        )

        # Verify recorded data
        file_data = manifest.data["files"][str(input_file.absolute())]
        assert file_data["status"] == "success"
        assert file_data["output_path"] == str(output_file.absolute())
        assert file_data["run_id"] == "20251228_143022"
        assert "hash" in file_data
        assert "last_processed" in file_data

    def test_record_success_with_validation_report(self, manifest, tmp_path):
        """Test recording success with validation report."""
        input_file = tmp_path / "input.txt"
        input_file.write_text("content")
        output_file = tmp_path / "output.json"

        validation_report = {
            "status": "PASS",
            "checks": ["identity", "cleanliness"]
        }

        manifest.record_success(
            input_path=input_file,
            output_path=output_file,
            run_id="test_run",
            validation_report=validation_report
        )

        file_data = manifest.data["files"][str(input_file.absolute())]
        assert file_data["validation_report"] == validation_report

    def test_record_failure(self, manifest, tmp_path):
        """Test recording processing failure."""
        input_file = tmp_path / "failed.txt"
        input_file.write_text("content")

        manifest.record_failure(
            input_path=input_file,
            run_id="test_run",
            reason="validation_failed"
        )

        # Verify recorded data
        file_data = manifest.data["files"][str(input_file.absolute())]
        assert file_data["status"] == "failed"
        assert file_data["reason"] == "validation_failed"
        assert file_data["attempt_count"] == 1
        assert "last_attempt" in file_data

    def test_record_failure_increments_attempts(self, manifest, tmp_path):
        """Test that recording multiple failures increments attempt count."""
        input_file = tmp_path / "failed.txt"
        input_file.write_text("content")

        # First failure
        manifest.record_failure(input_file, "run1", "error1")
        assert manifest.data["files"][str(input_file.absolute())]["attempt_count"] == 1

        # Second failure
        manifest.record_failure(input_file, "run2", "error2")
        assert manifest.data["files"][str(input_file.absolute())]["attempt_count"] == 2

    def test_record_failure_with_quarantine(self, manifest, tmp_path):
        """Test recording failure with quarantine path."""
        input_file = tmp_path / "failed.txt"
        input_file.write_text("content")
        quarantine_path = tmp_path / "quarantine" / "failed_FAILED.json"

        validation_report = {"status": "FAIL", "errors": ["missing_data"]}

        manifest.record_failure(
            input_path=input_file,
            run_id="test_run",
            reason="validation_failed",
            quarantine_path=quarantine_path,
            validation_report=validation_report
        )

        file_data = manifest.data["files"][str(input_file.absolute())]
        assert file_data["quarantine_path"] == str(quarantine_path.absolute())
        assert file_data["validation_report"] == validation_report

    def test_prune_deleted_files(self, manifest, tmp_path):
        """Test pruning deleted files from manifest."""
        # Create files
        file1 = tmp_path / "exists.txt"
        file1.write_text("content")
        file2_path = tmp_path / "deleted.txt"

        # Add both to manifest
        manifest.data["files"][str(file1.absolute())] = {"status": "success"}
        manifest.data["files"][str(file2_path.absolute())] = {"status": "success"}

        # Prune (file2 doesn't exist)
        pruned_count = manifest.prune_deleted_files(tmp_path)

        assert pruned_count == 1
        assert str(file1.absolute()) in manifest.data["files"]
        assert str(file2_path.absolute()) not in manifest.data["files"]

    def test_get_failed_files(self, manifest, tmp_path):
        """Test querying failed files."""
        # Add successful file
        success_file = tmp_path / "success.txt"
        success_file.write_text("content")
        manifest.data["files"][str(success_file.absolute())] = {
            "status": "success"
        }

        # Add failed files
        failed1 = tmp_path / "failed1.txt"
        failed1.write_text("content")
        manifest.data["files"][str(failed1.absolute())] = {
            "status": "failed",
            "reason": "error1"
        }

        failed2 = tmp_path / "failed2.txt"
        failed2.write_text("content")
        manifest.data["files"][str(failed2.absolute())] = {
            "status": "failed",
            "reason": "error2"
        }

        # Query failed files
        failed_files = manifest.get_failed_files()

        assert len(failed_files) == 2
        assert str(failed1.absolute()) in failed_files
        assert str(failed2.absolute()) in failed_files
        assert str(success_file.absolute()) not in failed_files

    def test_update_run_config(self, manifest):
        """Test updating run configuration."""
        config_snapshot = {
            "git_commit": "abc123",
            "researcher": "Test User",
            "timestamp": "2025-12-28T14:30:00"
        }

        manifest.update_run_config(config_snapshot)

        # Verify stored in run_configs with timestamp as key
        assert len(manifest.data["run_configs"]) == 1
        stored_config = list(manifest.data["run_configs"].values())[0]
        assert stored_config == config_snapshot

    def test_get_statistics(self, manifest, tmp_path):
        """Test getting processing statistics."""
        # Add files with different statuses
        for i in range(5):
            file_path = tmp_path / f"success_{i}.txt"
            file_path.write_text("content")
            manifest.data["files"][str(file_path.absolute())] = {"status": "success"}

        for i in range(3):
            file_path = tmp_path / f"failed_{i}.txt"
            file_path.write_text("content")
            manifest.data["files"][str(file_path.absolute())] = {"status": "failed"}

        stats = manifest.get_statistics()

        assert stats["total"] == 8
        assert stats["success"] == 5
        assert stats["failed"] == 3

    def test_statistics_empty_manifest(self, manifest):
        """Test statistics for empty manifest."""
        stats = manifest.get_statistics()

        assert stats["total"] == 0
        assert stats["success"] == 0
        assert stats["failed"] == 0


class TestRunContext:
    """Test cases for RunContext configuration snapshot."""

    def test_basic_initialization(self):
        """Test basic RunContext initialization."""
        run = RunContext(name="test_run")

        assert run.name == "test_run"
        assert run.base_dir is not None
        assert run.timestamp is not None

    def test_auto_git_sha_capture(self):
        """Test automatic git SHA capture."""
        with patch('src.config.run_context._get_current_git_sha', return_value='abc123'):
            run = RunContext(name="test_run", auto_git_sha=True)

            assert run.git_sha == 'abc123'

    def test_config_snapshot_capture(self):
        """Test config snapshot capture."""
        run = RunContext(name="test_run", capture_config=True)

        assert run.config_snapshot is not None
        assert "timestamp" in run.config_snapshot
        assert "python_version" in run.config_snapshot
        assert "platform" in run.config_snapshot

    def test_config_snapshot_git_metadata(self):
        """Test config snapshot includes git metadata."""
        with patch('src.config.run_context._get_current_git_sha', return_value='abc123'):
            with patch('subprocess.check_output') as mock_output:
                # Mock git branch
                mock_output.side_effect = [
                    b'main\n',  # git branch
                    b'Test User\n'  # git user.name
                ]

                run = RunContext(
                    name="test_run",
                    auto_git_sha=True,
                    capture_config=True
                )

                assert run.config_snapshot["git_commit"] == 'abc123'
                assert run.config_snapshot["git_branch"] == 'main'
                assert run.config_snapshot["researcher"] == 'Test User'

    def test_run_id_format(self):
        """Test run_id uses naming config format."""
        run = RunContext(name="test_run")

        # Should be in format YYYYMMDD_HHMMSS
        assert len(run.run_id) == 15
        assert run.run_id[8] == '_'

    def test_output_dir_naming(self):
        """Test output directory naming convention."""
        with patch('src.config.run_context._get_current_git_sha', return_value='abc123'):
            run = RunContext(
                name="test_run",
                auto_git_sha=True
            )

            output_dir_name = run.output_dir.name

            # Should contain run_id, name, and git_sha
            assert "test_run" in output_dir_name
            assert "abc123" in output_dir_name

    def test_create_output_directory(self, tmp_path):
        """Test creating output directory."""
        run = RunContext(
            name="test_run",
            base_dir=tmp_path
        )

        run.create()

        assert run.output_dir.exists()
        assert run.output_dir.is_dir()

    def test_save_config(self, tmp_path):
        """Test saving run configuration."""
        run = RunContext(name="test_run", base_dir=tmp_path)
        run.create()

        config = {"model": "test-model", "batch_size": 32}
        config_path = run.save_config(config)

        assert config_path.exists()
        assert config_path.name == "run_config.yaml"

    def test_save_metrics(self, tmp_path):
        """Test saving run metrics."""
        run = RunContext(name="test_run", base_dir=tmp_path)
        run.create()

        metrics = {"accuracy": 0.95, "f1_score": 0.93}
        metrics_path = run.save_metrics(metrics)

        assert metrics_path.exists()
        assert metrics_path.name == "metrics.json"

        # Verify metrics include metadata
        with open(metrics_path) as f:
            saved_data = json.load(f)

        assert saved_data["metrics"] == metrics
        assert "run_id" in saved_data
        assert "timestamp" in saved_data

    def test_load_metrics(self, tmp_path):
        """Test loading run metrics."""
        run = RunContext(name="test_run", base_dir=tmp_path)
        run.create()

        # Save metrics
        metrics = {"accuracy": 0.95}
        run.save_metrics(metrics)

        # Load metrics
        loaded = run.load_metrics()

        assert loaded is not None
        assert loaded["metrics"]["accuracy"] == 0.95

    def test_load_metrics_not_found(self, tmp_path):
        """Test loading metrics when file doesn't exist."""
        run = RunContext(name="test_run", base_dir=tmp_path)
        run.create()

        loaded = run.load_metrics()

        assert loaded is None

    def test_get_artifact_path(self, tmp_path):
        """Test getting artifact path."""
        run = RunContext(name="test_run", base_dir=tmp_path)

        artifact_path = run.get_artifact_path("model.pt")

        assert artifact_path.name == "model.pt"
        assert artifact_path.parent == run.output_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
