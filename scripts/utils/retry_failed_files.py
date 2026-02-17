"""
Retry failed files from Dead Letter Queue with increased resources.

Usage:
    # Retry with 2x timeout
    python scripts/utils/retry_failed_files.py --timeout-multiplier 2.0

    # Retry with single-core isolation for all files
    python scripts/utils/retry_failed_files.py --force-isolated

    # Retry only large files
    python scripts/utils/retry_failed_files.py --min-size 40

    # Dry run (show what would be retried)
    python scripts/utils/retry_failed_files.py --dry-run
"""

import argparse
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.preprocessing.pipeline import SECPreprocessingPipeline, PipelineConfig
from src.utils.memory_semaphore import MemorySemaphore, FileCategory
from src.utils.parallel import ParallelProcessor

logger = logging.getLogger(__name__)


def load_dead_letter_queue(dlq_path: Path) -> List[Dict[str, Any]]:
    """Load failed files from Dead Letter Queue."""
    if not dlq_path.exists():
        logger.warning(f"Dead letter queue not found: {dlq_path}")
        return []

    with open(dlq_path, 'r') as f:
        failures = json.load(f)

    logger.info(f"Loaded {len(failures)} failed files from DLQ")
    return failures


def filter_failures(
    failures: List[Dict[str, Any]],
    min_size_mb: Optional[float] = None,
    max_attempts: int = 3,
    failure_types: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Filter failures for retry eligibility.

    Args:
        failures: List of failure records
        min_size_mb: Only retry files >= this size
        max_attempts: Skip files that have failed >= this many times
        failure_types: Only retry these failure types (e.g., ['timeout'])

    Returns:
        Filtered list of failures to retry
    """
    filtered = []

    for failure in failures:
        # Check attempt count
        attempt_count = failure.get('attempt_count', 1)
        if attempt_count >= max_attempts:
            logger.debug(f"Skipping {failure['file']} (max attempts: {attempt_count})")
            continue

        # Check file size
        if min_size_mb is not None:
            file_size = failure.get('file_size_mb', 0)
            if file_size < min_size_mb:
                logger.debug(f"Skipping {failure['file']} (size: {file_size}MB < {min_size_mb}MB)")
                continue

        # Check failure type
        if failure_types is not None:
            error_type = failure.get('error_type', 'unknown')
            if error_type not in failure_types:
                logger.debug(f"Skipping {failure['file']} (type: {error_type})")
                continue

        filtered.append(failure)

    logger.info(f"Filtered to {len(filtered)} eligible files for retry")
    return filtered


def retry_files(
    failures: List[Dict[str, Any]],
    timeout_multiplier: float = 2.0,
    force_isolated: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Retry failed files with increased resources.

    Args:
        failures: List of failure records to retry
        timeout_multiplier: Multiply original timeout by this factor
        force_isolated: Force single-core isolation for all files
        dry_run: Don't actually retry, just show what would happen

    Returns:
        Dict with retry results
    """
    semaphore = MemorySemaphore()
    results = {
        'total': len(failures),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }

    for failure in failures:
        file_path = Path(failure['file'])

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            results['skipped'] += 1
            continue

        # Get resource estimate
        estimate = semaphore.get_resource_estimate(file_path)
        retry_timeout = int(estimate.recommended_timeout_sec * timeout_multiplier)

        logger.info(
            f"Retry: {file_path.name} "
            f"({estimate.file_size_mb:.1f}MB, {estimate.category.value}, "
            f"timeout: {retry_timeout}s)"
        )

        if dry_run:
            results['details'].append({
                'file': str(file_path),
                'size_mb': estimate.file_size_mb,
                'category': estimate.category.value,
                'timeout': retry_timeout,
                'action': 'dry_run'
            })
            continue

        # Check memory availability
        if not semaphore.can_allocate(estimate.estimated_memory_mb):
            logger.warning(f"Waiting for memory: {file_path.name}")
            if not semaphore.wait_for_memory(estimate.estimated_memory_mb, timeout=600):
                logger.error(f"Memory timeout: {file_path.name}")
                results['skipped'] += 1
                continue

        # Process with increased resources
        try:
            config = PipelineConfig()
            pipeline = SECPreprocessingPipeline(config)

            # Use ProcessPoolExecutor with single worker for isolation
            max_workers = 1 if (force_isolated or estimate.worker_pool == "isolated") else None

            processor = ParallelProcessor(
                max_workers=max_workers,
                task_timeout=retry_timeout
            )

            result = pipeline.process_risk_factors(
                file_path,
                save_output=Path("data/processed/retry") / f"{file_path.stem}_segmented.json"
            )

            if result and len(result) > 0:
                logger.info(f"Success: {file_path.name} ({len(result)} segments)")
                results['success'] += 1
                results['details'].append({
                    'file': str(file_path),
                    'status': 'success',
                    'segments': len(result)
                })
            else:
                logger.error(f"Failed: {file_path.name} (no result)")
                results['failed'] += 1
                results['details'].append({
                    'file': str(file_path),
                    'status': 'failed',
                    'error': 'no_result'
                })

        except Exception as e:
            logger.error(f"Exception: {file_path.name} - {e}")
            results['failed'] += 1
            results['details'].append({
                'file': str(file_path),
                'status': 'failed',
                'error': str(e)
            })

    return results


def update_dead_letter_queue(
    dlq_path: Path,
    retry_results: Dict[str, Any]
):
    """Update DLQ by removing successful retries and incrementing attempt counts."""
    if not dlq_path.exists():
        return

    with open(dlq_path, 'r') as f:
        failures = json.load(f)

    successful_files = {
        detail['file'] for detail in retry_results['details']
        if detail.get('status') == 'success'
    }

    # Remove successful retries
    updated_failures = [
        f for f in failures
        if f['file'] not in successful_files
    ]

    # Increment attempt count for still-failing files
    for failure in updated_failures:
        failure['attempt_count'] = failure.get('attempt_count', 1) + 1
        failure['last_retry'] = datetime.now().isoformat()

    with open(dlq_path, 'w') as f:
        json.dump(updated_failures, f, indent=2)

    logger.info(
        f"Updated DLQ: Removed {len(successful_files)} successful, "
        f"{len(updated_failures)} remaining"
    )


def main():
    parser = argparse.ArgumentParser(description="Retry failed files from Dead Letter Queue")
    parser.add_argument(
        '--dlq-path',
        type=Path,
        default=Path('logs/failed_files.json'),
        help='Path to dead letter queue JSON file'
    )
    parser.add_argument(
        '--timeout-multiplier',
        type=float,
        default=2.0,
        help='Multiply original timeout by this factor (default: 2.0)'
    )
    parser.add_argument(
        '--force-isolated',
        action='store_true',
        help='Force single-core isolation for all files'
    )
    parser.add_argument(
        '--min-size',
        type=float,
        help='Only retry files >= this size in MB'
    )
    parser.add_argument(
        '--max-attempts',
        type=int,
        default=3,
        help='Skip files that have failed >= this many times (default: 3)'
    )
    parser.add_argument(
        '--failure-types',
        nargs='+',
        help='Only retry these failure types (e.g., timeout exception)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be retried without actually processing'
    )
    parser.add_argument(
        '--update-dlq',
        action='store_true',
        help='Update DLQ after retry (remove successful, increment attempt counts)'
    )

    args = parser.parse_args()

    # Load failures
    failures = load_dead_letter_queue(args.dlq_path)
    if not failures:
        logger.info("No failures to retry")
        return

    # Filter
    eligible = filter_failures(
        failures,
        min_size_mb=args.min_size,
        max_attempts=args.max_attempts,
        failure_types=args.failure_types
    )

    if not eligible:
        logger.info("No eligible files for retry after filtering")
        return

    # Retry
    results = retry_files(
        eligible,
        timeout_multiplier=args.timeout_multiplier,
        force_isolated=args.force_isolated,
        dry_run=args.dry_run
    )

    # Report
    logger.info(f"\nRetry Results:")
    logger.info(f"  Total: {results['total']}")
    logger.info(f"  Success: {results['success']}")
    logger.info(f"  Failed: {results['failed']}")
    logger.info(f"  Skipped: {results['skipped']}")

    # Update DLQ
    if args.update_dlq and not args.dry_run:
        update_dead_letter_queue(args.dlq_path, results)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    main()
