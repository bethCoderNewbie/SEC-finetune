#!/usr/bin/env python
"""
Diagnose short segments in a preprocessing batch — Phase A Tasks 1 & 2.

Task 1: Sample N segments from the [bracket-lo, bracket-hi] word-count bracket
        and write a TSV with a blank 'category' column for manual classification
        (header / transitional / boilerplate / genuine-brief-risk).

Task 2: Measure parent_subsection fill rate across ALL segments in the batch.

Reads all *_segmented_risks.json / *_segmented.json files in --run-dir
(same glob convention as check_word_count_distribution.py).

Usage:
    python scripts/validation/data_quality/diagnose_short_segments.py \\
        --run-dir data/processed/20260223_182806_preprocessing_3ef72af \\
        --output  reports/short_segment_sample.tsv

    # Custom bracket and sample size
    python scripts/validation/data_quality/diagnose_short_segments.py \\
        --run-dir data/processed/... \\
        --output  reports/short_segment_sample.tsv \\
        --bracket-lo 5 --bracket-hi 25 --sample-n 100 --seed 7

Exit Codes:
    0 - Completed successfully
    1 - No JSON files found, or bracket produced zero candidates
"""

import argparse
import csv
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Tuple


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_segments_full(run_dir: Path) -> Generator[Dict[str, Any], None, None]:
    """
    Yield one dict per segment from all *.json files in run_dir.

    Skips checkpoint / manifest files (names starting with '_').
    Handles both:
      - old flat schema  → top-level 'segments' list, seg['id'] as chunk_id
      - v2 structured schema → top-level 'chunks' list, chunk['chunk_id']
    """
    for path in sorted(run_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        # v2 schema uses 'chunks'; old flat schema uses 'segments'
        if "chunks" in data:
            raw = data["chunks"]
            for chunk in raw:
                yield {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "filing": path.stem,
                    "parent_subsection": chunk.get("parent_subsection"),
                    "word_count": chunk.get(
                        "word_count",
                        len(chunk.get("text", "").split()),
                    ),
                    "text": chunk.get("text", ""),
                }
        else:
            raw = data.get("segments", [])
            for seg in raw:
                yield {
                    "chunk_id": seg.get("id") or seg.get("chunk_id", ""),
                    "filing": path.stem,
                    "parent_subsection": seg.get("parent_subsection"),
                    "word_count": seg.get(
                        "word_count",
                        len(seg.get("text", "").split()),
                    ),
                    "text": seg.get("text", ""),
                }


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

FILL_RATE_TARGET = 90.0   # ≥ 90% fill → PASS


def run_analysis(
    run_dir: Path,
    bracket_lo: int,
    bracket_hi: int,
    sample_n: int,
    seed: int,
) -> Dict[str, Any]:
    """
    Load all segments, compute fill rate (Task 2), sample short bracket (Task 1).
    Returns a result dict.
    """
    all_segs: List[Dict[str, Any]] = []
    for seg in load_segments_full(run_dir):
        all_segs.append(seg)

    total = len(all_segs)
    if total == 0:
        return {"error": "No segments found"}

    # Task 2 — parent_subsection fill rate across ALL segments
    filled = sum(1 for s in all_segs if s["parent_subsection"] is not None)
    none_count = total - filled
    fill_pct = filled / total * 100

    # Task 1 — short segment bracket
    short = [s for s in all_segs if bracket_lo <= s["word_count"] <= bracket_hi]
    short_count = len(short)
    short_pct = short_count / total * 100

    rng = random.Random(seed)
    sample = rng.sample(short, min(sample_n, short_count))
    sample.sort(key=lambda s: s["word_count"])

    return {
        "timestamp": datetime.now().isoformat(),
        "run_directory": str(run_dir),
        "total_segments": total,
        "bracket": {"lo": bracket_lo, "hi": bracket_hi},
        "short_count": short_count,
        "short_pct": short_pct,
        "sampled": len(sample),
        "fill_rate": {
            "filled": filled,
            "none": none_count,
            "pct": fill_pct,
            "target": FILL_RATE_TARGET,
            "status": "PASS" if fill_pct >= FILL_RATE_TARGET else "WARN",
        },
        "sample": sample,
    }


# ---------------------------------------------------------------------------
# Word-count bracket labels
# ---------------------------------------------------------------------------

_WORD_BRACKETS: List[Tuple[str, int, int]] = [
    ("1-10",    1,   10),
    ("11-20",   11,  20),
    ("21-30",   21,  30),
    ("31-50",   31,  50),
    ("51-75",   51,  75),
    ("76-100",  76,  100),
    ("101-150", 101, 150),
    ("151-200", 151, 200),
    ("201-300", 201, 300),
    ("301-380", 301, 380),
    ("381-420", 381, 420),
    (">420",    421, 10**9),
]


def word_bracket(wc: int) -> str:
    """Return the bracket label for a word count."""
    for label, lo, hi in _WORD_BRACKETS:
        if lo <= wc <= hi:
            return label
    return f">{_WORD_BRACKETS[-2][2]}"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_tsv(sample: List[Dict[str, Any]], output_path: Path) -> None:
    """Write sample rows to TSV with blank 'category' column."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["chunk_id", "filing", "parent_subsection", "word_count",
                         "word_bracket", "text_preview", "category"])
        for s in sample:
            preview = s["text"][:100].replace("\n", " ")
            writer.writerow([
                s["chunk_id"],
                s["filing"],
                s["parent_subsection"] if s["parent_subsection"] is not None else "",
                s["word_count"],
                word_bracket(s["word_count"]),
                preview,
                "",   # blank — manual fill
            ])


def print_report(result: Dict[str, Any], output_path: Path) -> None:
    """Print human-readable summary to stdout."""
    total = result["total_segments"]
    sc = result["short_count"]
    sp = result["short_pct"]
    lo = result["bracket"]["lo"]
    hi = result["bracket"]["hi"]
    n  = result["sampled"]
    fr = result["fill_rate"]

    print(f"\n{'='*62}")
    print(f"  Short Segment Diagnostics — Phase A")
    print(f"{'='*62}")
    print(f"  Run directory : {result['run_directory']}")
    print(f"  Total segments: {total:,}")
    print(f"  Timestamp     : {result['timestamp']}")

    print(f"\n--- Task 1 : Short Segment Sample ({lo}–{hi} words) ---")
    print(f"  Short segments ({lo}-{hi} words): {sc:,} / {total:,} ({sp:.2f}%)")
    print(f"  Sampled {n} for manual review → {output_path}")

    print(f"\n--- Task 2 : parent_subsection fill rate (all segments) ---")
    print(f"  Filled : {fr['filled']:>7,} / {total:,}  ({fr['pct']:.1f}%)")
    print(f"  None   : {fr['none']:>7,} / {total:,}  ({100 - fr['pct']:.1f}%)")
    gate_label = f"≥{FILL_RATE_TARGET:.0f}% target → {fr['status']}"
    if fr["status"] == "WARN":
        gate_label += f"  ({100 - fr['pct']:.1f}% missing)"
    print(f"  Gate   : {gate_label}")
    print(f"\n{'='*62}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose short segments and measure parent_subsection fill rate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Batch directory containing *_segmented_risks.json / *_segmented.json files",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Write TSV sample to this path (e.g. reports/short_segment_sample.tsv)",
    )
    parser.add_argument(
        "--bracket-lo",
        type=int,
        default=10,
        metavar="N",
        help="Lower bound of short-segment word-count bracket, inclusive (default: 10)",
    )
    parser.add_argument(
        "--bracket-hi",
        type=int,
        default=19,
        metavar="N",
        help="Upper bound of short-segment word-count bracket, inclusive (default: 19)",
    )
    parser.add_argument(
        "--sample-n",
        type=int,
        default=50,
        metavar="N",
        help="Number of segments to sample from bracket (default: 50)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42)",
    )

    args = parser.parse_args()

    if not args.run_dir.exists():
        print(f"Error: directory not found: {args.run_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.run_dir.is_dir():
        print(f"Error: not a directory: {args.run_dir}", file=sys.stderr)
        sys.exit(1)
    if args.bracket_lo > args.bracket_hi:
        print(
            f"Error: --bracket-lo ({args.bracket_lo}) must be ≤ --bracket-hi ({args.bracket_hi})",
            file=sys.stderr,
        )
        sys.exit(1)

    result = run_analysis(
        run_dir=args.run_dir,
        bracket_lo=args.bracket_lo,
        bracket_hi=args.bracket_hi,
        sample_n=args.sample_n,
        seed=args.seed,
    )

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if result["short_count"] == 0:
        print(
            f"Error: no segments found in bracket "
            f"{args.bracket_lo}–{args.bracket_hi} words",
            file=sys.stderr,
        )
        sys.exit(1)

    write_tsv(result["sample"], args.output)
    print_report(result, args.output)


if __name__ == "__main__":
    main()
