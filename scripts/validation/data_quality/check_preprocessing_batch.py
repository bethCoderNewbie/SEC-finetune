#!/usr/bin/env python
"""
Batch validate preprocessing output with parallel processing and checkpointing.

This script validates all JSON files in a preprocessing run directory with:
- Parallel processing using ProcessPoolExecutor for speed
- Smart resume capability (skip already-validated files via checkpoint)
- Periodic checkpoint saves for crash recovery
- Consolidated JSON report with per-file and aggregate results

Usage:
    # Basic usage (sequential)
    python scripts/validation/data_quality/check_preprocessing_batch.py \
        --run-dir data/processed/20251212_161906_preprocessing_ea45dd2

    # Parallel processing with 8 workers
    python scripts/validation/data_quality/check_preprocessing_batch.py \
        --run-dir data/interim/parsed/20251212_171015_batch_parse_ea45dd2 \
        --max-workers 8

    # With verbose output and custom checkpoint interval
    python scripts/validation/data_quality/check_preprocessing_batch.py \
        --run-dir data/interim/parsed/... \
        --max-workers 4 \
        --checkpoint-interval 20 \
        --verbose

    # Resume from interrupted run
    python scripts/validation/data_quality/check_preprocessing_batch.py \
        --run-dir data/interim/parsed/... \
        --resume

    # Custom output location
    python scripts/validation/data_quality/check_preprocessing_batch.py \
        --run-dir data/interim/parsed/... \
        --output reports/batch_validation_20251227.json

Exit Codes:
    0 - All checks passed (or passed with warnings if not --fail-on-warn)
    1 - One or more checks failed (or warnings with --fail-on-warn)
"""

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.qa_validation import HealthCheckValidator
from src.utils.checkpoint import CheckpointManager
from src.utils.parallel import ParallelProcessor


# =============================================================================
# Global worker state (initialized once per worker process)
# =============================================================================

_worker_validator: Optional[HealthCheckValidator] = None


def _init_worker() -> None:
    """Initialize validator once per worker process."""
    global _worker_validator
    _worker_validator = HealthCheckValidator()


# =============================================================================
# Single File Validation
# =============================================================================

def validate_single_file(
    file_path: Path,
    run_dir: Path,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Validate a single JSON file using HealthCheckValidator.

    Args:
        file_path: Path to JSON file to validate
        run_dir: Parent directory (used for temp directory creation)
        verbose: Print detailed progress

    Returns:
        Structured validation result dict:
        {
            'file': str,                    # Original filename
            'file_path': str,               # Full path
            'status': str,                  # 'success', 'error'
            'overall_status': str,          # 'PASS', 'WARN', 'FAIL', 'ERROR'
            'validation_results': [...],    # List of ValidationResult dicts
            'blocking_summary': {...},      # Pass/fail/warn counts
            'elapsed_time': float,
            'error': Optional[str]
        }
    """
    start_time = time.time()

    try:
        # HealthCheckValidator.check_run() expects a directory, not a single file
        # PID-stamp the temp dir to prevent race conditions in parallel workers (Fix 4E)
        temp_dir = run_dir / f"_temp_validation_{os.getpid()}"
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / file_path.name

        # Copy file to temp location
        shutil.copy(file_path, temp_file)

        # Run validation
        validator = HealthCheckValidator()
        report = validator.check_run(temp_dir)

        # Clean up temp file
        temp_file.unlink()

        # Clean up temp dir if empty
        try:
            temp_dir.rmdir()
        except OSError:
            pass  # Directory not empty, leave it

        # Structure result
        return {
            'file': file_path.name,
            'file_path': str(file_path),
            'status': 'success',
            'overall_status': report['status'],
            'validation_results': report['validation_table'],
            'blocking_summary': report['blocking_summary'],
            'elapsed_time': time.time() - start_time,
            'error': None
        }

    except Exception as e:
        # Clean up on error
        try:
            if 'temp_file' in locals() and temp_file.exists():
                temp_file.unlink()
            if 'temp_dir' in locals() and temp_dir.exists():
                temp_dir.rmdir()
        except Exception:
            pass

        return {
            'file': file_path.name,
            'file_path': str(file_path),
            'status': 'error',
            'overall_status': 'ERROR',
            'validation_results': [],
            'blocking_summary': {},
            'elapsed_time': time.time() - start_time,
            'error': str(e)
        }


def validate_single_file_worker(args: Tuple[Path, Path, bool]) -> Dict[str, Any]:
    """
    Worker function for parallel validation (uses global _worker_validator).

    Args:
        args: Tuple of (file_path, run_dir, verbose)

    Returns:
        Validation result dict (same structure as validate_single_file)
    """
    file_path, run_dir, verbose = args
    start_time = time.time()

    try:
        # Use global validator initialized in worker
        global _worker_validator
        if _worker_validator is None:
            _worker_validator = HealthCheckValidator()

        # Create temp directory and copy file
        temp_dir = run_dir / f"_temp_validation_{os.getpid()}"
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / file_path.name

        shutil.copy(file_path, temp_file)

        # Run validation
        report = _worker_validator.check_run(temp_dir)

        # Clean up
        temp_file.unlink()
        try:
            temp_dir.rmdir()
        except OSError:
            pass

        return {
            'file': file_path.name,
            'file_path': str(file_path),
            'status': 'success',
            'overall_status': report['status'],
            'validation_results': report['validation_table'],
            'blocking_summary': report['blocking_summary'],
            'elapsed_time': time.time() - start_time,
            'error': None
        }

    except Exception as e:
        # Clean up on error
        try:
            if 'temp_file' in locals() and temp_file.exists():
                temp_file.unlink()
            if 'temp_dir' in locals() and temp_dir.exists():
                temp_dir.rmdir()
        except Exception:
            pass

        return {
            'file': file_path.name,
            'file_path': str(file_path),
            'status': 'error',
            'overall_status': 'ERROR',
            'validation_results': [],
            'blocking_summary': {},
            'elapsed_time': time.time() - start_time,
            'error': str(e)
        }


# =============================================================================
# Report Generation
# =============================================================================

def generate_consolidated_report(
    run_dir: Path,
    per_file_results: List[Dict]
) -> Dict[str, Any]:
    """
    Aggregate all validation results into consolidated report.

    Args:
        run_dir: Directory that was validated
        per_file_results: List of individual file validation results

    Returns:
        Consolidated report with overall status and aggregated metrics
    """
    # Count file-level statuses
    passed = sum(1 for r in per_file_results if r['overall_status'] == 'PASS')
    warned = sum(1 for r in per_file_results if r['overall_status'] == 'WARN')
    failed = sum(1 for r in per_file_results if r['overall_status'] == 'FAIL')
    errors = sum(1 for r in per_file_results if r['status'] == 'error')

    # Aggregate blocking check summaries across all files
    total_blocking = 0
    blocking_passed = 0
    blocking_failed = 0
    blocking_warned = 0

    for result in per_file_results:
        if result['status'] == 'success' and result['blocking_summary']:
            bs = result['blocking_summary']
            total_blocking += bs.get('total_blocking', 0)
            blocking_passed += bs.get('passed', 0)
            blocking_failed += bs.get('failed', 0)
            blocking_warned += bs.get('warned', 0)

    # Determine overall status
    if failed > 0 or blocking_failed > 0:
        overall_status = "FAIL"
    elif warned > 0 or blocking_warned > 0:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "run_directory": str(run_dir),
        "total_files": len(per_file_results),
        "files_validated": len([r for r in per_file_results if r['status'] == 'success']),
        "files_skipped": 0,  # For future enhancement
        "overall_summary": {
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "errors": errors
        },
        "blocking_summary": {
            "total_blocking": total_blocking,
            "passed": blocking_passed,
            "failed": blocking_failed,
            "warned": blocking_warned,
            "all_pass": blocking_failed == 0
        },
        "per_file_results": per_file_results
    }


def print_summary(report: Dict, verbose: bool = False) -> None:
    """
    Print human-readable summary of batch validation results.

    Args:
        report: Consolidated validation report
        verbose: Show per-file details
    """
    print(f"\n{'='*60}")
    print(f"Batch Validation: {report['status']}")
    print(f"{'='*60}")
    print(f"  Run directory: {report['run_directory']}")
    print(f"  Total files: {report['total_files']}")
    print(f"  Validated: {report['files_validated']}")

    summary = report['overall_summary']
    print(f"\n  File Status:")
    print(f"    Passed: {summary['passed']}")
    print(f"    Warned: {summary['warned']}")
    print(f"    Failed: {summary['failed']}")
    print(f"    Errors: {summary['errors']}")

    blocking = report['blocking_summary']
    print(f"\n  Blocking Checks (across all files):")
    print(f"    Total: {blocking['total_blocking']}")
    print(f"    Passed: {blocking['passed']}")
    print(f"    Failed: {blocking['failed']}")
    print(f"    Warned: {blocking['warned']}")

    if verbose and report.get('per_file_results'):
        print(f"\n{'='*60}")
        print("Per-File Results:")
        print(f"{'='*60}")
        for result in report['per_file_results']:
            status_icon = {
                'PASS': '[PASS]',
                'WARN': '[WARN]',
                'FAIL': '[FAIL]',
                'ERROR': '[ERR ]'
            }.get(result['overall_status'], '[----]')

            print(f"  {status_icon} {result['file']}")
            if result['status'] == 'error':
                print(f"         Error: {result['error']}")

    print(f"\n{'='*60}")
    if report['status'] == 'PASS':
        print("Result: ALL CHECKS PASSED")
    elif report['status'] == 'WARN':
        print("Result: PASSED WITH WARNINGS")
    else:
        print("Result: CHECKS FAILED")
    print(f"{'='*60}")


# =============================================================================
# Batch Validation Orchestrator (REFACTORED to use shared utilities)
# =============================================================================

def batch_validate_preprocessing_output(
    run_dir: Path,
    output_path: Optional[Path] = None,
    max_workers: Optional[int] = None,
    checkpoint_interval: int = 10,
    resume: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Validate all JSON files in run directory with parallel processing.

    Args:
        run_dir: Directory containing JSON files to validate
        output_path: Path for consolidated report (default: {run_dir}/validation_report.json)
        max_workers: Number of parallel workers (default: CPU count, 1 for sequential)
        checkpoint_interval: Save checkpoint every N files (default: 10)
        resume: Resume from checkpoint if exists (default: False)
        verbose: Print detailed progress (default: False)

    Returns:
        Consolidated validation report dict
    """
    # Setup paths
    if output_path is None:
        output_path = run_dir / "validation_report.json"

    checkpoint = CheckpointManager(run_dir / "_validation_checkpoint.json")

    # Find all JSON files (exclude metadata files starting with _ and the report itself)
    json_files = sorted([
        f for f in run_dir.glob("*.json")
        if not f.name.startswith("_")
        and f != output_path
    ])

    if not json_files:
        return {
            "status": "ERROR",
            "message": f"No JSON files found in: {run_dir}",
            "timestamp": datetime.now().isoformat(),
            "run_directory": str(run_dir)
        }

    total_files_found = len(json_files)
    print(f"Found {total_files_found} JSON files in: {run_dir}")

    # Resume from checkpoint if requested
    processed_files = []
    all_results = []
    current_metrics = {}

    if resume and checkpoint.exists():
        validated_set, all_results, current_metrics = checkpoint.load()
        processed_files = list(validated_set)
        json_files = [f for f in json_files if f.name not in validated_set]
        if validated_set:
            print(f"Resuming: {len(processed_files)} files already validated, {len(json_files)} remaining")

    if not json_files:
        print("All files already validated!")
        if all_results:
            # Generate report from checkpoint data
            report = generate_consolidated_report(run_dir, all_results)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            return report
        else:
            return {
                "status": "ERROR",
                "message": "No files to validate and no checkpoint data found",
                "timestamp": datetime.now().isoformat(),
                "run_directory": str(run_dir)
            }

    # Create parallel processor
    processor = ParallelProcessor(
        max_workers=max_workers,
        initializer=_init_worker,
        max_tasks_per_child=50
    )

    # Determine processing mode
    use_parallel = processor.should_use_parallel(len(json_files), max_workers)
    if use_parallel:
        workers = max_workers or min(os.cpu_count() or 4, len(json_files))
        print(f"Using {workers} parallel workers")
    else:
        print("Using sequential processing")

    # Process files with checkpoint callback
    start_time = time.time()

    def checkpoint_callback(idx: int, result: Dict):
        """Save checkpoint periodically."""
        all_results.append(result)
        processed_files.append(result['file'])

        if idx % checkpoint_interval == 0:
            current_metrics = {
                "total_files": total_files_found,
                "processed": len(processed_files)
            }
            checkpoint.save(processed_files, all_results, current_metrics)

    # Prepare task arguments
    task_args = [(f, run_dir, verbose) for f in json_files]

    # Process batch
    results = processor.process_batch(
        items=task_args,
        worker_func=validate_single_file_worker,
        progress_callback=checkpoint_callback,
        verbose=verbose
    )

    # Ensure all results are captured (in case callback wasn't called for last batch)
    for result in results:
        if result['file'] not in processed_files:
            all_results.append(result)
            processed_files.append(result['file'])

    elapsed_time = time.time() - start_time
    print(f"\nCompleted in {elapsed_time:.2f} seconds")

    # Generate final report
    report = generate_consolidated_report(run_dir, all_results)

    # Save report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"Report saved to: {output_path}")

    # Clean up checkpoint on success
    checkpoint.cleanup()

    return report


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Batch validate preprocessing output with parallel processing and checkpointing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Directory containing JSON output files to validate"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path for consolidated JSON report (default: {run-dir}/validation_report.json)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        help="Number of parallel workers (default: CPU count, use 1 for sequential)"
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Save checkpoint every N files (default: 10)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint if exists"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress per file"
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit with code 1 on warnings (useful for CI/CD)"
    )

    args = parser.parse_args()

    # Validate run directory exists
    if not args.run_dir.exists():
        print(f"Error: Directory not found: {args.run_dir}")
        sys.exit(1)

    if not args.run_dir.is_dir():
        print(f"Error: Not a directory: {args.run_dir}")
        sys.exit(1)

    # Run batch validation
    print(f"Starting batch validation on: {args.run_dir}")
    report = batch_validate_preprocessing_output(
        run_dir=args.run_dir,
        output_path=args.output,
        max_workers=args.max_workers,
        checkpoint_interval=args.checkpoint_interval,
        resume=args.resume,
        verbose=args.verbose
    )

    # Handle error case
    if report.get("status") == "ERROR":
        print(f"Error: {report.get('message', 'Unknown error')}")
        sys.exit(1)

    # Print summary
    print_summary(report, verbose=args.verbose)

    # Exit code logic
    if report['status'] == 'FAIL':
        sys.exit(1)
    if report['status'] == 'WARN' and args.fail_on_warn:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
