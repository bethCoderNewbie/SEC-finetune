"""
NarratorAgent — inline narrative generation within the orchestrator's tool-use loop.

This is NOT a separate Claude sub-agent with its own conversation context.
It is invoked as a skill call (summarize_cluster) inside the orchestrator's tool
loop (RFC-008 §4 Component Diagram note; PRD-005 §4.1 lists it as an "agent"
for organizational clarity only).

Keeping NarratorAgent inline avoids extra Claude API round-trips and keeps the
single-company analysis path simple (RFC-008 §2.1 Option C happy path).
"""
from __future__ import annotations

import logging
from typing import List

from src.analysis.models.analysis import ClusterResult
from src.analysis.skills.narrator import summarize_cluster

logger = logging.getLogger(__name__)


class NarratorAgent:
    """
    Generates narrative summaries for risk clusters via the summarize_cluster skill.

    Usage:
        narrator = NarratorAgent(model="claude-opus-4-6")
        cluster = narrator.narrate(cluster)  # mutates narrative_summary in place
    """

    def __init__(
        self,
        model: str = "claude-opus-4-6",
        max_tokens: int = 256,
        temperature: float = 0.2,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def narrate(self, cluster: ClusterResult) -> ClusterResult:
        """
        Generate and attach a narrative_summary to a ClusterResult.

        Args:
            cluster: ClusterResult with representative_segments populated.

        Returns:
            The same ClusterResult with narrative_summary set.
        """
        if not cluster.representative_segments:
            logger.debug("NarratorAgent: skipping empty cluster %s", cluster.archetype)
            return cluster

        try:
            summary = summarize_cluster(
                archetype=cluster.archetype,
                representative_segments=cluster.representative_segments,
                sasb_topic=cluster.sasb_topic or "",
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            cluster.narrative_summary = summary
        except Exception as exc:
            logger.warning(
                "NarratorAgent: summarize_cluster failed for %s: %s",
                cluster.archetype,
                exc,
            )
            cluster.narrative_summary = None

        return cluster

    def narrate_all(self, clusters: List[ClusterResult]) -> List[ClusterResult]:
        """Narrate each cluster sequentially (blocking; streaming deferred to Phase F)."""
        return [self.narrate(c) for c in clusters]
