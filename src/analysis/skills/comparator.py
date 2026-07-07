"""
diff_risk_profiles + aggregate_sector skills (US-036, US-038).

diff_risk_profiles: side-by-side archetype distribution diff between two companies.
aggregate_sector:   cohort-level risk aggregation for a SIC code.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from src.analysis.models.analysis import (
    ClassificationResult,
    ComparisonResult,
    RiskScore,
    SectorProfile,
)

logger = logging.getLogger(__name__)

_DIVERGENCE_THRESHOLD = 0.10  # 10% share difference triggers "divergent"
_ALL_ARCHETYPES = [
    "environment", "social_capital", "human_capital",
    "business_model", "governance", "other",
]


def diff_risk_profiles(
    ticker_a: str,
    ticker_b: str,
    classifications_a: List[ClassificationResult],
    classifications_b: List[ClassificationResult],
    fiscal_year: Optional[str] = None,
    score_a: Optional[RiskScore] = None,
    score_b: Optional[RiskScore] = None,
) -> ComparisonResult:
    """
    Compute a side-by-side archetype distribution diff between two companies.

    Args:
        ticker_a:            First company ticker.
        ticker_b:            Second company ticker.
        classifications_a:   classify_filing output for company A.
        classifications_b:   classify_filing output for company B.
        fiscal_year:         Fiscal year (for labeling).
        score_a:             Composite risk score for company A.
        score_b:             Composite risk score for company B.

    Returns:
        ComparisonResult with distributions and divergent archetypes.
    """
    dist_a = _count_labels(classifications_a)
    dist_b = _count_labels(classifications_b)

    total_a = max(sum(dist_a.values()), 1)
    total_b = max(sum(dist_b.values()), 1)

    divergent: List[str] = []
    for archetype in _ALL_ARCHETYPES:
        share_a = dist_a.get(archetype, 0) / total_a
        share_b = dist_b.get(archetype, 0) / total_b
        if abs(share_a - share_b) > _DIVERGENCE_THRESHOLD:
            divergent.append(archetype)

    logger.info(
        "diff_risk_profiles: %s vs %s → %d divergent archetypes",
        ticker_a,
        ticker_b,
        len(divergent),
    )
    return ComparisonResult(
        ticker_a=ticker_a,
        ticker_b=ticker_b,
        fiscal_year=fiscal_year,
        label_distribution_a=dist_a,
        label_distribution_b=dist_b,
        divergent_archetypes=divergent,
        score_a=score_a.score if score_a else None,
        score_b=score_b.score if score_b else None,
    )


def aggregate_sector(
    sic_code: str,
    filing_classifications: Dict[str, List[ClassificationResult]],
) -> SectorProfile:
    """
    Aggregate archetype distributions across a SIC cohort.

    Args:
        sic_code:               SIC code string (e.g. "3571").
        filing_classifications: Mapping of ticker → List[ClassificationResult].

    Returns:
        SectorProfile with aggregate label distribution and dominant archetypes.
    """
    aggregate: Dict[str, int] = defaultdict(int)
    tickers = sorted(filing_classifications.keys())

    for _ticker, classifications in filing_classifications.items():
        for cr in classifications:
            aggregate[cr.risk_label] += 1

    total = max(sum(aggregate.values()), 1)

    # Dominant = archetypes above 15% share, sorted by frequency
    dominant = [
        a for a in sorted(aggregate, key=lambda k: -aggregate[k])
        if aggregate[a] / total >= 0.15
    ]

    logger.info(
        "aggregate_sector: SIC %s → %d tickers, dominant=%s",
        sic_code,
        len(tickers),
        dominant,
    )
    return SectorProfile(
        sic_code=sic_code,
        filing_count=len(tickers),
        tickers=tickers,
        aggregate_label_distribution=dict(aggregate),
        dominant_archetypes=dominant,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _count_labels(classifications: List[ClassificationResult]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for cr in classifications:
        counts[cr.risk_label] += 1
    return dict(counts)
