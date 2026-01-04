"""Unit tests for Priority 3: Auto-Documentation System."""

from datetime import datetime
from pathlib import Path

import pytest

from src.utils.reporting import MarkdownReportGenerator, ReportFormatter


class TestMarkdownReportGenerator:
    """Test cases for MarkdownReportGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create MarkdownReportGenerator instance."""
        return MarkdownReportGenerator()

    @pytest.fixture
    def basic_metrics(self):
        """Create basic metrics dict."""
        return {
            "total_files": 100,
            "successful": 95,
            "failed_or_skipped": 5,
            "quarantined": 3,
            "form_type": "10-K",
            "run_id": "20251228_143022"
        }

    @pytest.fixture
    def manifest_stats(self):
        """Create manifest statistics dict."""
        return {
            "total": 100,
            "success": 95,
            "failed": 5
        }

    @pytest.fixture
    def failed_files(self):
        """Create failed files dict."""
        return {
            "/path/to/file1.html": {
                "reason": "validation_failed",
                "attempt_count": 2,
                "last_attempt": "2025-12-28T14:30:22",
                "quarantine_path": "/path/quarantine/file1_FAILED.json"
            },
            "/path/to/file2.html": {
                "reason": "extraction_error",
                "attempt_count": 1,
                "last_attempt": "2025-12-28T14:31:15",
                "quarantine_path": "/path/quarantine/file2_FAILED.json"
            },
            "/path/to/file3.html": {
                "reason": "validation_failed",
                "attempt_count": 3,
                "last_attempt": "2025-12-28T14:32:05",
                "quarantine_path": "/path/quarantine/file3_FAILED.json"
            }
        }

    @pytest.fixture
    def config_snapshot(self):
        """Create config snapshot dict."""
        return {
            "git_commit": "abc123",
            "git_branch": "main",
            "researcher": "Test User",
            "timestamp": "2025-12-28T14:30:00",
            "python_version": "3.11.5",
            "platform": "Windows-10",
            "config": {}
        }

    def test_generate_run_report_basic(self, generator, basic_metrics, tmp_path):
        """Test basic run report generation."""
        report = generator.generate_run_report(
            run_id="20251228_143022",
            run_name="test_run",
            metrics=basic_metrics,
            output_dir=tmp_path
        )

        # Should contain key sections
        assert "# Processing Run Report: test_run" in report
        assert "Run ID:" in report
        assert "Executive Summary" in report
        assert "Total Files: 100" in report
        assert "Successful: 95" in report

    def test_generate_run_report_success_rate_calculation(self, generator, basic_metrics, tmp_path):
        """Test success rate calculation and emoji."""
        report = generator.generate_run_report(
            run_id="test_run",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path
        )

        # 95/100 = 95% success rate
        assert "95.0%" in report or "95%" in report

        # Should have success emoji (>= 95%)
        assert "✅" in report

    def test_generate_run_report_warning_emoji(self, generator, tmp_path):
        """Test warning emoji for medium success rate."""
        metrics = {
            "total_files": 100,
            "successful": 85,  # 85% - should show warning
            "failed_or_skipped": 15,
            "form_type": "10-K",
            "run_id": "test"
        }

        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=metrics,
            output_dir=tmp_path
        )

        # Should have warning emoji (80-95%)
        assert "⚠️" in report

    def test_generate_run_report_fail_emoji(self, generator, tmp_path):
        """Test fail emoji for low success rate."""
        metrics = {
            "total_files": 100,
            "successful": 70,  # 70% - should show fail
            "failed_or_skipped": 30,
            "form_type": "10-K",
            "run_id": "test"
        }

        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=metrics,
            output_dir=tmp_path
        )

        # Should have fail emoji (< 80%)
        assert "❌" in report

    def test_generate_run_report_with_git_sha(self, generator, basic_metrics, tmp_path):
        """Test report includes git SHA when provided."""
        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path,
            git_sha="abc123"
        )

        assert "Git SHA:" in report
        assert "abc123" in report

    def test_generate_run_report_with_duration(self, generator, basic_metrics, tmp_path):
        """Test report includes duration when timestamps provided."""
        start_time = "2025-12-28T14:00:00"
        end_time = "2025-12-28T14:02:34"  # 2 minutes 34 seconds

        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path,
            start_time=start_time,
            end_time=end_time
        )

        assert "Duration:" in report
        assert "2m 34s" in report

    def test_generate_run_report_collapsible_sections(self, generator, basic_metrics, tmp_path):
        """Test report includes collapsible HTML sections."""
        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path
        )

        # Should contain HTML details tags
        assert "<details" in report
        assert "<summary>" in report
        assert "</details>" in report
        assert "Processing Details" in report

    def test_generate_run_report_with_manifest_stats(self, generator, basic_metrics, manifest_stats, tmp_path):
        """Test report includes manifest statistics."""
        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path,
            manifest_stats=manifest_stats
        )

        assert "Incremental Processing" in report or "Manifest" in report
        assert "Total Tracked Files: 100" in report

    def test_generate_run_report_with_failed_files(self, generator, basic_metrics, failed_files, tmp_path):
        """Test report includes failed files analysis."""
        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path,
            failed_files=failed_files
        )

        assert "Failed Files Analysis" in report
        assert "Total Failed Files: 3" in report
        assert "Breakdown by Reason" in report
        assert "validation_failed" in report
        assert "extraction_error" in report

        # Should have table of recent failures
        assert "|" in report  # Table formatting

    def test_generate_run_report_failure_section_open_by_default(self, generator, basic_metrics, failed_files, tmp_path):
        """Test failed files section is open by default."""
        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path,
            failed_files=failed_files
        )

        # Should find details tag with open attribute before Failed Files section
        lines = report.split("\n")
        found_failed_section = False
        for i, line in enumerate(lines):
            if "Failed Files Analysis" in line:
                # Look backwards for details tag
                for j in range(i, max(0, i-5), -1):
                    if "<details" in lines[j]:
                        assert " open" in lines[j]
                        found_failed_section = True
                        break
                break

        assert found_failed_section

    def test_generate_run_report_with_config_snapshot(self, generator, basic_metrics, config_snapshot, tmp_path):
        """Test report includes configuration snapshot."""
        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path,
            config_snapshot=config_snapshot
        )

        assert "Configuration Snapshot" in report
        assert "Git Commit:" in report
        assert "abc123" in report
        assert "Test User" in report
        assert "Python Version:" in report

    def test_generate_run_report_with_quarantine(self, generator, basic_metrics, tmp_path):
        """Test report includes quarantine information."""
        quarantine_dir = tmp_path / "quarantine"

        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path,
            quarantine_dir=quarantine_dir
        )

        assert "Quarantine Directory:" in report
        assert str(quarantine_dir) in report

    def test_generate_run_report_action_items(self, generator, basic_metrics, failed_files, tmp_path):
        """Test report includes action items based on results."""
        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path,
            failed_files=failed_files
        )

        assert "Next Steps" in report
        assert "--only-failed" in report or "only-failed" in report

    def test_generate_run_report_footer(self, generator, basic_metrics, tmp_path):
        """Test report includes footer."""
        report = generator.generate_run_report(
            run_id="test",
            run_name="test",
            metrics=basic_metrics,
            output_dir=tmp_path
        )

        assert "MLOps Auto-Documentation System" in report

    def test_generate_quarantine_summary_basic(self, generator, failed_files, tmp_path):
        """Test basic quarantine summary generation."""
        quarantine_dir = tmp_path / "quarantine"
        output_path = tmp_path / "summary.md"

        summary = generator.generate_quarantine_summary(
            failed_files=failed_files,
            quarantine_dir=quarantine_dir,
            output_path=output_path
        )

        assert "Quarantine Summary Report" in summary
        assert "Total Failed Files: 3" in summary
        assert "Failure Breakdown" in summary

    def test_generate_quarantine_summary_breakdown_by_reason(self, generator, failed_files, tmp_path):
        """Test quarantine summary groups failures by reason."""
        quarantine_dir = tmp_path / "quarantine"
        output_path = tmp_path / "summary.md"

        summary = generator.generate_quarantine_summary(
            failed_files=failed_files,
            quarantine_dir=quarantine_dir,
            output_path=output_path
        )

        # Should show breakdown
        assert "validation_failed" in summary
        assert "extraction_error" in summary
        assert "2 files" in summary  # validation_failed has 2 files
        assert "1 files" in summary  # extraction_error has 1 file

    def test_generate_quarantine_summary_detailed_listings(self, generator, failed_files, tmp_path):
        """Test quarantine summary includes detailed listings."""
        quarantine_dir = tmp_path / "quarantine"
        output_path = tmp_path / "summary.md"

        summary = generator.generate_quarantine_summary(
            failed_files=failed_files,
            quarantine_dir=quarantine_dir,
            output_path=output_path
        )

        assert "Detailed Listings" in summary
        assert "|" in summary  # Table formatting
        assert "Attempts" in summary
        assert "Last Attempt" in summary

    def test_generate_quarantine_summary_recovery_instructions(self, generator, failed_files, tmp_path):
        """Test quarantine summary includes recovery instructions."""
        quarantine_dir = tmp_path / "quarantine"
        output_path = tmp_path / "summary.md"

        summary = generator.generate_quarantine_summary(
            failed_files=failed_files,
            quarantine_dir=quarantine_dir,
            output_path=output_path
        )

        assert "Recovery Instructions" in summary
        assert "```bash" in summary
        assert "--incremental --only-failed" in summary

    def test_generate_quarantine_summary_collapsible_by_reason(self, generator, failed_files, tmp_path):
        """Test quarantine summary uses collapsible sections for each reason."""
        quarantine_dir = tmp_path / "quarantine"
        output_path = tmp_path / "summary.md"

        summary = generator.generate_quarantine_summary(
            failed_files=failed_files,
            quarantine_dir=quarantine_dir,
            output_path=output_path
        )

        # Should have collapsible sections
        assert "<details" in summary
        assert "validation_failed" in summary

    def test_create_collapsible_section_basic(self, generator):
        """Test creating basic collapsible section."""
        section = generator._create_collapsible_section(
            title="Test Section",
            content="Test content",
            open_by_default=False
        )

        assert "<details>" in section
        assert "<summary><strong>Test Section</strong></summary>" in section
        assert "Test content" in section
        assert "</details>" in section

    def test_create_collapsible_section_open_by_default(self, generator):
        """Test creating collapsible section open by default."""
        section = generator._create_collapsible_section(
            title="Test Section",
            content="Test content",
            open_by_default=True
        )

        assert "<details open>" in section

    def test_format_timestamp_default(self, generator):
        """Test format_timestamp with default (current time)."""
        timestamp = generator._format_timestamp()

        # Should be in format YYYY-MM-DD HH:MM:SS
        assert len(timestamp) == 19
        assert timestamp[4] == "-"
        assert timestamp[7] == "-"
        assert timestamp[10] == " "
        assert timestamp[13] == ":"
        assert timestamp[16] == ":"

    def test_format_timestamp_custom(self, generator):
        """Test format_timestamp with custom timestamp."""
        custom_timestamp = "2025-12-28T14:30:22"
        timestamp = generator._format_timestamp(custom_timestamp)

        assert timestamp == custom_timestamp

    def test_format_duration_basic(self, generator):
        """Test duration formatting for various durations."""
        # 2 minutes 34 seconds
        duration = generator._format_duration(
            "2025-12-28T14:00:00",
            "2025-12-28T14:02:34"
        )
        assert duration == "2m 34s"

    def test_format_duration_hours(self, generator):
        """Test duration formatting with hours."""
        # 1 hour 15 minutes 30 seconds
        duration = generator._format_duration(
            "2025-12-28T14:00:00",
            "2025-12-28T15:15:30"
        )
        assert duration == "1h 15m 30s"

    def test_format_duration_seconds_only(self, generator):
        """Test duration formatting for short durations."""
        # 45 seconds
        duration = generator._format_duration(
            "2025-12-28T14:00:00",
            "2025-12-28T14:00:45"
        )
        assert duration == "45s"

    def test_format_duration_invalid_format(self, generator):
        """Test duration formatting handles invalid timestamps."""
        duration = generator._format_duration(
            "invalid",
            "also invalid"
        )
        assert duration == "N/A"


class TestReportFormatter:
    """Test cases for ReportFormatter class."""

    def test_format_status_icon_pass(self):
        """Test PASS status icon."""
        icon = ReportFormatter.format_status_icon("PASS")
        assert icon == "[PASS]"

    def test_format_status_icon_fail(self):
        """Test FAIL status icon."""
        icon = ReportFormatter.format_status_icon("FAIL")
        assert icon == "[FAIL]"

    def test_format_status_icon_warn(self):
        """Test WARN status icon."""
        icon = ReportFormatter.format_status_icon("WARN")
        assert icon == "[WARN]"

    def test_format_status_icon_error(self):
        """Test ERROR status icon."""
        icon = ReportFormatter.format_status_icon("ERROR")
        assert icon == "[ERR ]"

    def test_format_status_icon_unknown(self):
        """Test unknown status returns default."""
        icon = ReportFormatter.format_status_icon("UNKNOWN")
        assert icon == "[----]"

    def test_print_summary_basic(self, capsys):
        """Test print_summary outputs to console."""
        report = {
            "status": "PASS",
            "run_directory": "/path/to/data",
            "total_files": 100,
            "files_validated": 98,
            "overall_summary": {
                "passed": 95,
                "warned": 3,
                "failed": 0,
                "errors": 2
            }
        }

        ReportFormatter.print_summary(report)

        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "Total files: 100" in captured.out
        assert "Validated: 98" in captured.out
        assert "Passed: 95" in captured.out

    def test_print_summary_with_verbose(self, capsys):
        """Test print_summary verbose mode shows file results."""
        report = {
            "status": "PASS",
            "run_directory": "/path/to/data",
            "total_files": 10,
            "files_validated": 10,
            "overall_summary": {
                "passed": 10,
                "warned": 0,
                "failed": 0,
                "errors": 0
            },
            "per_file_results": [
                {"file": "file1.json", "overall_status": "PASS"},
                {"file": "file2.json", "overall_status": "PASS"}
            ]
        }

        ReportFormatter.print_summary(report, verbose=True)

        captured = capsys.readouterr()
        assert "Per-File Results:" in captured.out
        assert "file1.json" in captured.out
        assert "file2.json" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
