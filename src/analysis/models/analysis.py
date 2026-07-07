"""
Pydantic V2 models for the agentic analysis layer (PRD-005 §3.2).

All models use extra="forbid" per ADR-001.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClassificationResult(BaseModel):
    """Result of the classify_filing skill for a single segment (US-034)."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    segment_id: str
    text: str
    risk_label: str  # environment|social_capital|human_capital|business_model|governance|other
    sasb_topic: Optional[str] = None
    sasb_industry: Optional[str] = None
    confidence: float
    label_source: str  # nli_zero_shot|heuristic|ancestor_prior|llm_silver|human
    word_count: int = 0


class LabeledSegment(BaseModel):
    """A segment with its classification metadata — used by score_risk."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    segment_id: str
    text: str
    risk_label: str
    confidence: float
    label_source: str
    word_count: int = 0


class ClusterResult(BaseModel):
    """A cluster of segments sharing the same SASB archetype."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    archetype: str
    sasb_topic: Optional[str] = None
    segment_count: int
    representative_segments: List[str] = Field(default_factory=list)
    narrative_summary: Optional[str] = None
    mean_confidence: float = 0.0
    pct_of_filing: float = 0.0
    risk_tier: Optional[str] = None


class RiskScore(BaseModel):
    """Composite risk score 1–100 for a filing (OQ-A02 formula resolved in RFC-008 §3)."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    score: int  # 1–100
    label_distribution: Dict[str, int] = Field(default_factory=dict)
    dominant_archetype: Optional[str] = None


class AnalysisResult(BaseModel):
    """Full structured output for one analysis run (PRD-005 §3.2)."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    schema_version: str = "1.0"
    command: str = "analyze company"
    generated_at: str = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    inputs: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    clusters: List[ClusterResult] = Field(default_factory=list)
    composite_risk_score: Optional[RiskScore] = None
    agent_model: str = "claude-opus-4-6"
    filing_date: Optional[str] = None
    sic_code: Optional[str] = None
    company_name_full: Optional[str] = None
    skill_versions: Dict[str, str] = Field(default_factory=dict)


class YoYDelta(BaseModel):
    """Year-over-year cluster-level delta (RFC-008 §2.3)."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    ticker: str
    year_current: str
    year_prior: str
    new_clusters: List[str] = Field(default_factory=list)      # max_sim < 0.70
    removed_clusters: List[str] = Field(default_factory=list)  # not in current
    shifted_clusters: List[str] = Field(default_factory=list)  # 0.70 ≤ sim < 0.85
    stable_clusters: List[str] = Field(default_factory=list)   # sim ≥ 0.85
    delta_score: Optional[float] = None                        # current_score − prior_score


class ComparisonResult(BaseModel):
    """Side-by-side risk profile diff between two companies (US-036)."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    ticker_a: str
    ticker_b: str
    fiscal_year: Optional[str] = None
    label_distribution_a: Dict[str, int] = Field(default_factory=dict)
    label_distribution_b: Dict[str, int] = Field(default_factory=dict)
    divergent_archetypes: List[str] = Field(default_factory=list)
    score_a: Optional[int] = None
    score_b: Optional[int] = None


class SectorProfile(BaseModel):
    """Aggregated risk profile across a SIC cohort (US-038)."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    sic_code: str
    filing_count: int
    tickers: List[str] = Field(default_factory=list)
    aggregate_label_distribution: Dict[str, int] = Field(default_factory=dict)
    dominant_archetypes: List[str] = Field(default_factory=list)
