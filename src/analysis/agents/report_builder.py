"""
ReportBuilderAgent — assembles all analytic outputs into the final AnalysisResult schema.

Responsible for:
- Building cluster summaries from raw ClassificationResult lists
- Computing top SASB topics
- Assembling the AnalysisResult summary dict
- Selecting representative segments per cluster (respecting RANDOM_SEED)
"""
from __future__ import annotations

import logging
import random
from collections import defaultdict
from typing import Dict, List, Optional

from src.analysis.models.analysis import (
    AnalysisResult,
    ClassificationResult,
    ClusterResult,
    RiskScore,
)

logger = logging.getLogger(__name__)


class ReportBuilderAgent:
    """
    Assembles AnalysisResult from raw skill outputs.

    Usage:
        builder = ReportBuilderAgent(config)
        result = builder.build(ticker, fiscal_year, run_dir, classifications, risk_score)
    """

    def __init__(
        self,
        model: str = "claude-opus-4-6",
        representative_segment_count: int = 3,
        random_seed: int = 42,
    ) -> None:
        self.model = model
        self.representative_segment_count = representative_segment_count
        self.random_seed = random_seed

    def build(
        self,
        ticker: str,
        fiscal_year: Optional[str],
        run_dir: str,
        classifications: List[ClassificationResult],
        risk_score: Optional[RiskScore] = None,
        command: str = "analyze company",
    ) -> AnalysisResult:
        """
        Assemble an AnalysisResult from classified segments.

        Args:
            ticker:          Company ticker.
            fiscal_year:     Fiscal year string.
            run_dir:         Preprocessing run directory used for input.
            classifications: Output of classify_filing.
            risk_score:      Output of score_risk (optional in Phase A stub).
            command:         CLI command string (e.g. "analyze company").

        Returns:
            AnalysisResult ready for export_report.
        """
        clusters = self._build_clusters(classifications)
        label_distribution = dict(risk_score.label_distribution) if risk_score else (
            self._count_labels(classifications)
        )
        top_sasb = self._top_sasb_topics(classifications, n=5)

        return AnalysisResult(
            command=command,
            inputs={
                "ticker": ticker,
                "fiscal_year": fiscal_year or "",
                "run_dir": run_dir,
            },
            summary={
                "total_segments": len(classifications),
                "risk_label_distribution": label_distribution,
                "top_sasb_topics": top_sasb,
                "composite_risk_score": risk_score.score if risk_score else None,
            },
            clusters=clusters,
            composite_risk_score=risk_score,
            agent_model=self.model,
            skill_versions={"classify": "1.0", "score": "1.0", "summarize": "1.0"},
        )

    def attach_narratives(
        self,
        result: AnalysisResult,
        narratives: Dict[str, str],
    ) -> AnalysisResult:
        """
        Attach narrative summaries to clusters by archetype key.

        Args:
            result:     AnalysisResult whose clusters will be updated.
            narratives: Dict mapping archetype → narrative string.

        Returns:
            Updated AnalysisResult (clusters mutated in place).
        """
        for cluster in result.clusters:
            if cluster.archetype in narratives:
                cluster.narrative_summary = narratives[cluster.archetype]
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_clusters(
        self, classifications: List[ClassificationResult]
    ) -> List[ClusterResult]:
        """Group classifications by archetype → ClusterResult list."""
        groups: Dict[str, List[ClassificationResult]] = defaultdict(list)
        for cr in classifications:
            groups[cr.risk_label].append(cr)

        rng = random.Random(self.random_seed)
        clusters: List[ClusterResult] = []

        for archetype, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            conf_sum = sum(m.confidence for m in members)
            mean_conf = conf_sum / len(members) if members else 0.0

            # Representative segment selection (Tech Req #7: RANDOM_SEED=42)
            top = sorted(members, key=lambda m: -m.confidence)
            rep_count = min(self.representative_segment_count, len(top))
            representative = [m.text for m in top[:rep_count]]
            # Shuffle only if we need to sample further down the list
            if len(top) > rep_count:
                tail = top[rep_count:]
                rng.shuffle(tail)

            # SASB topic: most common non-None value
            sasb_topic = _most_common_topic(members)

            clusters.append(
                ClusterResult(
                    archetype=archetype,
                    sasb_topic=sasb_topic,
                    segment_count=len(members),
                    representative_segments=representative,
                    mean_confidence=round(mean_conf, 4),
                )
            )

        return clusters

    def _count_labels(
        self, classifications: List[ClassificationResult]
    ) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for cr in classifications:
            counts[cr.risk_label] += 1
        return dict(counts)

    def _top_sasb_topics(
        self, classifications: List[ClassificationResult], n: int = 5
    ) -> List[str]:
        counts: Dict[str, int] = defaultdict(int)
        for cr in classifications:
            if cr.sasb_topic:
                counts[cr.sasb_topic] += 1
        return [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:n]]


def _most_common_topic(members: List[ClassificationResult]) -> Optional[str]:
    """Return the most frequently occurring sasb_topic among members, or None."""
    counts: Dict[str, int] = defaultdict(int)
    for m in members:
        if m.sasb_topic:
            counts[m.sasb_topic] += 1
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])
