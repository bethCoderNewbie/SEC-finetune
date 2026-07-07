"""
AnalysisOrchestrator — entry point for all analysis commands (PRD-005 §4.1, RFC-008 §2.1).

Architecture: Option C (hybrid) from RFC-008 §2.1:
  - Single-company path: pure tool-use loop (Option A).
  - Multi-company path (compare, sector): _parallel_dispatch() spawns ClassifierAgents
    in a ThreadPoolExecutor, then merges results.

Skill timeout enforcement: concurrent.futures.Future.result(timeout=N) — NOT signal.alarm,
which is incompatible with ThreadPoolExecutor threads (PRD-005 §10 Tech Req #9).

Trace logging: every LLM call, tool invocation, and decision is appended to
agent_trace.jsonl in the analysis run directory (G-A08).
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analysis.agents.classifier_agent import ClassifierAgent
from src.analysis.agents.comparator_agent import ComparatorAgent
from src.analysis.agents.narrator_agent import NarratorAgent
from src.analysis.agents.report_builder import ReportBuilderAgent
from src.analysis.agents.trend_agent import TrendAgent
from src.analysis.models.analysis import (
    AnalysisResult,
    ClassificationResult,
    ComparisonResult,
    RiskScore,
    SectorProfile,
    YoYDelta,
)
from src.analysis.models.report import ReportBundle
from src.analysis.skills.comparator import aggregate_sector, diff_risk_profiles
from src.analysis.skills.filing_loader import SkillError, SkillTimeoutError, load_filing
from src.analysis.skills.reporter import export_report
from src.analysis.skills.scorer import score_risk
from src.config.analysis import AnalysisConfig
from src.utils.metadata import RunMetadata

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Claude tool definitions (registered in tools= parameter)
# ---------------------------------------------------------------------------

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "load_filing",
        "description": "Load a SegmentedRisks JSON for a given ticker and fiscal year.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol."},
                "fiscal_year": {"type": "string", "description": "Four-digit year, e.g. '2024'."},
                "run_dir": {"type": "string", "description": "Preprocessing run directory path. Optional."},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "classify_filing",
        "description": (
            "Classify all risk segments in a filing by SASB archetype and topic. "
            "Returns label distribution and segment count. "
            "Uses SegmentAnnotator to preserve ancestor-prior context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "fiscal_year": {"type": "string"},
                "run_dir": {"type": "string"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "score_risk",
        "description": "Compute composite 1–100 risk score for a previously classified filing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "fiscal_year": {"type": "string"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "summarize_cluster",
        "description": "Generate a 1–3 sentence narrative for a risk cluster.",
        "input_schema": {
            "type": "object",
            "properties": {
                "archetype": {"type": "string", "description": "SASB archetype key."},
            },
            "required": ["archetype"],
        },
    },
    {
        "name": "format_report",
        "description": "Assemble and write the final report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["md", "json", "csv"]},
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# AnalysisOrchestrator
# ---------------------------------------------------------------------------


class AnalysisOrchestrator:
    """
    Entry point for all analysis commands.

    Usage:
        config = AnalysisConfig()
        orch = AnalysisOrchestrator(config, run_dir=Path("data/processed/20260220_..."))
        bundle = orch.analyze_company("AAPL", fiscal_year="2024", fmt="md")
    """

    def __init__(
        self,
        config: Optional[AnalysisConfig] = None,
        run_dir: Optional[Path] = None,
        report_run_dir: Optional[Path] = None,
    ) -> None:
        self._config = config or AnalysisConfig()
        self._run_dir = run_dir  # preprocessing run dir (input)
        self._report_run_dir = report_run_dir  # analysis output dir (created if None)
        self._context: Dict[str, Any] = {}  # in-process cache for skill results
        self._trace: List[Dict[str, Any]] = []  # agent_trace.jsonl entries

    # ------------------------------------------------------------------
    # Public command methods
    # ------------------------------------------------------------------

    def analyze_company(
        self,
        ticker: str,
        fiscal_year: Optional[str] = None,
        fmt: str = "md",
    ) -> ReportBundle:
        """
        Run the full analyze company workflow (US-033).

        Phase A: load → skeleton report (no LLM)
        Phase B: + classify_filing
        Phase C: + summarize_cluster (Claude Code CLI; falls back to API key)
        Phase D: + score_risk

        Returns:
            ReportBundle with paths to written output files.
        """
        self._trace_event("orchestrator_start", {"command": "analyze company", "ticker": ticker})

        # Phase A+B: classify
        self._log("classify_filing", ticker, fiscal_year)
        classifications = self._run_skill(
            "classify_filing",
            self._classify_filing_skill,
            ticker=ticker,
            fiscal_year=fiscal_year,
        )
        self._context[f"classifications_{ticker}"] = classifications

        # Capture filing metadata for the report header (load_filing is already imported)
        try:
            _seg = load_filing(
                ticker,
                fiscal_year,
                Path(str(self._run_dir)) if self._run_dir else None,
            )
            filing_metadata: Dict[str, Any] = {
                "filed_as_of_date": _seg.filed_as_of_date,
                "sic_code": _seg.sic_code,
                "company_name": _seg.company_name,
            }
        except Exception:
            filing_metadata = {}

        # Phase D: score
        risk_score = self._run_skill(
            "score_risk",
            lambda: score_risk(classifications),
        )

        # Phase C: narrate clusters
        builder = ReportBuilderAgent(
            model=self._config.model,
            representative_segment_count=self._config.representative_segment_count,
            random_seed=self._config.random_seed,
        )
        result = builder.build(
            ticker=ticker,
            fiscal_year=fiscal_year,
            run_dir=str(self._run_dir or ""),
            classifications=classifications,
            risk_score=risk_score,
            filing_metadata=filing_metadata,
        )

        # Narration (Phase C) — requires Claude Code CLI (subscription) or ANTHROPIC_API_KEY
        from src.analysis.skills.narrator import claude_cli_available
        if claude_cli_available() or os.environ.get("ANTHROPIC_API_KEY"):
            result = self._narrate(result)
        else:
            logger.info(
                "Claude Code CLI not found and ANTHROPIC_API_KEY not set — "
                "skipping narrative summaries (Phase C)."
            )

        # Export
        bundle = self._export(result, fmt)
        self._trace_event("orchestrator_end", {"report_dir": str(bundle.run_dir)})
        self._flush_trace(bundle.run_dir)
        return bundle

    def compare_companies(
        self,
        ticker_a: str,
        ticker_b: str,
        fiscal_year: Optional[str] = None,
        fmt: str = "md",
    ) -> ReportBundle:
        """
        Run compare <ticker_a> <ticker_b> (US-036).

        Spawns two ClassifierAgents in parallel (RFC-008 _parallel_dispatch).
        """
        self._trace_event(
            "orchestrator_start",
            {"command": "compare", "ticker_a": ticker_a, "ticker_b": ticker_b},
        )

        ticker_a_cls, score_a, ticker_b_cls, score_b = self._parallel_dispatch(
            [
                ComparatorAgent(ticker_a, fiscal_year, self._run_dir),
                ComparatorAgent(ticker_b, fiscal_year, self._run_dir),
            ]
        )

        comparison = diff_risk_profiles(
            ticker_a=ticker_a,
            ticker_b=ticker_b,
            classifications_a=ticker_a_cls,
            classifications_b=ticker_b_cls,
            fiscal_year=fiscal_year,
            score_a=score_a,
            score_b=score_b,
        )

        result = self._build_comparison_result(ticker_a, ticker_b, fiscal_year, comparison)
        bundle = self._export(result, fmt)
        self._trace_event("orchestrator_end", {"report_dir": str(bundle.run_dir)})
        self._flush_trace(bundle.run_dir)
        return bundle

    def analyze_sector(
        self,
        sic_code: str,
        fiscal_year: Optional[str] = None,
        fmt: str = "md",
    ) -> ReportBundle:
        """
        Run analyze sector <sic> (US-038).

        Finds all preprocessed filings for sic_code, spawns parallel ClassifierAgents.
        """
        self._trace_event(
            "orchestrator_start",
            {"command": "analyze sector", "sic_code": sic_code},
        )

        tickers = self._find_tickers_for_sic(sic_code, fiscal_year)
        if len(tickers) < self._config.sector_min_filings:
            raise SkillError(
                "analyze_sector",
                f"Found only {len(tickers)} filing(s) for SIC {sic_code}; "
                f"minimum required is {self._config.sector_min_filings}.",
            )

        agents = [ComparatorAgent(t, fiscal_year, self._run_dir) for t in tickers]
        results_flat = self._parallel_dispatch_sector(agents)

        profile = aggregate_sector(
            sic_code=sic_code,
            filing_classifications={t: cls for t, cls, _ in results_flat},
        )

        result = self._build_sector_result(sic_code, fiscal_year, profile)
        bundle = self._export(result, fmt)
        self._trace_event("orchestrator_end", {"report_dir": str(bundle.run_dir)})
        self._flush_trace(bundle.run_dir)
        return bundle

    def trend_analysis(
        self,
        ticker: str,
        years: List[str],
        fmt: str = "md",
    ) -> ReportBundle:
        """
        Run trend <ticker> --years N (US-037).

        Uses TrendAgent which processes years sequentially (each year's context is
        independent, so no parallelism benefit here).
        """
        self._trace_event(
            "orchestrator_start",
            {"command": "trend", "ticker": ticker, "years": years},
        )

        agent = TrendAgent(ticker=ticker, years=years, run_dir=self._run_dir)
        deltas = agent.run()

        result = self._build_trend_result(ticker, years, deltas)
        bundle = self._export(result, fmt)
        self._trace_event("orchestrator_end", {"report_dir": str(bundle.run_dir)})
        self._flush_trace(bundle.run_dir)
        return bundle

    # ------------------------------------------------------------------
    # Parallel dispatch (RFC-008 §2.1 Option C)
    # ------------------------------------------------------------------

    def _parallel_dispatch(
        self,
        agents: List[ComparatorAgent],
    ):
        """
        Spawn ComparatorAgents in a ThreadPoolExecutor, collect (ticker, cls, score) tuples.

        Returns flat values for exactly 2 agents: (cls_a, score_a, cls_b, score_b).
        Raises SkillTimeoutError if any agent exceeds skill_timeout_seconds.
        """
        timeout = self._config.skill_timeout_seconds
        results = []
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            futures = {executor.submit(agent.run): agent for agent in agents}
            for future, agent in futures.items():
                self._trace_event(
                    "sub_agent_spawn",
                    {"ticker": agent.ticker, "fiscal_year": agent.fiscal_year},
                )
                try:
                    ticker, cls, score = future.result(timeout=timeout)
                    results.append((ticker, cls, score))
                    self._trace_event(
                        "sub_agent_result",
                        {"ticker": ticker, "segment_count": len(cls)},
                    )
                except FuturesTimeoutError as exc:
                    raise SkillTimeoutError(
                        "parallel_dispatch",
                        f"Agent for {agent.ticker} timed out after {timeout}s",
                    ) from exc

        # Order by the input agent order
        ordered = sorted(results, key=lambda r: [a.ticker for a in agents].index(r[0]))
        _t_a, cls_a, score_a = ordered[0]
        _t_b, cls_b, score_b = ordered[1]
        return cls_a, score_a, cls_b, score_b

    def _parallel_dispatch_sector(
        self,
        agents: List[ComparatorAgent],
    ) -> List[tuple]:
        """Run all agents in parallel, collect (ticker, cls, score) for each."""
        timeout = self._config.skill_timeout_seconds
        results = []
        with ThreadPoolExecutor(max_workers=min(len(agents), 8)) as executor:
            futures = {executor.submit(agent.run): agent for agent in agents}
            for future, agent in futures.items():
                try:
                    ticker, cls, score = future.result(timeout=timeout)
                    results.append((ticker, cls, score))
                except FuturesTimeoutError:
                    logger.warning("Agent for %s timed out; skipping.", agent.ticker)
        return results

    # ------------------------------------------------------------------
    # Skill execution with timeout + trace logging
    # ------------------------------------------------------------------

    def _run_skill(self, name: str, fn, **kwargs):
        """Execute a skill function with timeout and trace logging."""
        start = time.monotonic()
        self._trace_event("tool_use", {"tool": name, "input": kwargs})
        timeout = self._config.skill_timeout_seconds
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fn, **kwargs) if kwargs else executor.submit(fn)
                try:
                    result = future.result(timeout=timeout)
                except FuturesTimeoutError as exc:
                    raise SkillTimeoutError(name, f"Timed out after {timeout}s") from exc
        except SkillTimeoutError:
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            self._trace_event("tool_error", {"tool": name, "error": str(exc), "duration_ms": duration_ms})
            raise SkillError(name, str(exc)) from exc

        duration_ms = int((time.monotonic() - start) * 1000)
        self._trace_event("tool_result", {"tool": name, "duration_ms": duration_ms, "status": "ok"})
        return result

    # ------------------------------------------------------------------
    # Internal skill wrappers (keep heavy imports out of __init__)
    # ------------------------------------------------------------------

    def _classify_filing_skill(self, ticker: str, fiscal_year: Optional[str]) -> List[ClassificationResult]:
        from src.analysis.skills.classifier import classify_filing
        return classify_filing(
            ticker=ticker,
            fiscal_year=fiscal_year,
            run_dir=str(self._run_dir) if self._run_dir else None,
        )

    def _log(self, skill: str, ticker: str, fiscal_year: Optional[str]) -> None:
        logger.info("Orchestrator: running %s for %s %s", skill, ticker, fiscal_year or "latest")

    # ------------------------------------------------------------------
    # Narration (Phase C)
    # ------------------------------------------------------------------

    def _narrate(self, result: AnalysisResult) -> AnalysisResult:
        """Attach Claude-generated narrative summaries to each cluster."""
        narrator = NarratorAgent(
            model=self._config.model,
            max_tokens=self._config.max_tokens,
            temperature=self._config.temperature,
        )
        result.clusters = narrator.narrate_all(result.clusters)
        return result

    # ------------------------------------------------------------------
    # Result builders for compare / sector / trend
    # ------------------------------------------------------------------

    def _build_comparison_result(
        self,
        ticker_a: str,
        ticker_b: str,
        fiscal_year: Optional[str],
        comparison: ComparisonResult,
    ) -> AnalysisResult:
        from src.analysis.models.analysis import ClusterResult
        clusters = []
        for archetype in comparison.divergent_archetypes:
            cnt_a = comparison.label_distribution_a.get(archetype, 0)
            cnt_b = comparison.label_distribution_b.get(archetype, 0)
            clusters.append(ClusterResult(
                archetype=archetype,
                segment_count=cnt_a + cnt_b,
                narrative_summary=(
                    f"{ticker_a}: {cnt_a} segments  |  {ticker_b}: {cnt_b} segments"
                ),
            ))
        return AnalysisResult(
            command="compare",
            inputs={
                "ticker_a": ticker_a,
                "ticker_b": ticker_b,
                "fiscal_year": fiscal_year or "",
            },
            summary={
                "divergent_archetypes": comparison.divergent_archetypes,
                "score_a": comparison.score_a,
                "score_b": comparison.score_b,
                "label_distribution_a": comparison.label_distribution_a,
                "label_distribution_b": comparison.label_distribution_b,
            },
            clusters=clusters,
            agent_model=self._config.model,
        )

    def _build_sector_result(
        self,
        sic_code: str,
        fiscal_year: Optional[str],
        profile: SectorProfile,
    ) -> AnalysisResult:
        from src.analysis.models.analysis import ClusterResult
        clusters = [
            ClusterResult(
                archetype=arch,
                segment_count=profile.aggregate_label_distribution.get(arch, 0),
            )
            for arch in profile.dominant_archetypes
        ]
        return AnalysisResult(
            command="analyze sector",
            inputs={"sic_code": sic_code, "fiscal_year": fiscal_year or ""},
            summary={
                "filing_count": profile.filing_count,
                "tickers": profile.tickers,
                "aggregate_label_distribution": profile.aggregate_label_distribution,
                "dominant_archetypes": profile.dominant_archetypes,
            },
            clusters=clusters,
            agent_model=self._config.model,
        )

    def _build_trend_result(
        self,
        ticker: str,
        years: List[str],
        deltas: List[YoYDelta],
    ) -> AnalysisResult:
        from src.analysis.models.analysis import ClusterResult
        clusters = []
        for delta in deltas:
            for arch in delta.new_clusters:
                clusters.append(ClusterResult(
                    archetype=arch,
                    segment_count=0,
                    narrative_summary=f"New in {delta.year_current} (absent in {delta.year_prior})",
                ))
            for arch in delta.shifted_clusters:
                clusters.append(ClusterResult(
                    archetype=arch,
                    segment_count=0,
                    narrative_summary=f"Shifted between {delta.year_prior} and {delta.year_current}",
                ))
        return AnalysisResult(
            command="trend",
            inputs={"ticker": ticker, "years": years},
            summary={
                "year_pairs": [
                    {"current": d.year_current, "prior": d.year_prior, "delta_score": d.delta_score}
                    for d in deltas
                ],
                "new_clusters": [d.new_clusters for d in deltas],
                "removed_clusters": [d.removed_clusters for d in deltas],
            },
            clusters=clusters,
            agent_model=self._config.model,
        )

    # ------------------------------------------------------------------
    # SIC ticker discovery
    # ------------------------------------------------------------------

    def _find_tickers_for_sic(
        self, sic_code: str, fiscal_year: Optional[str]
    ) -> List[str]:
        """
        Scan the preprocessing run directory for all filings matching sic_code.

        Returns a de-duplicated sorted list of ticker symbols found.
        """
        import json as _json

        if self._run_dir is None:
            from src.config import settings as _settings
            run_dirs = sorted(
                [d for d in _settings.paths.processed_data_dir.iterdir()
                 if d.is_dir() and "_preprocessing_" in d.name],
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            search_dirs = run_dirs[:1] if run_dirs else []
        else:
            search_dirs = [self._run_dir]

        tickers: set[str] = set()
        for search_dir in search_dirs:
            for f in search_dir.rglob("*_segmented.json"):
                try:
                    with open(f, encoding="utf-8") as fh:
                        data = _json.load(fh)
                    di = data.get("document_info", data)
                    if di.get("sic_code") == sic_code:
                        if fiscal_year is None or di.get("fiscal_year") == fiscal_year:
                            t = di.get("ticker")
                            if t:
                                tickers.add(t.upper())
                except Exception:
                    continue

        return sorted(tickers)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export(self, result: AnalysisResult, fmt: str) -> ReportBundle:
        """Write the report and return a ReportBundle."""
        bundle = export_report(
            result=result,
            fmt=fmt,
            report_output_dir=self._config.report_output_dir,
            run_dir=self._report_run_dir,
        )
        # Cache the run_dir for trace flushing
        if self._report_run_dir is None:
            self._report_run_dir = bundle.run_dir
        return bundle

    # ------------------------------------------------------------------
    # Trace logging (G-A08)
    # ------------------------------------------------------------------

    def _trace_event(self, event: str, data: Dict[str, Any]) -> None:
        if not self._config.trace_logging:
            return
        entry = {
            "ts": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "event": event,
            **data,
        }
        self._trace.append(entry)

    def _flush_trace(self, run_dir: Path) -> None:
        if not self._config.trace_logging or not self._trace:
            return
        trace_path = run_dir / "agent_trace.jsonl"
        with open(trace_path, "w", encoding="utf-8") as fh:
            for entry in self._trace:
                fh.write(json.dumps(entry, default=str) + "\n")
        logger.info("Trace written to %s (%d events)", trace_path, len(self._trace))
