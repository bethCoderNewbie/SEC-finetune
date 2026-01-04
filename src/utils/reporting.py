"""Report formatting utilities for validation scripts."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReportFormatter:
    """
    Utilities for formatting validation reports.

    Provides consistent formatting for status icons, summaries, and tables
    across all validation scripts.
    """

    @staticmethod
    def format_status_icon(status: str) -> str:
        """
        Convert status to consistent icon format.

        Args:
            status: Status string ('PASS', 'WARN', 'FAIL', 'ERROR')

        Returns:
            Formatted icon string (e.g., '[PASS]', '[FAIL]')

        Example:
            >>> ReportFormatter.format_status_icon('PASS')
            '[PASS]'
            >>> ReportFormatter.format_status_icon('FAIL')
            '[FAIL]'
        """
        icons = {
            'PASS': '[PASS]',
            'WARN': '[WARN]',
            'FAIL': '[FAIL]',
            'ERROR': '[ERR ]'
        }
        return icons.get(status, '[----]')

    @staticmethod
    def print_summary(
        report: Dict[str, Any],
        title: str = "Validation Report",
        verbose: bool = False
    ) -> None:
        """
        Print human-readable summary to console.

        Args:
            report: Validation report dict
            title: Report title
            verbose: Show detailed per-file results

        Expected report structure:
            {
                "status": "PASS",
                "run_directory": "/path/to/data",
                "total_files": 100,
                "files_validated": 98,
                "overall_summary": {
                    "passed": 95,
                    "warned": 3,
                    "failed": 0,
                    "errors": 2
                },
                "per_file_results": [...]  # Optional for verbose mode
            }
        """
        print(f"\n{'='*60}")
        print(f"{title}: {report['status']}")
        print(f"{'='*60}")
        print(f"  Run directory: {report['run_directory']}")
        print(f"  Total files: {report['total_files']}")
        print(f"  Validated: {report['files_validated']}")

        if 'overall_summary' in report:
            summary = report['overall_summary']
            print(f"\n  File Status:")
            print(f"    Passed: {summary['passed']}")
            print(f"    Warned: {summary['warned']}")
            print(f"    Failed: {summary['failed']}")
            print(f"    Errors: {summary['errors']}")

        if verbose and report.get('per_file_results'):
            print(f"\n{'='*60}")
            print("Per-File Results:")
            print(f"{'='*60}")

            # Limit output to first 50 files in verbose mode
            for result in report['per_file_results'][:50]:
                status_icon = ReportFormatter.format_status_icon(
                    result.get('overall_status', 'ERROR')
                )

                print(f"  {status_icon} {result.get('file', 'unknown')}")

                if result.get('status') == 'error':
                    print(f"         Error: {result.get('error', 'Unknown error')}")

        print(f"\n{'='*60}")
        if report['status'] == 'PASS':
            print("Result: ALL CHECKS PASSED")
        elif report['status'] == 'WARN':
            print("Result: PASSED WITH WARNINGS")
        else:
            print("Result: CHECKS FAILED")
        print(f"{'='*60}")


class MarkdownReportGenerator:
    """
    Generate interactive markdown reports for batch processing runs.

    Features:
    - Collapsible sections for detailed information
    - Processing statistics and quality metrics
    - Manifest tracking information
    - Quarantine failure analysis
    - Executive summary for quick overview

    Usage:
        generator = MarkdownReportGenerator()
        report_content = generator.generate_run_report(
            run_id="20251228_143022",
            run_name="batch_parse",
            metrics=metrics_dict,
            manifest_stats=manifest.get_statistics(),
            output_dir=Path("data/interim/parsed/...")
        )
        report_path = output_dir / "RUN_REPORT.md"
        report_path.write_text(report_content)
    """

    def __init__(self):
        """Initialize the markdown report generator."""
        pass

    @staticmethod
    def _create_collapsible_section(title: str, content: str, open_by_default: bool = False) -> str:
        """
        Create a collapsible HTML details section for markdown.

        Args:
            title: Section title
            content: Section content (markdown supported)
            open_by_default: Whether section should be expanded by default

        Returns:
            HTML details block as string
        """
        open_attr = " open" if open_by_default else ""
        return f"""<details{open_attr}>
<summary><strong>{title}</strong></summary>

{content}

</details>
"""

    @staticmethod
    def _format_timestamp(timestamp: Optional[str] = None) -> str:
        """Format timestamp for display."""
        if timestamp:
            return timestamp
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _format_duration(start: str, end: str) -> str:
        """Calculate and format duration between two ISO timestamps."""
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            duration = end_dt - start_dt

            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        except Exception:
            return "N/A"

    def generate_run_report(
        self,
        run_id: str,
        run_name: str,
        metrics: Dict[str, Any],
        output_dir: Path,
        manifest_stats: Optional[Dict[str, Any]] = None,
        failed_files: Optional[Dict[str, Any]] = None,
        quarantine_dir: Optional[Path] = None,
        git_sha: Optional[str] = None,
        config_snapshot: Optional[Dict[str, Any]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> str:
        """
        Generate comprehensive markdown report for a processing run.

        Args:
            run_id: Run identifier (timestamp)
            run_name: Run name/stage
            metrics: Processing metrics dict
            output_dir: Output directory path
            manifest_stats: Optional manifest statistics
            failed_files: Optional failed files dict from manifest
            quarantine_dir: Optional quarantine directory path
            git_sha: Optional git commit SHA
            config_snapshot: Optional config snapshot dict
            start_time: Optional ISO timestamp for start
            end_time: Optional ISO timestamp for end

        Returns:
            Markdown report content as string
        """
        sections = []

        # Header
        sections.append(f"# Processing Run Report: {run_name}")
        sections.append(f"\n**Run ID:** `{run_id}`")
        if git_sha:
            sections.append(f"**Git SHA:** `{git_sha}`")
        sections.append(f"**Generated:** {self._format_timestamp()}")
        sections.append("")

        # Executive Summary
        sections.append("## 📊 Executive Summary")
        sections.append("")

        success_rate = 0
        if metrics.get('total_files', 0) > 0:
            success_rate = (metrics.get('successful', 0) / metrics['total_files']) * 100

        status_emoji = "✅" if success_rate >= 95 else "⚠️" if success_rate >= 80 else "❌"
        sections.append(f"{status_emoji} **Status:** {success_rate:.1f}% Success Rate")
        sections.append(f"- **Total Files:** {metrics.get('total_files', 0)}")
        sections.append(f"- **Successful:** {metrics.get('successful', 0)}")
        sections.append(f"- **Failed/Skipped:** {metrics.get('failed_or_skipped', 0)}")

        if metrics.get('quarantined', 0) > 0:
            sections.append(f"- **Quarantined:** {metrics.get('quarantined', 0)} (validation failures)")

        if start_time and end_time:
            duration = self._format_duration(start_time, end_time)
            sections.append(f"- **Duration:** {duration}")

        sections.append("")

        # Processing Details (Collapsible)
        details_content = f"""**Form Type:** {metrics.get('form_type', 'N/A')}
**Output Directory:** `{output_dir}`
**Run ID:** `{metrics.get('run_id', run_id)}`
"""

        if quarantine_dir:
            details_content += f"**Quarantine Directory:** `{quarantine_dir}`  \n"

        sections.append(self._create_collapsible_section(
            "📁 Processing Details",
            details_content,
            open_by_default=False
        ))
        sections.append("")

        # Manifest Statistics (if available)
        if manifest_stats:
            manifest_content = f"""**Total Tracked Files:** {manifest_stats.get('total', 0)}
**Successful:** {manifest_stats.get('success', 0)}
**Failed:** {manifest_stats.get('failed', 0)}

This run uses hash-based incremental processing to skip unchanged files.
"""

            sections.append(self._create_collapsible_section(
                "🔄 Incremental Processing (Manifest)",
                manifest_content,
                open_by_default=False
            ))
            sections.append("")

        # Failed Files Analysis (if any)
        if failed_files and len(failed_files) > 0:
            # Group by reason
            failures_by_reason = {}
            for file_path, file_data in failed_files.items():
                reason = file_data.get('reason', 'unknown')
                if reason not in failures_by_reason:
                    failures_by_reason[reason] = []
                failures_by_reason[reason].append((Path(file_path).name, file_data))

            failure_content = f"**Total Failed Files:** {len(failed_files)}\n\n"
            failure_content += "### Breakdown by Reason\n\n"

            for reason, files in sorted(failures_by_reason.items(), key=lambda x: len(x[1]), reverse=True):
                failure_content += f"- **{reason}:** {len(files)} files\n"

            failure_content += "\n### Recent Failures\n\n"
            recent = sorted(
                failed_files.items(),
                key=lambda x: x[1].get('last_attempt', ''),
                reverse=True
            )[:10]

            failure_content += "| File | Reason | Attempts | Last Attempt |\n"
            failure_content += "|------|--------|----------|-------------|\n"

            for file_path, file_data in recent:
                file_name = Path(file_path).name
                reason = file_data.get('reason', 'unknown')
                attempts = file_data.get('attempt_count', 1)
                last_attempt = file_data.get('last_attempt', 'N/A')[:19]  # Truncate timestamp

                failure_content += f"| {file_name} | {reason} | {attempts} | {last_attempt} |\n"

            if quarantine_dir:
                failure_content += f"\n**Quarantine Location:** `{quarantine_dir}`\n"
                failure_content += "\nEach failed file has:\n"
                failure_content += "- `*_FAILED.json` - Extracted data (for inspection)\n"
                failure_content += "- `*_FAILURE_REPORT.md` - Detailed failure analysis\n"

            sections.append(self._create_collapsible_section(
                "⚠️ Failed Files Analysis",
                failure_content,
                open_by_default=True  # Show failures by default
            ))
            sections.append("")

        # Configuration Snapshot (if available)
        if config_snapshot:
            config_content = f"""**Git Commit:** `{config_snapshot.get('git_commit', 'N/A')}`
**Git Branch:** `{config_snapshot.get('git_branch', 'N/A')}`
**Researcher:** {config_snapshot.get('researcher', 'N/A')}
**Python Version:** {config_snapshot.get('python_version', 'N/A')}
**Platform:** {config_snapshot.get('platform', 'N/A')}
**Timestamp:** {config_snapshot.get('timestamp', 'N/A')}

This snapshot enables full reproducibility of this processing run.
"""

            sections.append(self._create_collapsible_section(
                "⚙️ Configuration Snapshot",
                config_content,
                open_by_default=False
            ))
            sections.append("")

        # Action Items
        sections.append("## 🎯 Next Steps")
        sections.append("")

        if metrics.get('quarantined', 0) > 0:
            sections.append("- ⚠️ **Review quarantined files** - Check failure reports in quarantine directory")
            sections.append(f"- 🔄 **Reprocess failures** - Run with `--only-failed` flag after fixing issues")

        if manifest_stats and manifest_stats.get('failed', 0) > 0:
            sections.append(f"- 🔍 **Inspect quarantine** - Run with `--inspect-quarantine` to see detailed failure analysis")

        if success_rate >= 95:
            sections.append("- ✅ **All systems nominal** - Proceed with downstream processing")
        else:
            sections.append("- 🔧 **Investigate failures** - Review logs and failure reports")

        sections.append("")

        # Footer
        sections.append("---")
        sections.append("*Report generated by MLOps Auto-Documentation System*")

        return "\n".join(sections)

    def generate_quarantine_summary(
        self,
        failed_files: Dict[str, Any],
        quarantine_dir: Path,
        output_path: Path
    ) -> str:
        """
        Generate a focused summary report for quarantined files.

        Args:
            failed_files: Failed files dict from manifest
            quarantine_dir: Quarantine directory path
            output_path: Where to save the summary

        Returns:
            Markdown summary content as string
        """
        sections = []

        sections.append("# Quarantine Summary Report")
        sections.append(f"\n**Generated:** {self._format_timestamp()}")
        sections.append(f"**Quarantine Directory:** `{quarantine_dir}`")
        sections.append("")

        # Statistics
        sections.append("## 📊 Overview")
        sections.append(f"\n**Total Failed Files:** {len(failed_files)}")
        sections.append("")

        # Group by reason
        failures_by_reason = {}
        for file_path, file_data in failed_files.items():
            reason = file_data.get('reason', 'unknown')
            if reason not in failures_by_reason:
                failures_by_reason[reason] = []
            failures_by_reason[reason].append((file_path, file_data))

        sections.append("### Failure Breakdown")
        sections.append("")
        for reason, files in sorted(failures_by_reason.items(), key=lambda x: len(x[1]), reverse=True):
            sections.append(f"- **{reason}:** {len(files)} files")
        sections.append("")

        # Detailed listings by reason
        sections.append("## 📋 Detailed Listings")
        sections.append("")

        for reason, files in sorted(failures_by_reason.items(), key=lambda x: len(x[1]), reverse=True):
            reason_content = f"**Count:** {len(files)}\n\n"
            reason_content += "| File | Attempts | Last Attempt | Quarantine Path |\n"
            reason_content += "|------|----------|--------------|----------------|\n"

            for file_path, file_data in sorted(files, key=lambda x: x[1].get('last_attempt', ''), reverse=True):
                file_name = Path(file_path).name
                attempts = file_data.get('attempt_count', 1)
                last_attempt = file_data.get('last_attempt', 'N/A')[:19]
                qpath = file_data.get('quarantine_path', 'N/A')
                qpath_name = Path(qpath).name if qpath != 'N/A' else 'N/A'

                reason_content += f"| {file_name} | {attempts} | {last_attempt} | {qpath_name} |\n"

            sections.append(self._create_collapsible_section(
                f"🔴 {reason} ({len(files)} files)",
                reason_content,
                open_by_default=(len(files) <= 5)  # Open if few files
            ))
            sections.append("")

        # Recovery instructions
        sections.append("## 🔧 Recovery Instructions")
        sections.append("")
        sections.append("1. **Inspect failure reports:**")
        sections.append(f"   ```bash")
        sections.append(f"   ls {quarantine_dir}/*_FAILURE_REPORT.md")
        sections.append(f"   ```")
        sections.append("")
        sections.append("2. **Review quarantined data:**")
        sections.append(f"   ```bash")
        sections.append(f"   cat {quarantine_dir}/<filename>_FAILED.json")
        sections.append(f"   ```")
        sections.append("")
        sections.append("3. **Reprocess after fixes:**")
        sections.append(f"   ```bash")
        sections.append(f"   python scripts/data_preprocessing/batch_parse.py --incremental --only-failed")
        sections.append(f"   ```")
        sections.append("")

        sections.append("---")
        sections.append("*Report generated by MLOps Auto-Documentation System*")

        return "\n".join(sections)
