"""
Test Suite Runner for All Phases

Runs all unit tests for preprocessing pipeline optimization phases.
Can be run individually or as part of the full test suite.
"""

import pytest
import sys
from pathlib import Path


def run_phase1_tests():
    """Run Phase 1 tests (Memory-Aware Resource Allocation)."""
    print("\n" + "="*70)
    print("PHASE 1: Memory-Aware Resource Allocation")
    print("="*70)

    return pytest.main([
        str(Path(__file__).parent / "test_memory_semaphore.py"),
        "-v",
        "--tb=short"
    ])


def run_phase2_tests():
    """Run Phase 2 tests (Production Pipeline Global Workers)."""
    print("\n" + "="*70)
    print("PHASE 2: Production Pipeline Global Workers")
    print("="*70)

    return pytest.main([
        str(Path(__file__).parent / "test_pipeline_global_workers.py"),
        "-v",
        "--tb=short"
    ])


def run_phase3_tests():
    """Run Phase 3 tests (Automated Retry Mechanism)."""
    print("\n" + "="*70)
    print("PHASE 3: Automated Retry Mechanism")
    print("="*70)

    return pytest.main([
        str(Path(__file__).parent / "test_retry_mechanism.py"),
        "-v",
        "--tb=short"
    ])


def run_all_phases():
    """Run all phase tests sequentially."""
    print("\n" + "="*70)
    print("PREPROCESSING PIPELINE OPTIMIZATION - ALL PHASES")
    print("="*70)

    results = {
        'Phase 1': run_phase1_tests(),
        'Phase 2': run_phase2_tests(),
        'Phase 3': run_phase3_tests(),
    }

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    all_passed = True
    for phase, result in results.items():
        status = "✓ PASSED" if result == 0 else "✗ FAILED"
        print(f"{phase:20s}: {status}")
        if result != 0:
            all_passed = False

    print("="*70)

    if all_passed:
        print("\n✅ ALL PHASES PASSED")
        return 0
    else:
        print("\n❌ SOME PHASES FAILED")
        return 1


if __name__ == "__main__":
    # Check command-line arguments
    if len(sys.argv) > 1:
        phase = sys.argv[1].lower()

        if phase == "phase1" or phase == "1":
            sys.exit(run_phase1_tests())
        elif phase == "phase2" or phase == "2":
            sys.exit(run_phase2_tests())
        elif phase == "phase3" or phase == "3":
            sys.exit(run_phase3_tests())
        elif phase == "all":
            sys.exit(run_all_phases())
        else:
            print(f"Unknown phase: {phase}")
            print("Usage: python test_all_phases.py [phase1|phase2|phase3|all]")
            sys.exit(1)
    else:
        # Default: run all phases
        sys.exit(run_all_phases())
