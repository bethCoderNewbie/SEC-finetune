#!/usr/bin/env python
"""
Diagnose short segments in a preprocessing batch — Phase A Tasks 1, 2 & 3.

Task 1: Sample N segments from the [bracket-lo, bracket-hi] word-count bracket
        and write a TSV with a blank 'category' column for manual classification
        (header / transitional / boilerplate / genuine-brief-risk).

Task 2: Measure parent_subsection fill rate across ALL segments in the batch.

Task 3: Section contamination report — break down segments by section_identifier
        (extracted from the filename stem, e.g. part1item1a / part2item8) and flag
        which sections are non-target, their segment counts, and deduplication rates.
        Answers OQ-6: is boilerplate caused by wrong section types in the run?

Reads all *_segmented_risks.json / *_segmented.json files in --run-dir
(same glob convention as check_word_count_distribution.py).

Usage:
    python scripts/validation/data_quality/diagnose_short_segments.py \\
        --run-dir data/processed/20260223_182806_preprocessing_3ef72af \\
        --output  reports/short_segment_sample.tsv

    # Custom bracket, sample size, and target section
    python scripts/validation/data_quality/diagnose_short_segments.py \\
        --run-dir data/processed/... \\
        --output  reports/short_segment_sample.tsv \\
        --bracket-lo 5 --bracket-hi 25 --sample-n 100 --seed 7 \\
        --target-section part1item1a

Exit Codes:
    0 - Completed successfully
    1 - No JSON files found, or bracket produced zero candidates
"""

import argparse
import csv
import json
import re
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple


# Regex to extract section identifier from filename stem.
# e.g. "WFC_10K_2025_part1item1b_segmented" → "part1item1b"
_SECTION_ID_PAT = re.compile(r'_(part\w+)_segmented')


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _extract_section_id(stem: str) -> str:
    """Extract section identifier from a filename stem.

    'WFC_10K_2025_part1item1b_segmented' → 'part1item1b'
    Falls back to '(unknown)' when the pattern does not match.
    """
    m = _SECTION_ID_PAT.search(stem)
    return m.group(1) if m else "(unknown)"


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

        section_id = _extract_section_id(path.stem)

        # v2 schema uses 'chunks'; old flat schema uses 'segments'
        if "chunks" in data:
            raw = data["chunks"]
            for chunk in raw:
                yield {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "filing": path.stem,
                    "section_id": section_id,
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
                    "section_id": section_id,
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

FILL_RATE_TARGET   = 90.0   # ≥ 90% fill → PASS
DEFAULT_TARGET_SECTION = "part1item1a"
TOP_PATTERNS_N     = 10     # repeated text previews shown per section
TOP_SUBSECTIONS_N  = 10     # parent_subsections shown for bracket population


def _section_contamination(
    all_segs: List[Dict[str, Any]],
    target_section: str,
    top_n: int,
) -> Dict[str, Any]:
    """Task 3 — per-section segment count, dedup rate, and top repeated previews."""
    counts:    Counter                      = Counter()
    previews:  Dict[str, List[str]]         = defaultdict(list)

    for s in all_segs:
        sid = s["section_id"]
        counts[sid] += 1
        previews[sid].append(s["text"][:100].strip())

    total = len(all_segs)
    rows = []
    for sid, n in counts.most_common():
        unique     = len(set(previews[sid]))
        dup_pct    = (n - unique) / n * 100
        top_pats   = [
            {"text": txt, "count": cnt}
            for txt, cnt in Counter(previews[sid]).most_common(top_n)
        ]
        rows.append({
            "section_id":     sid,
            "is_target":      sid == target_section,
            "count":          n,
            "pct_of_total":   n / total * 100,
            "unique_previews": unique,
            "dup_pct":        dup_pct,
            "top_patterns":   top_pats,
        })

    target_n   = counts.get(target_section, 0)
    non_target = total - target_n
    return {
        "target_section":     target_section,
        "target_count":       target_n,
        "target_pct":         target_n / total * 100 if total else 0,
        "non_target_count":   non_target,
        "non_target_pct":     non_target / total * 100 if total else 0,
        "sections":           rows,
    }


def _bracket_patterns(
    short: List[Dict[str, Any]],
    top_n: int,
) -> List[Dict[str, Any]]:
    """Top repeated text previews within the bracket population (boilerplate signal)."""
    by_bracket: Dict[str, List[str]] = defaultdict(list)
    all_previews: List[str] = []

    for s in short:
        preview = s["text"][:100].strip()
        all_previews.append(preview)
        by_bracket[word_bracket(s["word_count"])].append(preview)

    result = []
    for txt, cnt in Counter(all_previews).most_common(top_n):
        brackets = sorted(
            {wb for wb, ps in by_bracket.items() if txt in ps},
            key=lambda b: next(
                (i for i, (lbl, *_) in enumerate(_WORD_BRACKETS) if lbl == b), 99
            ),
        )
        result.append({"text": txt, "count": cnt, "brackets": brackets})
    return result


def _bracket_subsections(
    short: List[Dict[str, Any]],
    top_n: int,
) -> List[Dict[str, Any]]:
    """Top parent_subsections generating segments in the bracket."""
    total = len(short)
    counter: Counter = Counter(
        (s["parent_subsection"] or "(none)") for s in short
    )
    unique_by_sub: Dict[str, set] = defaultdict(set)
    for s in short:
        unique_by_sub[s["parent_subsection"] or "(none)"].add(
            s["text"][:100].strip()
        )

    return [
        {
            "parent_subsection": sub,
            "count":             cnt,
            "pct":               cnt / total * 100,
            "unique_previews":   len(unique_by_sub[sub]),
            "dup_pct":           (cnt - len(unique_by_sub[sub])) / cnt * 100,
        }
        for sub, cnt in counter.most_common(top_n)
    ]


def run_analysis(
    run_dir: Path,
    bracket_lo: int,
    bracket_hi: int,
    sample_n: int,
    seed: int,
    target_section: str = DEFAULT_TARGET_SECTION,
) -> Dict[str, Any]:
    """
    Load all segments, then run Tasks 1, 2, and 3.
    Returns a result dict.
    """
    all_segs: List[Dict[str, Any]] = []
    for seg in load_segments_full(run_dir):
        all_segs.append(seg)

    total = len(all_segs)
    if total == 0:
        return {"error": "No segments found"}

    # Task 2 — parent_subsection fill rate across ALL segments
    filled     = sum(1 for s in all_segs if s["parent_subsection"] is not None)
    none_count = total - filled
    fill_pct   = filled / total * 100

    # Task 1 — short segment bracket
    short       = [s for s in all_segs if bracket_lo <= s["word_count"] <= bracket_hi]
    short_count = len(short)
    short_pct   = short_count / total * 100

    rng    = random.Random(seed)
    sample = rng.sample(short, min(sample_n, short_count))
    sample.sort(key=lambda s: s["word_count"])

    # Task 3 — section contamination
    contamination = _section_contamination(all_segs, target_section, TOP_PATTERNS_N)

    # Bracket diagnostics — patterns and subsections within the bracket
    bracket_pats = _bracket_patterns(short, TOP_PATTERNS_N)
    bracket_subs = _bracket_subsections(short, TOP_SUBSECTIONS_N)

    return {
        "timestamp":       datetime.now().isoformat(),
        "run_directory":   str(run_dir),
        "total_segments":  total,
        "bracket":         {"lo": bracket_lo, "hi": bracket_hi},
        "short_count":     short_count,
        "short_pct":       short_pct,
        "sampled":         len(sample),
        "fill_rate": {
            "filled":  filled,
            "none":    none_count,
            "pct":     fill_pct,
            "target":  FILL_RATE_TARGET,
            "status":  "PASS" if fill_pct >= FILL_RATE_TARGET else "WARN",
        },
        "contamination":   contamination,
        "bracket_patterns": bracket_pats,
        "bracket_subsections": bracket_subs,
        "sample":          sample,
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
    sc    = result["short_count"]
    sp    = result["short_pct"]
    lo    = result["bracket"]["lo"]
    hi    = result["bracket"]["hi"]
    n     = result["sampled"]
    fr    = result["fill_rate"]
    ct    = result["contamination"]

    print(f"\n{'='*70}")
    print(f"  Short Segment Diagnostics")
    print(f"{'='*70}")
    print(f"  Run directory : {result['run_directory']}")
    print(f"  Total segments: {total:,}")
    print(f"  Timestamp     : {result['timestamp']}")

    # ------------------------------------------------------------------ Task 1
    print(f"\n--- Task 1 : Short Segment Sample ({lo}–{hi} words) ---")
    print(f"  Short segments ({lo}-{hi} words): {sc:,} / {total:,} ({sp:.2f}%)")
    print(f"  Sampled {n} for manual review → {output_path}")

    # ------------------------------------------------------------------ Task 2
    print(f"\n--- Task 2 : parent_subsection fill rate (all segments) ---")
    print(f"  Filled : {fr['filled']:>7,} / {total:,}  ({fr['pct']:.1f}%)")
    print(f"  None   : {fr['none']:>7,} / {total:,}  ({100 - fr['pct']:.1f}%)")
    gate_label = f"≥{FILL_RATE_TARGET:.0f}% target → {fr['status']}"
    if fr["status"] == "WARN":
        gate_label += f"  ({100 - fr['pct']:.1f}% missing)"
    print(f"  Gate   : {gate_label}")

    # ------------------------------------------------------------------ Task 3
    print(f"\n--- Task 3 : Section contamination (target: {ct['target_section']}) ---")
    print(
        f"  Target  : {ct['target_count']:>7,} / {total:,}  "
        f"({ct['target_pct']:.1f}%)"
    )
    print(
        f"  Non-target noise: {ct['non_target_count']:>7,} / {total:,}  "
        f"({ct['non_target_pct']:.1f}%)  ← OQ-6"
    )
    print()
    print(f"  {'Section ID':<22}  {'Segs':>8}  {'%Total':>7}  {'Dup%':>6}  {'Flag'}")
    print(f"  {'-'*22}  {'-'*8}  {'-'*7}  {'-'*6}  {'-'*18}")
    for row in ct["sections"]:
        flag = "TARGET ✓" if row["is_target"] else "NOT RISK FACTORS ✗"
        print(
            f"  {row['section_id']:<22}  {row['count']:>8,}  "
            f"{row['pct_of_total']:>6.1f}%  {row['dup_pct']:>5.1f}%  {flag}"
        )

    # Top patterns per non-target section
    non_target_rows = [r for r in ct["sections"] if not r["is_target"]]
    if non_target_rows:
        print(f"\n  Top repeated patterns in non-target sections:")
        for row in non_target_rows[:3]:   # show worst 3
            print(f"\n  [{row['section_id']}]")
            for p in row["top_patterns"][:5]:
                print(f"    {p['count']:>4}x  {p['text'][:70]!r}")

    # --------------------------------- Bracket diagnostics: patterns & subsections
    print(f"\n--- Bracket ({lo}–{hi} words) : top repeated text previews ---")
    bpats = result.get("bracket_patterns", [])
    if bpats:
        print(f"  {'Count':>6}  {'Brackets':<22}  {'Text preview'}")
        print(f"  {'-'*6}  {'-'*22}  {'-'*50}")
        for p in bpats:
            brackets_str = ",".join(p["brackets"])
            print(f"  {p['count']:>6,}  {brackets_str:<22}  {p['text'][:55]!r}")
    else:
        print("  (none)")

    print(f"\n--- Bracket ({lo}–{hi} words) : top parent_subsections ---")
    bsubs = result.get("bracket_subsections", [])
    if bsubs:
        print(f"  {'Count':>7}  {'Dup%':>5}  {'Subsection'}")
        print(f"  {'-'*7}  {'-'*5}  {'-'*48}")
        for s in bsubs:
            print(
                f"  {s['count']:>7,}  {s['dup_pct']:>4.0f}%  "
                f"{s['parent_subsection'][:48]}"
            )
    else:
        print("  (none)")

    print(f"\n{'='*70}\n")


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
    parser.add_argument(
        "--target-section",
        default=DEFAULT_TARGET_SECTION,
        metavar="ID",
        help=(
            "Section identifier considered the training target "
            f"(default: {DEFAULT_TARGET_SECTION}). "
            "All other section_ids are flagged as non-target contamination."
        ),
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
        target_section=args.target_section,
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
