"""
Analysis CLI — agentic analysis layer entry point (PRD-005 §4.3).

Usage:
    python -m src.analysis.cli analyze company AAPL [--year 2024] [--format md|json|csv]
    python -m src.analysis.cli analyze sector 3571  [--year 2024] [--format md]
    python -m src.analysis.cli compare AAPL MSFT    [--year 2024] [--format md]
    python -m src.analysis.cli trend  AAPL          [--years 3]   [--format md]
    python -m src.analysis.cli report AAPL          [--year 2024] [--format md]  # US-041

Exit codes (PRD-005 §10 Tech Req #10):
    0  success
    1  user input error
    2  skill / agent failure
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _build_orchestrator(run_dir: Optional[str]):
    """Construct AnalysisOrchestrator, resolving run_dir."""
    from src.analysis.orchestrator import AnalysisOrchestrator
    from src.config.analysis import AnalysisConfig

    config = AnalysisConfig()
    resolved: Optional[Path] = Path(run_dir) if run_dir else None
    return AnalysisOrchestrator(config=config, run_dir=resolved)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def cmd_analyze_company(args: argparse.Namespace) -> int:
    """Handler for: analyze company <ticker>"""
    orch = _build_orchestrator(args.run_dir)
    try:
        bundle = orch.analyze_company(
            ticker=args.ticker,
            fiscal_year=args.year,
            fmt=args.format,
        )
    except Exception as exc:
        logger.error("analyze company failed: %s", exc)
        return 2

    _print_bundle(bundle)
    return 0


def cmd_analyze_sector(args: argparse.Namespace) -> int:
    """Handler for: analyze sector <sic>"""
    orch = _build_orchestrator(args.run_dir)
    try:
        bundle = orch.analyze_sector(
            sic_code=args.sic,
            fiscal_year=args.year,
            fmt=args.format,
        )
    except Exception as exc:
        logger.error("analyze sector failed: %s", exc)
        return 2

    _print_bundle(bundle)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Handler for: compare <ticker1> <ticker2>"""
    orch = _build_orchestrator(args.run_dir)
    try:
        bundle = orch.compare_companies(
            ticker_a=args.ticker1,
            ticker_b=args.ticker2,
            fiscal_year=args.year,
            fmt=args.format,
        )
    except Exception as exc:
        logger.error("compare failed: %s", exc)
        return 2

    _print_bundle(bundle)
    return 0


def cmd_trend(args: argparse.Namespace) -> int:
    """Handler for: trend <ticker> --years N"""
    orch = _build_orchestrator(args.run_dir)

    # Resolve which years to fetch: if --years is given, scan for that many years
    # ending at --year (or the most recent available).
    # For Phase E, we accept explicit year list via --year-list; --years N is a count.
    if hasattr(args, "year_list") and args.year_list:
        years = [y.strip() for y in args.year_list.split(",")]
    else:
        # Infer N consecutive years ending at args.year or most recent
        n = getattr(args, "years", 3) or 3
        end_year = int(args.year) if args.year else _infer_latest_year(args.ticker, args.run_dir)
        years = [str(end_year - i) for i in range(n)]

    if len(years) < 2:
        logger.error("trend requires at least 2 years. Got: %s", years)
        return 1

    try:
        bundle = orch.trend_analysis(
            ticker=args.ticker,
            years=years,
            fmt=args.format,
        )
    except Exception as exc:
        logger.error("trend failed: %s", exc)
        return 2

    _print_bundle(bundle)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Handler for: report <ticker> (US-041 — alias for analyze company)"""
    # report is a thin alias; set format default to md if not explicitly provided
    orch = _build_orchestrator(args.run_dir)
    try:
        bundle = orch.analyze_company(
            ticker=args.ticker,
            fiscal_year=args.year,
            fmt=args.format,
        )
    except Exception as exc:
        logger.error("report failed: %s", exc)
        return 2

    _print_bundle(bundle)
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.analysis.cli",
        description="SEC 10-K Agentic Analysis CLI (PRD-005)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging.")

    sub = parser.add_subparsers(dest="command", required=True)

    # -- analyze --
    analyze_p = sub.add_parser("analyze", help="Analyze a single company or sector.")
    analyze_sub = analyze_p.add_subparsers(dest="subcommand", required=True)

    # analyze company
    ac = analyze_sub.add_parser("company", help="Full risk report for a single company.")
    ac.add_argument("ticker", help="Company ticker symbol (e.g. AAPL).")
    ac.add_argument("--year", help="Fiscal year (e.g. 2024). Defaults to most recent.")
    ac.add_argument("--run-dir", dest="run_dir", help="Preprocessing run directory path.")
    ac.add_argument("--format", default="md", choices=["md", "json", "csv"], help="Output format.")
    ac.set_defaults(func=cmd_analyze_company)

    # analyze sector
    asec = analyze_sub.add_parser("sector", help="Aggregated risk report for a SIC peer cohort.")
    asec.add_argument("sic", help="SIC code (e.g. 3571).")
    asec.add_argument("--year", help="Fiscal year.")
    asec.add_argument("--run-dir", dest="run_dir")
    asec.add_argument("--format", default="md", choices=["md", "json", "csv"])
    asec.set_defaults(func=cmd_analyze_sector)

    # -- compare --
    cmp = sub.add_parser("compare", help="Side-by-side risk comparison of two companies.")
    cmp.add_argument("ticker1", help="First company ticker.")
    cmp.add_argument("ticker2", help="Second company ticker.")
    cmp.add_argument("--year", help="Fiscal year.")
    cmp.add_argument("--run-dir", dest="run_dir")
    cmp.add_argument("--format", default="md", choices=["md", "json", "csv"])
    cmp.set_defaults(func=cmd_compare)

    # -- trend --
    trd = sub.add_parser("trend", help="YoY risk trend analysis for N consecutive years.")
    trd.add_argument("ticker", help="Company ticker.")
    trd.add_argument("--years", type=int, default=3, help="Number of years to analyse (default: 3).")
    trd.add_argument("--year", help="Most recent fiscal year (end of trend window).")
    trd.add_argument("--year-list", dest="year_list",
                     help="Comma-separated explicit year list, e.g. '2024,2023,2022'.")
    trd.add_argument("--run-dir", dest="run_dir")
    trd.add_argument("--format", default="md", choices=["md", "json", "csv"])
    trd.set_defaults(func=cmd_trend)

    # -- report (US-041 alias) --
    rep = sub.add_parser("report", help="Shorthand alias for 'analyze company' (US-041).")
    rep.add_argument("ticker", help="Company ticker.")
    rep.add_argument("--year", help="Fiscal year.")
    rep.add_argument("--run-dir", dest="run_dir")
    rep.add_argument("--format", default="md", choices=["md", "json", "csv"])
    rep.set_defaults(func=cmd_report)

    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_bundle(bundle) -> None:
    """Print the path of the primary output file to stdout."""
    primary = bundle.report_md or bundle.report_json or bundle.report_csv
    if primary:
        print(str(primary))
    else:
        print(str(bundle.run_dir))


def _infer_latest_year(ticker: str, run_dir: Optional[str]) -> int:
    """Heuristic: return the most recent fiscal year found for ticker in run_dir."""
    import json as _json

    search_path = Path(run_dir) if run_dir else None
    if search_path is None:
        try:
            from src.config import settings as _settings
            candidates = sorted(
                [d for d in _settings.paths.processed_dir.iterdir()
                 if d.is_dir() and "_preprocessing_" in d.name],
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            search_path = candidates[0] if candidates else None
        except Exception:
            pass

    years = set()
    if search_path:
        for f in search_path.rglob("*_segmented.json"):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = _json.load(fh)
                di = data.get("document_info", data)
                if (di.get("ticker") or "").upper() == ticker.upper():
                    fy = di.get("fiscal_year")
                    if fy and fy.isdigit():
                        years.add(int(fy))
            except Exception:
                continue

    return max(years) if years else 2024  # sensible fallback


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(getattr(args, "verbose", False))

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        return 1
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())
