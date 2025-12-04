#!/usr/bin/env python3
"""
Lint Audit Script - Full codebase lint report with Pylint and Flake8.

Usage:
    python hack/lint_audit.py                    # Full audit
    python hack/lint_audit.py src/preprocessing  # Single module
    python hack/lint_audit.py --threshold 9.0    # Fail if score < 9.0
    python hack/lint_audit.py --json             # Output JSON only
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def run_flake8(paths: List[Path], max_line_length: int = 100) -> Dict:
    """Run flake8 and return results."""
    cmd = [
        sys.executable, "-m", "flake8",
        "--max-line-length", str(max_line_length),
        "--format", "%(path)s:%(row)d:%(col)d: %(code)s %(text)s",
    ]
    cmd.extend(str(p) for p in paths)

    result = subprocess.run(cmd, capture_output=True, text=True)

    issues = []
    for line in result.stdout.strip().split("\n"):
        if line:
            issues.append(line)

    return {
        "tool": "flake8",
        "issue_count": len(issues),
        "issues": issues[:50],  # Limit output
        "exit_code": result.returncode,
    }


def run_pylint(paths: List[Path]) -> Dict:
    """Run pylint and return results."""
    # Run with text output first to get the score
    cmd_text = [
        sys.executable, "-m", "pylint",
        "--output-format", "text",
        "--max-line-length", "100",
    ]
    cmd_text.extend(str(p) for p in paths)

    result_text = subprocess.run(cmd_text, capture_output=True, text=True)

    # Extract score from text output
    score = 0.0
    all_output = result_text.stdout + result_text.stderr
    for line in all_output.split("\n"):
        if "rated at" in line:
            try:
                score = float(line.split("rated at")[1].split("/")[0].strip())
            except (IndexError, ValueError):
                pass

    # Run with JSON output to get structured issues
    cmd_json = [
        sys.executable, "-m", "pylint",
        "--output-format", "json",
        "--max-line-length", "100",
    ]
    cmd_json.extend(str(p) for p in paths)

    result_json = subprocess.run(cmd_json, capture_output=True, text=True)

    # Parse JSON output
    issues = []
    try:
        if result_json.stdout.strip():
            issues = json.loads(result_json.stdout)
    except json.JSONDecodeError:
        pass

    # Group by type
    by_type = {}
    for issue in issues:
        msg_id = issue.get("message-id", "unknown")
        by_type[msg_id] = by_type.get(msg_id, 0) + 1

    return {
        "tool": "pylint",
        "score": score,
        "issue_count": len(issues),
        "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])[:10]),
        "issues": issues[:20],  # Limit output
        "exit_code": result_text.returncode,
    }


def find_python_files(paths: List[str]) -> List[Path]:
    """Find all Python files in given paths."""
    python_files = []

    for path_str in paths:
        path = Path(path_str)
        if path.is_file() and path.suffix == ".py":
            python_files.append(path)
        elif path.is_dir():
            python_files.extend(path.rglob("*.py"))

    return sorted(set(python_files))


def save_history(report: Dict, history_file: Path) -> None:
    """Append report summary to history file."""
    history = []
    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []

    history.append({
        "timestamp": report["timestamp"],
        "pylint_score": report["pylint"]["score"],
        "flake8_issues": report["flake8"]["issue_count"],
        "files_checked": report["files_checked"],
    })

    # Keep last 100 entries
    history = history[-100:]

    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Lint audit for Python codebase")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["src", "tests"],
        help="Paths to audit (default: src tests)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=8.0,
        help="Minimum pylint score (default: 8.0)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON only"
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Don't save to history file"
    )

    args = parser.parse_args()

    # Find Python files
    python_files = find_python_files(args.paths)

    if not python_files:
        print("No Python files found.")
        return 1

    # Run linters
    flake8_results = run_flake8(python_files)
    pylint_results = run_pylint(python_files)

    # Build report
    report = {
        "timestamp": datetime.now().isoformat(),
        "paths": args.paths,
        "files_checked": len(python_files),
        "flake8": flake8_results,
        "pylint": pylint_results,
        "threshold": args.threshold,
        "status": "PASS" if pylint_results["score"] >= args.threshold else "FAIL",
    }

    # Save history
    if not args.no_history:
        project_root = Path(__file__).parent.parent
        history_file = project_root / "logs" / "lint_history.json"
        save_history(report, history_file)

    # Output
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{'='*60}")
        print("LINT AUDIT REPORT")
        print(f"{'='*60}")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Files checked: {report['files_checked']}")
        print(f"Paths: {', '.join(args.paths)}")
        print()
        print(f"Flake8: {flake8_results['issue_count']} issues")
        if flake8_results['issues']:
            for issue in flake8_results['issues'][:5]:
                print(f"  {issue}")
            if len(flake8_results['issues']) > 5:
                print(f"  ... and {len(flake8_results['issues']) - 5} more")
        print()
        print(f"Pylint: {pylint_results['score']:.2f}/10")
        print(f"  Issues: {pylint_results['issue_count']}")
        if pylint_results['by_type']:
            print("  Top issues:")
            for msg_id, count in list(pylint_results['by_type'].items())[:5]:
                print(f"    {msg_id}: {count}")
        print()
        print(f"Threshold: {args.threshold}")
        print(f"Status: {report['status']}")
        print(f"{'='*60}")

    # Return exit code
    if report["status"] == "FAIL":
        return 1
    if flake8_results["issue_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
