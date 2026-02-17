#!/usr/bin/env python3
"""
Test Memory Semaphore Implementation

Verifies the memory estimation, file classification, and resource
allocation logic without requiring actual file processing.
"""

import sys
from pathlib import Path
import tempfile

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.memory_semaphore import (
    MemorySemaphore,
    FileCategory,
    ResourceEstimate,
    get_file_estimate
)


def create_test_file(size_mb: float) -> Path:
    """Create a temporary file of specified size."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
    # Write data to reach desired size
    chunk_size = 1024 * 1024  # 1MB chunks
    bytes_to_write = int(size_mb * chunk_size)

    written = 0
    while written < bytes_to_write:
        to_write = min(chunk_size, bytes_to_write - written)
        temp_file.write(b'0' * to_write)
        written += to_write

    temp_file.close()
    return Path(temp_file.name)


def test_file_classification():
    """Test file size classification."""
    print("=" * 60)
    print("TEST 1: File Classification")
    print("=" * 60)

    test_cases = [
        (10, FileCategory.SMALL),
        (19.9, FileCategory.SMALL),
        (20.1, FileCategory.MEDIUM),
        (30, FileCategory.MEDIUM),
        (49.9, FileCategory.MEDIUM),
        (50.1, FileCategory.LARGE),
        (68, FileCategory.LARGE),
    ]

    passed = 0
    for size_mb, expected_category in test_cases:
        file_path = create_test_file(size_mb)
        try:
            category = MemorySemaphore.classify_file(file_path)
            if category == expected_category:
                print(f"✓ {size_mb:5.1f}MB -> {category.value:6s} (correct)")
                passed += 1
            else:
                print(f"✗ {size_mb:5.1f}MB -> {category.value:6s} (expected {expected_category.value})")
        finally:
            file_path.unlink()

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_memory_estimation():
    """Test memory estimation formula."""
    print("\n" + "=" * 60)
    print("TEST 2: Memory Estimation")
    print("=" * 60)

    test_cases = [
        # (file_size_mb, expected_memory_mb)
        (1, 512),      # 1 * 12 + 500 = 512
        (10, 620),     # 10 * 12 + 500 = 620
        (20, 740),     # 20 * 12 + 500 = 740
        (50, 1100),    # 50 * 12 + 500 = 1,100
        (68, 1316),    # 68 * 12 + 500 = 1,316
    ]

    passed = 0
    print(f"{'File Size':>10s} {'Estimated':>12s} {'Expected':>10s} {'Status':>8s}")
    print("-" * 50)

    for file_size_mb, expected_mb in test_cases:
        estimated_mb = MemorySemaphore.estimate_file_memory(file_size_mb)
        if abs(estimated_mb - expected_mb) < 1:  # Allow 1MB tolerance
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"

        print(f"{file_size_mb:9.1f}MB {estimated_mb:10.0f}MB {expected_mb:9.0f}MB {status}")

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_resource_estimate():
    """Test complete resource estimate."""
    print("\n" + "=" * 60)
    print("TEST 3: Resource Estimate")
    print("=" * 60)

    test_cases = [
        # (size_mb, expected_category, expected_timeout, expected_pool)
        (10, FileCategory.SMALL, 600, "shared"),
        (30, FileCategory.MEDIUM, 1200, "shared"),
        (68, FileCategory.LARGE, 2400, "isolated"),
    ]

    passed = 0
    for size_mb, exp_category, exp_timeout, exp_pool in test_cases:
        file_path = create_test_file(size_mb)
        try:
            estimate = MemorySemaphore.get_resource_estimate(file_path)

            checks = [
                (estimate.file_size_mb >= size_mb * 0.99, "size"),
                (estimate.category == exp_category, "category"),
                (estimate.recommended_timeout_sec == exp_timeout, "timeout"),
                (estimate.worker_pool == exp_pool, "pool"),
            ]

            all_passed = all(check[0] for check in checks)

            if all_passed:
                print(f"✓ {size_mb}MB file:")
                print(f"    {estimate}")
                passed += 1
            else:
                print(f"✗ {size_mb}MB file failed:")
                for check, name in checks:
                    status = "✓" if check else "✗"
                    print(f"    {status} {name}")

        finally:
            file_path.unlink()

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_memory_semaphore():
    """Test MemorySemaphore class."""
    print("\n" + "=" * 60)
    print("TEST 4: MemorySemaphore Class")
    print("=" * 60)

    try:
        # Initialize semaphore
        semaphore = MemorySemaphore(safety_margin=0.2)
        print(f"✓ Semaphore initialized")
        print(f"  Total memory: {semaphore.total_memory_mb:.0f}MB")
        print(f"  Reserved: {semaphore.reserved_memory_mb:.0f}MB (20%)")

        # Test memory status
        status = semaphore.get_memory_status()
        print(f"\n✓ Memory status retrieved:")
        print(f"  Available: {status['available_mb']:.0f}MB")
        print(f"  Used: {status['percent']:.1f}%")

        # Test can_allocate
        test_allocations = [100, 500, 1000, 5000]
        print(f"\n✓ Testing can_allocate():")
        for alloc_mb in test_allocations:
            can_alloc = semaphore.can_allocate(alloc_mb)
            status_str = "can allocate" if can_alloc else "cannot allocate"
            print(f"  {alloc_mb:5d}MB: {status_str}")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_convenience_function():
    """Test convenience function."""
    print("\n" + "=" * 60)
    print("TEST 5: Convenience Function")
    print("=" * 60)

    file_path = create_test_file(50)
    try:
        estimate = get_file_estimate(file_path)
        print(f"✓ get_file_estimate() works:")
        print(f"  {estimate}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        file_path.unlink()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MEMORY SEMAPHORE TEST SUITE")
    print("=" * 60)

    results = {
        "classification": test_file_classification(),
        "estimation": test_memory_estimation(),
        "resource_estimate": test_resource_estimate(),
        "semaphore_class": test_memory_semaphore(),
        "convenience": test_convenience_function(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:20s}: {status}")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✓ ALL TESTS PASSED - Memory semaphore implementation verified!")
        print("\nKey Features Verified:")
        print("  - File classification (SMALL/MEDIUM/LARGE)")
        print("  - Memory estimation formula (12x + 500MB)")
        print("  - Adaptive timeout (600s/1200s/2400s)")
        print("  - Worker pool allocation (shared/isolated)")
        print("  - Memory availability checking")
        print("  - Resource estimate generation")
        return 0
    else:
        print("\n⚠ Some tests failed - review output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
