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


# ---------------------------------------------------------------------------
# Tier helpers
# ---------------------------------------------------------------------------

_SCORE_TIERS = [
    (76, 100, "🔴", "Critical"),
    (51, 75,  "🟠", "High"),
    (26, 50,  "🟡", "Moderate"),
    (1,  25,  "🟢", "Low"),
]

_CLUSTER_TIER_EMOJI = {"High": "🔴", "Moderate": "🟡", "Low": "🟢"}


def _score_tier_badge(score: int) -> tuple:
    """Return (emoji, label) for a composite score 1–100."""
    for lo, hi, emoji, label in _SCORE_TIERS:
        if lo <= score <= hi:
            return emoji, label
    return "⚪", "Unknown"


def _cluster_tier_badge(risk_tier: Optional[str]) -> str:
    """Return 'EMOJI Label' for a cluster risk_tier string."""
    if not risk_tier:
        return "—"
    return f"{_CLUSTER_TIER_EMOJI.get(risk_tier, '⚪')} {risk_tier}"


def _format_filing_date(raw: Optional[str]) -> str:
    """Format YYYYMMDD → YYYY-MM-DD, or return raw value unchanged."""
    if raw and len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw or ""


def _format_markdown(result: AnalysisResult) -> str:  # noqa: C901
    ticker = result.inputs.get("ticker", "Unknown")
    fiscal_year = result.inputs.get("fiscal_year", "Unknown")
    run_dir_str = result.inputs.get("run_dir", "")

    score_obj = result.composite_risk_score
    score_val = score_obj.score if score_obj else 0
    dominant_arch = (score_obj.dominant_archetype or "n/a") if score_obj else "n/a"
    score_emoji, score_tier_label = _score_tier_badge(score_val) if score_obj else ("⚪", "Unknown")

    total_segs = result.summary.get("total_segments", 0)
    top_sasb = result.summary.get("top_sasb_topics", [])

    non_other = [c for c in result.clusters if c.archetype != "other"]
    other_clusters = [c for c in result.clusters if c.archetype == "other"]

    # Confidence stats across scored clusters
    if non_other:
        all_confs = [c.mean_confidence for c in non_other]
        min_conf = min(all_confs)
        max_conf = max(all_confs)
        weighted_sum = sum(c.mean_confidence * c.segment_count for c in non_other)
        mean_conf_overall = weighted_sum / max(sum(c.segment_count for c in non_other), 1)
    else:
        min_conf = max_conf = mean_conf_overall = 0.0

    other_pct = other_clusters[0].pct_of_filing if other_clusters else 0.0
    non_other_segs = sum(c.segment_count for c in non_other)
    pct_classified = round(non_other_segs / total_segs * 100, 1) if total_segs else 0.0

    lines: list[str] = []

    # ---------------------------------------------------------------
    # Section 1 — Report Header
    # ---------------------------------------------------------------
    lines.append(f"# Risk Analysis Report — {ticker}")
    lines.append("")

    subtitle_parts = []
    if result.company_name_full:
        subtitle_parts.append(result.company_name_full)
    subtitle_parts.append(f"Fiscal Year {fiscal_year}")
    if result.filing_date:
        subtitle_parts.append(f"Filed: {_format_filing_date(result.filing_date)}")
    lines.append(f"**{' | '.join(subtitle_parts)}**")

    meta_parts = []
    if result.sic_code:
        meta_parts.append(f"SIC {result.sic_code}")
    meta_parts.append(f"Analysis {result.generated_at}")
    meta_parts.append(f"Model: {result.agent_model}")
    lines.append(f"*{' · '.join(meta_parts)}*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---------------------------------------------------------------
    # Section 2 — Executive Summary
    # ---------------------------------------------------------------
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(
        f"**{total_segs} segments classified** across **{len(non_other)} SASB dimensions**."
    )
    if score_obj:
        lines.append(f"Composite risk score: **{score_val}/100 ({score_tier_label})**.")
    lines.append("")

    top_findings = [
        c for c in sorted(result.clusters, key=lambda c: -c.segment_count)
        if c.archetype != "other" and c.pct_of_filing >= 5.0
    ]
    if top_findings:
        lines.append("**Key findings:**")
        for c in top_findings[:5]:
            arch_title = c.archetype.replace("_", " ").title()
            finding = f"- **{arch_title} ({c.pct_of_filing}%)**"
            if c.sasb_topic:
                finding += f" — {c.sasb_topic}"
            if c.narrative_summary:
                finding += f". {c.narrative_summary}"
            lines.append(finding)

        env_segs = next((c.segment_count for c in result.clusters if c.archetype == "environment"), 0)
        social_segs = next((c.segment_count for c in result.clusters if c.archetype == "social_capital"), 0)
        env_social_pct = round((env_segs + social_segs) / total_segs * 100, 1) if total_segs else 0.0
        if env_social_pct < 3.0:
            lines.append(
                f"- **Low ESG signal** — Environment + Social Capital combined "
                f"{env_social_pct}% of classified segments."
            )
        lines.append("")

    # ---------------------------------------------------------------
    # Section 3 — Risk Score Card
    # ---------------------------------------------------------------
    lines.append("## Composite Risk Score")
    lines.append("")
    if score_obj:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **Score** | {score_val} / 100 |")
        lines.append(f"| **Tier** | {score_emoji} {score_tier_label} |")
        lines.append(f"| **Dominant archetype** | {dominant_arch} |")
        lines.append(
            f"| **Total segments classified** | {non_other_segs} ({pct_classified}% of filing) |"
        )
        lines.append(f"| **Mean model confidence** | {mean_conf_overall:.2f} |")
        lines.append("")
        lines.append(
            '> **Scoring note:** Frequency-weighted mean NLI confidence across SASB dimensions '
            '(excluding "other"), scaled 1–100. Scores reflect disclosure density, not risk severity.'
        )
    else:
        lines.append("*Risk score not computed.*")
    lines.append("")

    # ---------------------------------------------------------------
    # Section 4 — SASB Dimension Distribution
    # ---------------------------------------------------------------
    lines.append("## SASB Dimension Distribution")
    lines.append("")
    if result.clusters:
        lines.append("| Dimension | Segments | % of Filing | Mean Confidence | Tier |")
        lines.append("|-----------|----------|-------------|-----------------|------|")
        sorted_clusters = sorted(
            result.clusters,
            key=lambda c: (c.archetype == "other", -c.segment_count),
        )
        for c in sorted_clusters:
            dim_name = c.archetype.replace("_", " ").title()
            if c.archetype == "other":
                lines.append(
                    f"| *Other (unclassified)* | {c.segment_count} | {c.pct_of_filing}% | — | — |"
                )
            else:
                badge = _cluster_tier_badge(c.risk_tier)
                lines.append(
                    f"| {dim_name} | {c.segment_count} | {c.pct_of_filing}% "
                    f"| {c.mean_confidence:.2f} | {badge} |"
                )
        lines.append("")

    if top_sasb:
        lines.append(f"**Top SASB Topics:** {', '.join(top_sasb)}")
        lines.append("")

    # ---------------------------------------------------------------
    # Section 5 — Risk Clusters (detailed)
    # ---------------------------------------------------------------
    if result.clusters:
        lines.append("---")
        lines.append("")
        lines.append("## Risk Clusters")
        lines.append("")

        cluster_order = sorted(non_other, key=lambda c: -c.segment_count) + other_clusters
        for rank, cluster in enumerate(cluster_order, 1):
            arch_title = cluster.archetype.replace("_", " ").title()
            lines.append(f"### {rank}. {arch_title}")

            detail_parts = []
            if cluster.sasb_topic:
                detail_parts.append(f"*SASB Topic: {cluster.sasb_topic}*")
            if cluster.archetype != "other":
                detail_parts.append(f"**{_cluster_tier_badge(cluster.risk_tier)}**")
            if detail_parts:
                lines.append(" · ".join(detail_parts))
            lines.append("")

            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(
                f"| Segments | {cluster.segment_count} ({cluster.pct_of_filing}% of filing) |"
            )
            if cluster.archetype != "other":
                lines.append(f"| Mean confidence | {cluster.mean_confidence:.2f} |")
            lines.append("")

            if cluster.narrative_summary:
                lines.append(cluster.narrative_summary)
                lines.append("")

            if cluster.representative_segments:
                lines.append("**Representative disclosures:**")
                lines.append("")
                for seg in cluster.representative_segments[:3]:
                    excerpt = seg[:400]
                    ellipsis = "\u2026" if len(seg) > 400 else ""
                    lines.append(f'> "{excerpt}{ellipsis}"')
                    lines.append("")

    # ---------------------------------------------------------------
    # Section 6 — Model Transparency & Limitations
    # ---------------------------------------------------------------
    lines.append("## Model Transparency & Limitations")
    lines.append("")
    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")
    lines.append("| Classification model | facebook/bart-large-mnli (NLI zero-shot) |")
    lines.append("| Taxonomy | SASB 5-Dimension, 6 archetypes (ADR-016) |")
    lines.append("| Hypothesis templates | Section-specific (part1item1a, part2item7, etc.) |")
    lines.append(
        "| Scoring formula | \u03a3(count_i \u00d7 mean_conf_i) / total \u00d7 100, excluding \"other\" |"
    )
    if non_other:
        lines.append(f"| Confidence range in this report | {min_conf:.2f} \u2013 {max_conf:.2f} |")
    lines.append("")
    lines.append("**Known limitations:**")
    lines.append(
        "- Zero-shot NLI confidence scores near 0.30\u20130.40 are near the model\u2019s uncertainty boundary; "
        "tier labels are directional."
    )
    lines.append(
        f'- "Other" segments ({other_pct}%) carry no SASB signal and are excluded from the risk score.'
    )
    lines.append(
        "- Narrative summaries require Phase C (Claude CLI / API); current clusters show representative excerpts only."
    )
    lines.append(
        "- This report reflects disclosed language; it does not assess the probability of risk materialization."
    )
    lines.append("")
    lines.append("---")
    if run_dir_str:
        lines.append(f"*Run directory: {run_dir_str} \u00b7 Trace: agent_trace.jsonl*")

    return "\n".join(lines)


def _format_csv(result: AnalysisResult) -> str:
    """Render cluster-level tabular export as CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "ticker", "fiscal_year", "archetype", "sasb_topic",
        "segment_count", "pct_of_filing", "mean_confidence", "risk_tier",
        "composite_score", "narrative_summary",
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
            cluster.pct_of_filing,
            round(cluster.mean_confidence, 4),
            cluster.risk_tier or "",
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
