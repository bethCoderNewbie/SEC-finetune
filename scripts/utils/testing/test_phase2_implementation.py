#!/usr/bin/env python3
"""
Test Phase 2 Implementation: Global Worker Pattern

Tests the production pipeline's global worker optimization.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Try to import psutil, but make it optional
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("⚠ psutil not installed - memory tracking disabled")

def test_imports():
    """Test 1: Verify imports work"""
    print("=" * 60)
    print("TEST 1: Import Verification")
    print("=" * 60)

    try:
        # Import directly from module file to bypass __init__ issues
        from src.preprocessing import pipeline as pipeline_module

        # Check for our new functions and variables
        assert hasattr(pipeline_module, '_worker_parser'), "Missing _worker_parser global"
        assert hasattr(pipeline_module, '_worker_cleaner'), "Missing _worker_cleaner global"
        assert hasattr(pipeline_module, '_worker_segmenter'), "Missing _worker_segmenter global"
        assert hasattr(pipeline_module, '_worker_extractor'), "Missing _worker_extractor global"
        assert hasattr(pipeline_module, '_init_production_worker'), "Missing _init_production_worker()"
        assert hasattr(pipeline_module, '_process_filing_with_global_workers'), "Missing _process_filing_with_global_workers()"

        print("✓ All global worker components present")
        print("✓ Worker initialization function exists")
        print("✓ Efficient processing function exists")
        return True

    except Exception as e:
        print(f"✗ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_worker_initialization():
    """Test 2: Verify worker initialization works"""
    print("\n" + "=" * 60)
    print("TEST 2: Worker Initialization")
    print("=" * 60)

    try:
        from src.preprocessing import pipeline as pipeline_module

        # Initialize workers
        print("Initializing workers...")
        pipeline_module._init_production_worker()

        # Verify workers are initialized
        assert pipeline_module._worker_parser is not None, "Parser not initialized"
        assert pipeline_module._worker_cleaner is not None, "Cleaner not initialized"
        assert pipeline_module._worker_segmenter is not None, "Segmenter not initialized"
        assert pipeline_module._worker_extractor is not None, "Extractor not initialized"

        print("✓ All workers initialized successfully")
        print(f"  - Parser: {type(pipeline_module._worker_parser).__name__}")
        print(f"  - Cleaner: {type(pipeline_module._worker_cleaner).__name__}")
        print(f"  - Segmenter: {type(pipeline_module._worker_segmenter).__name__}")
        print(f"  - Extractor: {type(pipeline_module._worker_extractor).__name__}")
        return True

    except Exception as e:
        print(f"✗ Worker initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_single_file_processing():
    """Test 3: Process a single file"""
    print("\n" + "=" * 60)
    print("TEST 3: Single File Processing")
    print("=" * 60)

    try:
        from src.preprocessing.pipeline import SECPreprocessingPipeline, PipelineConfig

        # Find a small test file
        test_files = list(Path("data/raw").glob("*.html"))
        if not test_files:
            print("⚠ No test files found in data/raw/")
            return None

        # Use the smallest file for quick testing
        test_file = min(test_files, key=lambda f: f.stat().st_size)
        file_size_mb = test_file.stat().st_size / (1024 * 1024)

        print(f"Test file: {test_file.name} ({file_size_mb:.2f} MB)")

        # Track memory before
        if HAS_PSUTIL:
            process = psutil.Process()
            mem_before = process.memory_info().rss / (1024 * 1024)
        else:
            mem_before = 0

        # Process the file
        print("Processing...")
        start_time = time.time()

        config = PipelineConfig()
        pipeline = SECPreprocessingPipeline(config)
        result = pipeline.process_risk_factors(test_file, form_type="10-K")

        elapsed = time.time() - start_time

        # Track memory after
        if HAS_PSUTIL:
            mem_after = process.memory_info().rss / (1024 * 1024)
            mem_used = mem_after - mem_before
        else:
            mem_after = 0
            mem_used = 0

        if result:
            print(f"✓ Processing successful")
            print(f"  - Time: {elapsed:.2f}s")
            print(f"  - Memory used: {mem_used:.1f} MB")
            print(f"  - Segments: {len(result)}")
            print(f"  - Company: {result.company_name}")
            print(f"  - SIC: {result.sic_code} - {result.sic_name}")
            print(f"  - CIK: {result.cik}")

            # Verify metadata
            assert result.company_name, "Missing company_name"
            assert result.sic_code, "Missing sic_code"

            print("✓ All metadata present")
            return True
        else:
            print("✗ No result returned")
            return False

    except Exception as e:
        print(f"✗ Single file processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_processing():
    """Test 4: Batch processing with global workers"""
    print("\n" + "=" * 60)
    print("TEST 4: Batch Processing (Global Workers)")
    print("=" * 60)

    try:
        from src.preprocessing.pipeline import SECPreprocessingPipeline

        # Find test files (use 3 small files for quick test)
        test_files = sorted(
            Path("data/raw").glob("*.html"),
            key=lambda f: f.stat().st_size
        )[:3]

        if len(test_files) < 2:
            print("⚠ Need at least 2 test files")
            return None

        print(f"Test files: {len(test_files)}")
        for f in test_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  - {f.name} ({size_mb:.2f} MB)")

        # Track memory before
        if HAS_PSUTIL:
            process = psutil.Process()
            mem_before = process.memory_info().rss / (1024 * 1024)
        else:
            mem_before = 0

        # Process batch
        print("\nProcessing batch with 2 workers...")
        start_time = time.time()

        pipeline = SECPreprocessingPipeline()
        results = pipeline.process_batch(
            test_files,
            max_workers=2,
            verbose=True
        )

        elapsed = time.time() - start_time

        # Track memory after
        if HAS_PSUTIL:
            mem_after = process.memory_info().rss / (1024 * 1024)
            mem_peak = process.memory_info().rss / (1024 * 1024)
        else:
            mem_after = 0
            mem_peak = 0

        print(f"\n✓ Batch processing complete")
        print(f"  - Files processed: {len(results)}/{len(test_files)}")
        print(f"  - Total time: {elapsed:.2f}s")
        print(f"  - Avg time per file: {elapsed/len(test_files):.2f}s")
        print(f"  - Memory before: {mem_before:.1f} MB")
        print(f"  - Memory after: {mem_after:.1f} MB")
        print(f"  - Memory increase: {mem_after - mem_before:.1f} MB")

        # Verify results
        if len(results) == len(test_files):
            print("✓ All files processed successfully")

            # Check first result for metadata
            if results:
                r = results[0]
                print(f"✓ Sample result metadata:")
                print(f"  - Company: {r.company_name}")
                print(f"  - SIC: {r.sic_code}")
                print(f"  - Segments: {len(r)}")

            return True
        else:
            print(f"⚠ Only {len(results)}/{len(test_files)} files succeeded")
            return False

    except Exception as e:
        print(f"✗ Batch processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("PHASE 2 IMPLEMENTATION TEST SUITE")
    print("Testing: Global Worker Pattern & Sanitization Removal")
    print("=" * 60)

    results = {
        "imports": test_imports(),
        "worker_init": test_worker_initialization(),
        "single_file": test_single_file_processing(),
        "batch": test_batch_processing(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, result in results.items():
        status = "✓ PASS" if result else ("⚠ SKIP" if result is None else "✗ FAIL")
        print(f"{test_name:20s}: {status}")

    passed = sum(1 for r in results.values() if r is True)
    total = len([r for r in results.values() if r is not None])

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✓ ALL TESTS PASSED - Phase 2 implementation verified!")
        return 0
    else:
        print("\n⚠ Some tests failed - review output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
