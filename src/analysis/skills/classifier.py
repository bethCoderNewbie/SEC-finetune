"""
classify_filing skill — SASB archetype + topic classification for all segments in a filing.

Wraps SegmentAnnotator.annotate() to preserve ancestor-prior context across adjacent
segments (US-034). One tool call per filing, not one per segment.

Cache strategy (ADR-017):
    1. Check SQLite database for pre-computed classifications matching the current
       classifier_version. If found, return immediately (<1ms).
    2. If cache miss, instantiate SegmentAnnotator (loads BART-MNLI), classify,
       store results in DB for future calls.

Why filing-level (not per-text):
    SegmentAnnotator._classify_segment() uses ancestor heading priors that require
    the full ordered segment list. A per-text wrapper silently drops the
    'ancestor_prior' label_source path (Layer 3 of 5 classification layers).
    See PRD-005 critique §1 for full analysis.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from src.analysis.models.analysis import ClassificationResult
from src.analysis.skills.filing_loader import SkillError, load_filing

logger = logging.getLogger(__name__)


def _try_cached_classifications(
    ticker: str,
    fiscal_year: Optional[str],
) -> Optional[List[ClassificationResult]]:
    """Check the SQLite DB for pre-computed classifications.

    Returns None on cache miss or DB unavailability.
    """
    if fiscal_year is None:
        return None

    try:
        from src.config.analysis import AnalysisConfig
        from src.storage.database import get_database, compute_classifier_version
        from src.config import settings

        config = AnalysisConfig()
        if not config.db_path.exists():
            return None

        cfg = settings.annotation
        cv = compute_classifier_version(
            model_name=cfg.model_name,
            confidence_threshold=cfg.confidence_threshold,
            gate_threshold=cfg.binary_gate_threshold,
            merge_lo=cfg.merge_lo,
            merge_hi=cfg.merge_hi,
        )

        db = get_database(config.db_path)
        if not db.has_classifications(ticker, fiscal_year, classifier_version=cv):
            return None

        rows = db.get_classifications(ticker, fiscal_year)
        if not rows:
            return None

        results = [
            ClassificationResult(
                segment_id=str(row.get("chunk_id") or row.get("segment_index", i)),
                text=row.get("text", ""),
                risk_label=row.get("risk_label", "other"),
                sasb_topic=row.get("sasb_topic"),
                sasb_industry=row.get("sasb_industry"),
                confidence=float(row.get("confidence", 0.0)),
                label_source=row.get("label_source", "heuristic"),
                word_count=int(row.get("word_count", 0)),
            )
            for i, row in enumerate(rows)
        ]
        logger.info(
            "classify_filing: DB cache hit for %s %s — %d segments",
            ticker, fiscal_year, len(results),
        )
        return results
    except Exception as exc:
        logger.debug("DB cache check failed: %s", exc)
        return None


def _store_classifications_to_db(
    ticker: str,
    fiscal_year: str,
    records: list,
) -> None:
    """Store fresh classification results into the DB (best-effort, non-blocking)."""
    try:
        from src.config.analysis import AnalysisConfig
        from src.storage.database import get_database, compute_classifier_version
        from src.config import settings

        config = AnalysisConfig()
        if not config.db_path.exists():
            return

        cfg = settings.annotation
        cv = compute_classifier_version(
            model_name=cfg.model_name,
            confidence_threshold=cfg.confidence_threshold,
            gate_threshold=cfg.binary_gate_threshold,
            merge_lo=cfg.merge_lo,
            merge_hi=cfg.merge_hi,
        )

        db = get_database(config.db_path)
        filing = db.get_filing(ticker, fiscal_year)
        if filing is None:
            return
        db.store_classifications(
            filing_id=filing["id"],
            classifications=records,
            classifier_version=cv,
            ticker=ticker,
            fiscal_year=fiscal_year,
        )
        logger.debug("Stored %d classifications in DB for %s %s", len(records), ticker, fiscal_year)
    except Exception as exc:
        logger.warning("Failed to store classifications in DB: %s", exc)


def classify_filing(
    ticker: str,
    fiscal_year: Optional[str] = None,
    run_dir: Optional[str] = None,
) -> List[ClassificationResult]:
    """
    Classify all segments in a filing by SASB archetype and topic.

    Args:
        ticker:      Company ticker symbol.
        fiscal_year: Four-digit year string. If None, the most recent filing is used.
        run_dir:     Stamped preprocessing run directory path string.
                     If None, the latest data/processed/ directory is used.

    Returns:
        List of ClassificationResult — one entry per annotated segment.

    Raises:
        SkillError: On filing-not-found or annotation failure.
    """
    # Check DB cache first (returns in <1ms on hit)
    cached = _try_cached_classifications(ticker, fiscal_year)
    if cached is not None:
        return cached

    # Cache miss — run full classification pipeline
    resolved_run_dir = Path(run_dir) if run_dir else None

    try:
        segmented = load_filing(ticker, fiscal_year, resolved_run_dir)
    except Exception as exc:
        raise SkillError("classify_filing", f"load_filing failed: {exc}") from exc

    try:
        # Lazy import: SegmentAnnotator loads a heavy NLI model on construction.
        from src.analysis.segment_annotator import SegmentAnnotator  # type: ignore
        annotator = SegmentAnnotator()
        records = annotator.annotate(segmented)
    except Exception as exc:
        raise SkillError("classify_filing", f"SegmentAnnotator.annotate failed: {exc}") from exc

    results: List[ClassificationResult] = []
    for i, rec in enumerate(records):
        results.append(
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
        )

    logger.info(
        "classify_filing: %s %s → %d segments classified",
        ticker,
        fiscal_year or "latest",
        len(results),
    )

    # Store to DB for future cache hits (best-effort)
    if fiscal_year:
        _store_classifications_to_db(ticker, fiscal_year, records)

    return results
