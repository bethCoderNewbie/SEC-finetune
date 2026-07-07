"""
detect_yoy_delta skill — year-over-year cluster-level change detection.

Algorithm (RFC-008 §2.3, OQ-A04 resolved):
    1. Group segments by archetype for each year.
    2. Build one representative text per archetype (concatenate up to 10 segments).
    3. Encode with all-MiniLM-L6-v2 (already in worker_pool; no new dependency).
    4. Compute cosine similarity matrix between current and prior cluster embeddings.
    5. Classify each archetype:
       - new:     max row similarity < delta_new_threshold (0.70)
       - removed: archetype absent from current but present in prior
       - shifted: delta_new_threshold ≤ max_sim < delta_stable_threshold (0.85)
       - stable:  max_sim ≥ delta_stable_threshold

Thresholds are configurable via AnalysisConfig (RFC-008 §2.3).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from src.analysis.models.analysis import ClassificationResult, RiskScore, YoYDelta

logger = logging.getLogger(__name__)

_DEFAULT_NEW_THRESHOLD = 0.70
_DEFAULT_STABLE_THRESHOLD = 0.85


def _build_cluster_texts(
    classifications: List[ClassificationResult], max_segments_per_cluster: int = 10
) -> Dict[str, str]:
    """Group segments by archetype, return concatenated representative text per archetype."""
    groups: Dict[str, List[str]] = defaultdict(list)
    for cr in classifications:
        groups[cr.risk_label].append(cr.text)

    return {
        archetype: " ".join(segs[:max_segments_per_cluster])
        for archetype, segs in groups.items()
    }


def detect_yoy_delta(
    current_classifications: List[ClassificationResult],
    prior_classifications: List[ClassificationResult],
    ticker: str,
    year_current: str,
    year_prior: str,
    current_score: Optional[RiskScore] = None,
    prior_score: Optional[RiskScore] = None,
    new_threshold: float = _DEFAULT_NEW_THRESHOLD,
    stable_threshold: float = _DEFAULT_STABLE_THRESHOLD,
) -> YoYDelta:
    """
    Compute cluster-level YoY delta between two filing analyses.

    Args:
        current_classifications: ClassificationResult list for the current year.
        prior_classifications:   ClassificationResult list for the prior year.
        ticker:                  Company ticker (for output labeling).
        year_current:            Current fiscal year string (e.g. "2024").
        year_prior:              Prior fiscal year string (e.g. "2023").
        current_score:           RiskScore for current year (for delta_score).
        prior_score:             RiskScore for prior year (for delta_score).
        new_threshold:           Cosine similarity below which a cluster is "new" (0.70).
        stable_threshold:        Cosine similarity above which a cluster is "stable" (0.85).

    Returns:
        YoYDelta with new/removed/shifted/stable cluster lists.
    """
    current_texts = _build_cluster_texts(current_classifications)
    prior_texts = _build_cluster_texts(prior_classifications)

    current_archetypes = list(current_texts.keys())
    prior_archetypes = list(prior_texts.keys())

    removed = [a for a in prior_archetypes if a not in current_archetypes]

    if not current_archetypes or not prior_archetypes:
        # Edge case: one year has no segments
        return YoYDelta(
            ticker=ticker,
            year_current=year_current,
            year_prior=year_prior,
            new_clusters=current_archetypes,
            removed_clusters=removed,
            shifted_clusters=[],
            stable_clusters=[],
            delta_score=_delta_score(current_score, prior_score),
        )

    # Load sentence transformer (already in worker pool — no new download needed)
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
        import numpy as np  # type: ignore

        model = SentenceTransformer("all-MiniLM-L6-v2")
        current_embeddings = model.encode(
            [current_texts[a] for a in current_archetypes], show_progress_bar=False
        )
        prior_embeddings = model.encode(
            [prior_texts[a] for a in prior_archetypes], show_progress_bar=False
        )
        # shape: (len(current), len(prior))
        sim_matrix = cosine_similarity(current_embeddings, prior_embeddings)

    except Exception as exc:
        logger.warning(
            "detect_yoy_delta: sentence embedding failed (%s); "
            "falling back to archetype-name matching.",
            exc,
        )
        # Graceful fallback: treat exact archetype name match as stable
        prior_set = set(prior_archetypes)
        new_clusters = [a for a in current_archetypes if a not in prior_set]
        stable = [a for a in current_archetypes if a in prior_set]
        return YoYDelta(
            ticker=ticker,
            year_current=year_current,
            year_prior=year_prior,
            new_clusters=new_clusters,
            removed_clusters=removed,
            shifted_clusters=[],
            stable_clusters=stable,
            delta_score=_delta_score(current_score, prior_score),
        )

    new_clusters: List[str] = []
    shifted_clusters: List[str] = []
    stable_clusters: List[str] = []

    for i, archetype in enumerate(current_archetypes):
        if not prior_archetypes:
            new_clusters.append(archetype)
            continue
        max_sim = float(np.max(sim_matrix[i]))
        if max_sim < new_threshold:
            new_clusters.append(archetype)
        elif max_sim < stable_threshold:
            shifted_clusters.append(archetype)
        else:
            stable_clusters.append(archetype)

    logger.info(
        "detect_yoy_delta: %s %s vs %s → new=%d shifted=%d stable=%d removed=%d",
        ticker,
        year_current,
        year_prior,
        len(new_clusters),
        len(shifted_clusters),
        len(stable_clusters),
        len(removed),
    )

    return YoYDelta(
        ticker=ticker,
        year_current=year_current,
        year_prior=year_prior,
        new_clusters=new_clusters,
        removed_clusters=removed,
        shifted_clusters=shifted_clusters,
        stable_clusters=stable_clusters,
        delta_score=_delta_score(current_score, prior_score),
    )


def _delta_score(
    current: Optional[RiskScore], prior: Optional[RiskScore]
) -> Optional[float]:
    """Return score delta (current − prior) or None if either score is unavailable."""
    if current is not None and prior is not None:
        return float(current.score - prior.score)
    return None
