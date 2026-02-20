#!/usr/bin/env python
"""
Analyse segment word-count distribution across a preprocessing batch.

Reads all *_segmented_risks.json files in a run directory and reports:
  - Full word-count bucket histogram
  - Key threshold rates (>350, >380, >420, >500 words)
  - Per-filing over-limit breakdown
  - Corpus-level descriptive statistics (mean, p50, p95, max)

The 380-word ceiling is the RFC-003 Option A threshold (~512 tokens at
1.35 tok/word).  Post-Option-A deployment the over-limit rate should be ~0%.

Usage:
    # Quick summary — latest batch
    python scripts/validation/data_quality/check_word_count_distribution.py \\
        --run-dir data/processed/20260218_142659_preprocessing_0b83409

    # Show per-filing table
    python scripts/validation/data_quality/check_word_count_distribution.py \\
        --run-dir data/processed/... --verbose

    # Custom ceiling and fail-above threshold (useful in CI)
    python scripts/validation/data_quality/check_word_count_distribution.py \\
        --run-dir data/processed/... --ceil 380 --fail-above 0.05

    # Save JSON report
    python scripts/validation/data_quality/check_word_count_distribution.py \\
        --run-dir data/processed/... --output reports/word_count_dist.json

Exit Codes:
    0 - Over-limit rate is at or below --fail-above (default: always 0)
    1 - Over-limit rate exceeds --fail-above, or no JSON files found
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean, median, quantiles
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_batch(run_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all *_segmented_risks.json files from run_dir.

    Returns list of dicts with keys: filing_name, segments (list of word_count ints).
    Skips checkpoint / manifest files (names starting with '_').
    """
    records = []
    for path in sorted(run_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        word_counts = [
            seg.get("word_count", len(seg.get("text", "").split()))
            for seg in data.get("segments", [])
        ]
        if not word_counts:
            continue
        records.append({
            "filing_name": path.stem,
            "ticker": data.get("ticker", ""),
            "form_type": data.get("form_type", ""),
            "word_counts": word_counts,
        })
    return records


# ---------------------------------------------------------------------------
# Distribution analysis
# ---------------------------------------------------------------------------

BUCKETS: List[Tuple[str, Optional[int], Optional[int]]] = [
    ("≤100",     None, 100),
    ("101–200",  101,  200),
    ("201–300",  201,  300),
    ("301–380",  301,  380),
    ("381–420",  381,  420),
    ("421–500",  421,  500),
    (">500",     501,  None),
]

THRESHOLDS = [350, 380, 420, 500]


def analyse(records: List[Dict], ceil: int) -> Dict[str, Any]:
    """Compute distribution statistics from loaded records."""
    all_counts: List[int] = []
    for r in records:
        all_counts.extend(r["word_counts"])

    total = len(all_counts)
    if total == 0:
        return {"error": "No segments found"}

    # Bucket histogram
    buckets = []
    for label, lo, hi in BUCKETS:
        count = sum(
            1 for wc in all_counts
            if (lo is None or wc >= lo) and (hi is None or wc <= hi)
        )
        buckets.append({
            "bucket": label,
            "count": count,
            "pct": count / total * 100,
        })

    # Threshold rates
    threshold_rows = []
    for t in THRESHOLDS:
        count = sum(1 for wc in all_counts if wc > t)
        threshold_rows.append({
            "threshold": f">{t} words",
            "count": count,
            "rate": count / total,
            "pct": count / total * 100,
        })

    # Descriptive stats
    p95 = quantiles(all_counts, n=20)[18] if len(all_counts) >= 20 else max(all_counts)
    stats = {
        "total_segments": total,
        "total_filings": len(records),
        "mean": mean(all_counts),
        "median": median(all_counts),
        "p95": p95,
        "max": max(all_counts),
        "min": min(all_counts),
    }

    # Per-filing over-limit
    per_filing = []
    for r in records:
        wcs = r["word_counts"]
        over = sum(1 for wc in wcs if wc > ceil)
        per_filing.append({
            "filing": r["filing_name"],
            "ticker": r["ticker"],
            "form_type": r["form_type"],
            "total": len(wcs),
            "over_limit": over,
            "rate": over / len(wcs) if wcs else 0.0,
        })
    per_filing.sort(key=lambda x: x["rate"], reverse=True)

    # Corpus over-limit rate
    over_limit_count = sum(1 for wc in all_counts if wc > ceil)
    over_limit_rate = over_limit_count / total

    return {
        "timestamp": datetime.now().isoformat(),
        "run_directory": "",      # filled by caller
        "ceil": ceil,
        "stats": stats,
        "buckets": buckets,
        "thresholds": threshold_rows,
        "over_limit_count": over_limit_count,
        "over_limit_rate": over_limit_rate,
        "per_filing": per_filing,
    }


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def _pct_bar(pct: float, width: int = 30) -> str:
    filled = round(pct / 100 * width)
    return "[" + "#" * filled + " " * (width - filled) + "]"


def print_report(result: Dict, verbose: bool = False, ceil: int = 380) -> None:
    """Print a human-readable distribution report."""
    s = result["stats"]
    over_rate = result["over_limit_rate"]
    over_count = result["over_limit_count"]

    print(f"\n{'='*62}")
    print(f"  Segment Word-Count Distribution")
    print(f"{'='*62}")
    print(f"  Run directory : {result.get('run_directory', '')}")
    print(f"  Filings       : {s['total_filings']}")
    print(f"  Segments      : {s['total_segments']}")
    print(f"  Timestamp     : {result['timestamp']}")

    print(f"\n--- Descriptive Statistics ---")
    print(f"  Mean   : {s['mean']:>7.1f} words")
    print(f"  Median : {s['median']:>7.1f} words")
    print(f"  p95    : {s['p95']:>7.1f} words")
    print(f"  Max    : {s['max']:>7}  words")

    print(f"\n--- Word-Count Distribution ---")
    print(f"  {'Bucket':<12}  {'Count':>6}  {'%':>6}  {'Bar'}")
    print(f"  {'-'*12}  {'-'*6}  {'-'*6}  {'-'*30}")
    for b in result["buckets"]:
        marker = " <-- Option A ceil" if b["bucket"] == "301–380" else ""
        print(
            f"  {b['bucket']:<12}  {b['count']:>6}  "
            f"{b['pct']:>5.1f}%  {_pct_bar(b['pct'])}{marker}"
        )

    print(f"\n--- Threshold Summary ---")
    print(f"  {'Threshold':<16}  {'Count':>6}  {'Rate':>7}  {'Status'}")
    print(f"  {'-'*16}  {'-'*6}  {'-'*7}  {'-'*10}")
    for t in result["thresholds"]:
        if t["threshold"] == f">{ceil} words":
            status = "PASS" if t["rate"] == 0.0 else ("WARN" if t["rate"] <= 0.05 else "FAIL")
        else:
            status = ""
        print(f"  {t['threshold']:<16}  {t['count']:>6}  {t['rate']:>6.2%}  {status}")

    print(f"\n--- Option A Ceiling (>{ceil} words) ---")
    print(f"  Over-limit : {over_count} / {s['total_segments']} segments  ({over_rate:.2%})")
    if over_rate == 0.0:
        verdict = "PASS  — Option A ceiling is enforced"
    elif over_rate <= 0.05:
        verdict = "WARN  — Pre-Option-A baseline or pharma outlier; deploy RFC-003 Option A"
    else:
        verdict = "FAIL  — Exceeds 5%; review ModernBERT contingency (PRD-002 §4.1 OQ-3)"
    print(f"  Verdict    : {verdict}")

    if verbose and result["per_filing"]:
        print(f"\n--- Per-Filing Breakdown (sorted by over-limit rate) ---")
        print(f"  {'Filing':<36}  {'Over':>5}  {'Total':>6}  {'Rate':>7}")
        print(f"  {'-'*36}  {'-'*5}  {'-'*6}  {'-'*7}")
        for row in result["per_filing"]:
            marker = " *" if row["over_limit"] > 0 else ""
            print(
                f"  {row['filing']:<36}  {row['over_limit']:>5}  "
                f"{row['total']:>6}  {row['rate']:>6.2%}{marker}"
            )

    print(f"\n{'='*62}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse segment word-count distribution in a preprocessing batch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Batch directory containing *_segmented_risks.json files",
    )
    parser.add_argument(
        "--ceil",
        type=int,
        default=380,
        help="Word-count ceiling for Option A analysis (default: 380)",
    )
    parser.add_argument(
        "--fail-above",
        type=float,
        default=None,
        metavar="RATE",
        help=(
            "Exit 1 if over-limit rate exceeds RATE (0.0–1.0). "
            "Example: --fail-above 0.05 enforces the OQ-RFC3-2 trigger. "
            "Default: no threshold enforcement."
        ),
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Write full JSON report to this path",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show per-filing breakdown",
    )

    args = parser.parse_args()

    if not args.run_dir.exists():
        print(f"Error: directory not found: {args.run_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.run_dir.is_dir():
        print(f"Error: not a directory: {args.run_dir}", file=sys.stderr)
        sys.exit(1)

    records = load_batch(args.run_dir)
    if not records:
        print(f"Error: no *_segmented_risks.json files found in {args.run_dir}", file=sys.stderr)
        sys.exit(1)

    result = analyse(records, ceil=args.ceil)
    result["run_directory"] = str(args.run_dir)

    print_report(result, verbose=args.verbose, ceil=args.ceil)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print(f"JSON report saved to: {args.output}")

    if args.fail_above is not None and result["over_limit_rate"] > args.fail_above:
        print(
            f"\nFAIL: over-limit rate {result['over_limit_rate']:.2%} "
            f"exceeds --fail-above {args.fail_above:.2%}",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
