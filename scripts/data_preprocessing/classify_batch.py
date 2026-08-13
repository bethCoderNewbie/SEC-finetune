#!/usr/bin/env python3
"""
Batch classification script — classify all filings in the SQLite database.

Loads SegmentAnnotator ONCE (avoiding the 5–10 second model load per filing),
then classifies all unclassified filings in the database sequentially.

Usage:
    # Classify only filings not yet classified with current config
    python scripts/data_preprocessing/classify_batch.py

    # Re-classify all filings (e.g., after config change)
    python scripts/data_preprocessing/classify_batch.py --force

    # Backfill DB from latest run dir, then classify
    python scripts/data_preprocessing/classify_batch.py --backfill-latest

    # Limit to specific tickers
    python scripts/data_preprocessing/classify_batch.py --tickers AAPL MSFT GOOG
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config.analysis import AnalysisConfig
from src.storage.database import FilingDatabase, compute_classifier_version, classify_and_store

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch classify SEC filings")
    parser.add_argument("--force", action="store_true", help="Re-classify all filings")
    parser.add_argument("--backfill-latest", action="store_true",
                        help="Backfill DB from latest run dir before classifying")
    parser.add_argument("--tickers", nargs="+", help="Limit to specific tickers")
    parser.add_argument("--db-path", type=Path, help="Override database path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    config = AnalysisConfig()
    if args.db_path:
        config = AnalysisConfig(db_path=args.db_path)

    db = FilingDatabase(config.db_path)
    db.connect()

    try:
        # Optional: backfill first
        if args.backfill_latest:
            processed_root = config.processed_dir
            candidates = sorted(
                [d for d in processed_root.iterdir()
                 if d.is_dir() and "_preprocessing_" in d.name],
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            if not candidates:
                print(f"Error: no run directories under {processed_root}", file=sys.stderr)
                sys.exit(1)
            run_dir = candidates[0]
            print(f"Backfilling from {run_dir.name} ...")
            count, skipped = db.backfill_from_run_dir(run_dir)
            print(f"  Imported {count} filing records ({skipped} skipped)")

        # Compute current classifier version
        from src.config import settings
        cfg = settings.annotation
        cv = compute_classifier_version(
            model_name=cfg.model_name,
            confidence_threshold=cfg.confidence_threshold,
            gate_threshold=cfg.binary_gate_threshold,
            merge_lo=cfg.merge_lo,
            merge_hi=cfg.merge_hi,
        )
        print(f"Classifier version: {cv}")

        # Get filings to classify
        if args.force:
            filings = db.list_filings()
        else:
            filings = db.get_unclassified_filings(classifier_version=cv)

        # Filter by tickers if specified
        if args.tickers:
            ticker_set = {t.upper() for t in args.tickers}
            filings = [f for f in filings if f["ticker"] in ticker_set]

        if not filings:
            print("No filings need classification.")
            return

        print(f"Filings to classify: {len(filings)}")
        print("Loading SegmentAnnotator (BART-MNLI model) ...")

        # Load annotator ONCE
        from src.analysis.segment_annotator import SegmentAnnotator

        load_start = time.monotonic()
        annotator = SegmentAnnotator()
        load_time = time.monotonic() - load_start
        print(f"Model loaded in {load_time:.1f}s")

        classified = 0
        errors = 0
        total_segments = 0
        start = time.monotonic()

        for filing in filings:
            try:
                seg_count = classify_and_store(db, filing, annotator, cv)
                total_segments += seg_count
                classified += 1
                if classified % 25 == 0:
                    elapsed = time.monotonic() - start
                    rate = classified / elapsed if elapsed > 0 else 0
                    print(
                        f"  [{classified}/{len(filings)}] "
                        f"{filing['ticker']} {filing['fiscal_year']} — "
                        f"{seg_count} segments ({rate:.1f} filings/s)"
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to classify filing %d (%s %s): %s",
                    filing["id"], filing["ticker"], filing["fiscal_year"], exc,
                )
                errors += 1

        elapsed = time.monotonic() - start
        print(f"\nDone:")
        print(f"  Classified: {classified}/{len(filings)} filings")
        print(f"  Segments:   {total_segments}")
        print(f"  Errors:     {errors}")
        print(f"  Time:       {elapsed:.1f}s ({classified / elapsed:.1f} filings/s)" if elapsed > 0 else "")

    finally:
        db.close()


if __name__ == "__main__":
    main()
