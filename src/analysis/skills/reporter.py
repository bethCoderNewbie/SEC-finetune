"""
format_report + export_report skills — render AnalysisResult to md/json/csv
and write to a stamped data/reports/ directory (PRD-005 §4.2, ADR-007).
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.analysis.models.analysis import AnalysisResult
from src.analysis.models.report import ReportBundle
from src.utils.metadata import RunMetadata

logger = logging.getLogger(__name__)

_VALID_FORMATS = {"md", "json", "csv"}


# ---------------------------------------------------------------------------
# Stamped run directory creation (ADR-007)
# ---------------------------------------------------------------------------


def _make_report_run_dir(report_output_dir: Path) -> Path:
    """Create a stamped analysis run directory under report_output_dir."""
    meta = RunMetadata.gather()
    git_sha = meta.get("git_commit", "unknown")[:7]
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = report_output_dir / f"{ts}_analysis_{git_sha}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def format_report(result: AnalysisResult, fmt: str = "md") -> str:
    """
    Render an AnalysisResult to a string in the requested format.

    Args:
        result: Completed AnalysisResult from the orchestrator.
        fmt:    Output format — "md" (default), "json", or "csv".

    Returns:
        Rendered string.

    Raises:
        ValueError: If fmt is not one of the supported values.
    """
    if fmt not in _VALID_FORMATS:
        raise ValueError(f"Unsupported format {fmt!r}. Choose from: {sorted(_VALID_FORMATS)}")

    if fmt == "json":
        return result.model_dump_json(indent=2)

    if fmt == "csv":
        return _format_csv(result)

    return _format_markdown(result)


def _format_markdown(result: AnalysisResult) -> str:
    ticker = result.inputs.get("ticker", "Unknown")
    fiscal_year = result.inputs.get("fiscal_year", "Unknown")
    score_line = ""
    if result.composite_risk_score:
        score_line = (
            f"\n**Composite Risk Score:** {result.composite_risk_score.score}/100"
            f"  (dominant: {result.composite_risk_score.dominant_archetype or 'n/a'})\n"
        )

    summary = result.summary
    label_dist = summary.get("risk_label_distribution", {})
    top_sasb = summary.get("top_sasb_topics", [])
    total_segs = summary.get("total_segments", 0)

    lines: list[str] = [
        f"# Risk Analysis Report — {ticker} ({fiscal_year})",
        "",
        f"*Generated {result.generated_at} · Model: {result.agent_model}*",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Total segments analysed:** {total_segs}",
        score_line,
    ]

    if label_dist:
        lines.append("### SASB Dimension Distribution\n")
        lines.append("| Dimension | Segments |")
        lines.append("|-----------|----------|")
        for label, count in sorted(label_dist.items(), key=lambda x: -x[1]):
            lines.append(f"| {label} | {count} |")
        lines.append("")

    if top_sasb:
        lines.append(f"**Top SASB Topics:** {', '.join(top_sasb)}\n")

    if result.clusters:
        lines.append("---")
        lines.append("")
        lines.append("## Risk Clusters")
        lines.append("")
        for cluster in result.clusters:
            lines.append(f"### {cluster.archetype.replace('_', ' ').title()}")
            if cluster.sasb_topic:
                lines.append(f"*SASB Topic: {cluster.sasb_topic}*")
            lines.append(f"**Segments:** {cluster.segment_count}  |  "
                         f"**Mean confidence:** {cluster.mean_confidence:.2f}")
            lines.append("")
            if cluster.narrative_summary:
                lines.append(cluster.narrative_summary)
                lines.append("")
            if cluster.representative_segments:
                lines.append("**Representative segments:**")
                for seg in cluster.representative_segments[:3]:
                    lines.append(f"> {seg[:200]}{'…' if len(seg) > 200 else ''}")
                lines.append("")

    return "\n".join(lines)


def _format_csv(result: AnalysisResult) -> str:
    """Render cluster-level tabular export as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "ticker", "fiscal_year", "archetype", "sasb_topic",
        "segment_count", "mean_confidence", "composite_score",
        "narrative_summary",
    ])
    ticker = result.inputs.get("ticker", "")
    fiscal_year = result.inputs.get("fiscal_year", "")
    score = result.composite_risk_score.score if result.composite_risk_score else ""
    for cluster in result.clusters:
        writer.writerow([
            ticker,
            fiscal_year,
            cluster.archetype,
            cluster.sasb_topic or "",
            cluster.segment_count,
            round(cluster.mean_confidence, 4),
            score,
            (cluster.narrative_summary or "").replace("\n", " "),
        ])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# export_report
# ---------------------------------------------------------------------------


def export_report(
    result: AnalysisResult,
    fmt: str = "md",
    report_output_dir: Optional[Path] = None,
    run_dir: Optional[Path] = None,
) -> ReportBundle:
    """
    Write rendered report content to a stamped run directory (ADR-007).

    Args:
        result:             AnalysisResult to render.
        fmt:                Format string — "md", "json", or "csv".
        report_output_dir:  Root for report run directories (default: data/reports/).
        run_dir:            Explicit run directory; if None, a new stamped dir is created.

    Returns:
        ReportBundle with paths to every file written.
    """
    from src.config.analysis import AnalysisConfig
    cfg = AnalysisConfig()

    if report_output_dir is None:
        report_output_dir = cfg.report_output_dir

    if run_dir is None:
        run_dir = _make_report_run_dir(report_output_dir)

    bundle = ReportBundle(run_dir=run_dir)

    def _write(content: str, suffix: str) -> Path:
        path = run_dir / f"report.{suffix}"
        path.write_text(content, encoding="utf-8")
        logger.info("Wrote %s", path)
        return path

    content = format_report(result, fmt)
    if fmt == "md":
        bundle.report_md = _write(content, "md")
    elif fmt == "json":
        bundle.report_json = _write(content, "json")
    elif fmt == "csv":
        bundle.report_csv = _write(content, "csv")

    # Always write JSON alongside other formats for machine consumption
    if fmt != "json":
        bundle.report_json = _write(format_report(result, "json"), "json")

    return bundle
