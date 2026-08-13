"""Analysis layer configuration (PRD-005 / RFC-008 / ADR-006)."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalysisConfig(BaseSettings):
    """
    Configuration for the agentic analysis layer.

    All fields are overridable via environment variables (prefix: SEC_ANALYSIS__).

    Examples:
        SEC_ANALYSIS__MODEL=claude-opus-4-6
        SEC_ANALYSIS__SKILL_TIMEOUT_SECONDS=60
        SEC_ANALYSIS__TRACE_LOGGING=false
        SEC_ANALYSIS__REPORT_OUTPUT_DIR=/mnt/analysis_output
    """

    model_config = SettingsConfigDict(
        env_prefix="SEC_ANALYSIS__",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    model: str = Field(default="claude-opus-4-6")
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.2)
    skill_timeout_seconds: int = Field(default=600)
    trace_logging: bool = Field(default=True)
    report_output_dir: Path = Field(default=Path("data/reports"))
    # ADR-007: processed run directory root for auto-discovery
    processed_dir: Path = Field(default=Path("data/processed"))
    # Tech Req #7
    random_seed: int = Field(default=42)
    # Minimum representative segments to include per cluster in report
    representative_segment_count: int = Field(default=3)
    # Sector command: minimum filings to produce a meaningful sector report
    sector_min_filings: int = Field(default=2)
    # YoY delta thresholds (RFC-008 §2.3)
    delta_new_threshold: float = Field(default=0.70)
    delta_stable_threshold: float = Field(default=0.85)
    # SQLite filing database path (ADR-017)
    db_path: Path = Field(default=Path("data/sec_filings.db"))
