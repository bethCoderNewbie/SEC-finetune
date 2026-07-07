"""
TrendAgent — multi-year YoY trend analysis (Phase E, US-037).

Runs the orchestrator's tool-use loop sequentially across N fiscal years,
calling classify_filing and detect_yoy_delta for each consecutive year pair.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from src.analysis.models.analysis import ClassificationResult, RiskScore, YoYDelta
from src.analysis.skills.classifier import classify_filing
from src.analysis.skills.delta_detector import detect_yoy_delta
from src.analysis.skills.scorer import score_risk

logger = logging.getLogger(__name__)


class TrendAgent:
    """
    Computes YoY deltas across N consecutive fiscal years for a single ticker.

    Usage:
        agent = TrendAgent(ticker="AAPL", years=["2024", "2023", "2022"])
        deltas = agent.run()
    """

    def __init__(
        self,
        ticker: str,
        years: List[str],
        run_dir: Optional[Path] = None,
    ) -> None:
        if len(years) < 2:
            raise ValueError("TrendAgent requires at least 2 years for YoY comparison.")
        self.ticker = ticker
        self.years = sorted(years, reverse=True)  # most recent first
        self.run_dir = run_dir

    def run(self) -> List[YoYDelta]:
        """
        Classify each year's filing and compute YoY deltas for consecutive pairs.

        Returns:
            List of YoYDelta, one per consecutive year pair (most recent pair first).
        """
        # Classify each year
        year_classifications: dict[str, List[ClassificationResult]] = {}
        year_scores: dict[str, Optional[RiskScore]] = {}

        for year in self.years:
            logger.info("TrendAgent: classifying %s %s", self.ticker, year)
            try:
                classifications = classify_filing(
                    ticker=self.ticker,
                    fiscal_year=year,
                    run_dir=str(self.run_dir) if self.run_dir else None,
                )
                year_classifications[year] = classifications
                year_scores[year] = score_risk(classifications)
            except Exception as exc:
                logger.warning(
                    "TrendAgent: classify_filing failed for %s %s: %s",
                    self.ticker,
                    year,
                    exc,
                )
                year_classifications[year] = []
                year_scores[year] = None

        # Compute deltas for each consecutive pair (years already sorted desc)
        deltas: List[YoYDelta] = []
        for current_year, prior_year in zip(self.years, self.years[1:]):
            current_cls = year_classifications.get(current_year, [])
            prior_cls = year_classifications.get(prior_year, [])

            delta = detect_yoy_delta(
                current_classifications=current_cls,
                prior_classifications=prior_cls,
                ticker=self.ticker,
                year_current=current_year,
                year_prior=prior_year,
                current_score=year_scores.get(current_year),
                prior_score=year_scores.get(prior_year),
            )
            deltas.append(delta)

        return deltas
