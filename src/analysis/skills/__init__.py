"""
Analysis skills — composable Python callables registered as Claude tools (PRD-005 §4.2).

Each skill is independently unit-testable; the orchestrator dispatches them by name
from Claude's tool_use blocks (RFC-008 §2.2 Option A: direct Python function dispatch).
"""

from src.analysis.skills.classifier import classify_filing
from src.analysis.skills.comparator import aggregate_sector, diff_risk_profiles
from src.analysis.skills.delta_detector import detect_yoy_delta
from src.analysis.skills.filing_loader import (
    FilingNotFoundError,
    SkillError,
    SkillTimeoutError,
    load_filing,
)
from src.analysis.skills.narrator import summarize_cluster
from src.analysis.skills.reporter import export_report, format_report
from src.analysis.skills.scorer import score_risk

__all__ = [
    "aggregate_sector",
    "classify_filing",
    "detect_yoy_delta",
    "diff_risk_profiles",
    "export_report",
    "FilingNotFoundError",
    "format_report",
    "load_filing",
    "score_risk",
    "SkillError",
    "SkillTimeoutError",
    "summarize_cluster",
]
