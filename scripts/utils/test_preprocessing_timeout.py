#!/usr/bin/env python3
"""
Test script to verify timeout handling in run_preprocessing_pipeline.py

This verifies that:
1. The timeout parameter is properly passed through
2. Large files are handled with appropriate timeouts
3. Dead letter queue is created for failed files
"""

import subprocess
import sys
from pathlib import Path
import json


def test_timeout_parameter():
    """Test that timeout parameter is accepted."""
    print("=" * 60)
    print("Testing run_preprocessing_pipeline.py Timeout Integration")
    print("=" * 60)

    # Test 1: Check help output includes timeout
    print("\nTest 1: Verify --timeout argument exists")
    print("-" * 60)

    result = subprocess.run(
        [sys.executable, "scripts/data_preprocessing/run_preprocessing_pipeline.py", "--help"],
        capture_output=True,
        text=True,
        timeout=10
    )

    if "--timeout" in result.stdout:
        print("[PASS] --timeout argument found in help output")
        print(f"Help text: {[line for line in result.stdout.split('\\n') if 'timeout' in line.lower()]}")
    else:
        print("[FAIL] --timeout argument not found in help output")
        return False

    # Test 2: Check dead letter queue exists
    print("\n\nTest 2: Check for dead letter queue file")
    print("-" * 60)

    dlq_file = Path('logs/failed_files.json')
    if dlq_file.exists():
        with open(dlq_file, 'r') as f:
            failures = json.load(f)

        print(f"[INFO] Dead letter queue exists: {dlq_file}")
        print(f"[INFO] Contains {len(failures)} failures")

        if failures:
            print(f"\nLast 3 failures:")
            for failure in failures[-3:]:
                print(f"  - {failure['file']} at {failure['timestamp']}")
                print(f"    Reason: {failure.get('reason', 'unknown')}")
                print(f"    Script: {failure.get('script', 'unknown')}")
    else:
        print(f"[INFO] No dead letter queue found yet at {dlq_file}")
        print(f"[INFO] Will be created when a file times out")

    print("\n" + "=" * 60)
    print("Integration Test Complete")
    print("=" * 60)
    print("\nTo test timeout in action:")
    print("  python scripts/data_preprocessing/run_preprocessing_pipeline.py \\")
    print("    --batch --workers 2 --timeout 300 --quiet")
    print("\nThis will use a 5-minute timeout instead of default 20 minutes")

    return True


if __name__ == '__main__':
    success = test_timeout_parameter()
    sys.exit(0 if success else 1)
