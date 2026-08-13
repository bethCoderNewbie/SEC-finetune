"""
Storage admin CLI — database management commands.

Usage:
    python -m src.storage.cli status
    python -m src.storage.cli backfill <run_dir>
    python -m src.storage.cli backfill-latest
    python -m src.storage.cli classify-all [--force]
    python -m src.storage.cli refresh <run_dir>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from src.config.analysis import AnalysisConfig
from src.storage.database import FilingDatabase

logger = logging.getLogger(__name__)


def _get_db(config: AnalysisConfig) -> FilingDatabase:
    db = FilingDatabase(config.db_path)
    db.connect()
    return db


def cmd_status(args: argparse.Namespace, config: AnalysisConfig) -> None:
    """Print database statistics."""
    db = _get_db(config)
    try:
        stats = db.get_statistics()
        print(f"Database: {config.db_path}")
        print(f"  Total filing records:   {stats['total_filings']}")
        print(f"  Unique tickers:         {stats['unique_tickers']}")
        print(f"  Classified filings:     {stats['classified_filings']}")
        print(f"  Unclassified filings:   {stats['unclassified_filings']}")
        print(f"  Total classifications:  {stats['total_classifications']}")
        print(f"  Total risk scores:      {stats['total_risk_scores']}")
        if stats.get("by_form_type"):
            print("  By form type:")
            for ft, cnt in stats["by_form_type"].items():
                print(f"    {ft}: {cnt}")
        if stats.get("fiscal_year_range"):
            yr_min, yr_max = stats["fiscal_year_range"]
            print(f"  Fiscal year range:      {yr_min} - {yr_max}")
    finally:
        db.close()


def cmd_backfill(args: argparse.Namespace, config: AnalysisConfig) -> None:
    """Backfill database from a preprocessing run directory."""
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"Error: directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    db = _get_db(config)
    try:
        start = time.monotonic()
        count = db.backfill_from_run_dir(run_dir)
        elapsed = time.monotonic() - start
        print(f"Backfilled {count} filing records from {run_dir} ({elapsed:.1f}s)")
    finally:
        db.close()


def cmd_backfill_latest(args: argparse.Namespace, config: AnalysisConfig) -> None:
    """Backfill from the most recent preprocessing run directory."""
    processed_root = config.processed_dir
    if not processed_root.is_dir():
        print(f"Error: processed directory not found: {processed_root}", file=sys.stderr)
        sys.exit(1)

    candidates = sorted(
        [d for d in processed_root.iterdir() if d.is_dir() and "_preprocessing_" in d.name],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        print(f"Error: no stamped run directories found under {processed_root}", file=sys.stderr)
        sys.exit(1)

    run_dir = candidates[0]
    print(f"Using latest run directory: {run_dir.name}")

    db = _get_db(config)
    try:
        start = time.monotonic()
        count = db.backfill_from_run_dir(run_dir)
        elapsed = time.monotonic() - start
        print(f"Backfilled {count} filing records ({elapsed:.1f}s)")
    finally:
        db.close()


def cmd_classify_all(args: argparse.Namespace, config: AnalysisConfig) -> None:
    """Classify all unclassified filings in the database.

    Loads SegmentAnnotator once and processes filings in batch.
    Use --force to re-classify all filings regardless of version.
    """
    from src.storage.database import compute_classifier_version
    from src.config import settings

    db = _get_db(config)
    try:
        cfg = settings.annotation
        cv = compute_classifier_version(
            model_name=cfg.model_name,
            confidence_threshold=cfg.confidence_threshold,
            gate_threshold=cfg.binary_gate_threshold,
            merge_lo=cfg.merge_lo,
            merge_hi=cfg.merge_hi,
        )

        if args.force:
            filings = db.list_filings()
        else:
            filings = db.get_unclassified_filings(classifier_version=cv)

        if not filings:
            print("All filings are up to date (no classification needed).")
            return

        print(f"Classifier version: {cv}")
        print(f"Filings to classify: {len(filings)}")

        # Load annotator once (heavy — loads BART NLI model)
        from src.analysis.segment_annotator import SegmentAnnotator
        from src.preprocessing.models.segmentation import SegmentedRisks
        from src.analysis.skills.scorer import score_risk
        from src.analysis.models.analysis import ClassificationResult

        annotator = SegmentAnnotator()

        classified = 0
        errors = 0
        start = time.monotonic()

        for filing in filings:
            json_path = filing.get("segmented_json_path")
            if not json_path or not Path(json_path).exists():
                logger.warning("Skipping filing %d: missing JSON at %s", filing["id"], json_path)
                errors += 1
                continue

            try:
                segmented = SegmentedRisks.load_from_json(json_path)
                records = annotator.annotate(segmented)

                db.store_classifications(
                    filing_id=filing["id"],
                    classifications=records,
                    classifier_version=cv,
                    ticker=filing["ticker"],
                    fiscal_year=filing["fiscal_year"],
                )

                # Convert records to ClassificationResult for scoring
                cls_results = [
                    ClassificationResult(
                        segment_id=str(rec.get("index", i)),
                        text=rec.get("text", ""),
                        risk_label=rec.get("risk_label", "other"),
                        sasb_topic=rec.get("sasb_topic"),
                        sasb_industry=rec.get("sasb_industry"),
                        confidence=float(rec.get("confidence", 0.0)),
                        label_source=rec.get("label_source", "heuristic"),
                        word_count=int(rec.get("word_count", 0)),
                    )
                    for i, rec in enumerate(records)
                ]

                if cls_results:
                    risk = score_risk(cls_results)
                    db.store_risk_score(
                        filing_id=filing["id"],
                        ticker=filing["ticker"],
                        fiscal_year=filing["fiscal_year"],
                        form_type=filing["form_type"],
                        score=risk.score,
                        dominant_archetype=risk.dominant_archetype,
                        label_distribution=risk.label_distribution,
                    )

                classified += 1
                if classified % 50 == 0:
                    elapsed = time.monotonic() - start
                    rate = classified / elapsed if elapsed > 0 else 0
                    print(f"  ... classified {classified}/{len(filings)} ({rate:.1f}/s)")

            except Exception as exc:
                logger.warning("Failed to classify filing %d (%s): %s",
                               filing["id"], filing.get("ticker"), exc)
                errors += 1

        elapsed = time.monotonic() - start
        print(f"Done: {classified} classified, {errors} errors ({elapsed:.1f}s)")
    finally:
        db.close()


def cmd_refresh(args: argparse.Namespace, config: AnalysisConfig) -> None:
    """Full refresh: backfill from run_dir then classify all."""
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"Error: directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    db = _get_db(config)
    try:
        start = time.monotonic()
        count = db.backfill_from_run_dir(run_dir)
        print(f"Backfilled {count} filing records")
    finally:
        db.close()

    # Now classify — reuse cmd_classify_all
    args.force = False
    cmd_classify_all(args, config)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.storage.cli",
        description="SEC Filing Database Admin CLI",
    )
    parser.add_argument(
        "--db-path", type=Path, default=None,
        help="Override database path (default: from AnalysisConfig)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    subparsers.add_parser("status", help="Show database statistics")

    # backfill <run_dir>
    p_backfill = subparsers.add_parser("backfill", help="Import JSON files from a run directory")
    p_backfill.add_argument("run_dir", type=str, help="Preprocessing run directory path")

    # backfill-latest
    subparsers.add_parser("backfill-latest", help="Import from the most recent run directory")

    # classify-all
    p_classify = subparsers.add_parser("classify-all", help="Classify unclassified filings")
    p_classify.add_argument("--force", action="store_true", help="Re-classify all filings")

    # refresh <run_dir>
    p_refresh = subparsers.add_parser("refresh", help="Backfill + classify all")
    p_refresh.add_argument("run_dir", type=str, help="Preprocessing run directory path")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    config = AnalysisConfig()
    if args.db_path:
        config = AnalysisConfig(db_path=args.db_path)

    dispatch = {
        "status": cmd_status,
        "backfill": cmd_backfill,
        "backfill-latest": cmd_backfill_latest,
        "classify-all": cmd_classify_all,
        "refresh": cmd_refresh,
    }
    dispatch[args.command](args, config)


if __name__ == "__main__":
    main()
