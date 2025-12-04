"""Risk analysis configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("features/risk_analysis.yaml", "model")


class RiskAnalysisConfig(BaseSettings):
    """
    Risk analysis configuration (Drift Detection & Auto-Labeling).
    Loads from configs/features/risk_analysis.yaml with environment variable overrides.
    """
    model_config = SettingsConfigDict(
        env_prefix='RISK_ANALYSIS_',
        case_sensitive=False
    )

    drift_threshold: float = Field(
        default_factory=lambda: _get_config().get('drift_threshold', 0.15)
    )
    labeling_model: str = Field(
        default_factory=lambda: _get_config().get('labeling_model', "facebook/bart-large-mnli")
    )
    labeling_batch_size: int = Field(
        default_factory=lambda: _get_config().get('labeling_batch_size', 16)
    )
    labeling_multi_label: bool = Field(
        default_factory=lambda: _get_config().get('labeling_multi_label', True)
    )
    device: str = Field(
        default_factory=lambda: _get_config().get('device', "auto")
    )
