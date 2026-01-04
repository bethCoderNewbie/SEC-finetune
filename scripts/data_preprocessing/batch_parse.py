"""
Batch parse all SEC filings in data/raw/ directory and save as JSON files

Usage:
    # Basic usage (creates new run folder with timestamp)
    python scripts/data_preprocessing/batch_parse.py
    python scripts/data_preprocessing/batch_parse.py --run-name my_parsing_run

    # Form type selection
    python scripts/data_preprocessing/batch_parse.py --form-type 10-K
    python scripts/data_preprocessing/batch_parse.py --form-type 10-Q

    # Resume mode - skip files already parsed in ANY run
    python scripts/data_preprocessing/batch_parse.py --resume
    python scripts/data_preprocessing/batch_parse.py --resume --run-name ver1

    # Incremental mode - skip unchanged files based on content hash (NEW)
    python scripts/data_preprocessing/batch_parse.py --incremental
    python scripts/data_preprocessing/batch_parse.py --incremental --prune-deleted

    # Validation with quarantine (NEW)
    python scripts/data_preprocessing/batch_parse.py --validate

    # Selective reprocessing (NEW)
    python scripts/data_preprocessing/batch_parse.py --only-failed  # Reprocess only failed files
    python scripts/data_preprocessing/batch_parse.py --inspect-quarantine  # View quarantine status

    # Continue a specific previous run (reuse existing run folder)
    python scripts/data_preprocessing/batch_parse.py --continue-run 20251212_200149_ver1_ea45dd2

    # Performance options
    python scripts/data_preprocessing/batch_parse.py --quiet                    # Minimal output
    python scripts/data_preprocessing/batch_parse.py --checkpoint-interval 5    # Save progress every 5 files
    python scripts/data_preprocessing/batch_parse.py --timeout 600              # Set 10-minute timeout per file

    # Overwrite existing files
    python scripts/data_preprocessing/batch_parse.py --overwrite

    # Combined example
    python scripts/data_preprocessing/batch_parse.py --run-name production --incremental --quiet

Output Structure:
    data/interim/parsed/{run_id}_{run_name}_{git_sha}/
    ├── AAPL_10K_2021_{run_id}_parsed.json
    ├── MSFT_10K_2022_{run_id}_parsed.json
    ├── metrics.json
    ├── RUN_REPORT.md  (auto-generated documentation)
    ├── .manifest.json  (state tracking for incremental processing)
    └── _checkpoint.json  (removed on completion)

    # If validation failures occur:
    data/interim/parsed/quarantine_{run_id}_{stage}_{git_sha}/
    ├── {filename}_FAILED.json
    ├── {filename}_FAILURE_REPORT.md
    └── QUARANTINE_SUMMARY.md  (auto-generated summary)
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import functools

from src.preprocessing.parser import SECFilingParser
from src.preprocessing.pipeline import SECPreprocessingPipeline
from src.config import settings, RunContext
from src.config.qa_validation import HealthCheckValidator
from src.utils.state_manager import StateManifest
from src.utils.reporting import MarkdownReportGenerator
from src.utils.progress_logger import BatchProgressLogger


# =============================================================================
# Timeout Handling
# =============================================================================

def run_with_timeout(func, timeout_seconds, *args, **kwargs):
    """
    Execute a function with a timeout using ThreadPoolExecutor (cross-platform).

    Args:
        func: Function to execute
        timeout_seconds: Maximum execution time in seconds
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Function result if completed within timeout

    Raises:
        TimeoutError: If function execution exceeds timeout
        Exception: Any exception raised by func

    Note:
        Uses ThreadPoolExecutor for cross-platform compatibility (works on Windows).
        For CPU-bound operations, this provides timeout protection even though
        Python's GIL may limit true parallelism.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError:
            # Try to cancel the future, though it may not stop the underlying thread
            future.cancel()
            raise TimeoutError(f"Operation exceeded timeout of {timeout_seconds} seconds")


# =============================================================================
# Resume & Smart Sampling Helpers
# =============================================================================

def is_file_parsed(input_file: Path, output_dir: Path, run_id: Optional[str] = None, form_type: str = "10-K") -> bool:
    """
    Check if a file has already been parsed by checking for output in output_dir.

    Args:
        input_file: Path to input HTML file
        output_dir: Directory containing parsed files
        run_id: Optional run identifier for filename matching
        form_type: SEC form type (10-K or 10-Q)

    Returns:
        True if the parsed output file exists, False otherwise
    """
    run_suffix = f"_{run_id}" if run_id else ""
    output_filename = f"{input_file.stem}{run_suffix}_parsed.json"
    output_path = output_dir / output_filename
    return output_path.exists()


def get_parsed_files_set(output_dir: Path, run_id: Optional[str] = None) -> Set[str]:
    """
    Get set of all already parsed file stems for fast lookup.
    More efficient than checking each file individually.

    Args:
        output_dir: Directory containing parsed files
        run_id: Optional run identifier for filename matching (None = check ANY run)

    Returns:
        Set of file stems that have been parsed
    """
    parsed = set()
    if not output_dir.exists():
        return parsed

    # Pattern: {stem}_{run_id}_parsed.json
    # If run_id is None, match any run_id with wildcard
    if run_id:
        pattern = f"*_{run_id}_parsed.json"
    else:
        pattern = "*_parsed.json"

    for f in output_dir.glob(pattern):
        # Extract original stem by removing suffix
        # Filename: AAPL_10K_2021_20241212_153022_parsed.json
        stem = f.stem  # e.g., "AAPL_10K_2021_20241212_153022_parsed"
        # Remove "_parsed" suffix
        stem = stem.replace("_parsed", "")
        # Remove run_id (timestamp pattern YYYYMMDD_HHMMSS)
        stem = re.sub(r'_\d{8}_\d{6}$', '', stem)
        parsed.add(stem)

    return parsed


def get_parsed_files_set_all_runs(base_dir: Path) -> Set[str]:
    """
    Get set of all already parsed file stems across ALL run folders.
    Use this for --resume to skip files parsed in any previous run.

    Args:
        base_dir: Base directory containing run folders (e.g., data/interim/parsed/)

    Returns:
        Set of file stems that have been parsed in any run
    """
    parsed = set()
    if not base_dir.exists():
        return parsed

    # Check all run folders
    for run_folder in base_dir.iterdir():
        if run_folder.is_dir():
            parsed.update(get_parsed_files_set(run_folder, run_id=None))

    return parsed


def filter_unparsed_files(
    html_files: List[Path],
    output_dir: Path,
    run_id: Optional[str] = None,
    quiet: bool = False,
    check_all_runs: bool = False,
    base_dir: Optional[Path] = None
) -> List[Path]:
    """
    Filter out already parsed files efficiently using batch lookup.

    Args:
        html_files: List of input HTML file paths
        output_dir: Directory containing parsed files for current run
        run_id: Optional run identifier (only used if check_all_runs=False)
        quiet: If True, suppress output
        check_all_runs: If True, check ALL run folders in base_dir
        base_dir: Base directory containing all run folders (required if check_all_runs=True)

    Returns:
        List of unparsed files
    """
    if check_all_runs and base_dir:
        parsed_stems = get_parsed_files_set_all_runs(base_dir)
    else:
        parsed_stems = get_parsed_files_set(output_dir, run_id)

    unparsed = [f for f in html_files if f.stem not in parsed_stems]

    skipped = len(html_files) - len(unparsed)
    if skipped > 0 and not quiet:
        print(f"Resume mode: Skipping {skipped} already parsed files")

    return unparsed


def save_checkpoint(checkpoint_path: Path, processed_files: List[str], metrics: dict) -> None:
    """
    Save checkpoint for crash recovery.

    Args:
        checkpoint_path: Path to checkpoint file
        processed_files: List of successfully processed file names
        metrics: Current metrics dict
    """
    checkpoint_data = {
        "processed_files": processed_files,
        "metrics": metrics,
        "timestamp": datetime.now().isoformat()
    }
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(checkpoint_data, f, indent=2)


def load_checkpoint(checkpoint_path: Path) -> Optional[dict]:
    """
    Load checkpoint if exists.

    Args:
        checkpoint_path: Path to checkpoint file

    Returns:
        Checkpoint data or None if not found
    """
    if not checkpoint_path.exists():
        return None
    with open(checkpoint_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def inspect_quarantine(input_dir: Path, quiet: bool = False) -> None:
    """
    Inspect quarantined files and show failure statistics.

    Args:
        input_dir: Directory containing the manifest
        quiet: Minimize output
    """
    manifest_path = input_dir / ".manifest.json"
    if not manifest_path.exists():
        print(f"No manifest found at: {manifest_path}")
        print("Run with --incremental first to create manifest tracking.")
        return

    # Load manifest
    manifest = StateManifest(manifest_path)
    manifest.load()

    # Get failed files
    failed_files = manifest.get_failed_files()

    if not failed_files:
        print("✓ No failed files in manifest")
        return

    # Get statistics
    stats = manifest.get_statistics()

    print("=" * 80)
    print("QUARANTINE INSPECTION REPORT")
    print("=" * 80)
    print(f"\nManifest: {manifest_path}")
    print(f"\nOverall Statistics:")
    print(f"  Total tracked files: {stats['total']}")
    print(f"  Successful: {stats['success']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Failure rate: {stats['failed'] / stats['total'] * 100:.1f}%")

    # Group failures by reason
    failures_by_reason = {}
    for file_path, file_data in failed_files.items():
        reason = file_data.get('reason', 'unknown')
        if reason not in failures_by_reason:
            failures_by_reason[reason] = []
        failures_by_reason[reason].append((file_path, file_data))

    print(f"\nFailure Breakdown:")
    for reason, files in sorted(failures_by_reason.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {reason}: {len(files)} files")

    # Show recent failures (last 5)
    print(f"\nRecent Failures (last 5):")
    recent_failures = sorted(
        failed_files.items(),
        key=lambda x: x[1].get('last_attempt', ''),
        reverse=True
    )[:5]

    for file_path, file_data in recent_failures:
        print(f"\n  File: {Path(file_path).name}")
        print(f"    Reason: {file_data.get('reason', 'unknown')}")
        print(f"    Last Attempt: {file_data.get('last_attempt', 'N/A')}")
        print(f"    Attempt Count: {file_data.get('attempt_count', 1)}")

        quarantine_path = file_data.get('quarantine_path')
        if quarantine_path:
            print(f"    Quarantine: {Path(quarantine_path).name}")

            # Check if failure report exists
            failure_report = Path(str(quarantine_path).replace('_FAILED.json', '_FAILURE_REPORT.md'))
            if failure_report.exists():
                print(f"    Report: {failure_report.name}")

    # Show quarantine directories
    if 'quarantine_path' in next(iter(failed_files.values()), {}):
        quarantine_dirs = set()
        for file_data in failed_files.values():
            qpath = file_data.get('quarantine_path')
            if qpath:
                quarantine_dirs.add(Path(qpath).parent)

        if quarantine_dirs:
            print(f"\nQuarantine Directories:")
            for qdir in sorted(quarantine_dirs):
                if qdir.exists():
                    file_count = len(list(qdir.glob("*_FAILED.json")))
                    report_count = len(list(qdir.glob("*_FAILURE_REPORT.md")))
                    print(f"  {qdir}")
                    print(f"    Files: {file_count}, Reports: {report_count}")

    print("\n" + "=" * 80)
    print(f"\nTo reprocess failed files, run:")
    print(f"  python scripts/data_preprocessing/batch_parse.py --only-failed")
    print("=" * 80)


def batch_parse_filings(
    input_dir: Path = None,
    output_dir: Path = None,
    form_type: str = "10-K",
    pattern: str = "*.html",
    overwrite: bool = False,
    run_context: RunContext = None,
    resume: bool = False,
    checkpoint_interval: int = 10,
    quiet: bool = False,
    explicit_run_id: Optional[str] = None,
    incremental: bool = False,
    prune_deleted: bool = False,
    use_validation: bool = False,
    only_failed: bool = False,
    timeout: int = 1200
):
    """
    Parse all HTML filings in a directory and save as JSON files

    Args:
        input_dir: Directory containing HTML files (defaults to settings.paths.raw_data_dir)
        output_dir: Directory to save parsed files (defaults to settings.paths.parsed_data_dir)
        form_type: Type of SEC form (10-K or 10-Q)
        pattern: File pattern to match (default: *.html)
        overwrite: Whether to overwrite existing JSON files
        run_context: Optional RunContext for metric logging
        resume: Whether to skip already parsed files
        checkpoint_interval: Save checkpoint every N files (default: 10)
        quiet: Minimize output
        explicit_run_id: Optional explicit run_id (used when continuing a previous run)
        incremental: Whether to use hash-based incremental processing (skip unchanged files)
        prune_deleted: Whether to prune deleted files from manifest
        use_validation: Whether to validate output and quarantine failures
        only_failed: Whether to reprocess only failed files from manifest (NEW)
        timeout: Maximum time in seconds to parse each file (default: 1200 = 20 minutes)
    """
    # Capture start time for duration tracking
    start_time = datetime.now().isoformat()

    # Use default if not provided
    if input_dir is None:
        input_dir = settings.paths.raw_data_dir

    if output_dir is None:
        output_dir = settings.paths.parsed_data_dir

    # Ensure directories exist
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    settings.paths.ensure_directories()

    # Initialize state manifest for incremental processing
    manifest = None
    if incremental:
        manifest_path = input_dir / ".manifest.json"
        manifest = StateManifest(manifest_path)
        manifest.load()

        # Prune deleted files if requested
        if prune_deleted:
            pruned_count = manifest.prune_deleted_files(input_dir)
            if pruned_count > 0 and not quiet:
                print(f"Pruned {pruned_count} deleted files from manifest")

        # Update run config with snapshot if run_context available
        if run_context and run_context.config_snapshot:
            manifest.update_run_config(run_context.config_snapshot)

    # Set up quarantine directory for validation failures (NEW)
    quarantine_dir = None
    pipeline = None
    validator = None
    if use_validation:
        # Use explicit_run_id or get from run_context
        temp_run_id = explicit_run_id or (run_context.run_id if run_context else None)
        if temp_run_id is None:
            temp_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Quarantine directory naming: quarantine_{run_id}_{stage}_{git_sha}
        git_sha = run_context.git_sha if run_context else None
        quarantine_name = f"quarantine_{temp_run_id}_batch_parse"
        if git_sha:
            quarantine_name += f"_{git_sha}"

        quarantine_dir = output_dir.parent / quarantine_name
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        # Initialize pipeline and validator
        pipeline = SECPreprocessingPipeline()
        validator = HealthCheckValidator()

        if not quiet:
            print(f"Validation enabled - Quarantine directory: {quarantine_dir}")

    # Find all HTML files
    html_files = sorted(list(input_dir.glob(pattern)))  # Sort for deterministic order

    if not html_files:
        print(f"No files matching '{pattern}' found in: {input_dir}")
        return

    total_found = len(html_files)
    # Use explicit_run_id if provided (for --continue-run), otherwise get from run_context
    run_id = explicit_run_id or (run_context.run_id if run_context else None)

    # Only-failed: filter to only failed files from manifest (NEW)
    if only_failed:
        if not manifest:
            print("Error: --only-failed requires manifest tracking (use --incremental)")
            return

        failed_files_dict = manifest.get_failed_files()
        if not failed_files_dict:
            print("No failed files in manifest. Nothing to reprocess.")
            return

        # Convert failed files dict keys (strings) to Path objects for filtering
        failed_paths = {Path(fp) for fp in failed_files_dict.keys()}

        # Filter to only files that are in the failed set
        original_count = len(html_files)
        html_files = [f for f in html_files if f in failed_paths]

        if not html_files:
            print(f"No failed files found in input directory: {input_dir}")
            print(f"Manifest contains {len(failed_paths)} failed files, but none were found in input.")
            return

        if not quiet:
            print(f"Only-failed mode: Reprocessing {len(html_files)} failed files (out of {len(failed_paths)} total failures)")

    # Incremental: filter files using hash-based change detection
    if incremental and manifest and not overwrite:
        original_count = len(html_files)
        html_files = [f for f in html_files if manifest.should_process(f, force=overwrite)]
        skipped_count = original_count - len(html_files)
        if skipped_count > 0 and not quiet:
            print(f"Incremental mode: Skipping {skipped_count} unchanged files (hash-based)")

    # Resume: filter out already parsed files (check ALL run folders)
    elif resume and not overwrite:
        # Get base_dir (parent of output_dir, e.g., data/interim/parsed/)
        base_dir = output_dir.parent if output_dir else settings.paths.parsed_data_dir
        html_files = filter_unparsed_files(
            html_files,
            output_dir,
            run_id=run_id,
            quiet=quiet,
            check_all_runs=True,
            base_dir=base_dir
        )
        if not html_files:
            print("All files have already been parsed. Nothing to do.")
            return

    # Initialize progress logger for real-time monitoring
    progress_log_path = output_dir / "_progress.log"
    progress_logger = BatchProgressLogger(
        log_path=progress_log_path,
        total_items=len(html_files),
        console=not quiet,
        quiet=quiet
    )

    if not quiet:
        print(f"Found {total_found} file(s) total")
        if resume:
            print(f"Processing {len(html_files)} unparsed file(s)")
        print(f"Output directory: {output_dir}")
        if run_context and run_context.git_sha:
            print(f"Git SHA: {run_context.git_sha}")
        print(f"Progress log: {progress_log_path}")
        print("=" * 80)

    # Checkpoint setup
    checkpoint_path = output_dir / "_checkpoint.json" if output_dir else None
    processed_files: List[str] = []

    # Initialize parser (only if not using validation)
    parser = None
    if not use_validation:
        parser = SECFilingParser()

    # Parse each file
    success_count = 0
    error_count = 0
    skipped_count = 0
    quarantine_count = 0  # NEW: Track quarantined files

    # Use run_id for consistent naming (already set above)
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    for idx, html_file in enumerate(html_files, 1):
        # Log file processing start
        progress_logger.log_item_start(html_file.name)

        try:
            # Construct output path with consistent run_id
            # Convention: {original_stem}_{run_id}_{output_type}.json
            filename = f"{html_file.stem}_{run_id}_parsed.json"
            output_path = output_dir / filename

            # Process with or without validation
            if use_validation:
                # Use pipeline with inline validation (with timeout protection)
                result, status, validation_report = run_with_timeout(
                    pipeline.process_and_validate,
                    timeout,
                    file_path=html_file,
                    form_type=form_type,
                    validator=validator
                )

                if status == "FAIL":
                    # Quarantine the file
                    quarantine_count += 1
                    if result:
                        # Save to quarantine directory
                        quarantine_path = quarantine_dir / f"{html_file.stem}_FAILED.json"
                        result.save_to_json(quarantine_path, overwrite=True)

                        # Write failure report
                        failure_report_path = quarantine_dir / f"{html_file.stem}_FAILURE_REPORT.md"
                        failure_report_path.write_text(
                            f"# Validation Failure\n\n"
                            f"**File:** {html_file.name}\n"
                            f"**Status:** {status}\n"
                            f"**Timestamp:** {validation_report.get('timestamp', 'N/A')}\n\n"
                            f"## Blocking Issues\n\n{validation_report.get('blocking_summary', 'No summary available')}\n\n"
                            f"## Full Report\n\n```\n{validation_report.get('validation_table', 'No details available')}\n```\n"
                        )

                        # Log quarantine
                        progress_logger.log_item_error(
                            html_file.name,
                            f"Validation failed - quarantined: {quarantine_path.name}"
                        )

                        # Record failure in manifest
                        if manifest:
                            manifest.record_failure(
                                input_path=html_file,
                                run_id=run_id,
                                reason="validation_failed",
                                quarantine_path=quarantine_path,
                                validation_report=validation_report
                            )
                    error_count += 1
                    continue  # Skip to next file

                # Validation passed - save to production
                if result:
                    result.save_to_json(output_path, overwrite=overwrite)
                    progress_logger.log_item_success(
                        html_file.name,
                        f"Validation PASS - {len(result)} segments → {output_path.name}"
                    )
                else:
                    # Processing failed but didn't raise exception
                    error_count += 1
                    progress_logger.log_item_error(html_file.name, "Processing returned None")
                    continue

                filing = result  # For compatibility with success tracking below

            else:
                # Standard parsing without validation (with timeout protection)
                filing = run_with_timeout(
                    parser.parse_filing,
                    timeout,
                    html_file,
                    form_type=form_type,
                    save_output=output_path,
                    overwrite=overwrite
                )

                # Log success
                sections = filing.get_section_names()
                section_info = f", first: {sections[0]}" if sections else ""
                progress_logger.log_item_success(
                    html_file.name,
                    f"{len(filing)} elements, {filing.metadata['num_sections']} sections{section_info}"
                )

                # Update progress indicator
                if quiet:
                    progress_logger.update_progress()

            success_count += 1
            processed_files.append(html_file.name)

            # Record success in manifest (incremental mode)
            if manifest:
                manifest.record_success(
                    input_path=html_file,
                    output_path=output_path,
                    run_id=run_id,
                    validation_report=validation_report if use_validation else None
                )

            # Save checkpoint periodically
            if checkpoint_path and idx % checkpoint_interval == 0:
                current_metrics = {
                    "total_files": len(html_files),
                    "successful": success_count,
                    "failed_or_skipped": error_count,
                    "skipped": skipped_count,
                    "form_type": form_type
                }
                save_checkpoint(checkpoint_path, processed_files, current_metrics)

        except FileExistsError:
            progress_logger.log_item_warning(
                html_file.name,
                "File already exists (use --overwrite to replace)"
            )
            skipped_count += 1
            error_count += 1  # Count as error/skip for total tracking

        except TimeoutError as e:
            # Handle timeout specifically for better tracking
            timeout_msg = f"Timeout after {timeout}s"
            progress_logger.log_item_error(html_file.name, timeout_msg)
            error_count += 1

            # Record timeout in manifest (incremental mode)
            if manifest:
                manifest.record_failure(
                    input_path=html_file,
                    run_id=run_id,
                    reason=f"timeout_{timeout}s"
                )

        except Exception as e:
            progress_logger.log_item_error(html_file.name, str(e))
            error_count += 1

            # Record failure in manifest (incremental mode)
            if manifest:
                manifest.record_failure(
                    input_path=html_file,
                    run_id=run_id,
                    reason=str(e)
                )

    # Log summary to progress logger
    progress_logger.log_summary()

    # Metrics
    metrics = {
        "total_files": len(html_files),
        "successful": success_count,
        "failed_or_skipped": error_count,
        "skipped": skipped_count,
        "quarantined": quarantine_count,  # NEW
        "form_type": form_type,
        "run_id": run_id
    }

    # Save metrics to RunContext if available
    if run_context:
        run_context.save_metrics(metrics)
        if not quiet:
            print(f"\nMetrics saved to: {run_context.output_dir / 'metrics.json'}")

    # Save manifest (incremental mode)
    if manifest:
        manifest.save()
        if not quiet:
            stats = manifest.get_statistics()
            print(f"\nManifest Statistics:")
            print(f"  Total tracked files: {stats['total']}")
            print(f"  Successful: {stats['success']}")
            print(f"  Failed: {stats['failed']}")

    # Remove checkpoint on successful completion
    if checkpoint_path and checkpoint_path.exists():
        checkpoint_path.unlink()

    # Generate markdown report (auto-documentation)
    end_time = datetime.now().isoformat()
    report_generator = MarkdownReportGenerator()

    # Gather data for report
    manifest_stats = manifest.get_statistics() if manifest else None
    failed_files_dict = manifest.get_failed_files() if manifest else None
    config_snapshot = run_context.config_snapshot if run_context else None
    git_sha = run_context.git_sha if run_context else None

    # Determine run name
    report_run_name = run_context.name if run_context else "batch_parse"

    # Generate comprehensive run report
    report_content = report_generator.generate_run_report(
        run_id=run_id,
        run_name=report_run_name,
        metrics=metrics,
        output_dir=output_dir,
        manifest_stats=manifest_stats,
        failed_files=failed_files_dict,
        quarantine_dir=quarantine_dir,
        git_sha=git_sha,
        config_snapshot=config_snapshot,
        start_time=start_time,
        end_time=end_time
    )

    # Save run report
    report_path = output_dir / "RUN_REPORT.md"
    report_path.write_text(report_content, encoding='utf-8')

    if not quiet:
        print(f"\n📄 Run report generated: {report_path}")

    # Generate quarantine summary if there are failures
    if quarantine_dir and failed_files_dict and len(failed_files_dict) > 0:
        quarantine_summary = report_generator.generate_quarantine_summary(
            failed_files=failed_files_dict,
            quarantine_dir=quarantine_dir,
            output_path=quarantine_dir / "QUARANTINE_SUMMARY.md"
        )

        quarantine_summary_path = quarantine_dir / "QUARANTINE_SUMMARY.md"
        quarantine_summary_path.write_text(quarantine_summary, encoding='utf-8')

        if not quiet:
            print(f"📄 Quarantine summary: {quarantine_summary_path}")

    # Summary
    if not quiet:
        print("\n" + "=" * 80)
        print(f"Batch processing complete!")
        print(f"  Successful: {success_count}")
        print(f"  Errors/Skipped: {error_count}")
        if use_validation:
            print(f"  Quarantined (validation failed): {quarantine_count}")
        print(f"  Total: {len(html_files)}")
        print(f"\nParsed files saved to: {output_dir}")
        if use_validation and quarantine_count > 0:
            print(f"Quarantined files: {quarantine_dir}")
        print(f"Progress log: {progress_log_path}")
    else:
        summary = f"Complete: {success_count}/{len(html_files)} successful"
        if use_validation and quarantine_count > 0:
            summary += f", {quarantine_count} quarantined"
        print(summary)

    # Close progress logger
    progress_logger.close()


def main():
    parser = argparse.ArgumentParser(
        description="Batch parse SEC filings and save as JSON files"
    )
    parser.add_argument(
        '--form-type',
        type=str,
        default='10-K',
        choices=['10-K', '10-Q'],
        help='Type of SEC form (default: 10-K)'
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        help=f'Input directory (default: {settings.paths.raw_data_dir})'
    )
    parser.add_argument(
        '--pattern',
        type=str,
        default='*.html',
        help='File pattern to match (default: *.html)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing JSON files'
    )
    parser.add_argument(
        '--run-name',
        type=str,
        default='batch_parse',
        help='Name for this execution run'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Skip files that have already been parsed (smart sampling)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimize output for better performance'
    )
    parser.add_argument(
        '--checkpoint-interval',
        type=int,
        default=10,
        help='Save checkpoint every N files (default: 10)'
    )
    parser.add_argument(
        '--continue-run',
        type=str,
        default=None,
        metavar='RUN_FOLDER',
        help='Continue a previous run by specifying its folder name (e.g., 20251212_200149_ver1_ea45dd2)'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Use hash-based incremental processing (skip unchanged files)'
    )
    parser.add_argument(
        '--prune-deleted',
        action='store_true',
        help='Prune deleted files from manifest (use with --incremental)'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate output and quarantine failures (inline gatekeeper pattern)'
    )
    parser.add_argument(
        '--only-failed',
        action='store_true',
        help='Reprocess only failed files from manifest (requires --incremental)'
    )
    parser.add_argument(
        '--inspect-quarantine',
        action='store_true',
        help='Show quarantine status and exit (does not process files)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=1200,
        help='Maximum time in seconds to parse each file (default: 1200 = 20 minutes)'
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir) if args.input_dir else settings.paths.raw_data_dir

    # Handle --inspect-quarantine: show status and exit (NEW)
    if args.inspect_quarantine:
        inspect_quarantine(input_dir, quiet=args.quiet)
        return

    # Handle --continue-run: reuse existing run folder
    if args.continue_run:
        output_dir = settings.paths.parsed_data_dir / args.continue_run
        if not output_dir.exists():
            print(f"Error: Run folder not found: {output_dir}")
            print(f"Available runs in {settings.paths.parsed_data_dir}:")
            if settings.paths.parsed_data_dir.exists():
                for folder in sorted(settings.paths.parsed_data_dir.iterdir()):
                    if folder.is_dir():
                        print(f"  - {folder.name}")
            return

        # Extract run_id from folder name (first part before second underscore)
        # Format: 20251212_200149_ver1_ea45dd2
        parts = args.continue_run.split('_')
        run_id = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else args.continue_run

        if not args.quiet:
            print(f"Continuing run: {args.continue_run}")
            print(f"Run ID: {run_id}")
            print(f"Output Directory: {output_dir}")

        batch_parse_filings(
            input_dir=input_dir,
            output_dir=output_dir,
            form_type=args.form_type,
            pattern=args.pattern,
            overwrite=args.overwrite,
            run_context=None,  # No new RunContext for continued runs
            resume=True,  # Always resume when continuing
            checkpoint_interval=args.checkpoint_interval,
            quiet=args.quiet,
            explicit_run_id=run_id,
            incremental=args.incremental,
            prune_deleted=args.prune_deleted,
            use_validation=args.validate,
            only_failed=args.only_failed,
            timeout=args.timeout
        )
        return

    # Initialize new RunContext
    run = RunContext(
        name=args.run_name,
        auto_git_sha=True,
        base_dir=settings.paths.parsed_data_dir
    )
    run.create()

    if not args.quiet:
        print(f"Run ID: {run.run_id}")
        print(f"Output Directory: {run.output_dir}")
        if run.git_sha:
            print(f"Git SHA: {run.git_sha}")

    batch_parse_filings(
        input_dir=input_dir,
        output_dir=run.output_dir,
        form_type=args.form_type,
        pattern=args.pattern,
        overwrite=args.overwrite,
        run_context=run,
        resume=args.resume,
        checkpoint_interval=args.checkpoint_interval,
        quiet=args.quiet,
        incremental=args.incremental,
        prune_deleted=args.prune_deleted,
        use_validation=args.validate,
        only_failed=args.only_failed,
        timeout=args.timeout
    )


if __name__ == "__main__":
    main()
