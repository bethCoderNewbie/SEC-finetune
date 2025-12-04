"""Section extraction configuration."""

from typing import List, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("extraction", {})


class ExtractionConfig(BaseSettings):
    """Section extraction configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='EXTRACTION_',
        case_sensitive=False
    )

    min_confidence: float = Field(
        default_factory=lambda: _get_config().get('min_confidence', 0.7)
    )
    enable_audit_logging: bool = Field(
        default_factory=lambda: _get_config().get('enable_audit_logging', True)
    )
    output_format: Literal["json", "parquet", "both"] = Field(
        default_factory=lambda: _get_config().get('output_format', "json")
    )
    default_sections: List[str] = Field(
        default_factory=lambda: _get_config().get('default_sections', ["part1item1a"])
    )
