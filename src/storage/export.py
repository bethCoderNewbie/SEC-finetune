"""
Export utilities for SEC filing data.

Provides:
  - export_corpus_jsonl: Flatten all segments from a run directory into a single JSONL file.
  - diff_runs: Compare aggregate statistics between two preprocessing runs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def export_corpus_jsonl(
    run_dir: Path,
    output_path: Optional[Path] = None,
) -> Path:
    """Export all segments from a run directory to a single JSONL file.

    Each line is a flat JSON object with fields:
        ticker, fiscal_year, form_type, section_id, cik, sic_code,
        chunk_id, segment_hash, parent_subsection, ancestors, text,
        word_count, char_count

    Args:
        run_dir: Path to a stamped preprocessing run directory.
        output_path: Where to write the JSONL file.  Defaults to
            ``run_dir / "corpus.jsonl"``.

    Returns:
        Path to the written JSONL file.
    """
    from src.preprocessing.models.segmentation import SegmentedRisks

    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    if output_path is None:
        output_path = run_dir / "corpus.jsonl"
    output_path = Path(output_path)

    segment_count = 0
    file_count = 0

    with open(output_path, "w", encoding="utf-8") as out:
        for json_path in sorted(run_dir.rglob("*_segmented.json")):
            try:
                sr = SegmentedRisks.load_from_json(json_path)
            except Exception as exc:
                logger.warning("Skipping %s: %s", json_path.name, exc)
                continue

            file_count += 1
            for seg in sr.segments:
                record = {
                    "ticker": sr.ticker,
                    "fiscal_year": sr.fiscal_year,
                    "form_type": sr.form_type,
                    "section_id": sr.section_identifier,
                    "cik": sr.cik,
                    "sic_code": sr.sic_code,
                    "chunk_id": seg.chunk_id,
                    "segment_hash": seg.segment_hash,
                    "parent_subsection": seg.parent_subsection,
                    "ancestors": seg.ancestors,
                    "text": seg.text,
                    "word_count": seg.word_count,
                    "char_count": seg.char_count,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                segment_count += 1

    logger.info(
        "Exported %d segments from %d files to %s",
        segment_count, file_count, output_path,
    )
    return output_path


def _collect_run_stats(run_dir: Path) -> Dict[str, Any]:
    """Collect aggregate statistics from a run directory.

    Returns a dict with keys: filing_count, segment_count, tickers,
    avg_coverage_ratio, segment_counts (list), coverage_ratios (list).
    """
    run_dir = Path(run_dir)
    tickers: Set[str] = set()
    segment_counts: List[int] = []
    coverage_ratios: List[float] = []
    filing_count = 0

    for json_path in sorted(run_dir.rglob("*_segmented.json")):
        try:
            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue

        filing_count += 1

        # Extract metadata
        if "document_info" in data:
            di = data["document_info"]
            sm = data.get("section_metadata", {})
            stats = sm.get("stats", {})
            chunks = data.get("segments") or data.get("chunks", [])
        else:
            di = data
            stats = {}
            chunks = data.get("segments", [])

        ticker = di.get("ticker")
        if ticker:
            tickers.add(ticker)

        n_segments = stats.get("total_chunks") or len(chunks)
        segment_counts.append(n_segments)

        # Coverage ratio
        text_coverage = stats.get("text_coverage")
        if isinstance(text_coverage, dict) and "coverage_ratio" in text_coverage:
            coverage_ratios.append(text_coverage["coverage_ratio"])

    total_segments = sum(segment_counts)
    avg_coverage = (
        sum(coverage_ratios) / len(coverage_ratios) if coverage_ratios else None
    )

    return {
        "filing_count": filing_count,
        "segment_count": total_segments,
        "tickers": sorted(tickers),
        "avg_coverage_ratio": avg_coverage,
        "segment_counts": segment_counts,
        "coverage_ratios": coverage_ratios,
    }


def diff_runs(run_dir_a: Path, run_dir_b: Path) -> Dict[str, Any]:
    """Compare aggregate statistics between two run directories.

    Args:
        run_dir_a: Path to the baseline (older) run directory.
        run_dir_b: Path to the comparison (newer) run directory.

    Returns:
        Dict with keys: filing_count_delta, segment_count_delta,
        avg_coverage_delta, new_tickers, removed_tickers,
        run_a, run_b (the raw stats for each run).
    """
    run_dir_a = Path(run_dir_a)
    run_dir_b = Path(run_dir_b)

    if not run_dir_a.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir_a}")
    if not run_dir_b.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir_b}")

    stats_a = _collect_run_stats(run_dir_a)
    stats_b = _collect_run_stats(run_dir_b)

    tickers_a = set(stats_a["tickers"])
    tickers_b = set(stats_b["tickers"])

    avg_a = stats_a["avg_coverage_ratio"]
    avg_b = stats_b["avg_coverage_ratio"]
    avg_delta = None
    if avg_a is not None and avg_b is not None:
        avg_delta = round(avg_b - avg_a, 4)

    return {
        "filing_count_delta": stats_b["filing_count"] - stats_a["filing_count"],
        "segment_count_delta": stats_b["segment_count"] - stats_a["segment_count"],
        "avg_coverage_delta": avg_delta,
        "new_tickers": sorted(tickers_b - tickers_a),
        "removed_tickers": sorted(tickers_a - tickers_b),
        "run_a": {
            "path": str(run_dir_a),
            "filing_count": stats_a["filing_count"],
            "segment_count": stats_a["segment_count"],
            "ticker_count": len(tickers_a),
            "avg_coverage_ratio": avg_a,
        },
        "run_b": {
            "path": str(run_dir_b),
            "filing_count": stats_b["filing_count"],
            "segment_count": stats_b["segment_count"],
            "ticker_count": len(tickers_b),
            "avg_coverage_ratio": avg_b,
        },
    }
