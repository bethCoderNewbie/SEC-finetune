"""
ComparatorAgent — parallel sub-agent for compare / analyze sector commands.

Spawned by AnalysisOrchestrator._parallel_dispatch() alongside one or more
other ComparatorAgents or ClassifierAgents.  Each instance independently
classifies and scores its assigned filing, then the orchestrator merges results
via diff_risk_profiles or aggregate_sector (RFC-008 §2.1 Option C).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from src.analysis.models.analysis import ClassificationResult, RiskScore
from src.analysis.skills.classifier import classify_filing
from src.analysis.skills.scorer import score_risk

logger = logging.getLogger(__name__)


class ComparatorAgent:
    """
    Classifies and scores a single filing for use in multi-company comparisons.

    Returns (ticker, classifications, risk_score) — the orchestrator merges
    multiple ComparatorAgent results into a ComparisonResult or SectorProfile.
    """

    def __init__(
        self,
        ticker: str,
        fiscal_year: Optional[str] = None,
        run_dir: Optional[Path] = None,
    ) -> None:
        self.ticker = ticker
        self.fiscal_year = fiscal_year
        self.run_dir = run_dir

    def run(self) -> Tuple[str, List[ClassificationResult], RiskScore]:
        """
        Classify and score the assigned filing.

        Returns:
            Tuple of (ticker, classifications, risk_score).
        """
        logger.info(
            "ComparatorAgent: processing %s %s",
            self.ticker,
            self.fiscal_year or "latest",
        )
        classifications = classify_filing(
            ticker=self.ticker,
            fiscal_year=self.fiscal_year,
            run_dir=str(self.run_dir) if self.run_dir else None,
        )
        score = score_risk(classifications)
        return self.ticker, classifications, score
