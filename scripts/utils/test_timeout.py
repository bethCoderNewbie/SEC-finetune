#!/usr/bin/env python3
"""
Test script to verify timeout handling in ParallelProcessor.

This script tests:
1. Timeout handling for tasks that exceed time limit
2. Dead letter queue creation for failed tasks
3. Elapsed time tracking
"""

import time
from pathlib import Path
from typing import Dict, Any

from src.utils.parallel import ParallelProcessor


def mock_fast_worker(item: int) -> Dict[str, Any]:
    """Mock worker that completes quickly."""
    time.sleep(0.5)  # 0.5 seconds
    return {
        'status': 'success',
        'file': f'fast_file_{item}.html',
        'elapsed_time': 0.5,
    }


def mock_slow_worker(item: int) -> Dict[str, Any]:
    """Mock worker that times out (sleeps longer than timeout)."""
    time.sleep(10)  # 10 seconds (will timeout with 5s limit)
    return {
        'status': 'success',
        'file': f'slow_file_{item}.html',
        'elapsed_time': 10,
    }


def test_timeout_handling():
    """Test that timeout handling works correctly."""
    print("=" * 60)
    print("Testing ParallelProcessor Timeout Handling")
    print("=" * 60)

    # Test 1: Fast workers (should succeed)
    print("\nTest 1: Fast workers (should all succeed)")
    print("-" * 60)

    processor_fast = ParallelProcessor(
        max_workers=2,
        task_timeout=5  # 5 second timeout
    )

    fast_items = list(range(3))
    fast_results = processor_fast.process_batch(
        items=fast_items,
        worker_func=mock_fast_worker,
        verbose=True
    )

    print(f"\nResults: {len(fast_results)} completed")
    successes = [r for r in fast_results if r.get('status') == 'success']
    errors = [r for r in fast_results if r.get('status') == 'error']
    print(f"Successes: {len(successes)}")
    print(f"Errors: {len(errors)}")

    assert len(successes) == 3, "All fast tasks should succeed"
    assert len(errors) == 0, "No fast tasks should timeout"
    print("[PASS] Test 1 PASSED")

    # Test 2: Slow workers (should timeout)
    print("\n\nTest 2: Slow workers (should timeout)")
    print("-" * 60)

    processor_slow = ParallelProcessor(
        max_workers=2,
        task_timeout=3  # 3 second timeout (workers sleep 10s)
    )

    slow_items = list(range(2))
    slow_results = processor_slow.process_batch(
        items=slow_items,
        worker_func=mock_slow_worker,
        verbose=True
    )

    print(f"\nResults: {len(slow_results)} completed")
    successes = [r for r in slow_results if r.get('status') == 'success']
    errors = [r for r in slow_results if r.get('status') == 'error']
    timeouts = [r for r in errors if r.get('error_type') == 'timeout']

    print(f"Successes: {len(successes)}")
    print(f"Errors: {len(errors)}")
    print(f"Timeouts: {len(timeouts)}")

    assert len(errors) == 2, "All slow tasks should timeout"
    assert len(timeouts) == 2, "All errors should be timeouts"
    print("[PASS] Test 2 PASSED")

    # Test 3: Check dead letter queue
    print("\n\nTest 3: Check dead letter queue")
    print("-" * 60)

    dlq_file = Path('logs/failed_files.json')
    if dlq_file.exists():
        import json
        with open(dlq_file, 'r') as f:
            failures = json.load(f)

        print(f"Dead letter queue contains {len(failures)} failures")
        print("\nFailed items:")
        for failure in failures[-2:]:  # Show last 2
            print(f"  - {failure['file']} ({failure['reason']}) at {failure['timestamp']}")

        print(f"\n[PASS] Test 3 PASSED - DLQ file exists at {dlq_file}")
    else:
        print(f"[FAIL] Test 3 FAILED - DLQ file not found at {dlq_file}")

    print("\n" + "=" * 60)
    print("All Tests Completed")
    print("=" * 60)


if __name__ == '__main__':
    test_timeout_handling()
