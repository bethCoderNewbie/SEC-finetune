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
from src.storage.database import FilingDatabase, classify_and_store

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

        if getattr(args, "quality", False):
            _run_quality_audit(db)
    finally:
        db.close()


def _run_quality_audit(db: FilingDatabase) -> None:
    """Run data quality audit queries against the database."""
    from src.analysis.segment_annotator import ARCHETYPE_NAMES, _VALID_LABEL_SOURCES

    print()
    print("  Quality Audit:")
    print("  " + "=" * 40)

    total_issues = 0

    # Define audit checks: (label, SQL, params)
    archetype_placeholders = ", ".join("?" for _ in ARCHETYPE_NAMES)
    source_placeholders = ", ".join("?" for _ in _VALID_LABEL_SOURCES)

    checks = [
        (
            "Missing CIK",
            "SELECT COUNT(*) as cnt FROM filings WHERE cik IS NULL OR cik = ''",
            (),
        ),
        (
            "Missing Company Name",
            "SELECT COUNT(*) as cnt FROM filings WHERE company_name IS NULL OR company_name = ''",
            (),
        ),
        (
            "Zero Segments",
            "SELECT COUNT(*) as cnt FROM filings WHERE total_segments IS NULL OR total_segments = 0",
            (),
        ),
        (
            "Missing SIC Code",
            "SELECT COUNT(*) as cnt FROM filings WHERE sic_code IS NULL OR sic_code = ''",
            (),
        ),
        (
            "Empty Classification Text",
            "SELECT COUNT(*) as cnt FROM classifications WHERE text IS NULL OR text = ''",
            (),
        ),
        (
            "Invalid Risk Labels",
            f"SELECT COUNT(*) as cnt FROM classifications WHERE risk_label NOT IN ({archetype_placeholders})",
            tuple(ARCHETYPE_NAMES),
        ),
        (
            "Out-of-Range Confidence",
            "SELECT COUNT(*) as cnt FROM classifications WHERE confidence < 0 OR confidence > 1",
            (),
        ),
        (
            "Invalid Label Sources",
            f"SELECT COUNT(*) as cnt FROM classifications WHERE label_source NOT IN ({source_placeholders})",
            tuple(_VALID_LABEL_SOURCES),
        ),
    ]

    for label, sql, params in checks:
        row = db.conn.execute(sql, params).fetchone()
        count = row["cnt"]
        tag = "  OK" if count == 0 else "FAIL"
        print(f"    [{tag}] {label}: {count}")
        total_issues += count

    print("  " + "=" * 40)
    print(f"  Total issues: {total_issues}")


def cmd_backfill(args: argparse.Namespace, config: AnalysisConfig) -> None:
    """Backfill database from a preprocessing run directory."""
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"Error: directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    db = _get_db(config)
    try:
        start = time.monotonic()
        count, skipped = db.backfill_from_run_dir(run_dir)
        elapsed = time.monotonic() - start
        print(f"Backfilled {count} filing records ({skipped} skipped) from {run_dir} ({elapsed:.1f}s)")
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
        count, skipped = db.backfill_from_run_dir(run_dir)
        elapsed = time.monotonic() - start
        print(f"Backfilled {count} filing records ({skipped} skipped) ({elapsed:.1f}s)")
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

        annotator = SegmentAnnotator()

        classified = 0
        errors = 0
        start = time.monotonic()

        for filing in filings:
            try:
                classify_and_store(db, filing, annotator, cv)
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
        count, skipped = db.backfill_from_run_dir(run_dir)
        print(f"Backfilled {count} filing records ({skipped} skipped)")
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
    p_status = subparsers.add_parser("status", help="Show database statistics")
    p_status.add_argument("--quality", action="store_true", help="Run data quality audit")

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
