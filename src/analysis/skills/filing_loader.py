"""
load_filing skill — locate and deserialize a SegmentedRisks JSON for a given ticker+year.

Filing lookup strategy (ADR-017):
1. Try SQLite database lookup (O(1) via index) — returns in <1ms.
2. If DB unavailable or miss, fall back to glob scan (original O(n) path).
3. Merge segments from all matching sections into one SegmentedRisks.
4. If run_dir is not supplied, use the most-recently-modified stamped directory
   under data/processed/ (ADR-007).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from src.preprocessing.models.segmentation import RiskSegment, SegmentedRisks

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SkillError(Exception):
    """Base exception for all skill failures."""

    def __init__(self, skill_name: str, reason: str) -> None:
        self.skill_name = skill_name
        self.reason = reason
        super().__init__(f"[{skill_name}] {reason}")


class SkillTimeoutError(SkillError):
    """Raised when a skill invocation exceeds AnalysisConfig.skill_timeout_seconds."""


class FilingNotFoundError(SkillError):
    """Raised when no preprocessed filing matches the requested ticker + fiscal_year."""

    def __init__(self, ticker: str, fiscal_year: Optional[str], run_dir: Path) -> None:
        super().__init__(
            "load_filing",
            f"No segmented JSON found for ticker={ticker!r} fiscal_year={fiscal_year!r} "
            f"in run_dir={run_dir}",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _latest_processed_dir(processed_root: Path) -> Path:
    """Return the most recently modified stamped preprocessing run directory."""
    candidates = sorted(
        [d for d in processed_root.iterdir() if d.is_dir() and "_preprocessing_" in d.name],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise SkillError(
            "load_filing",
            f"No stamped preprocessing run directories found under {processed_root}",
        )
    return candidates[0]


def _peek_document_info(path: Path) -> dict:
    """Return document_info dict from a segmented JSON without full parsing."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if "document_info" in data:
        return data["document_info"]
    # Old flat schema — top-level keys are document fields
    return data


def _find_segmented_files(
    run_dir: Path, ticker: str, fiscal_year: Optional[str]
) -> List[Path]:
    """Glob run_dir for *_segmented.json files matching ticker (and optional fiscal_year)."""
    matched: List[Path] = []
    for candidate in sorted(run_dir.rglob("*_segmented.json")):
        try:
            di = _peek_document_info(candidate)
        except Exception as exc:
            logger.debug("Skipping %s: %s", candidate, exc)
            continue
        if (di.get("ticker") or "").upper() != ticker.upper():
            continue
        if fiscal_year and di.get("fiscal_year") != fiscal_year:
            continue
        matched.append(candidate)
    return matched


def _find_segmented_files_via_db(
    ticker: str, fiscal_year: Optional[str]
) -> Optional[List[Path]]:
    """Try to find segmented JSON paths from the SQLite database.

    Returns None if DB is unavailable or contains no results (caller falls back to glob).
    Returns a list of Paths if DB has matching records.
    """
    try:
        from src.config.analysis import AnalysisConfig
        from src.storage.database import FilingDatabase

        config = AnalysisConfig()
        if not config.db_path.exists():
            return None

        db = FilingDatabase(config.db_path)
        with db:
            paths = db.get_segmented_json_paths(ticker, fiscal_year)
            if not paths:
                return None
            # Verify paths still exist on disk
            valid = [Path(p) for p in paths if Path(p).exists()]
            return valid if valid else None
    except Exception as exc:
        logger.debug("DB lookup failed, falling back to glob: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public skill
# ---------------------------------------------------------------------------


def load_filing(
    ticker: str,
    fiscal_year: Optional[str] = None,
    run_dir: Optional[Path] = None,
) -> SegmentedRisks:
    """
    Locate and deserialize the SegmentedRisks for ticker + fiscal_year.

    Args:
        ticker:      Company ticker symbol (case-insensitive).
        fiscal_year: Four-digit year string, e.g. "2024". If None, the most
                     recent filing for the ticker in run_dir is returned.
        run_dir:     Stamped preprocessing run directory. If None, the latest
                     directory under data/processed/ is used (ADR-007).

    Returns:
        SegmentedRisks with all matched sections' segments merged.

    Raises:
        FilingNotFoundError: When no matching file is found.
        SkillError: On unexpected I/O errors.
    """
    # Strategy 1: DB lookup (O(1) index scan — <1ms)
    if run_dir is None and fiscal_year is not None:
        db_paths = _find_segmented_files_via_db(ticker, fiscal_year)
        if db_paths:
            logger.info(
                "load_filing: DB hit — %d section file(s) for %s %s",
                len(db_paths), ticker, fiscal_year,
            )
            return _load_and_merge(db_paths)

    # Strategy 2: glob fallback (original O(n) scan)
    if run_dir is None:
        from src.config import settings as _settings
        run_dir = _latest_processed_dir(_settings.paths.processed_data_dir)

    matched = _find_segmented_files(run_dir, ticker, fiscal_year)
    if not matched:
        raise FilingNotFoundError(ticker, fiscal_year, run_dir)

    logger.info(
        "load_filing: glob found %d section file(s) for %s %s in %s",
        len(matched),
        ticker,
        fiscal_year or "latest",
        run_dir,
    )

    return _load_and_merge(matched)


def _load_and_merge(paths: List[Path]) -> SegmentedRisks:
    """Load and merge all section SegmentedRisks files into one."""
    primary = SegmentedRisks.load_from_json(paths[0])
    if len(paths) == 1:
        return primary

    all_segments: List[RiskSegment] = list(primary.segments)
    for extra_file in paths[1:]:
        extra = SegmentedRisks.load_from_json(extra_file)
        all_segments.extend(extra.segments)

    primary.segments = all_segments
    primary.total_segments = len(all_segments)
    return primary
