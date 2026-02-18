"""Parallel processing utilities for batch validation."""

import logging
import os
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from src.utils.dead_letter_queue import DeadLetterQueue

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ParallelProcessor:
    """
    Manages parallel processing with ProcessPoolExecutor.

    Follows project pattern:
    - ProcessPoolExecutor with initializer function
    - max_tasks_per_child=50 for memory management
    - Progress tracking with configurable verbosity

    Usage:
        def _init_worker():
            global _worker_obj
            _worker_obj = MyObject()

        def worker_func(args):
            file_path, param = args
            # Process using global _worker_obj
            return result

        processor = ParallelProcessor(
            max_workers=8,
            initializer=_init_worker
        )

        results = processor.process_batch(
            items=[(file1, param), (file2, param)],
            worker_func=worker_func,
            verbose=True
        )
    """

    def __init__(
        self,
        max_workers: Optional[int] = None,
        initializer: Optional[Callable] = None,
        max_tasks_per_child: int = 50,
        task_timeout: int = 1200
    ):
        """
        Initialize parallel processor.

        Args:
            max_workers: Number of parallel workers (default: auto-determine)
            initializer: Optional initialization function for workers
            max_tasks_per_child: Restart workers after N tasks (default: 50)
            task_timeout: Timeout per task in seconds (default: 1200 = 20 minutes)
        """
        self.max_workers = max_workers
        self.initializer = initializer
        self.max_tasks_per_child = max_tasks_per_child
        self.task_timeout = task_timeout

    def should_use_parallel(self, num_items: int, max_workers: Optional[int] = None) -> bool:
        """
        Determine if parallel processing is beneficial.

        Args:
            num_items: Number of items to process
            max_workers: Max workers requested (None or 1 means sequential)

        Returns:
            True if should use parallel processing
        """
        return max_workers != 1 and num_items > 1

    def process_batch(
        self,
        items: List[T],
        worker_func: Callable,
        progress_callback: Optional[Callable[[int, Any], None]] = None,
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Process items in parallel using ProcessPoolExecutor.

        Args:
            items: List of items to process
            worker_func: Function to apply to each item (receives item as arg)
            progress_callback: Optional callback for progress updates (receives idx, result)
            verbose: Print per-item progress

        Returns:
            List of results from worker_func (order may differ from input)
        """
        # Auto-determine max_workers
        if self.max_workers is None:
            max_workers = min(os.cpu_count() or 4, len(items))
        else:
            max_workers = self.max_workers

        # Sequential processing if requested or single item
        if not self.should_use_parallel(len(items), max_workers):
            return self._process_sequential(items, worker_func, progress_callback, verbose)

        # Parallel processing
        return self._process_parallel(
            items, worker_func, progress_callback, verbose, max_workers
        )

    def _process_sequential(
        self,
        items: List[T],
        worker_func: Callable,
        progress_callback: Optional[Callable],
        verbose: bool
    ) -> List[Dict[str, Any]]:
        """Process items sequentially."""
        results = []

        for idx, item in enumerate(items, 1):
            if verbose:
                print(f"[{idx}/{len(items)}] Processing: {item}")

            result = worker_func(item)
            results.append(result)

            if progress_callback:
                progress_callback(idx, result)

        return results

    def _process_parallel(
        self,
        items: List[T],
        worker_func: Callable,
        progress_callback: Optional[Callable],
        verbose: bool,
        max_workers: int
    ) -> List[Dict[str, Any]]:
        """Process items in parallel with timeout handling and dead letter queue."""
        results = []
        failed_items = []  # Track timeouts for dead letter queue

        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=self.initializer,
            max_tasks_per_child=self.max_tasks_per_child
        ) as executor:
            # Submit all tasks
            future_to_item = {
                executor.submit(worker_func, item): item
                for item in items
            }

            # Process results with timeout
            # Note: We iterate over as_completed with timeout to catch hung workers
            completed_count = 0
            for future in as_completed(future_to_item, timeout=None):
                completed_count += 1
                item = future_to_item[future]

                try:
                    # Get result with timeout
                    # This catches cases where future completed but result() blocks
                    result = future.result(timeout=self.task_timeout)

                    # Warn about slow tasks (> 5 minutes)
                    elapsed = result.get('elapsed_time', 0)
                    if elapsed > 300 and verbose:
                        logger.warning(f"Slow task ({elapsed:.1f}s): {result.get('file', 'unknown')}")

                except TimeoutError:
                    # Task exceeded timeout limit
                    logger.error(f"Task timeout ({self.task_timeout}s): {item}")
                    result = {
                        'status': 'error',
                        'file': str(item),
                        'error': f'Processing timeout ({self.task_timeout}s)',
                        'error_type': 'timeout'
                    }
                    failed_items.append(item)
                    # Cancel the future to free resources
                    future.cancel()

                except Exception as e:
                    # Task raised an exception
                    logger.error(f"Task failed with exception: {item} - {e}")
                    result = {
                        'status': 'error',
                        'file': str(item),
                        'error': str(e),
                        'error_type': 'exception'
                    }
                    failed_items.append(item)

                results.append(result)

                if verbose:
                    status = result.get('status', 'unknown')
                    file_name = result.get('file', 'unknown')
                    print(f"[{completed_count}/{len(items)}] {status.upper()}: {file_name}")

                if progress_callback:
                    progress_callback(completed_count, result)

                # Print progress for non-verbose mode
                if not verbose and (completed_count % 10 == 0 or completed_count == len(items)):
                    print(f"Progress: {completed_count}/{len(items)}", end='\r')

        # Clear progress line
        if not verbose:
            print()  # New line after progress

        # Write failed items to dead letter queue
        if failed_items:
            dlq = DeadLetterQueue()
            dlq.add_failures(failed_items, script_name="ParallelProcessor")

        return results
