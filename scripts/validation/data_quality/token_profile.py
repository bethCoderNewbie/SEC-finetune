#!/usr/bin/env python
"""
Token-profile a preprocessing batch with DebertaV2TokenizerFast — Phase A Task 3.

Tokenizes every segment text (with add_special_tokens=True so counts include
[CLS] and [SEP] and match DeBERTa's actual inference token budget) and reports:
  - Descriptive statistics: p50 / p95 / p99 / max
  - Danger zone count  (segments where token length ∈ [danger-lo, danger-hi])
  - Over-512 count     (silent truncation territory)
  - Full histogram across seven fixed buckets

First run will download the tokenizer files from Hugging Face (~400 MB).
Use --max-files N for a quick subset smoke-test (e.g. --max-files 20).

Usage:
    # Full corpus run (~30–60 min for 607K segments)
    python scripts/validation/data_quality/token_profile.py \\
        --run-dir  data/processed/20260223_182806_preprocessing_3ef72af \\
        --output   reports/token_profile.json

    # Quick smoke-test (first 20 files)
    python scripts/validation/data_quality/token_profile.py \\
        --run-dir  data/processed/20260223_182806_preprocessing_3ef72af \\
        --max-files 20 \\
        --output   reports/token_profile_test.json

    # Custom model and danger zone
    python scripts/validation/data_quality/token_profile.py \\
        --run-dir  data/processed/... \\
        --model    microsoft/deberta-v3-base \\
        --danger-lo 360 --danger-hi 512

Exit Codes:
    0 - Completed successfully
    1 - No JSON files found, tokenizer load failure, or other fatal error
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Histogram bucket definitions
# ---------------------------------------------------------------------------

# (label, lo_inclusive, hi_inclusive)  None = open-ended
BUCKETS: List[Tuple[str, Optional[int], Optional[int]]] = [
    ("≤100",     None, 100),
    ("101-200",  101,  200),
    ("201-300",  201,  300),
    ("301-380",  301,  380),
    ("381-480",  381,  480),
    ("481-512",  481,  512),
    (">512",     513,  None),
]


# ---------------------------------------------------------------------------
# Data loading  (mirrors check_word_count_distribution.py:load_batch pattern)
# ---------------------------------------------------------------------------

def iter_texts(run_dir: Path, max_files: Optional[int] = None):
    """
    Yield (file_index, total_in_file, [text, ...]) tuples from all *.json
    files in run_dir.  Skips checkpoint / manifest files (names starting with '_').
    Handles both v2 schema ('chunks' key) and old flat schema ('segments' key).
    """
    paths = sorted(p for p in run_dir.glob("*.json") if not p.name.startswith("_"))
    if max_files is not None:
        paths = paths[:max_files]

    for idx, path in enumerate(paths):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        if "chunks" in data:
            texts = [c.get("text", "") for c in data["chunks"]]
        else:
            texts = [s.get("text", "") for s in data.get("segments", [])]

        yield idx, len(paths), texts


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

def _chunks(lst: List[str], n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def tokenize_corpus(
    run_dir: Path,
    model_name: str,
    batch_size: int,
    max_files: Optional[int],
) -> List[int]:
    """
    Load tokenizer, iterate all files, return sorted list of per-segment token lengths.
    """
    try:
        from transformers import DebertaV2TokenizerFast  # type: ignore
    except ImportError as exc:
        print(
            "Error: 'transformers' package not found. "
            "Install with:  pip install 'transformers>=4.35.0'",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    print(f"Loading tokenizer: {model_name}")
    try:
        tokenizer = DebertaV2TokenizerFast.from_pretrained(model_name)
    except Exception as exc:
        print(
            f"Error: failed to load tokenizer '{model_name}': {exc}\n"
            "Check network connectivity or set TRANSFORMERS_OFFLINE=1 "
            "if you have a cached version.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    token_lengths: List[int] = []
    progress_every = 50

    for file_idx, total_files, texts in iter_texts(run_dir, max_files):
        if not texts:
            continue
        for batch in _chunks(texts, batch_size):
            enc = tokenizer(
                batch,
                add_special_tokens=True,   # include [CLS] + [SEP]
                truncation=False,           # count actual length, no cap
            )
            token_lengths.extend(len(ids) for ids in enc["input_ids"])

        if (file_idx + 1) % progress_every == 0 or (file_idx + 1) == total_files:
            print(
                f"  [{file_idx + 1:>5}/{total_files}]  "
                f"segments so far: {len(token_lengths):,}",
                flush=True,
            )

    return token_lengths


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_percentile(sorted_data: List[int], p: float) -> int:
    """Return the p-th percentile (0–100) of a pre-sorted list."""
    if not sorted_data:
        return 0
    idx = int(len(sorted_data) * p / 100)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def analyse(
    token_lengths: List[int],
    model_name: str,
    run_dir: Path,
    danger_lo: int,
    danger_hi: int,
) -> Dict[str, Any]:
    """Compute all statistics and return the JSON-serialisable result dict."""
    token_lengths.sort()
    n = len(token_lengths)

    p50 = compute_percentile(token_lengths, 50)
    p95 = compute_percentile(token_lengths, 95)
    p99 = compute_percentile(token_lengths, 99)

    danger_count = sum(1 for t in token_lengths if danger_lo <= t <= danger_hi)
    over_512 = sum(1 for t in token_lengths if t > 512)

    # Histogram buckets
    buckets = []
    for label, lo, hi in BUCKETS:
        count = sum(
            1 for t in token_lengths
            if (lo is None or t >= lo) and (hi is None or t <= hi)
        )
        buckets.append({
            "bucket": label,
            "count": count,
            "pct": count / n * 100 if n else 0.0,
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "run_directory": str(run_dir),
        "model": model_name,
        "stats": {
            "total_segments": n,
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "max": token_lengths[-1] if token_lengths else 0,
            "min": token_lengths[0] if token_lengths else 0,
        },
        "buckets": buckets,
        "danger_zone": {
            "lo": danger_lo,
            "hi": danger_hi,
            "count": danger_count,
            "pct": danger_count / n * 100 if n else 0.0,
        },
        "over_512": {
            "count": over_512,
            "pct": over_512 / n * 100 if n else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def _pct_bar(pct: float, width: int = 30) -> str:
    filled = round(pct / 100 * width)
    return "[" + "#" * filled + " " * (width - filled) + "]"


def print_report(result: Dict[str, Any]) -> None:
    s = result["stats"]
    dz = result["danger_zone"]
    ov = result["over_512"]
    n = s["total_segments"]

    print(f"\n{'='*62}")
    print(f"  Token Profile — {result['model']}")
    print(f"{'='*62}")
    print(f"  Run directory   : {result['run_directory']}")
    print(f"  Segments tokenized: {n:,}")
    print(f"  Timestamp       : {result['timestamp']}")

    print(f"\n--- Descriptive Statistics ---")
    print(f"  p50 : {s['p50']:>7,} tokens")
    print(f"  p95 : {s['p95']:>7,} tokens")
    print(f"  p99 : {s['p99']:>7,} tokens")
    print(f"  Max : {s['max']:>7,} tokens")
    print(f"  Min : {s['min']:>7,} tokens")

    print(f"\n--- Danger Zone ({dz['lo']}–{dz['hi']} tokens) ---")
    print(f"  Count : {dz['count']:,}  ({dz['pct']:.2f}%)")

    print(f"\n--- Over-512 (silent truncation) ---")
    print(f"  Count : {ov['count']:,}  ({ov['pct']:.2f}%)")

    print(f"\n--- Token Distribution ---")
    print(f"  {'Bucket':<12}  {'Count':>8}  {'%':>6}  {'Bar'}")
    print(f"  {'-'*12}  {'-'*8}  {'-'*6}  {'-'*30}")
    for b in result["buckets"]:
        print(
            f"  {b['bucket']:<12}  {b['count']:>8,}  "
            f"{b['pct']:>5.1f}%  {_pct_bar(b['pct'])}"
        )

    # p95 success criterion (research doc §9.3)
    p95_status = "PASS" if s["p95"] <= 400 else "WARN"
    print(f"\n  p95 ≤ 400 tokens (§9.3 gate): {p95_status}  (p95 = {s['p95']})")
    print(f"\n{'='*62}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Token-profile a preprocessing batch with DebertaV2TokenizerFast",
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
        help="Write JSON report to this path (e.g. reports/token_profile.json)",
    )
    parser.add_argument(
        "--model",
        default="microsoft/deberta-v3-base",
        help="HuggingFace model ID to load tokenizer from (default: microsoft/deberta-v3-base)",
    )
    parser.add_argument(
        "--danger-lo",
        type=int,
        default=360,
        metavar="N",
        help="Lower bound of danger zone, inclusive (default: 360)",
    )
    parser.add_argument(
        "--danger-hi",
        type=int,
        default=512,
        metavar="N",
        help="Upper bound of danger zone, inclusive (default: 512)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N files (useful for quick smoke-tests)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="Tokenizer batch size per call (default: 256)",
    )

    args = parser.parse_args()

    if not args.run_dir.exists():
        print(f"Error: directory not found: {args.run_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.run_dir.is_dir():
        print(f"Error: not a directory: {args.run_dir}", file=sys.stderr)
        sys.exit(1)

    # Check at least one file exists before starting tokenizer download
    json_files = [
        p for p in args.run_dir.glob("*.json")
        if not p.name.startswith("_")
    ]
    if not json_files:
        print(
            f"Error: no *.json files found in {args.run_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Token Profile — Phase A Task 3")
    print(f"Run dir  : {args.run_dir}")
    print(f"Files    : {len(json_files):,}" +
          (f"  (capped at {args.max_files})" if args.max_files else ""))
    print(f"Model    : {args.model}")

    token_lengths = tokenize_corpus(
        run_dir=args.run_dir,
        model_name=args.model,
        batch_size=args.batch_size,
        max_files=args.max_files,
    )

    if not token_lengths:
        print("Error: no segments found after loading all files.", file=sys.stderr)
        sys.exit(1)

    result = analyse(
        token_lengths=token_lengths,
        model_name=args.model,
        run_dir=args.run_dir,
        danger_lo=args.danger_lo,
        danger_hi=args.danger_hi,
    )

    print_report(result)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(f"JSON report saved to: {args.output}")

    sys.exit(0)


if __name__ == "__main__":
    main()
