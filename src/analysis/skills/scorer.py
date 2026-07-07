"""
score_risk skill — composite 1–100 risk score from classified segments.

Formula (OQ-A02, resolved in RFC-008 §3):
    raw  = Σ(count_i × mean_confidence_i) / total_segments
           where i iterates over the 5 non-"other" SASB archetypes
    score = clip(round(raw × 100), 1, 100)

Rationale: frequency weighting captures how much of the filing is risk-focused;
confidence weighting captures how strongly the NLI model agrees with each label.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import List, Optional

from src.analysis.models.analysis import ClassificationResult, RiskScore

logger = logging.getLogger(__name__)

_SCORED_ARCHETYPES = {
    "environment",
    "social_capital",
    "human_capital",
    "business_model",
    "governance",
}


def score_risk(classifications: List[ClassificationResult]) -> RiskScore:
    """
    Compute a composite 1–100 risk score from a filing's classified segments.

    Args:
        classifications: Output of classify_filing — one ClassificationResult per segment.

    Returns:
        RiskScore with score (1–100), label_distribution, and dominant_archetype.
    """
    if not classifications:
        return RiskScore(score=0, label_distribution={}, dominant_archetype=None)

    count: dict[str, int] = defaultdict(int)
    conf_sum: dict[str, float] = defaultdict(float)

    for cr in classifications:
        count[cr.risk_label] += 1
        conf_sum[cr.risk_label] += cr.confidence

    total = len(classifications)

    # OQ-A02 formula: frequency-weighted mean confidence across scored archetypes
    numerator = sum(
        count[arch] * (conf_sum[arch] / count[arch])
        for arch in _SCORED_ARCHETYPES
        if count[arch] > 0
    )
    raw = numerator / total
    score = max(1, min(100, round(raw * 100)))

    scored_present: List[str] = [a for a in _SCORED_ARCHETYPES if count.get(a, 0) > 0]
    dominant: Optional[str] = max(scored_present, key=lambda a: count[a]) if scored_present else None

    label_distribution = dict(count)

    logger.info(
        "score_risk: %d segments → score=%d (dominant=%s)",
        total,
        score,
        dominant,
    )
    return RiskScore(
        score=score,
        label_distribution=label_distribution,
        dominant_archetype=dominant,
    )
