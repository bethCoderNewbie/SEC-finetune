"""Sub-agents for the agentic analysis layer (RFC-008 §2.1 Option C hybrid model)."""

from src.analysis.agents.classifier_agent import ClassifierAgent
from src.analysis.agents.comparator_agent import ComparatorAgent
from src.analysis.agents.narrator_agent import NarratorAgent
from src.analysis.agents.report_builder import ReportBuilderAgent
from src.analysis.agents.trend_agent import TrendAgent

__all__ = [
    "ClassifierAgent",
    "ComparatorAgent",
    "NarratorAgent",
    "ReportBuilderAgent",
    "TrendAgent",
]
