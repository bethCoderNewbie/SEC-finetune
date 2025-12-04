"""ML model configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config._loader import load_yaml_section


def _get_config() -> dict:
    return load_yaml_section("config.yaml").get("models", {})


class ModelsConfig(BaseSettings):
    """ML model configuration settings."""
    model_config = SettingsConfigDict(
        env_prefix='MODELS_',
        case_sensitive=False
    )

    default_model: str = Field(
        default_factory=lambda: _get_config().get('default_model', "ProsusAI/finbert")
    )
    zero_shot_model: str = Field(
        default_factory=lambda: _get_config().get('zero_shot_model', "facebook/bart-large-mnli")
    )
