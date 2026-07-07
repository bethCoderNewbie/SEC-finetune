"""
classify_filing skill — SASB archetype + topic classification for all segments in a filing.

Wraps SegmentAnnotator.annotate() to preserve ancestor-prior context across adjacent
segments (US-034). One tool call per filing, not one per segment.

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
    return results
