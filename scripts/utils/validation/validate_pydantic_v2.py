#!/usr/bin/env python3
"""
Validate that code uses Pydantic v2 patterns only.
Checks for deprecated v1 patterns and fails if found.

Usage:
    python scripts/validate_pydantic_v2.py <file1> <file2> ...
    python scripts/validate_pydantic_v2.py $(find src -name "*.py")

Exit codes:
    0: All files pass validation
    1: Deprecated patterns found
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, NamedTuple

class PatternMatch(NamedTuple):
    """Represents a matched deprecated pattern."""
    line_num: int
    line_content: str
    pattern: str
    suggestion: str

# Deprecated patterns to detect (pattern, suggestion)
DEPRECATED_PATTERNS = [
    (
        r'from pydantic import BaseSettings\b',
        'Use: from pydantic_settings import BaseSettings'
    ),
    (
        r'from pydantic import validator\b',
        'Use: from pydantic import field_validator'
    ),
    (
        r'from pydantic import root_validator\b',
        'Use: from pydantic import model_validator'
    ),
    (
        r'@validator\s*\(',
        'Use: @field_validator() with @classmethod decorator'
    ),
    (
        r'@root_validator\s*\(',
        'Use: @model_validator(mode="after") with @classmethod decorator'
    ),
    (
        r'^\s*class Config\s*:',
        'Use: model_config = ConfigDict(...) or SettingsConfigDict(...)'
    ),
    (
        r'\.dict\s*\(',
        'Use: .model_dump()'
    ),
    (
        r'\.json\s*\(',
        'Use: .model_dump_json()'
    ),
    (
        r'\.parse_obj\s*\(',
        'Use: .model_validate()'
    ),
    (
        r'\.parse_raw\s*\(',
        'Use: .model_validate_json()'
    ),
    (
        r'\.parse_file\s*\(',
        'Use: with open() + .model_validate()'
    ),
    (
        r'\.schema\s*\(',
        'Use: .model_json_schema()'
    ),
    (
        r'\.schema_json\s*\(',
        'Use: json.dumps(.model_json_schema())'
    ),
    (
        r'\.construct\s*\(',
        'Use: .model_construct()'
    ),
    (
        r'Field\s*\([^)]*\bregex\s*=',
        'Use: Field(..., pattern=...) instead of regex='
    ),
]

# Files or patterns to skip
SKIP_PATTERNS = [
    r'test_.*\.py$',  # Test files may test legacy behavior
    r'.*_test\.py$',
    r'migration.*\.py$',  # Migration scripts
    r'validate_pydantic_v2\.py$',  # This file itself
]

def should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped."""
    file_str = str(file_path)
    return any(re.search(pattern, file_str) for pattern in SKIP_PATTERNS)

def check_file(file_path: Path, verbose: bool = False) -> List[PatternMatch]:
    """
    Check a single file for deprecated patterns.

    Args:
        file_path: Path to the Python file to check
        verbose: Whether to print verbose output

    Returns:
        List of PatternMatch objects for any deprecated patterns found
    """
    if should_skip_file(file_path):
        if verbose:
            print(f"⏭️  Skipping {file_path}", file=sys.stderr)
        return []

    errors = []

    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            # Skip comments and docstrings
            stripped = line.strip()
            if stripped.startswith('#'):
                continue

            for pattern, suggestion in DEPRECATED_PATTERNS:
                if re.search(pattern, line):
                    errors.append(PatternMatch(
                        line_num=line_num,
                        line_content=line.strip(),
                        pattern=pattern,
                        suggestion=suggestion
                    ))

        if verbose and not errors:
            print(f"✅ {file_path}", file=sys.stderr)

    except UnicodeDecodeError:
        if verbose:
            print(f"⚠️  Skipping binary file: {file_path}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}", file=sys.stderr)

    return errors

def format_error_report(file_path: Path, errors: List[PatternMatch]) -> str:
    """Format error report for a file."""
    lines = [f"\n📄 {file_path}:"]

    for error in errors:
        lines.append(f"  Line {error.line_num}:")
        lines.append(f"    Code: {error.line_content[:80]}")
        lines.append(f"    ❌ Found deprecated pattern")
        lines.append(f"    ✅ {error.suggestion}")

    return '\n'.join(lines)

def main():
    """Main validation function."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate Pydantic v2 patterns in Python files',
        epilog='Exit code 0: all files pass, 1: deprecated patterns found'
    )
    parser.add_argument(
        'files',
        nargs='+',
        type=Path,
        help='Python files to check'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Only output errors, no success messages'
    )

    args = parser.parse_args()

    if args.verbose:
        print("🔍 Validating Pydantic v2 patterns...\n", file=sys.stderr)

    files_to_check = [f for f in args.files if f.exists() and f.suffix == '.py']

    if not files_to_check:
        print("⚠️  No Python files found to check", file=sys.stderr)
        sys.exit(0)

    all_errors = []
    files_checked = 0
    files_with_errors = 0

    for file_path in files_to_check:
        errors = check_file(file_path, verbose=args.verbose)
        files_checked += 1

        if errors:
            all_errors.append((file_path, errors))
            files_with_errors += 1

    # Report results
    if all_errors:
        print("\n" + "="*80, file=sys.stderr)
        print("❌ DEPRECATED PYDANTIC v1 PATTERNS FOUND", file=sys.stderr)
        print("="*80, file=sys.stderr)

        for file_path, errors in all_errors:
            print(format_error_report(file_path, errors), file=sys.stderr)

        print("\n" + "="*80, file=sys.stderr)
        print(f"📊 Summary:", file=sys.stderr)
        print(f"   Files checked: {files_checked}", file=sys.stderr)
        print(f"   Files with errors: {files_with_errors}", file=sys.stderr)
        print(f"   Total errors: {sum(len(errors) for _, errors in all_errors)}", file=sys.stderr)
        print("="*80, file=sys.stderr)

        print("\n⚠️  All code must use Pydantic v2 patterns.", file=sys.stderr)
        print("📖 See docs/PYDANTIC_V2_ENFORCEMENT.md for migration guide.", file=sys.stderr)
        print("📖 See docs/ENUM_CONFIG_PATTERNS.md for code examples.\n", file=sys.stderr)

        sys.exit(1)

    if not args.quiet:
        print("\n" + "="*80, file=sys.stderr)
        print("✅ ALL FILES PASS VALIDATION", file=sys.stderr)
        print("="*80, file=sys.stderr)
        print(f"📊 Checked {files_checked} Python files", file=sys.stderr)
        print("✅ All files use Pydantic v2 patterns correctly.", file=sys.stderr)
        print("="*80 + "\n", file=sys.stderr)

    sys.exit(0)

if __name__ == '__main__':
    main()
