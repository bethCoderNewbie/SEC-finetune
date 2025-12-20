#!/usr/bin/env python
"""
Validate preprocessing output against data quality standards.

This script validates that preprocessing output meets MLOps quality standards:
1. Completeness - Are required identity fields present (CIK, company name)?
2. Cleanliness - Is the text free of HTML artifacts and page numbers?
3. Substance - Are segments meaningful (non-empty, sufficient length)?
4. Consistency - Are there duplicate filings? Do risk keywords exist?

Usage:
    # Basic usage
    python scripts/utils/validation/validate_preprocessing_output.py \\
        --run-dir data/processed/20251212_161906_preprocessing_ea45dd2

    # With verbose output
    python scripts/utils/validation/validate_preprocessing_output.py \\
        --run-dir data/processed/... -v

    # Save report to file
    python scripts/utils/validation/validate_preprocessing_output.py \\
        --run-dir data/processed/... --output reports/health_check.json

    # Fail on warnings (for CI/CD)
    python scripts/utils/validation/validate_preprocessing_output.py \\
        --run-dir data/processed/... --fail-on-warn

Exit Codes:
    0 - All checks passed
    1 - One or more blocking checks failed (or warnings with --fail-on-warn)
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.qa_validation import HealthCheckValidator


def main():
    parser = argparse.ArgumentParser(
        description="Validate preprocessing output against data quality standards",
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
        help="Output JSON report file (optional)"
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Exit with code 1 on warnings (useful for CI/CD)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed validation table"
    )

    args = parser.parse_args()

    # Validate run directory exists
    if not args.run_dir.exists():
        print(f"Error: Directory not found: {args.run_dir}")
        sys.exit(1)

    if not args.run_dir.is_dir():
        print(f"Error: Not a directory: {args.run_dir}")
        sys.exit(1)

    # Run health check
    print(f"Running health check on: {args.run_dir}")
    validator = HealthCheckValidator()
    report = validator.check_run(args.run_dir)

    # Handle error case
    if report.get("status") == "ERROR":
        print(f"Error: {report.get('message', 'Unknown error')}")
        sys.exit(1)

    # Save output if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Report saved to: {args.output}")

    # Print summary
    print(f"\n{'='*50}")
    print(f"Data Health Check: {report['status']}")
    print(f"{'='*50}")
    print(f"  Run directory: {report['run_directory']}")
    print(f"  Files checked: {report['files_checked']}")
    print(f"  Timestamp: {report['timestamp']}")

    summary = report['blocking_summary']
    print(f"\n  Blocking Checks:")
    print(f"    Passed: {summary['passed']}/{summary['total_blocking']}")
    print(f"    Failed: {summary['failed']}")
    print(f"    Warned: {summary['warned']}")

    if args.verbose:
        print(f"\n{'='*50}")
        print("Validation Details:")
        print(f"{'='*50}")
        for item in report['validation_table']:
            status = item['status']
            if status == "PASS":
                icon = "[PASS]"
            elif status == "FAIL":
                icon = "[FAIL]"
            elif status == "WARN":
                icon = "[WARN]"
            else:
                icon = "[----]"

            # Format actual value
            actual = item['actual']
            if isinstance(actual, float):
                actual_str = f"{actual:.4f}"
            else:
                actual_str = str(actual)

            print(f"  {icon} {item['display_name']}")
            print(f"         Actual: {actual_str} | Target: {item['target']}")

    # Final status line
    print(f"\n{'='*50}")
    if report['status'] == "PASS":
        print("Result: ALL CHECKS PASSED")
    elif report['status'] == "WARN":
        print("Result: PASSED WITH WARNINGS")
    else:
        print("Result: CHECKS FAILED")
    print(f"{'='*50}")

    # Exit code
    if report['status'] == "FAIL":
        sys.exit(1)
    if report['status'] == "WARN" and args.fail_on_warn:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
