"""
ClassifierAgent — parallel sub-agent for SASB classification of a single filing.

Used by AnalysisOrchestrator._parallel_dispatch() when processing multiple filings
concurrently (compare, analyze sector commands).  Each instance runs classify_filing
independently so that context windows stay focused on one filing (RFC-008 §2.1 Option C).

This is NOT a Claude API sub-agent — it is a pure Python worker that wraps the
classify_filing skill.  The "agent" label reflects its role as an autonomous,
independently-executable unit of work.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from src.analysis.models.analysis import ClassificationResult
from src.analysis.skills.classifier import classify_filing

logger = logging.getLogger(__name__)


class ClassifierAgent:
    """
    Classifies all segments in a single filing.

    Designed to be instantiated and run inside a ThreadPoolExecutor worker
    (RFC-008 _parallel_dispatch pattern).
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

    def run(self) -> List[ClassificationResult]:
        """
        Execute classification for this agent's filing.

        Returns:
            List of ClassificationResult — one per annotated segment.
        """
        logger.info(
            "ClassifierAgent: starting classification for %s %s",
            self.ticker,
            self.fiscal_year or "latest",
        )
        results = classify_filing(
            ticker=self.ticker,
            fiscal_year=self.fiscal_year,
            run_dir=str(self.run_dir) if self.run_dir else None,
        )
        logger.info(
            "ClassifierAgent: %s %s → %d segments",
            self.ticker,
            self.fiscal_year or "latest",
            len(results),
        )
        return results
