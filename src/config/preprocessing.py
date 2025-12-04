"""Text preprocessing configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("preprocessing", {})


class PreprocessingConfig(BaseSettings):
    """Text preprocessing configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='PREPROCESSING_',
        case_sensitive=False
    )

    min_segment_length: int = Field(
        default_factory=lambda: _get_config().get('min_segment_length', 50)
    )
    max_segment_length: int = Field(
        default_factory=lambda: _get_config().get('max_segment_length', 2000)
    )
    remove_html_tags: bool = Field(
        default_factory=lambda: _get_config().get('remove_html_tags', True)
    )
    normalize_whitespace: bool = Field(
        default_factory=lambda: _get_config().get('normalize_whitespace', True)
    )
    remove_page_numbers: bool = Field(
        default_factory=lambda: _get_config().get('remove_page_numbers', True)
    )
