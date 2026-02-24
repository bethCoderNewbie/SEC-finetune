#!/usr/bin/env python
"""
Descriptive analysis of short_segment_sample.tsv for further investigation.

Reads a TSV produced by diagnose_short_segments.py and computes:
  1. Bracket distribution — count / % / uniqueness rate per word_bracket
  2. Duplicate text patterns — most-repeated text_previews (boilerplate signal)
  3. Subsection distribution — which parent_subsections generate short segments
  4. Filing distribution — which filings contribute most short segments
  5. Uniqueness rate — what fraction of each bracket is deduplicated text

Outputs:
  --output-json   Full JSON report (all tables)
  --output-patterns  TSV of deduplicated (text_preview, count, brackets) sorted by freq

Usage:
    python scripts/validation/data_quality/analyse_short_segments.py \\
        --input   reports/short_segment_sample2.tsv \\
        --output-json     reports/short_segment_analysis.json \\
        --output-patterns reports/short_segment_patterns.tsv

    # Top-N controls
    python scripts/validation/data_quality/analyse_short_segments.py \\
        --input reports/short_segment_sample2.tsv \\
        --top-subsections 30 --top-patterns 100
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Ordered bracket labels for display
BRACKET_ORDER = ["1-10", "11-20", "21-30", "31-50", "51-75", "76-100",
                 "101-150", "151-200", "201-300", "301-380", "381-420", ">420"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_tsv(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return list(reader)


# ---------------------------------------------------------------------------
# Analysis passes
# ---------------------------------------------------------------------------

def bracket_distribution(rows: List[Dict]) -> List[Dict[str, Any]]:
    """Count, %, and uniqueness rate per word_bracket."""
    total = len(rows)
    counts: Counter = Counter(r["word_bracket"] for r in rows)

    # unique text_preview per bracket
    previews_by_bracket: Dict[str, set] = defaultdict(set)
    for r in rows:
        previews_by_bracket[r["word_bracket"]].add(r["text_preview"].strip())

    result = []
    for label in BRACKET_ORDER:
        n = counts.get(label, 0)
        if n == 0:
            continue
        unique = len(previews_by_bracket[label])
        result.append({
            "bracket": label,
            "count": n,
            "pct": n / total * 100,
            "unique_previews": unique,
            "uniqueness_rate": unique / n * 100,
        })
    return result


def duplicate_patterns(rows: List[Dict], top_n: int) -> List[Dict[str, Any]]:
    """
    Most-repeated text_preview values across all rows.
    High repeat-count = boilerplate / header candidate.
    """
    counter: Counter = Counter(r["text_preview"].strip() for r in rows)

    # Collect which brackets each preview appears in
    brackets_by_preview: Dict[str, set] = defaultdict(set)
    for r in rows:
        brackets_by_preview[r["text_preview"].strip()].add(r["word_bracket"])

    result = []
    for text, count in counter.most_common(top_n):
        result.append({
            "count": count,
            "brackets": sorted(brackets_by_preview[text],
                               key=lambda b: BRACKET_ORDER.index(b) if b in BRACKET_ORDER else 99),
            "text_preview": text,
        })
    return result


def subsection_distribution(rows: List[Dict], top_n: int) -> List[Dict[str, Any]]:
    """Top parent_subsections by frequency in the short-segment set."""
    total = len(rows)
    counter: Counter = Counter(
        (r["parent_subsection"].strip() or "(none)") for r in rows
    )

    # Count unique text_previews per subsection (uniqueness signal)
    unique_by_sub: Dict[str, set] = defaultdict(set)
    bracket_by_sub: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        sub = r["parent_subsection"].strip() or "(none)"
        unique_by_sub[sub].add(r["text_preview"].strip())
        bracket_by_sub[sub][r["word_bracket"]] += 1

    result = []
    for sub, count in counter.most_common(top_n):
        result.append({
            "parent_subsection": sub,
            "count": count,
            "pct": count / total * 100,
            "unique_previews": len(unique_by_sub[sub]),
            "uniqueness_rate": len(unique_by_sub[sub]) / count * 100,
            "dominant_bracket": bracket_by_sub[sub].most_common(1)[0][0],
        })
    return result


def filing_distribution(rows: List[Dict], top_n: int) -> List[Dict[str, Any]]:
    """Filings that contribute the most short segments."""
    total = len(rows)
    counter: Counter = Counter(r["filing"] for r in rows)

    result = []
    for filing, count in counter.most_common(top_n):
        result.append({
            "filing": filing,
            "count": count,
            "pct": count / total * 100,
        })
    return result


def uniqueness_summary(rows: List[Dict]) -> Dict[str, Any]:
    """Corpus-level uniqueness: how many distinct text_previews vs total rows."""
    total = len(rows)
    unique = len({r["text_preview"].strip() for r in rows})
    duplicate_rows = total - unique
    return {
        "total_rows": total,
        "unique_previews": unique,
        "duplicate_rows": duplicate_rows,
        "duplication_rate": duplicate_rows / total * 100,
        "uniqueness_rate": unique / total * 100,
    }


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def _pct_bar(pct: float, width: int = 25) -> str:
    filled = round(pct / 100 * width)
    return "[" + "#" * filled + " " * (width - filled) + "]"


def print_report(result: Dict[str, Any], top_patterns: int) -> None:
    print(f"\n{'='*70}")
    print(f"  Short Segment Analysis")
    print(f"{'='*70}")
    print(f"  Input     : {result['input']}")
    print(f"  Rows      : {result['uniqueness']['total_rows']:,}")
    print(f"  Timestamp : {result['timestamp']}")

    # Uniqueness summary
    u = result["uniqueness"]
    print(f"\n--- Corpus Uniqueness ---")
    print(f"  Distinct text_previews : {u['unique_previews']:,} / {u['total_rows']:,}  "
          f"({u['uniqueness_rate']:.1f}% unique)")
    print(f"  Duplicate rows         : {u['duplicate_rows']:,}  "
          f"({u['duplication_rate']:.1f}%)")

    # Bracket distribution
    print(f"\n--- Bracket Distribution ---")
    print(f"  {'Bracket':<12}  {'Count':>8}  {'%':>6}  {'Unique%':>8}  {'Bar'}")
    print(f"  {'-'*12}  {'-'*8}  {'-'*6}  {'-'*8}  {'-'*25}")
    for b in result["brackets"]:
        print(
            f"  {b['bracket']:<12}  {b['count']:>8,}  {b['pct']:>5.1f}%  "
            f"{b['uniqueness_rate']:>7.1f}%  {_pct_bar(b['pct'])}"
        )

    # Top duplicate patterns
    print(f"\n--- Top {top_patterns} Repeated Text Patterns (boilerplate candidates) ---")
    print(f"  {'Count':>6}  {'Brackets':<20}  {'Text preview'}")
    print(f"  {'-'*6}  {'-'*20}  {'-'*50}")
    for p in result["duplicate_patterns"][:top_patterns]:
        brackets_str = ",".join(p["brackets"])
        print(f"  {p['count']:>6,}  {brackets_str:<20}  {p['text_preview'][:60]!r}")

    # Top subsections
    print(f"\n--- Top {len(result['subsections'])} parent_subsections ---")
    print(f"  {'Count':>7}  {'Uniq%':>6}  {'Dom bracket':<12}  {'Subsection'}")
    print(f"  {'-'*7}  {'-'*6}  {'-'*12}  {'-'*45}")
    for s in result["subsections"]:
        print(
            f"  {s['count']:>7,}  {s['uniqueness_rate']:>5.1f}%  "
            f"{s['dominant_bracket']:<12}  {s['parent_subsection'][:45]}"
        )

    print(f"\n{'='*70}\n")


# ---------------------------------------------------------------------------
# Patterns TSV output
# ---------------------------------------------------------------------------

def write_patterns_tsv(patterns: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["count", "brackets", "text_preview"])
        for p in patterns:
            writer.writerow([p["count"], ",".join(p["brackets"]), p["text_preview"]])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descriptive analysis of short_segment_sample.tsv",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="TSV file produced by diagnose_short_segments.py",
    )
    parser.add_argument(
        "--output-json", "-o",
        type=Path,
        help="Write full JSON report to this path",
    )
    parser.add_argument(
        "--output-patterns",
        type=Path,
        help="Write deduplicated text pattern TSV to this path",
    )
    parser.add_argument(
        "--top-patterns",
        type=int,
        default=20,
        help="Number of top repeated patterns to show in stdout (default: 20)",
    )
    parser.add_argument(
        "--top-subsections",
        type=int,
        default=20,
        help="Number of top parent_subsections to show (default: 20)",
    )
    parser.add_argument(
        "--top-filings",
        type=int,
        default=20,
        help="Number of top filings to include in JSON report (default: 20)",
    )
    parser.add_argument(
        "--all-patterns",
        type=int,
        default=500,
        help="Number of patterns to write to --output-patterns TSV (default: 500)",
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {args.input} …", flush=True)
    rows = load_tsv(args.input)
    if not rows:
        print("Error: no rows found in input file.", file=sys.stderr)
        sys.exit(1)
    print(f"Loaded {len(rows):,} rows.", flush=True)

    result = {
        "timestamp": datetime.now().isoformat(),
        "input": str(args.input),
        "uniqueness": uniqueness_summary(rows),
        "brackets": bracket_distribution(rows),
        "duplicate_patterns": duplicate_patterns(rows, top_n=args.all_patterns),
        "subsections": subsection_distribution(rows, top_n=args.top_subsections),
        "filings": filing_distribution(rows, top_n=args.top_filings),
    }

    print_report(result, top_patterns=args.top_patterns)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print(f"JSON report saved to: {args.output_json}")

    if args.output_patterns:
        write_patterns_tsv(result["duplicate_patterns"], args.output_patterns)
        print(f"Patterns TSV saved to: {args.output_patterns}")

    sys.exit(0)


if __name__ == "__main__":
    main()
